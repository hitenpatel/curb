"""Thin asyncpg query helpers. No ORM; SQL is part of the contract."""

from __future__ import annotations

import json
from datetime import datetime
from uuid import UUID

from asyncpg import Connection, Pool
from curb_shared import Audit, AuditState, Patch, Remediation, Violation


async def create_audit(pool: Pool, url: str) -> Audit:
    row = await pool.fetchrow(
        """
        INSERT INTO audits (url, status) VALUES ($1, 'queued')
        RETURNING id, url, status, created_at, updated_at, error, violation_count
        """,
        url,
    )
    assert row is not None  # INSERT ... RETURNING always emits one row
    return Audit(**dict(row))


async def get_audit(pool: Pool, audit_id: UUID) -> Audit | None:
    row = await pool.fetchrow(
        """
        SELECT id, url, status, created_at, updated_at, error, violation_count
        FROM audits WHERE id = $1
        """,
        audit_id,
    )
    return Audit(**dict(row)) if row else None


async def list_violations(pool: Pool, audit_id: UUID) -> list[Violation]:
    rows = await pool.fetch(
        """
        SELECT id, audit_id, rule_id, wcag_criterion, description, help, help_url,
               severity, selector, markup, failure_summary
        FROM violations WHERE audit_id = $1
        ORDER BY severity, rule_id
        """,
        audit_id,
    )
    return [Violation(**dict(r)) for r in rows]


async def list_remediations(pool: Pool, audit_id: UUID) -> list[Remediation]:
    rows = await pool.fetch(
        """
        SELECT violation_id, wcag_criterion, severity, explanation, patch,
               confidence, verified, new_violations
        FROM remediations WHERE audit_id = $1
        ORDER BY verified DESC, severity, wcag_criterion
        """,
        audit_id,
    )
    out: list[Remediation] = []
    for r in rows:
        patch_dict = r["patch"] if isinstance(r["patch"], dict) else json.loads(r["patch"])
        out.append(
            Remediation(
                violation_id=r["violation_id"],
                wcag_criterion=r["wcag_criterion"],
                severity=r["severity"],
                explanation=r["explanation"],
                patch=Patch(**patch_dict),
                confidence=float(r["confidence"]),
                verified=r["verified"],
                new_violations=list(r["new_violations"]),
            )
        )
    return out


async def update_audit_status(
    conn: Connection | Pool,
    audit_id: UUID,
    status: AuditState,
    *,
    error: str | None = None,
    updated_at: datetime | None = None,
) -> None:
    await conn.execute(
        """
        UPDATE audits
        SET status = $2,
            error = $3,
            updated_at = COALESCE($4, now())
        WHERE id = $1
        """,
        audit_id,
        status,
        error,
        updated_at,
    )


async def insert_violations(conn: Connection, audit_id: UUID, violations: list[Violation]) -> None:
    """Bulk insert with a single round-trip. Caller commits the transaction."""
    if not violations:
        return
    await conn.executemany(
        """
        INSERT INTO violations (
            id, audit_id, rule_id, wcag_criterion, description, help, help_url,
            severity, selector, markup, failure_summary
        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)
        """,
        [
            (
                v.id,
                audit_id,
                v.rule_id,
                v.wcag_criterion,
                v.description,
                v.help,
                v.help_url,
                v.severity,
                v.selector,
                v.markup,
                v.failure_summary,
            )
            for v in violations
        ],
    )
    await conn.execute(
        "UPDATE audits SET violation_count = $2 WHERE id = $1",
        audit_id,
        len(violations),
    )
