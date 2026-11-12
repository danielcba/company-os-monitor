-- SAP R/3 integration — Fase 1: asset finance support table.
--
-- Non-canonical support table (D-2026-08-07 / ADR-0002) for the SAP
-- integration: holds the financial data (hourly rate, currency, business
-- value) needed to price downtime. It is NOT a cognitive table; it is read by
-- the SAP bridge (Fase 3) and never consumed as cognitive input. P1's
-- append-only discipline applies as a compliance choice: a finance config row
-- is INSERT-only, keyed by a deterministic content-addressed id so re-saving
-- the same asset config is idempotent (ON CONFLICT DO NOTHING).

CREATE TABLE IF NOT EXISTS asset_finance (
    id UUID PRIMARY KEY,
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    asset_id UUID NOT NULL,
    rate_per_hour NUMERIC(12,4) NOT NULL DEFAULT 0 CHECK (rate_per_hour >= 0),
    currency VARCHAR(3) NOT NULL DEFAULT 'USD',
    business_value NUMERIC(14,2) CHECK (business_value IS NULL OR business_value >= 0),
    updated_by UUID,  -- author of this finance config (audit trail)
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tenant_id, asset_id)
);

-- Idempotent column backfill for installations where the table already existed
-- before the `updated_by` column was introduced.
ALTER TABLE asset_finance
    ADD COLUMN IF NOT EXISTS updated_by UUID;

-- Deterministic id is computed in-app (uuid5); ensure lookup index.
CREATE INDEX IF NOT EXISTS idx_asset_finance_tenant
    ON asset_finance (tenant_id, asset_id);

-- Immutability trigger (append-only), same pattern as `reports` (ADR-0002,
-- non-canonical output artifact). A recorded finance row may have been posted
-- to SAP; it must never be mutated or deleted retroactively.
DROP TRIGGER IF EXISTS asset_finance_immutable_trigger ON asset_finance;

CREATE OR REPLACE FUNCTION prevent_asset_finance_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Asset finance row is immutable (append-only support artifact, ADR-0002). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER asset_finance_immutable_trigger
    BEFORE UPDATE OR DELETE ON asset_finance
    FOR EACH ROW EXECUTE FUNCTION prevent_asset_finance_update();
