"""End-to-end audit pipeline.

Per job: detect → persist → for each violation, retrieve guidance and (when
a model is configured) run the remediation agent with its self-check loop.
Persistence is the source of truth; events are a UX nicety.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import asyncpg
import structlog
from curb_shared import AuditEvent, AuditRequest, Violation
from curb_shared.bus import events_channel
from curb_shared.config import Settings
from playwright.async_api import Browser
from redis.asyncio import Redis

from curb_worker import repository
from curb_worker.agent import build_agent, propose_and_verify
from curb_worker.detector import open_audit_page, run_axe_on_page
from curb_worker.gateway import build_model, resolve
from curb_worker.retrieval import retrieve_for_violation

log = structlog.get_logger()

# Bound LLM cost: we only attempt remediation for the worst-N violations
# per audit. The rest still surface in the report; they just don't get a
# proposed fix in this run.
REMEDIATE_TOP_N = 5
_SEVERITY_RANK = {"critical": 0, "serious": 1, "moderate": 2, "minor": 3}


async def _publish(redis: Redis, event: AuditEvent) -> None:
    await redis.publish(events_channel(event.audit_id), event.model_dump_json())


def _event(audit_id: UUID, kind: str, **payload: Any) -> AuditEvent:
    return AuditEvent(
        audit_id=audit_id,
        kind=kind,  # type: ignore[arg-type]
        payload=payload,
        at=datetime.now(UTC),
    )


def _pick_targets(violations: list[Violation]) -> list[Violation]:
    return sorted(violations, key=lambda v: _SEVERITY_RANK.get(v.severity, 9))[:REMEDIATE_TOP_N]


async def _emit_guidance(audit_id: UUID, pool: asyncpg.Pool, redis: Redis, v: Violation) -> None:
    try:
        guidance = await retrieve_for_violation(
            pool,
            rule_id=v.rule_id,
            wcag_criterion=v.wcag_criterion,
            description=v.description,
            help_text=v.help,
            k=3,
        )
    except Exception:
        log.exception("retrieval_failed", audit_id=str(audit_id))
        return
    payload = [{"criterion": g.criterion, "title": g.title, "score": g.score} for g in guidance]
    await _publish(
        redis,
        _event(
            audit_id,
            "violation",
            rule_id=v.rule_id,
            wcag_criterion=v.wcag_criterion,
            severity=v.severity,
            selector=v.selector,
            guidance=payload,
        ),
    )


async def _remediate_top(
    *,
    audit_id: UUID,
    targets: list[Violation],
    page: Any,
    pool: asyncpg.Pool,
    redis: Redis,
    settings: Settings,
    request: AuditRequest | None,
) -> None:
    """Run the agent over the chosen targets, persist + publish each result."""
    choice = resolve(
        settings,
        byok_provider=request.model_provider if request else None,
        byok_api_key=request.model_api_key if request else None,
    )
    if choice is None:
        log.info("remediation_skipped", reason="no_model_configured")
        return
    try:
        model = build_model(choice)
    except Exception:
        log.exception("model_build_failed")
        return
    agent = build_agent(model)

    for v in targets:
        guidance = await retrieve_for_violation(
            pool,
            rule_id=v.rule_id,
            wcag_criterion=v.wcag_criterion,
            description=v.description,
            help_text=v.help,
            k=3,
        )
        remediation = await propose_and_verify(
            agent=agent,
            page=page,
            violation=v,
            guidance=guidance,
            model_label=choice.qualified,
        )
        if remediation is None:
            continue
        await repository.persist_remediation(
            pool,
            audit_id=audit_id,
            remediation=remediation,
            model_used=choice.qualified,
        )
        await _publish(
            redis,
            _event(
                audit_id,
                "remediation",
                violation_id=str(v.id),
                wcag_criterion=remediation.wcag_criterion,
                verified=remediation.verified,
                confidence=remediation.confidence,
                explanation=remediation.explanation,
                patch=remediation.patch.model_dump(),
                new_violations=remediation.new_violations,
                model=choice.qualified,
            ),
        )


async def run_audit(
    audit_id: UUID,
    *,
    pool: asyncpg.Pool,
    redis: Redis,
    browser: Browser,
    settings: Settings,
    request: AuditRequest | None = None,
) -> None:
    """Run one audit end-to-end. Errors are caught and surfaced as 'failed'."""
    url = await repository.get_audit_url(pool, audit_id)
    if url is None:
        log.warning("audit_missing", audit_id=str(audit_id))
        return

    await repository.set_status(pool, audit_id, "running")
    await _publish(redis, _event(audit_id, "status", status="running"))
    log.info("audit_start", audit_id=str(audit_id), url=url)

    context = page = None
    try:
        context, page = await open_audit_page(url, browser)
        violations = await run_axe_on_page(audit_id, page)
        await repository.persist_violations(pool, audit_id, violations)
        for v in violations:
            await _emit_guidance(audit_id, pool, redis, v)
        # Phase 3: remediation pass over the worst N violations.
        if violations:
            await _remediate_top(
                audit_id=audit_id,
                targets=_pick_targets(violations),
                page=page,
                pool=pool,
                redis=redis,
                settings=settings,
                request=request,
            )
        await repository.set_status(pool, audit_id, "complete")
        await _publish(
            redis,
            _event(audit_id, "complete", violation_count=len(violations)),
        )
        log.info(
            "audit_complete",
            audit_id=str(audit_id),
            violation_count=len(violations),
        )
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}"
        await repository.set_status(pool, audit_id, "failed", error=msg)
        await _publish(redis, _event(audit_id, "error", error=msg))
        log.exception("audit_failed", audit_id=str(audit_id))
    finally:
        if context is not None:
            await context.close()
