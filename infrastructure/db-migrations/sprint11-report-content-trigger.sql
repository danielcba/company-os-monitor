-- Sprint 11 - Report immutability trigger (migration for existing DBs).
--
-- The `reports` table already exists from the base schema (docs/01, docs/04).
-- `reports` is the OUTPUT table of the Report Generator, an external
-- NON-canonical capability (ADR-0002): it only FORMATS what the canonical flow
-- already committed and never feeds the pipeline back.
--
-- Immutability decision: P1's precedent (append-only + immutable content)
-- applies to the canonical chain tables; for the non-canonical output table we
-- adopt append-only with a content immutability trigger as a COMPLIANCE choice.
-- A generated and served report (potentially cited in an audit) must not be
-- retroactively modified; every column of `reports` is content (there is no
-- lifecycle flag), so UPDATE and DELETE are blocked. Dedup is handled by the
-- deterministic report id (tenant + report_type + period), never by UPDATE.
--
-- Apply on an existing database (installations with a fresh volume apply the
-- same DDL automatically from 01-schema.sql):
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint11-report-content-trigger.sql

DROP TRIGGER IF EXISTS report_content_immutable_trigger ON reports;

CREATE OR REPLACE FUNCTION prevent_report_content_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Report content is immutable (append-only output artifact, ADR-0002). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER report_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON reports
    FOR EACH ROW EXECUTE FUNCTION prevent_report_content_update();