-- Curb schema. Idempotent: every CREATE is IF NOT EXISTS.
-- Applied on API startup via curb_api.db.pool.init_pool().
--
-- Phase 1 ships audits + violations. remediations + eval_results lock in
-- later but the columns are noted in docs/ARCHITECTURE.md ahead of time
-- so the agent and eval phases don't surprise anyone.

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS audits (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    url             text NOT NULL,
    status          text NOT NULL CHECK (status IN ('queued', 'running', 'complete', 'failed')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    updated_at      timestamptz NOT NULL DEFAULT now(),
    error           text,
    violation_count integer NOT NULL DEFAULT 0,
    model_used      text,
    summary         jsonb NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS audits_created_at_idx ON audits (created_at DESC);

CREATE TABLE IF NOT EXISTS violations (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    audit_id        uuid NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    rule_id         text NOT NULL,
    wcag_criterion  text NOT NULL,
    description     text NOT NULL DEFAULT '',
    help            text NOT NULL DEFAULT '',
    help_url        text NOT NULL DEFAULT '',
    severity        text NOT NULL CHECK (severity IN ('critical', 'serious', 'moderate', 'minor')),
    selector        text NOT NULL,
    markup          text NOT NULL,
    failure_summary text NOT NULL DEFAULT '',
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS violations_audit_id_idx ON violations (audit_id);
CREATE INDEX IF NOT EXISTS violations_rule_id_idx ON violations (rule_id);
