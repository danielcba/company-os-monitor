-- Sprint 4 - Context content immutability trigger (migration for existing DBs).
--
-- The `contexts` table already exists from the base schema (docs/01). This
-- migration adds the content trigger that enforces P1 without breaking the
-- is_active lifecycle:
--   - content columns (evidence_ids, mental_model_id, purpose, coherence_score,
--     competing_models) are immutable once activated;
--   - is_active is a lifecycle flag (a purpose may be re-activated with new
--     evidence) and is the only column allowed to change;
--   - rows are never deleted (persistent audit trail).
--
-- Apply on an existing database (installations with a fresh volume apply the
-- same DDL automatically from 01-schema.sql):
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint4-context-content-trigger.sql

DROP TRIGGER IF EXISTS context_content_immutable_trigger ON contexts;

CREATE OR REPLACE FUNCTION protect_context_content()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'Context rows are never deleted (audit trail).';
    ELSIF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.evidence_ids IS DISTINCT FROM OLD.evidence_ids
       OR NEW.mental_model_id IS DISTINCT FROM OLD.mental_model_id
       OR NEW.purpose IS DISTINCT FROM OLD.purpose
       OR NEW.coherence_score IS DISTINCT FROM OLD.coherence_score
       OR NEW.competing_models IS DISTINCT FROM OLD.competing_models
       OR NEW.activated_at IS DISTINCT FROM OLD.activated_at THEN
        RAISE EXCEPTION 'Context content is immutable (P1). Only is_active may change.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER context_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON contexts
    FOR EACH ROW EXECUTE FUNCTION protect_context_content();
