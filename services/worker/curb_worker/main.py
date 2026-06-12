"""Worker entrypoint. BLPOPs jobs off Redis, runs the audit pipeline.

Runs forever. One Chromium browser, one asyncpg pool, one redis client; we
spin up a fresh BrowserContext per audit inside the detector.
"""

from __future__ import annotations

import asyncio
import signal
from contextlib import suppress
from typing import Any
from uuid import UUID

import structlog
from curb_shared.bus import JOB_QUEUE
from curb_shared.config import load_settings
from playwright.async_api import Browser, async_playwright
from redis.asyncio import Redis
from redis.exceptions import TimeoutError as RedisTimeoutError

from curb_worker import repository
from curb_worker.pipeline import run_audit

log = structlog.get_logger()


async def _consume(
    *,
    pool: Any,
    redis: Redis,
    browser: Browser,
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
            audit_id = UUID(raw.decode() if isinstance(raw, bytes) else raw)
        except ValueError:
            log.warning("invalid_job", raw=raw)
            continue
        await run_audit(audit_id, pool=pool, redis=redis, browser=browser)


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

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop.set)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=["--no-sandbox"])
        try:
            await _consume(pool=pool, redis=redis, browser=browser, stop=stop)
        finally:
            await browser.close()
            await redis.aclose()
            await pool.close()
            log.info("worker_stopped")


if __name__ == "__main__":
    with suppress(KeyboardInterrupt):
        asyncio.run(main())
