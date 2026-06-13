"""Worker entrypoint. BLPOPs jobs off Redis, runs the audit pipeline.

Runs forever. One Chromium browser, one asyncpg pool, one redis client; we
spin up a fresh BrowserContext per audit inside the detector.
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from typing import Any

import structlog
from curb_shared import AuditRequest
from curb_shared.bus import JOB_QUEUE, deserialize_job
from curb_shared.config import Settings, load_settings
from playwright.async_api import Browser, async_playwright
from pydantic import HttpUrl
from redis.asyncio import Redis
from redis.exceptions import TimeoutError as RedisTimeoutError

from curb_worker import repository
from curb_worker.pipeline import run_audit

log = structlog.get_logger()


async def _maybe_ingest_corpus() -> None:
    """Run corpus ingest on startup if the table is empty.

    Imported lazily so the worker still boots if the corpus package isn't
    on sys.path (containers set PYTHONPATH=/app; local dev gets it via uv)."""
    try:
        from corpus.ingest import ingest  # noqa: PLC0415
    except ImportError:
        log.info("corpus_ingest_skipped", reason="corpus_module_not_importable")
        return
    try:
        count = await ingest()
        log.info("corpus_ready", chunks=count)
    except Exception:
        # Don't crash the worker on ingest failure — fail open, log loudly.
        log.exception("corpus_ingest_failed")


async def _consume(
    *,
    pool: Any,
    redis: Redis,
    browser: Browser,
    settings: Settings,
    stop: asyncio.Event,
) -> None:
    log.info("worker_ready", queue=JOB_QUEUE)
    while not stop.is_set():
        # Block up to 5s; bounded so we can react to shutdown signals.
        # redis-py raises TimeoutError on socket-level timeouts when BLPOP
        # returns nil — semantically equivalent to "no work", so treat the
        # same as None and loop.
        try:
            msg = await redis.blpop([JOB_QUEUE], timeout=5)
        except RedisTimeoutError:
            continue
        if msg is None:
            continue
        _, raw = msg
        try:
            job = deserialize_job(raw)
        except Exception:
            log.warning("invalid_job", raw=raw)
            continue
        # Build a per-audit AuditRequest from the BYOK fields on the job.
        # The URL is recovered from DB by run_audit; we don't carry it on
        # the job payload (single source of truth = the audits row).
        request = AuditRequest(
            url=HttpUrl("https://placeholder.invalid/"),
            model_provider=job.byok_provider,
            model_api_key=job.byok_api_key,
        )
        await run_audit(
            job.audit_id,
            pool=pool,
            redis=redis,
            browser=browser,
            settings=settings,
            request=request,
        )


async def main() -> None:
    settings = load_settings()
    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.JSONRenderer(),
        ]
    )

    pool = await repository.make_pool(settings.database_url)
    redis = Redis.from_url(settings.redis_url)
    stop = asyncio.Event()

    # Ingest the WCAG corpus if the table is empty. Idempotent; safe to run
    # on every restart. Costs a model download + ~50 embeddings on first boot.
    await _maybe_ingest_corpus()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            await _consume(pool=pool, redis=redis, browser=browser, settings=settings, stop=stop)
        finally:
            await browser.close()
            await redis.aclose()
            await pool.close()
            log.info("worker_stopped")


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
