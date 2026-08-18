-- Sprint 6 - Anomaly content immutability trigger (migration for existing DBs).
--
-- The `anomalies` table already exists from the base schema (docs/01). This
-- migration adds the trigger that enforces P1 at the data layer:
--   - all content columns (context_id, pattern_id, deviation_score,
--     tolerance_threshold, anomaly_class, detected_at) are immutable once
--     detected;
--   - unlike `patterns`/`contexts`, `anomalies` has NO lifecycle flag
--     (is_active): a detected anomaly is a one-shot signal, so the row is
--     fully immutable and both UPDATE and DELETE are blocked (same policy as
--     `evidence`).
--
-- An anomaly is only ever re-detected as a NEW deterministic row (idempotent
-- dedup by primary key), never an UPDATE of an existing one - this trigger
-- makes that non-negotiable.
--
-- Apply on an existing database (installations with a fresh volume apply the
-- same DDL automatically from 01-schema.sql):
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint6-anomaly-content-trigger.sql

DROP TRIGGER IF EXISTS anomaly_content_immutable_trigger ON anomalies;

CREATE OR REPLACE FUNCTION prevent_anomaly_content_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Anomalies are immutable (P1). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER anomaly_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON anomalies
    FOR EACH ROW EXECUTE FUNCTION prevent_anomaly_content_update();