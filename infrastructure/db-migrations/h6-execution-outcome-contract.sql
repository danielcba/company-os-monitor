-- H6: Execution & Outcome Contract
-- Creates execution_records table to formalize the Execution domain concept.
--
-- Relationship:
--   Decision 1 ─── 0..N ExecutionRecord
--   ExecutionRecord 1 ─── 0..1 Outcome (OutcomeRevision)
--
-- ExecutionRecord = explicit, auditable record that a Decision was executed
-- (manually or externally). Does NOT imply automated execution.
--
-- P1: append-only (no UPDATE/DELETE on content columns)
-- P6: execution is explicitly recorded, never assumed
-- Tenant isolation: tenant_id on every row

CREATE TABLE IF NOT EXISTS execution_records (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL,
    decision_id     UUID NOT NULL,
    execution_status VARCHAR(20) NOT NULL DEFAULT 'executed'
        CHECK (execution_status IN ('executed', 'failed', 'cancelled', 'unknown')),
    executed_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    executed_by     UUID,                -- user_id who recorded the execution
    notes           TEXT,                -- optional human-readable notes
    metadata        JSONB DEFAULT '{}',  -- extensible structured data
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT fk_execution_record_decision
        FOREIGN KEY (decision_id) REFERENCES decisions(id)
);

CREATE INDEX IF NOT EXISTS idx_execution_records_tenant
    ON execution_records (tenant_id);
CREATE INDEX IF NOT EXISTS idx_execution_records_decision
    ON execution_records (tenant_id, decision_id, created_at DESC);

-- Append-only: execution records are immutable once created (P1, P6).
-- Only lifecycle fields (none in this table) would be mutable; all fields
-- are content and must not change.
CREATE OR REPLACE FUNCTION prevent_execution_record_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Execution records are append-only (P6). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS execution_record_immutable_trigger ON execution_records;
CREATE TRIGGER execution_record_immutable_trigger
    BEFORE UPDATE OR DELETE ON execution_records
    FOR EACH ROW EXECUTE FUNCTION prevent_execution_record_update();
