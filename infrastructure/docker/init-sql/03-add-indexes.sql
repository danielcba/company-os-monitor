-- Migration: Add performance indexes for tenant-scoped queries
-- Run after 01-schema.sql and 02-seed.sql

-- Anomalies: tenant_id + detected_at for paginated list queries
CREATE INDEX IF NOT EXISTS idx_anomalies_tenant_detected
ON anomalies (tenant_id, detected_at DESC);

-- Confidence scores: tenant_id + computed_at for paginated list queries
CREATE INDEX IF NOT EXISTS idx_confidence_tenant_computed
ON confidence_scores (tenant_id, computed_at DESC);

-- Hypotheses: tenant_id + generated_at for paginated list queries
CREATE INDEX IF NOT EXISTS idx_hypotheses_tenant_generated
ON hypotheses (tenant_id, generated_at DESC);

-- Recommendations: tenant_id + proposed_at for paginated list queries
CREATE INDEX IF NOT EXISTS idx_recommendations_tenant_proposed
ON recommendations (tenant_id, proposed_at DESC);

-- Insights: tenant_id + generated_at for paginated list queries
CREATE INDEX IF NOT EXISTS idx_insights_tenant_generated
ON insights (tenant_id, generated_at DESC);
