"""Pydantic models shared between API and worker.

Phase 0 stubs only. The full schema lands in Phase 1 (detection) and Phase 3 (agent).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

Severity = Literal["critical", "serious", "moderate", "minor"]


class AuditStatus(BaseModel):
    id: str
    url: str
    status: Literal["queued", "running", "scoring", "complete", "failed"]


class Violation(BaseModel):
    id: str
    audit_id: str
    rule_id: str
    wcag_criterion: str
    severity: Severity
    selector: str
    markup: str


class Patch(BaseModel):
    target_selector: str
    original: str
    fixed: str
    unified_diff: str


class Remediation(BaseModel):
    violation_id: str
    wcag_criterion: str
    severity: Severity
    explanation: str
    patch: Patch
    confidence: float = Field(ge=0.0, le=1.0)
    verified: bool = False
    new_violations: list[str] = Field(default_factory=list)
