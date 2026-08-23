-- Sprint 8: Confidence indexes for query performance
-- Indexes for ConfidenceStore queries (tenant_id + computed_at, target_type + target_id, tenant_id)

-- Index for list_confidence(tenant_id) ORDER BY computed_at
CREATE INDEX IF NOT EXISTS idx_confidence_scores_tenant_computed
ON confidence_scores (tenant_id, computed_at);

-- Index for get_confidence(target_type, target_id) ORDER BY computed_at DESC
CREATE INDEX IF NOT EXISTS idx_confidence_scores_target_latest
ON confidence_scores (target_type, target_id, computed_at DESC);

-- Index for list_tenant_ids() - partial index on distinct tenant_id
-- Note: DISTINCT tenant_id benefits from the above composite index

-- Index for confidence_scores target_type filtering (used by metrics)
CREATE INDEX IF NOT EXISTS idx_confidence_scores_target_type
ON confidence_scores (target_type);

-- Verify indexes
-- \d confidence_scores