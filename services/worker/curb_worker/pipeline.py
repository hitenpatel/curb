"""End-to-end audit pipeline.

Called per job. Wires detector → repository → bus. The bus side is
fire-and-forget; persistence is the source of truth, events are a UX nicety.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg
import structlog
from curb_shared import AuditEvent
from curb_shared.bus import events_channel
from playwright.async_api import Browser
from redis.asyncio import Redis

from curb_worker import repository
from curb_worker.detector import audit_url

log = structlog.get_logger()


async def _publish(redis: Redis, event: AuditEvent) -> None:
    await redis.publish(events_channel(event.audit_id), event.model_dump_json())


def _event(audit_id: UUID, kind: str, **payload: Any) -> AuditEvent:
    return AuditEvent(
        audit_id=audit_id,
        kind=kind,  # type: ignore[arg-type]
        payload=payload,
        at=datetime.now(UTC),
    )


async def run_audit(
    audit_id: UUID,
    *,
    pool: asyncpg.Pool,
    redis: Redis,
    browser: Browser,
) -> None:
    """Run one audit end-to-end. Errors are caught and surfaced as 'failed'."""
    url = await repository.get_audit_url(pool, audit_id)
    if url is None:
        log.warning("audit_missing", audit_id=str(audit_id))
        return

    await repository.set_status(pool, audit_id, "running")
    await _publish(redis, _event(audit_id, "status", status="running"))
    log.info("audit_start", audit_id=str(audit_id), url=url)

    try:
        violations = await audit_url(audit_id, url, browser)
        await repository.persist_violations(pool, audit_id, violations)
        for v in violations:
            await _publish(
                redis,
                _event(
                    audit_id,
                    "violation",
                    rule_id=v.rule_id,
                    wcag_criterion=v.wcag_criterion,
                    severity=v.severity,
                    selector=v.selector,
                ),
            )
        await repository.set_status(pool, audit_id, "complete")
        await _publish(
            redis,
            _event(audit_id, "complete", violation_count=len(violations)),
        )
        log.info("audit_complete", audit_id=str(audit_id), violation_count=len(violations))
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        await repository.set_status(pool, audit_id, "failed", error=msg)
        await _publish(redis, _event(audit_id, "error", error=msg))
        log.exception("audit_failed", audit_id=str(audit_id))
