-- Phase 7: Confidence Evidence Scope
-- Add evidence_ids column to track which evidence was used for calibration.
-- This ensures provenance: the confidence of a hypothesis can be reconstructed
-- exclusively from its scoped evidence.

ALTER TABLE confidence_scores
    ADD COLUMN IF NOT EXISTS evidence_ids UUID[] DEFAULT '{}';

-- Backfill existing rows with empty array (they predate evidence tracking).
UPDATE confidence_scores SET evidence_ids = '{}' WHERE evidence_ids IS NULL;

-- Add index for querying by evidence scope.
CREATE INDEX IF NOT EXISTS idx_confidence_evidence_ids
    ON confidence_scores USING GIN (evidence_ids);
