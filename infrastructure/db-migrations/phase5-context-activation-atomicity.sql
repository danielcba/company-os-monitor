-- Phase 5: Context Activation Atomicity
-- Add UNIQUE partial index to guarantee at most one active context per tenant+purpose.
-- This is a safety net beyond the application-level transaction.

-- First, clean up any existing duplicates (keep the most recent).
DELETE FROM contexts
WHERE id NOT IN (
    SELECT DISTINCT ON (tenant_id, purpose) id
    FROM contexts
    WHERE is_active = true
    ORDER BY tenant_id, purpose, activated_at DESC
)
AND is_active = true;

-- Create the unique partial index.
CREATE UNIQUE INDEX IF NOT EXISTS idx_contexts_unique_active
    ON contexts (tenant_id, purpose)
    WHERE is_active = true;
