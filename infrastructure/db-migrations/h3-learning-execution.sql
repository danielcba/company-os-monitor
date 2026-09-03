-- H3 — Learning Hardening: Durable Execution & Outcome History
-- Authorized 2026-08-31. Phase 1/Phase 2 transaction model.
--
-- Tables:
--   outcome_revisions  — append-only outcome history (Phase 1, lock-free)
--   learning_executions — durable execution lifecycle (Phase 2, advisory-locked)
--
-- Modifications:
--   learning_memory — adds execution_id FK for provenance traceability

-- ============================================
-- OUTCOME REVISIONS (Phase 1 — append-only)
-- ============================================
-- Records every submitted outcome revision. Lock-free: multiple concurrent
-- Phase 1 commits are safe because this is append-only (no contention).
-- Each revision is an immutable historical record traceable to its decision.

CREATE TABLE IF NOT EXISTS outcome_revisions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    decision_id     UUID NOT NULL,
    actual_outcomes JSONB NOT NULL,
    executed_at     TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_outcome_revisions_tenant
    ON outcome_revisions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_outcome_revisions_decision
    ON outcome_revisions (tenant_id, decision_id, created_at DESC);

-- Append-only: outcome revisions are immutable historical records (P6).
CREATE OR REPLACE FUNCTION prevent_outcome_revision_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Outcome revisions are append-only (P6). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS outcome_revision_immutable_trigger ON outcome_revisions;
CREATE TRIGGER outcome_revision_immutable_trigger
    BEFORE UPDATE OR DELETE ON outcome_revisions
    FOR EACH ROW EXECUTE FUNCTION prevent_outcome_revision_update();

-- ============================================
-- LEARNING EXECUTIONS (Phase 2 — lifecycle)
-- ============================================
-- Tracks the durable lifecycle of each learning execution. A learning execution
-- is created for each outcome_revision and follows a deterministic state machine:
--   pending → running → completed | failed | stale
--
-- Advisory lock (transaction-scoped) serializes concurrent executions for the
-- same decision. The UNIQUE partial index prevents duplicate active executions
-- per outcome_revision.

CREATE TABLE IF NOT EXISTS learning_executions (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL,
    decision_id         UUID NOT NULL,
    outcome_revision_id UUID NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'pending',
    attempt_number      INTEGER NOT NULL DEFAULT 1,
    parent_execution_id UUID,
    started_at          TIMESTAMPTZ,
    completed_at        TIMESTAMPTZ,
    heartbeat_at        TIMESTAMPTZ,
    signal_count        INTEGER DEFAULT 0,
    failure_reason      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT chk_learning_execution_status
        CHECK (status IN ('pending', 'running', 'completed', 'failed', 'stale')),
    CONSTRAINT fk_learning_execution_outcome_revision
        FOREIGN KEY (outcome_revision_id) REFERENCES outcome_revisions(id),
    CONSTRAINT fk_learning_execution_parent
        FOREIGN KEY (parent_execution_id) REFERENCES learning_executions(id)
);

CREATE INDEX IF NOT EXISTS idx_learning_executions_tenant
    ON learning_executions (tenant_id);
CREATE INDEX IF NOT EXISTS idx_learning_executions_decision
    ON learning_executions (tenant_id, decision_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_learning_executions_status
    ON learning_executions (tenant_id, status, heartbeat_at);

-- At most one active (pending/running) execution per outcome_revision.
-- Completed/failed/stale are terminal and don't conflict with new executions.
CREATE UNIQUE INDEX IF NOT EXISTS uq_learning_execution_active
    ON learning_executions (outcome_revision_id)
    WHERE status IN ('pending', 'running');

-- ============================================
-- LEARNING_MEMORY — add execution_id FK
-- ============================================
-- Adds provenance traceability: every learning memory record can be traced
-- back to the execution that produced it. Existing pre-H3 records have
-- execution_id = NULL (legacy sentinel, backward compatible).

ALTER TABLE learning_memory
    ADD COLUMN IF NOT EXISTS execution_id UUID;

-- FK is added conditionally: only if the column was just added (idempotent).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM information_schema.table_constraints
        WHERE constraint_name = 'fk_learning_memory_execution'
        AND table_name = 'learning_memory'
    ) THEN
        ALTER TABLE learning_memory
            ADD CONSTRAINT fk_learning_memory_execution
            FOREIGN KEY (execution_id) REFERENCES learning_executions(id);
    END IF;
END $$;

-- Index for provenance queries (trace memory → execution).
CREATE INDEX IF NOT EXISTS idx_learning_memory_execution
    ON learning_memory (execution_id)
    WHERE execution_id IS NOT NULL;
