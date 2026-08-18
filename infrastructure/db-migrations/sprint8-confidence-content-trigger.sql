-- Sprint 8 - Confidence content immutability trigger (migration for existing DBs).
--
-- The `confidence_scores` table already exists from the base schema (docs/01).
-- This migration adds the trigger that enforces P1 at the data layer for the
-- Learning layer's Calibrate capability:
--   - all content columns (tenant_id, target_type, target_id, evidential_support,
--     explanatory_coherence, historical_calibration, confidence_score, alpha,
--     calibration_justification, calibration_error_estimate, computed_at) are
--     immutable once written;
--   - a confidence row has NO lifecycle flag (unlike patterns/contexts/
--     hypotheses): a re-calibration with different inputs is a NEW row produced
--     by the deterministic content-addressed id (append-only history, never an
--     UPDATE), so both UPDATE and DELETE are blocked (same policy as evidence);
--   - DELETE is blocked: a calibrated confidence is part of the persistent
--     audit trail (score + reasons + calibration error estimate) and is never
--     removed.
--
-- Apply on an existing database (installations with a fresh volume apply the
-- same DDL automatically from 01-schema.sql):
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint8-confidence-content-trigger.sql

DROP TRIGGER IF EXISTS confidence_content_immutable_trigger ON confidence_scores;

CREATE OR REPLACE FUNCTION prevent_confidence_content_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Confidence scores are immutable (P1). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER confidence_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON confidence_scores
    FOR EACH ROW EXECUTE FUNCTION prevent_confidence_content_update();