-- COS-Monitor Database Schema - Cognitive-First
-- Run on PostgreSQL 16

-- Enable extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================
-- TENANTS & SERVERS (Support tables)
-- ============================================

CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    slug VARCHAR(100) UNIQUE NOT NULL,
    plan VARCHAR(50) DEFAULT 'basic',
    settings JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE servers (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    hostname VARCHAR(255) NOT NULL,
    ip_address INET,
    os_type VARCHAR(50),  -- linux, windows, vmware
    os_version VARCHAR(100),
    agent_version VARCHAR(50),
    status VARCHAR(20) DEFAULT 'unknown',  -- online, offline, unknown
    last_seen TIMESTAMPTZ,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE(tenant_id, hostname)
);

CREATE INDEX idx_servers_tenant_status ON servers(tenant_id, status);
CREATE INDEX idx_servers_last_seen ON servers(last_seen);

-- ============================================
-- PERCEPTION LAYER TABLES
-- ============================================

-- Observations: Immutable captures from reality (P1)
CREATE TABLE observations (
    id UUID NOT NULL DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    source_id UUID NOT NULL,
    source_type VARCHAR(50) NOT NULL,  -- linux_agent, windows_agent, vmware_agent, etc.
    fact_type VARCHAR(100) NOT NULL,   -- cpu_utilization, memory_usage, disk_usage, event_log
    fact_value JSONB NOT NULL,         -- raw value without interpretation
    unit VARCHAR(20) NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL,
    quality_class VARCHAR(2) NOT NULL CHECK (quality_class IN ('Q1','Q2','Q3','Q4')),
    raw_payload JSONB NOT NULL,
    
    PRIMARY KEY (id, captured_at)
);

CREATE INDEX idx_observations_tenant_source ON observations(tenant_id, source_id, captured_at DESC);
CREATE INDEX idx_observations_tenant_fact ON observations(tenant_id, fact_type, captured_at DESC);

-- Trigger to enforce immutability
CREATE OR REPLACE FUNCTION prevent_observation_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Observations are immutable (P1). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER observations_immutable_trigger
    BEFORE UPDATE OR DELETE ON observations
    FOR EACH ROW EXECUTE FUNCTION prevent_observation_update();

