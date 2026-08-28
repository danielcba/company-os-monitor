-- Sprint 14 - Hypothesis Evaluation table + immutability trigger (Phase 3A).
--
-- The `hypothesis_evaluations` table stores the append-only record of
-- hypothesis evaluations against new evidence. This enables the learning loop:
-- candidate hypotheses can be confirmed, falsified, or kept as candidate when
-- evidence is insufficient.
--
-- P1 enforcement: content columns are immutable once written; the row is
-- never deleted (persistent audit trail). The deterministic `evaluation_id`
-- ensures idempotent dedup: re-evaluating the same hypothesis with the same
-- evidence and result produces the same id.
--
-- Apply on an existing database:
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint14-hypothesis-evaluation.sql

-- ============================================
-- HYPOTHESIS EVALUATIONS TABLE
-- ============================================

CREATE TABLE hypothesis_evaluations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE CASCADE,
    evidence_ids UUID[] NOT NULL DEFAULT '{}',
    observed_outcomes JSONB NOT NULL DEFAULT '[]',
    support_count INTEGER NOT NULL DEFAULT 0 CHECK (support_count >= 0),
    contradiction_count INTEGER NOT NULL DEFAULT 0 CHECK (contradiction_count >= 0),
    confidence_id UUID REFERENCES confidence_scores(id) ON DELETE SET NULL,
    result VARCHAR(20) NOT NULL CHECK (result IN ('confirmed', 'falsified', 'insufficient')),
    rationale TEXT NOT NULL,
    evaluated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evaluations_tenant_hypothesis ON hypothesis_evaluations(tenant_id, hypothesis_id, evaluated_at DESC);
CREATE INDEX idx_evaluations_tenant_result ON hypothesis_evaluations(tenant_id, result, evaluated_at DESC);

-- Evaluation content is immutable (P1): tenant_id, hypothesis_id, evidence_ids,
-- observed_outcomes, support_count, contradiction_count, confidence_id, result,
-- rationale and evaluated_at are assigned at evaluation and never retrofitted.
-- There is NO lifecycle flag: an evaluation is a one-shot assessment, so both
-- UPDATE and DELETE are blocked (same policy as evidence). A re-evaluation with
-- new evidence produces a NEW deterministic row (idempotent dedup), never an
-- UPDATE of an existing one.

CREATE OR REPLACE FUNCTION prevent_evaluation_content_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Hypothesis evaluations are immutable (P1). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER evaluation_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON hypothesis_evaluations
    FOR EACH ROW EXECUTE FUNCTION prevent_evaluation_content_update();