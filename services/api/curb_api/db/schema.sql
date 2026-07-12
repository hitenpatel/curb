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

-- Precomputed showcase audits, served by GET /api/audits/samples so the
-- landing-page demos don't burn a live run (and quota) per click.
ALTER TABLE audits ADD COLUMN IF NOT EXISTS is_sample boolean NOT NULL DEFAULT false;
CREATE INDEX IF NOT EXISTS audits_is_sample_idx ON audits (is_sample) WHERE is_sample;

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

-- Phase 2: WCAG 2.2 + ARIA APG guidance corpus.
-- Embedding dim 384 matches BAAI/bge-small-en-v1.5 + all-MiniLM-L6-v2.
CREATE TABLE IF NOT EXISTS wcag_chunks (
    id            uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    source        text NOT NULL,
    criterion     text NOT NULL,
    title         text NOT NULL,
    body          text NOT NULL,
    embedding     vector(384) NOT NULL,
    created_at    timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS wcag_chunks_criterion_idx ON wcag_chunks (criterion);

-- HNSW index over the embedding column. The pgvector cosine ops class
-- gives us 1 - cosine similarity as distance (lower = more similar).
CREATE INDEX IF NOT EXISTS wcag_chunks_embedding_hnsw_idx
    ON wcag_chunks USING hnsw (embedding vector_cosine_ops);

-- Phase 3: remediations.
-- The verified-only contract lives in code (worker overrides verified=true
-- to false if the validate tool didn't confirm) but the column is the
-- persistence side of that contract.
CREATE TABLE IF NOT EXISTS remediations (
    id              uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
    violation_id    uuid NOT NULL REFERENCES violations(id) ON DELETE CASCADE,
    audit_id        uuid NOT NULL REFERENCES audits(id) ON DELETE CASCADE,
    wcag_criterion  text NOT NULL,
    severity        text NOT NULL,
    explanation     text NOT NULL,
    patch           jsonb NOT NULL,
    confidence      real NOT NULL,
    verified        boolean NOT NULL DEFAULT false,
    new_violations  text[] NOT NULL DEFAULT '{}',
    model_used      text NOT NULL,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS remediations_audit_id_idx ON remediations (audit_id);
CREATE INDEX IF NOT EXISTS remediations_violation_id_idx ON remediations (violation_id);
