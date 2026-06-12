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

from curb_shared import Audit, AuditRequest, Violation
from curb_shared.bus import JOB_QUEUE, events_channel
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from curb_api.db import get_pool
from curb_api.db.queries import create_audit, get_audit, list_violations
from curb_api.queue import get_redis

router = APIRouter(prefix="/api/audits")


class AuditDetail(BaseModel):
    audit: Audit
    violations: list[Violation]


@router.post("", response_model=Audit, status_code=201)
async def enqueue_audit(req: AuditRequest) -> Audit:
    pool = get_pool()
    redis = get_redis()
    audit = await create_audit(pool, str(req.url))
    await redis.rpush(JOB_QUEUE, str(audit.id))
    return audit


@router.get("/{audit_id}", response_model=AuditDetail)
async def read_audit(audit_id: UUID) -> AuditDetail:
    pool = get_pool()
    audit = await get_audit(pool, audit_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="audit not found")
    violations = await list_violations(pool, audit_id)
    return AuditDetail(audit=audit, violations=violations)


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
