"""Pydantic models shared between API and worker.

Detection schema (Phase 1) is fully specified here. Remediation (Phase 3)
and scoring (Phase 4) extend, never break, these shapes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

Severity = Literal["critical", "serious", "moderate", "minor"]
AuditState = Literal["queued", "running", "complete", "failed"]

# The axe-core impact strings line up with our Severity enum 1:1 except
# axe also emits the lowercase form; coerce on the boundary.
_AXE_IMPACT_TO_SEVERITY: dict[str, Severity] = {
    "critical": "critical",
    "serious": "serious",
    "moderate": "moderate",
    "minor": "minor",
}


def coerce_severity(axe_impact: str | None) -> Severity:
    """Map axe-core's `impact` field to our Severity. Defaults to 'minor'."""
    if axe_impact is None:
        return "minor"
    return _AXE_IMPACT_TO_SEVERITY.get(axe_impact.lower(), "minor")


class AuditRequest(BaseModel):
    """Body of POST /audits."""

    url: HttpUrl
    model_provider: str | None = Field(
        default=None,
        description="BYOK provider override (e.g. 'google-gla', 'groq'). Ignored in Phase 1.",
    )
    model_api_key: str | None = Field(
        default=None,
        description="BYOK key. Never persisted or logged. Ignored in Phase 1.",
    )


class Audit(BaseModel):
    """One audit run, as persisted in the `audits` table."""

    id: UUID
    url: str
    status: AuditState
    created_at: datetime
    updated_at: datetime
    error: str | None = None
    violation_count: int = 0


class Violation(BaseModel):
    """One axe-core violation against a node on the audited page.

    `selector` is the unique CSS selector for the offending node (axe returns
    this as a JSON array because of iframe boundaries; we join with ' >>> ' to
    keep it round-trippable). `markup` is the rendered outerHTML at the time
    of the audit — what the remediation agent will be asked to patch.
    """

    id: UUID
    audit_id: UUID
    rule_id: str
    wcag_criterion: str
    description: str
    help: str
    help_url: str
    severity: Severity
    selector: str
    markup: str
    failure_summary: str = ""


class Patch(BaseModel):
    target_selector: str
    original: str
    fixed: str
    unified_diff: str


class Remediation(BaseModel):
    """One proposed fix for one violation.

    The verified-only contract lives on this model: `verified` may only be
    True if the validate tool confirmed (a) the original violation is gone
    and (b) no new violations appeared. The agent's claim is checked
    against the validate tool's last result by the worker — defence in
    depth so a hallucinated `verified=true` cannot ship."""

    violation_id: UUID
    wcag_criterion: str
    severity: Severity
    explanation: str
    patch: Patch
    confidence: float = Field(ge=0.0, le=1.0)
    verified: bool = False
    new_violations: list[str] = Field(default_factory=list)


class ValidationResult(BaseModel):
    """What the `validate` tool returns when the agent calls it."""

    resolved: bool
    new_violations: list[str] = Field(default_factory=list)
    notes: str = ""


# SSE event payloads. The frontend keys off `kind`.


class AuditEvent(BaseModel):
    audit_id: UUID
    kind: Literal["status", "violation", "remediation", "complete", "error"]
    payload: dict[str, object] = Field(default_factory=dict)
    at: datetime
