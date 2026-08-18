-- Sprint 9 - Recommendation content immutability trigger (migration for existing DBs).
--
-- The `recommendations` table already exists from the base schema (docs/01).
-- This migration adds the trigger that enforces P1 at the data layer for the
-- Action layer's Propose capability:
--   - all content columns (tenant_id, hypothesis_id, insight_id, confidence_id,
--     action_description, rationale, expected_consequences,
--     alternatives_considered, confidence_score, proposed_at) are immutable
--     once written;
--   - `status` is the ONLY flippable column: the lifecycle
--     proposed -> accepted/rejected/superseded is decided by the Decision layer
--     (Sprint 10), so an UPDATE that touches ONLY status is allowed while any
--     content change is rejected;
--   - DELETE is blocked: a proposed Recommendation is part of the persistent
--     audit trail (offer + rationale + expected consequences + alternatives +
--     calibrated confidence) and is never removed.
--
-- Apply on an existing database (installations with a fresh volume apply the
-- same DDL automatically from 01-schema.sql):
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint9-recommendation-content-trigger.sql

DROP TRIGGER IF EXISTS recommendation_content_immutable_trigger ON recommendations;

CREATE OR REPLACE FUNCTION prevent_recommendation_content_update()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.hypothesis_id IS DISTINCT FROM OLD.hypothesis_id
       OR NEW.insight_id IS DISTINCT FROM OLD.insight_id
       OR NEW.confidence_id IS DISTINCT FROM OLD.confidence_id
       OR NEW.action_description IS DISTINCT FROM OLD.action_description
       OR NEW.rationale IS DISTINCT FROM OLD.rationale
       OR NEW.expected_consequences IS DISTINCT FROM OLD.expected_consequences
       OR NEW.alternatives_considered IS DISTINCT FROM OLD.alternatives_considered
       OR NEW.confidence_score IS DISTINCT FROM OLD.confidence_score
       OR NEW.proposed_at IS DISTINCT FROM OLD.proposed_at THEN
        RAISE EXCEPTION 'Recommendation content is immutable (P1). Only status may change.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER recommendation_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON recommendations
    FOR EACH ROW EXECUTE FUNCTION prevent_recommendation_content_update();