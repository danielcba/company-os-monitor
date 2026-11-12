-- SAP R/3 integration — Fase 3: SAP posting log (append-only).
--
-- Non-canonical support table (D-2026-08-07 / ADR-0002). Records every
-- outward SAP posting made by the SapBridge, giving idempotence (dedup by the
-- deterministic posting_key) and an audit trail of what was sent to SAP.
-- It is NOT a cognitive table (never consumed as cognitive input). Append-only
-- with an immutability trigger, same precedent as `reports` (ADR-0002).

CREATE TABLE IF NOT EXISTS sap_posting_log (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    posting_key VARCHAR(255) NOT NULL,
    decision_id UUID NOT NULL,
    gateway_kind VARCHAR(32) NOT NULL,          -- 'rfc' | 'mock'
    outcome VARCHAR(16) NOT NULL,                -- success | failure | unavailable
    reference VARCHAR(255),
    message VARCHAR(500),
    posted_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, posting_key)
);

CREATE INDEX IF NOT EXISTS idx_sap_posting_log_tenant_key
    ON sap_posting_log (tenant_id, posting_key);

-- Idempotent column backfill guard (for tables created before later columns).
ALTER TABLE sap_posting_log
    ADD COLUMN IF NOT EXISTS posted_at TIMESTAMPTZ DEFAULT now();

-- Immutability trigger (append-only): a posting log row is permanent evidence.
-- DELETE is always blocked. UPDATE is allowed ONLY for the result lifecycle
-- fields (outcome/reference/message/posted_at) that the bridge writes after a
-- posting completes; the identity/content columns (id, tenant_id, posting_key,
-- decision_id, gateway_kind) are immutable. This is the same precedent as
-- `decisions` (content immutable, lifecycle fields flippable).
DROP TRIGGER IF EXISTS sap_posting_log_immutable_trigger ON sap_posting_log;

CREATE OR REPLACE FUNCTION prevent_sap_posting_log_update()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'SAP posting log row cannot be deleted (append-only audit, ADR-0002).';
    END IF;
    IF NEW.id <> OLD.id
       OR NEW.tenant_id <> OLD.tenant_id
       OR NEW.posting_key <> OLD.posting_key
       OR NEW.decision_id <> OLD.decision_id
       OR NEW.gateway_kind <> OLD.gateway_kind THEN
        RAISE EXCEPTION 'SAP posting log identity/content is immutable (ADR-0002). Only outcome/reference/message may change.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER sap_posting_log_immutable_trigger
    BEFORE UPDATE OR DELETE ON sap_posting_log
    FOR EACH ROW EXECUTE FUNCTION prevent_sap_posting_log_update();
