"""Build the wcag_chunks corpus.

Reads the two JSON files in this directory, splits each WCAG criterion and
ARIA pattern into searchable chunks, computes embeddings via fastembed,
and inserts them into Postgres.

Idempotent: if the table already has rows we no-op. Force-rebuild with
`--rebuild` which truncates first.

Usage:
    uv run python -m corpus.ingest         # ingest if empty
    uv run python -m corpus.ingest --rebuild
"""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import asyncpg
import structlog
from curb_shared.config import load_settings
from curb_worker.embeddings import EMBEDDING_DIM, embed_many
from pgvector.asyncpg import register_vector

log = structlog.get_logger()

CORPUS_DIR = Path(__file__).parent


def _wcag_chunks(data: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    source = data["source"]
    for c in data["criteria"]:
        body = (
            f"WCAG {c['criterion']} {c['title']} (Level {c['level']}).\n\n"
            f"What it requires: {c['what']}\n\n"
            f"How to meet it: {c['how_to_meet']}\n\n"
            f"Common failures: {c['common_failures']}\n\n"
            f"Related axe-core rules: {', '.join(c['axe_rules']) or 'none'}."
        )
        out.append(
            {
                "source": source,
                "criterion": c["criterion"],
                "title": f"{c['criterion']} {c['title']}",
                "body": body,
            }
        )
    return out


def _aria_chunks(data: dict[str, Any]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    source = data["source"]
    for p in data["patterns"]:
        for crit in p["criterion_hints"]:
            body = (
                f"ARIA APG: {p['title']} (relates to WCAG {crit}).\n\n"
                f"What: {p['what']}\n\n"
                f"How to apply: {p['how_to_meet']}\n\n"
                f"Common failures: {p['common_failures']}\n\n"
                f"Example: {p['snippet']}"
            )
            out.append(
                {
                    "source": source,
                    "criterion": crit,
                    "title": f"ARIA — {p['title']}",
                    "body": body,
                }
            )
    return out


def load_chunks() -> list[dict[str, Any]]:
    wcag = json.loads((CORPUS_DIR / "wcag22.json").read_text())
    aria = json.loads((CORPUS_DIR / "aria_patterns.json").read_text())
    return _wcag_chunks(wcag) + _aria_chunks(aria)


async def ingest(*, rebuild: bool = False) -> int:
    settings = load_settings()
    conn = await asyncpg.connect(settings.database_url)
    try:
        await register_vector(conn)
        if rebuild:
            await conn.execute("TRUNCATE wcag_chunks")
            log.info("corpus_truncated")
        existing = await conn.fetchval("SELECT count(*) FROM wcag_chunks")
        if existing and not rebuild:
            log.info("corpus_already_loaded", chunks=existing)
            return int(existing)

        chunks = load_chunks()
        # Embed the title + body together so vector similarity matches both.
        vectors = embed_many(f"{c['title']}\n\n{c['body']}" for c in chunks)
        for vec in vectors:
            if len(vec) != EMBEDDING_DIM:
                raise RuntimeError(
                    f"embedding dim {len(vec)} does not match schema ({EMBEDDING_DIM})"
                )
        await conn.executemany(
            """
            INSERT INTO wcag_chunks (source, criterion, title, body, embedding)
            VALUES ($1, $2, $3, $4, $5)
            """,
            [
                (
                    chunk["source"],
                    chunk["criterion"],
                    chunk["title"],
                    chunk["body"],
                    vec,
                )
                for chunk, vec in zip(chunks, vectors, strict=True)
            ],
        )
        log.info("corpus_ingested", chunks=len(chunks))
        return len(chunks)
    finally:
        await conn.close()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rebuild",
        action="store_true",
        help="Truncate the table before reingesting (otherwise no-op if rows exist).",
    )
    args = parser.parse_args()
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ]
    )
    count = asyncio.run(ingest(rebuild=args.rebuild))
    print(f"wcag_chunks: {count} rows")


if __name__ == "__main__":
    main()
