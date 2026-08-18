-- Sprint 5 - Pattern content immutability trigger (migration for existing DBs).
--
-- The `patterns` table already exists from the base schema (docs/01). This
-- migration adds the content trigger that enforces P1 without breaking the
-- lifecycle semantics:
--   - content columns (context_id, pattern_type, description,
--     strength_measure, frequency, detected_at) are immutable once detected;
--   - is_active is a lifecycle flag (a newer detection may supersede an older
--     candidate) and is the only column allowed to change;
--   - rows are never deleted (persistent audit trail).
--
-- A pattern is a working regularity (P4): revising it means publishing a NEW
-- library version that produces a new deterministic id, never an UPDATE of an
-- existing row - this trigger makes that non-negotiable at the data layer.
--
-- Apply on an existing database (installations with a fresh volume apply the
-- same DDL automatically from 01-schema.sql):
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint5-pattern-content-trigger.sql

DROP TRIGGER IF EXISTS pattern_content_immutable_trigger ON patterns;

CREATE OR REPLACE FUNCTION prevent_pattern_content_update()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Pattern rows are never deleted (audit trail).';
    ELSIF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.context_id IS DISTINCT FROM OLD.context_id
       OR NEW.pattern_type IS DISTINCT FROM OLD.pattern_type
       OR NEW.description IS DISTINCT FROM OLD.description
       OR NEW.strength_measure IS DISTINCT FROM OLD.strength_measure
       OR NEW.frequency IS DISTINCT FROM OLD.frequency
       OR NEW.detected_at IS DISTINCT FROM OLD.detected_at THEN
        RAISE EXCEPTION 'Pattern content is immutable (P1). Only is_active may change.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER pattern_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON patterns
    FOR EACH ROW EXECUTE FUNCTION prevent_pattern_content_update();
