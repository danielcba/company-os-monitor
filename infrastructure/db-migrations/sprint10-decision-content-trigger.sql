-- Sprint 10 - Decision content immutability trigger (migration for existing DBs).
--
-- The `decisions` table already exists from the base schema (docs/01, docs/04).
-- This migration adds the trigger that enforces P1 at the data layer for the
-- Action layer's Commit capability:
--   - all CONTENT columns (id, tenant_id, recommendation_id, confidence_id,
--     authority_id, commitment, expected_outcomes, risk_tolerance,
--     committed_at) are immutable once written;
--   - the LIFECYCLE fields are the only flippable ones: `status`
--     (committed -> executing/completed/rolled_back), `executed_at` and
--     `actual_outcomes` (populated ONLY by the Learning loop / execution
--     phases, future sprints); an UPDATE that touches ONLY lifecycle fields is
--     allowed while any content change is rejected;
--   - DELETE is blocked: a committed Decision is part of the persistent audit
--     trail (commitment + rationale + falsifiable expected outcomes + authority
--     + calibrated confidence) and is never removed.
--
-- Apply on an existing database (installations with a fresh volume apply the
-- same DDL automatically from 01-schema.sql):
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint10-decision-content-trigger.sql

DROP TRIGGER IF EXISTS decision_content_immutable_trigger ON decisions;

CREATE OR REPLACE FUNCTION prevent_decision_content_update()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.recommendation_id IS DISTINCT FROM OLD.recommendation_id
       OR NEW.confidence_id IS DISTINCT FROM OLD.confidence_id
       OR NEW.authority_id IS DISTINCT FROM OLD.authority_id
       OR NEW.commitment IS DISTINCT FROM OLD.commitment
       OR NEW.expected_outcomes IS DISTINCT FROM OLD.expected_outcomes
       OR NEW.risk_tolerance IS DISTINCT FROM OLD.risk_tolerance
       OR NEW.committed_at IS DISTINCT FROM OLD.committed_at THEN
        RAISE EXCEPTION 'Decision content is immutable (P1). Only status, executed_at and actual_outcomes (lifecycle) may change.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER decision_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON decisions
    FOR EACH ROW EXECUTE FUNCTION prevent_decision_content_update();