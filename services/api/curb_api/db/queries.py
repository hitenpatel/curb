"""Thin asyncpg query helpers. No ORM; SQL is part of the contract."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from asyncpg import Connection, Pool
from curb_shared import Audit, AuditState, Violation


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