-- Evidence: Organized observations (Perception - Organize)
CREATE TABLE evidence (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    observation_ids UUID[] NOT NULL,
    organization_type VARCHAR(50) NOT NULL,  -- resource_exhaustion_evidence, service_degradation_evidence, auth_anomaly_evidence, backup_failure_evidence, vmware_capacity_evidence, network_anomaly_evidence
    description TEXT NOT NULL,               -- NO interpretation, prediction, or recommendation
    quality_class VARCHAR(2) NOT NULL CHECK (quality_class IN ('Q1','Q2','Q3','Q4')),
    weight NUMERIC(3,2) NOT NULL CHECK (weight >= 0 AND weight <= 1),
    organized_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_evidence_tenant_type ON evidence(tenant_id, organization_type, organized_at DESC);

-- Evidence is immutable (P1, append-only): it organizes observations it never modifies.
CREATE OR REPLACE FUNCTION prevent_evidence_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Evidence is immutable (P1). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER evidence_immutable_trigger
    BEFORE UPDATE OR DELETE ON evidence
    FOR EACH ROW EXECUTE FUNCTION prevent_evidence_update();

-- Contexts: Active interpretations (Perception - Explain)
CREATE TABLE contexts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    evidence_ids UUID[] NOT NULL,
    mental_model_id VARCHAR(100) NOT NULL,
    purpose VARCHAR(200) NOT NULL,
    coherence_score NUMERIC(3,2) NOT NULL CHECK (coherence_score >= 0 AND coherence_score <= 1),
    competing_models JSONB DEFAULT '[]',
    activated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_contexts_tenant_active ON contexts(tenant_id, is_active, activated_at DESC);

-- Context content is immutable (P1): evidence_ids, mental_model_id, purpose,
-- coherence_score and competing_models are assigned at activation and never
-- retrofitted. is_active is a lifecycle flag (P2 allows a purpose to be
-- re-activated with new evidence), so only is_active may change afterwards.
-- The row itself is never deleted (persistent audit trail).
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

-- ============================================
-- REASONING LAYER TABLES
-- ============================================

-- Patterns: Recurring structures (Reasoning - Generalize)
CREATE TABLE patterns (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    context_id UUID NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    pattern_type VARCHAR(100) NOT NULL,  -- temporal, correlation, sequential, threshold
    description TEXT NOT NULL,
    strength_measure NUMERIC(5,4) NOT NULL,  -- support/frequency/p-value
    frequency VARCHAR(50),               -- weekly, daily, hourly, event-driven
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_patterns_tenant_type ON patterns(tenant_id, pattern_type, detected_at DESC);

-- Pattern content is immutable (P1): context_id, pattern_type, description,
-- strength_measure, frequency and detected_at are assigned at detection and
-- never retrofitted. is_active is a lifecycle flag (a newer detection may
-- supersede an older candidate), so only is_active may change afterwards.
-- The row itself is never deleted (persistent audit trail). A pattern is a
-- working regularity (P4): revising it means a NEW library version that
-- produces a new deterministic id, never an UPDATE of an existing row.
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

-- Anomalies: Deviations from patterns (Reasoning - Detect Deviation)
CREATE TABLE anomalies (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    context_id UUID NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    pattern_id UUID NOT NULL REFERENCES patterns(id) ON DELETE SET NULL,
    deviation_score NUMERIC(8,4) NOT NULL,
    tolerance_threshold NUMERIC(8,4) NOT NULL,
    anomaly_class VARCHAR(50) NOT NULL,  -- point, contextual, collective
    detected_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_anomalies_tenant_pattern ON anomalies(tenant_id, pattern_id, detected_at DESC);

-- Anomaly content is immutable (P1): context_id, pattern_id, deviation_score,
-- tolerance_threshold, anomaly_class and detected_at are assigned at detection
-- and never retrofitted. Unlike patterns/contexts, anomalies has NO lifecycle
-- flag (is_active): a detected anomaly is a one-shot signal, so both UPDATE
-- and DELETE are blocked (same policy as evidence). A re-detection produces a
-- NEW deterministic row (idempotent dedup), never an UPDATE of an existing one.
CREATE OR REPLACE FUNCTION prevent_anomaly_content_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Anomalies are immutable (P1). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER anomaly_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON anomalies
    FOR EACH ROW EXECUTE FUNCTION prevent_anomaly_content_update();

-- Hypotheses: Testable explanations (Reasoning - Predict)
CREATE TABLE hypotheses (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    anomaly_ids UUID[] NOT NULL,
    pattern_ids UUID[] DEFAULT '{}',
    description TEXT NOT NULL,
    predicted_consequences JSONB NOT NULL,  -- falsifiable predictions
    falsification_criterion TEXT NOT NULL,
    coherence_score NUMERIC(3,2) NOT NULL CHECK (coherence_score >= 0 AND coherence_score <= 1),
    status VARCHAR(20) DEFAULT 'candidate',  -- candidate, confirmed, falsified
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_hypotheses_tenant_status ON hypotheses(tenant_id, status, generated_at DESC);

-- Hypothesis content is immutable (P1): anomaly_ids, pattern_ids, description,
-- predicted_consequences, falsification_criterion, coherence_score and
-- generated_at are assigned at generation and never retrofitted. Unlike
-- patterns/contexts, hypotheses has NO lifecycle flag (is_active); like
-- evidence, once written the row is never deleted (persistent audit trail).
-- `status` is a LIFECYCLE field (candidate -> confirmed/falsified is decided
-- by future evidence + Confidence, Sprint 8), so it is the ONLY column allowed
-- to change. A re-generation produces a NEW deterministic row (idempotent
-- dedup), never an UPDATE of an existing one.
CREATE OR REPLACE FUNCTION prevent_hypothesis_content_update()
RETURNS TRIGGER AS $$
BEGIN
    IF (TG_OP = 'UPDATE') THEN
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
    RAISE EXCEPTION 'Hypotheses are immutable (P1). No DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER hypothesis_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON hypotheses
    FOR EACH ROW EXECUTE FUNCTION prevent_hypothesis_content_update();

-- Insights: Restructured understanding (Reasoning - Restructure)
CREATE TABLE insights (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    context_id UUID NOT NULL REFERENCES contexts(id) ON DELETE CASCADE,
    hypothesis_ids UUID[] NOT NULL,
    description TEXT NOT NULL,
    prior_understanding TEXT,
    mental_model_update JSONB,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_insights_tenant_context ON insights(tenant_id, context_id, generated_at DESC);

-- ============================================
-- LEARNING LAYER TABLES
-- ============================================

-- Confidence Scores: Calibrated judgments (Learning - Calibrate)
CREATE TABLE confidence_scores (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    target_type VARCHAR(50) NOT NULL,  -- hypothesis, recommendation, decision
    target_id UUID NOT NULL,
    evidential_support NUMERIC(5,4) NOT NULL,      -- S(H|E)
    explanatory_coherence NUMERIC(5,4) NOT NULL,   -- C(H)
    historical_calibration NUMERIC(5,4) NOT NULL,  -- 1 - ECE
    confidence_score NUMERIC(5,4) NOT NULL,        -- C_final
    alpha NUMERIC(3,2) NOT NULL DEFAULT 0.50,
    calibration_justification TEXT NOT NULL,
    calibration_error_estimate NUMERIC(5,4) NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_confidence_target ON confidence_scores(target_type, target_id);

-- Confidence content is immutable (P1): tenant_id, target_type, target_id,
-- evidential_support, explanatory_coherence, historical_calibration,
-- confidence_score, alpha, calibration_justification, calibration_error_estimate
-- and computed_at are assigned at calibration and never retrofitted. A
-- confidence row has NO lifecycle flag: a re-calibration with different inputs
-- (e.g. new evidence) is a NEW deterministic row (content-addressed id),
-- never an UPDATE of an existing one, so both UPDATE and DELETE are blocked
-- (same policy as evidence). The row is part of the persistent audit trail.
CREATE OR REPLACE FUNCTION prevent_confidence_content_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Confidence scores are immutable (P1). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER confidence_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON confidence_scores
    FOR EACH ROW EXECUTE FUNCTION prevent_confidence_content_update();

-- ============================================
-- ACTION LAYER TABLES
-- ============================================

-- Recommendations: Proposed actions (Action - Propose)
CREATE TABLE recommendations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    hypothesis_id UUID NOT NULL REFERENCES hypotheses(id) ON DELETE SET NULL,
    insight_id UUID REFERENCES insights(id) ON DELETE SET NULL,
    confidence_id UUID NOT NULL REFERENCES confidence_scores(id),
    action_description TEXT NOT NULL,
    rationale TEXT NOT NULL,
    expected_consequences JSONB NOT NULL,
    alternatives_considered JSONB DEFAULT '[]',
    confidence_score NUMERIC(5,4) NOT NULL,
    status VARCHAR(20) DEFAULT 'proposed',  -- proposed, accepted, rejected, superseded
    proposed_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_recommendations_tenant_status ON recommendations(tenant_id, status, proposed_at DESC);

-- Recommendation content immutability (P1): content columns immutable once
-- written; `status` is the ONLY flippable column (proposed -> accepted/
-- rejected/superseded lifecycle decided by the Decision layer); DELETE blocked
-- (persistent audit trail).
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

-- Decisions: Committed actions (Action - Commit)
CREATE TABLE decisions (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    recommendation_id UUID NOT NULL REFERENCES recommendations(id),
    confidence_id UUID NOT NULL REFERENCES confidence_scores(id),
    authority_id UUID NOT NULL,  -- user_id (real user, Sprint 12+) or policy_id
    commitment TEXT NOT NULL,
    expected_outcomes JSONB NOT NULL,  -- falsifiable predictions
    risk_tolerance VARCHAR(20) DEFAULT 'low',  -- low, medium, high
    status VARCHAR(20) DEFAULT 'committed',    -- committed, executing, completed, rolled_back
    committed_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    executed_at TIMESTAMPTZ,
    actual_outcomes JSONB
);

CREATE INDEX idx_decisions_tenant_status ON decisions(tenant_id, status, committed_at DESC);

-- Decision content immutability (P1): CONTENT columns immutable once written;
-- `status`, `executed_at` and `actual_outcomes` are LIFECYCLE fields (the
-- Learning loop / execution phases transition committed -> executing/
-- completed/rolled_back and populate the observed outcomes); DELETE blocked
-- (persistent audit trail).
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

-- ============================================
-- MEMORY LAYER TABLES
-- ============================================

-- Audit Log: Episodic Memory (what happened, when, in order)
CREATE TABLE audit_log (
    id UUID NOT NULL DEFAULT uuid_generate_v4(),
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    user_id UUID,  -- null for automated decisions
    policy_id UUID,  -- for automated decisions
    cognitive_layer VARCHAR(20) NOT NULL,  -- perception, reasoning, confidence, action, memory
    cognitive_concept VARCHAR(30) NOT NULL,  -- observation, evidence, context, pattern, anomaly, hypothesis, insight, confidence, recommendation, decision
    action VARCHAR(50) NOT NULL,  -- captured, organized, activated, detected, generated, restructured, calibrated, proposed, committed, executed
    resource_type VARCHAR(50) NOT NULL,
    resource_id UUID NOT NULL,
    details JSONB,  -- {old_values, new_values, confidence_score, rationale, expected_outcomes}
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    PRIMARY KEY (id, timestamp)
);

CREATE INDEX idx_audit_tenant_time ON audit_log(tenant_id, timestamp DESC);
CREATE INDEX idx_audit_cognitive_trace ON audit_log(cognitive_layer, cognitive_concept, resource_id);

-- Trigger to enforce immutability
CREATE OR REPLACE FUNCTION prevent_audit_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Audit log is immutable (Episodic Memory). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_log_immutable_trigger
    BEFORE UPDATE OR DELETE ON audit_log
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_update();

-- Alert Rules (referenced from anomalies)
CREATE TABLE alert_rules (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    metric_type VARCHAR(50) NOT NULL,
    condition VARCHAR(10) NOT NULL CHECK (condition IN ('gt','lt','gte','lte','eq')),
    threshold NUMERIC NOT NULL,
    duration_minutes INTEGER DEFAULT 0,
    severity VARCHAR(20) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    notification_channels JSONB DEFAULT '{}',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_alert_rules_tenant ON alert_rules(tenant_id, enabled, metric_type);

-- Reports
CREATE TABLE reports (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    report_type VARCHAR(50) NOT NULL,  -- executive, technical, compliance, json
    title VARCHAR(500) NOT NULL,
    summary TEXT,
    content JSONB NOT NULL,
    ai_generated BOOLEAN DEFAULT FALSE,
    model_used VARCHAR(100),
    period_start DATE,
    period_end DATE,
    generated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    file_path VARCHAR(500)
);

CREATE INDEX idx_reports_tenant_type ON reports(tenant_id, report_type, period_end DESC);

-- Trigger to enforce immutability (Sprint 11). `reports` is the OUTPUT table of
-- the Report Generator (external non-canonical capability, ADR-0002): it only
-- FORMATS what the canonical flow already committed and never feeds the pipeline
-- back. P1's precedent applies to the canonical chain tables; for this
-- non-canonical output table we adopt append-only with a content immutability
-- trigger as a COMPLIANCE choice: a generated and served report (potentially
-- cited in an audit) must not be retroactively modified. Every column is
-- content (no lifecycle flag); UPDATE/DELETE are blocked. Dedup is handled by
-- the deterministic report id (tenant + report_type + period).
CREATE OR REPLACE FUNCTION prevent_report_content_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'Report content is immutable (append-only output artifact, ADR-0002). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER report_content_immutable_trigger
    BEFORE UPDATE OR DELETE ON reports
    FOR EACH ROW EXECUTE FUNCTION prevent_report_content_update();

-- ============================================
-- ACCESS LAYER (EXTERNAL, ADR-0002 - auth/RBAC)
-- ============================================
-- Identity + Decision Authority binding (Sprint 12). This is an EXTERNAL
-- non-canonical capability (ADR-0002): it authenticates/authorizes and
-- protects access to the canonical flow (R3 - Cognitive Boundary), it NEVER
-- produces cognitive judgments. The RBAC is modeled as Decision Authority
-- binding: each role (viewer/operator/admin/superadmin) determines which
-- authority may execute which action on the pipeline (docs/04). ``users`` is
-- NOT a cognitive artifact: rows are MUTABLE by design (password/role/name
-- changes, is_active deactivation) - no P1 immutability trigger here.
-- ``decisions.authority_id`` may reference a real ``users.id``.

CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,  -- globally unique: login resolves the tenant
    password_hash TEXT NOT NULL,         -- bcrypt, never plaintext
    name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'viewer'
        CHECK (role IN ('viewer','operator','admin','superadmin')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX idx_users_tenant_email ON users(tenant_id, email);
CREATE INDEX idx_users_tenant_role ON users(tenant_id, role);