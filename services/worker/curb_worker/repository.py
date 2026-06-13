"""Worker-side database access.

The worker owns its own asyncpg pool; sharing one across process boundaries
isn't a thing. Queries match the API side so we end up with one schema.
"""

from __future__ import annotations

import json
from uuid import UUID

import asyncpg
from curb_shared import AuditState, Remediation, Violation


async def make_pool(dsn: str) -> asyncpg.Pool:
    return await asyncpg.create_pool(dsn, min_size=1, max_size=4)


async def set_status(
    pool: asyncpg.Pool,
    audit_id: UUID,
    status: AuditState,
    *,
    error: str | None = None,
) -> None:
    await pool.execute(
        """
        UPDATE audits SET status = $2, error = $3, updated_at = now()
        WHERE id = $1
        """,
        audit_id,
        status,
        error,
    )


async def persist_violations(
    pool: asyncpg.Pool, audit_id: UUID, violations: list[Violation]
) -> None:
    if not violations:
        await pool.execute("UPDATE audits SET violation_count = 0 WHERE id = $1", audit_id)
        return
    async with pool.acquire() as conn, conn.transaction():
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


async def get_audit_url(pool: asyncpg.Pool, audit_id: UUID) -> str | None:
    row = await pool.fetchrow("SELECT url FROM audits WHERE id = $1", audit_id)
    return row["url"] if row else None


async def persist_remediation(
    pool: asyncpg.Pool,
    *,
    audit_id: UUID,
    remediation: Remediation,
    model_used: str,
) -> None:
    await pool.execute(
        """
        INSERT INTO remediations (
            violation_id, audit_id, wcag_criterion, severity, explanation,
            patch, confidence, verified, new_violations, model_used
        ) VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10)
        """,
        remediation.violation_id,
        audit_id,
        remediation.wcag_criterion,
        remediation.severity,
        remediation.explanation,
        json.dumps(remediation.patch.model_dump()),
        remediation.confidence,
        remediation.verified,
        remediation.new_violations,
        model_used,
    )
