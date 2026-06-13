"""Hybrid retrieval over wcag_chunks.

Given a violation (rule_id + criterion + axe description), return the top-K
most relevant guidance chunks. The 'hybrid' part: we boost chunks whose
`criterion` column matches the violation's criterion, since we know the
deterministic mapping from axe-core to WCAG SC.

The boost is additive on the similarity score, not a filter — chunks with
strong semantic similarity but a different criterion (e.g. an ARIA APG
pattern that cross-references) still appear when relevant.
"""

from __future__ import annotations

from dataclasses import dataclass

import asyncpg
import structlog
from pgvector.asyncpg import register_vector

from curb_worker.embeddings import embed_one

log = structlog.get_logger()

# Boost added to (1 - distance) for chunks whose criterion id matches.
CRITERION_MATCH_BOOST = 0.2


@dataclass
class Guidance:
    criterion: str
    title: str
    body: str
    score: float


async def retrieve_guidance(
    pool: asyncpg.Pool,
    *,
    query: str,
    criterion: str,
    k: int = 4,
) -> list[Guidance]:
    """Return the top-k guidance chunks for a violation query.

    Hybrid: we always include all chunks whose `criterion` matches (axe gave
    us the SC id deterministically — we trust it as a strong signal), then
    fill the remaining slots with vector neighbours. Final score blends
    similarity with a criterion-match boost so the merged ordering still
    reflects semantic relevance.
    """
    vec = embed_one(query)
    candidate_pool = max(k * 3, 12)

    async with pool.acquire() as conn:
        await register_vector(conn)
        # Vector neighbours first.
        vector_rows = await conn.fetch(
            """
            SELECT criterion, title, body,
                   1 - (embedding <=> $1) AS similarity
            FROM wcag_chunks
            ORDER BY embedding <=> $1
            LIMIT $2
            """,
            vec,
            candidate_pool,
        )
        # Plus every chunk for the named criterion (even if vector missed it).
        criterion_rows = await conn.fetch(
            """
            SELECT criterion, title, body,
                   1 - (embedding <=> $1) AS similarity
            FROM wcag_chunks
            WHERE criterion = $2
            """,
            vec,
            criterion,
        )

    seen: dict[tuple[str, str], Guidance] = {}
    for r in list(vector_rows) + list(criterion_rows):
        key = (r["criterion"], r["title"])
        score = float(r["similarity"])
        if r["criterion"] == criterion:
            score += CRITERION_MATCH_BOOST
        # Keep the highest score if a chunk shows up in both queries.
        existing = seen.get(key)
        if existing is None or score > existing.score:
            seen[key] = Guidance(
                criterion=r["criterion"],
                title=r["title"],
                body=r["body"],
                score=score,
            )

    ordered = sorted(seen.values(), key=lambda g: g.score, reverse=True)
    return ordered[:k]


async def retrieve_for_violation(
    pool: asyncpg.Pool,
    *,
    rule_id: str,
    wcag_criterion: str,
    description: str,
    help_text: str,
    k: int = 4,
) -> list[Guidance]:
    """Convenience wrapper that builds the query from violation fields."""
    query = f"{rule_id}: {description}. {help_text}".strip()
    return await retrieve_guidance(pool, query=query, criterion=wcag_criterion, k=k)
