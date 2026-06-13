"""Audit endpoints.

POST /api/audits         enqueue a new audit
GET  /api/audits/{id}    audit status + violations
GET  /api/audits/{id}/events  SSE stream of progress events
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from uuid import UUID

from curb_shared import Audit, AuditRequest, Remediation, Violation
from curb_shared.bus import JOB_QUEUE, Job, events_channel, serialize_job
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from curb_api.db import get_pool
from curb_api.db.queries import create_audit, get_audit, list_remediations, list_violations
from curb_api.queue import get_redis

router = APIRouter(prefix="/api/audits")


class Scorecard(BaseModel):
    """Per-audit summary metrics. Primary metric is `pass_rate` — the
    fraction of attempted remediations the agent + axe self-check both
    confirmed. Mirrors the eval-harness ground truth, computed per audit."""

    violations_total: int
    violations_by_severity: dict[str, int]
    violations_by_criterion: dict[str, int]
    remediations_attempted: int
    remediations_verified: int
    pass_rate: float
    regressions_avoided: int  # remediations rejected because they introduced new violations


def _scorecard(violations: list[Violation], remediations: list[Remediation]) -> Scorecard:
    by_severity: dict[str, int] = {}
    by_criterion: dict[str, int] = {}
    for v in violations:
        by_severity[v.severity] = by_severity.get(v.severity, 0) + 1
        by_criterion[v.wcag_criterion] = by_criterion.get(v.wcag_criterion, 0) + 1
    attempted = len(remediations)
    verified = sum(1 for r in remediations if r.verified)
    regressions = sum(1 for r in remediations if r.new_violations)
    rate = (verified / attempted) if attempted else 0.0
    return Scorecard(
        violations_total=len(violations),
        violations_by_severity=by_severity,
        violations_by_criterion=by_criterion,
        remediations_attempted=attempted,
        remediations_verified=verified,
        pass_rate=rate,
        regressions_avoided=regressions,
    )


class AuditDetail(BaseModel):
    audit: Audit
    violations: list[Violation]
    remediations: list[Remediation]
    scorecard: Scorecard


@router.post("", response_model=Audit, status_code=201)
async def enqueue_audit(req: AuditRequest) -> Audit:
    pool = get_pool()
    redis = get_redis()
    audit = await create_audit(pool, str(req.url))
    # BYOK fields travel on the Redis job only; never persisted. The worker
    # forgets them after the run.
    job = Job(
        audit_id=audit.id,
        byok_provider=req.model_provider,
        byok_api_key=req.model_api_key,
    )
    await redis.rpush(JOB_QUEUE, serialize_job(job))
    return audit


@router.get("/{audit_id}", response_model=AuditDetail)
async def read_audit(audit_id: UUID) -> AuditDetail:
    pool = get_pool()
    audit = await get_audit(pool, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="audit not found")
    violations = await list_violations(pool, audit_id)
    remediations = await list_remediations(pool, audit_id)
    return AuditDetail(
        audit=audit,
        violations=violations,
        remediations=remediations,
        scorecard=_scorecard(violations, remediations),
    )


@router.get("/{audit_id}/events")
async def audit_events(audit_id: UUID) -> EventSourceResponse:
    """SSE stream of progress events for one audit.

    Subscribes to the per-audit Redis channel and forwards each message as an
    SSE 'message' event. The stream closes when a 'complete' or 'error' event
    arrives. If the audit is already terminal at subscribe time, we emit one
    'complete' / 'error' event derived from DB state and close immediately —
    no client gets stuck waiting on a channel no one will publish to.
    """
    pool = get_pool()
    audit = await get_audit(pool, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="audit not found")

    async def stream() -> AsyncIterator[dict[str, str]]:
        redis = get_redis()
        pubsub = redis.pubsub()
        await pubsub.subscribe(events_channel(audit_id))
        try:
            # If the audit already finished before the client subscribed,
            # synthesise a terminal event so we don't block.
            if audit.status in {"complete", "failed"}:
                kind = "complete" if audit.status == "complete" else "error"
                yield {"event": kind, "data": audit.model_dump_json()}
                return
            while True:
                msg = await pubsub.get_message(ignore_subscribe_messages=True, timeout=15.0)
                if msg is None:
                    # keep-alive ping so proxies don't drop the connection
                    yield {"event": "ping", "data": ""}
                    continue
                data = msg["data"]
                payload = data.decode() if isinstance(data, bytes) else str(data)
                # Re-parse just enough to know whether to close.
                try:
                    kind = json.loads(payload).get("kind", "status")
                except json.JSONDecodeError:
                    kind = "status"
                yield {"event": kind, "data": payload}
                if kind in {"complete", "error"}:
                    return
        finally:
            await pubsub.unsubscribe(events_channel(audit_id))
            await pubsub.aclose()  # type: ignore[no-untyped-call]

    async def heartbeat_safe() -> AsyncIterator[dict[str, str]]:
        # CancelledError on client disconnect is normal; swallow it cleanly.
        try:
            async for ev in stream():
                yield ev
        except asyncio.CancelledError:
            return

    return EventSourceResponse(heartbeat_safe())
