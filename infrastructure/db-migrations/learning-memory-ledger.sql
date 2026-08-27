-- Learning Memory ledger (P7 persistence, authorized 2026-08-27)
-- New persisted entity. Immutable-by-record: each authorized POST appends a row.
-- Idempotency via UNIQUE (tenant_id, target_type, target_id, signal_hash):
-- re-persisting an identical signal is a no-op (ON CONFLICT DO NOTHING).
-- Canonical cognitive entities are NOT mutated (P1); this is a separate
-- append-only ledger. Mirrors the immutability convention of other tables.

CREATE TABLE IF NOT EXISTS learning_memory (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id     UUID NOT NULL,
    target_type   VARCHAR(32) NOT NULL,           -- pattern | context | insight
    target_id     UUID NOT NULL,
    signal        JSONB NOT NULL,                 -- the learned adjustment
    provenance    JSONB NOT NULL,                 -- decision_ids, counts, verdicts
    signal_hash   VARCHAR(64) NOT NULL,           -- sha256 of canonical signal
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_learning_memory_tenant
    ON learning_memory (tenant_id);
CREATE INDEX IF NOT EXISTS idx_learning_memory_target
    ON learning_memory (tenant_id, target_type, target_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_learning_memory_signal
    ON learning_memory (tenant_id, target_type, target_id, signal_hash);

-- Append-only: a persisted learning record is never UPDATEd or DELETEd.
CREATE OR REPLACE FUNCTION prevent_learning_memory_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Learning Memory is append-only (P1): no UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS learning_memory_immutable_trigger ON learning_memory;
CREATE TRIGGER learning_memory_immutable_trigger
    BEFORE UPDATE OR DELETE ON learning_memory
    FOR EACH ROW EXECUTE FUNCTION prevent_learning_memory_update();
