-- Sprint 7 - Hypothesis content immutability trigger (migration for existing DBs).
--
-- The `hypotheses` table already exists from the base schema (docs/01). This
-- migration adds the trigger that enforces P1 at the data layer:
--   - content columns (anomaly_ids, pattern_ids, description,
--     predicted_consequences, falsification_criterion, coherence_score,
--     generated_at) are immutable once generated;
--   - `status` is a LIFECYCLE field (candidate -> confirmed/falsified is
--     decided by future evidence + Confidence, Sprint 8), so it is the ONLY
--     column allowed to change;
--   - DELETE is blocked: a hypothesis is a persistent audit trail and is
--     never removed.
--
-- Unlike `patterns`/`contexts`, a hypothesis has no `is_active` lifecycle
-- flag; like `evidence`, once written the row is only ever re-generated as a
-- NEW deterministic row (idempotent dedup by primary key), never an UPDATE of
-- an existing one - this trigger makes that non-negotiable while still
-- permitting the candidate -> confirmed/falsified status transition.
--
-- Apply on an existing database (installations with a fresh volume apply the
-- same DDL automatically from 01-schema.sql):
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint7-hypothesis-content-trigger.sql

DROP TRIGGER IF EXISTS hypothesis_content_immutable_trigger ON hypotheses;

CREATE OR REPLACE FUNCTION prevent_hypothesis_content_update()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
        -- Status is the only lifecycle flippable column.
        IF NEW.id <> OLD.id
           OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
           OR NEW.anomaly_ids IS DISTINCT FROM OLD.anomaly_ids
           OR NEW.pattern_ids IS DISTINCT FROM OLD.pattern_ids
           OR NEW.description IS DISTINCT FROM OLD.description
           OR NEW.predicted_consequences IS DISTINCT FROM OLD.predicted_consequences
           OR NEW.falsification_criterion IS DISTINCT FROM OLD.falsification_criterion
           OR NEW.coherence_score IS DISTINCT FROM OLD.coherence_score
           OR NEW.generated_at IS DISTINCT FROM OLD.generated_at THEN
            RAISE EXCEPTION 'Hypotheses content is immutable (P1). Only status may change.';
        END IF;
        RETURN NEW;
    END IF;
    -- DELETE blocked (persistent audit trail).
    RAISE EXCEPTION 'Hypotheses are immutable (P1). No DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER hypothesis_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON hypotheses
    FOR EACH ROW EXECUTE FUNCTION prevent_hypothesis_content_update();