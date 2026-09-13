-- H7: Outcome Status Semantics
-- Adds outcome_status lifecycle field to decisions table.
--
-- PENDING = outcome expected but not received
-- OBSERVED = outcome submitted and processed
--
-- Backward compatibility: existing Decisions with actual_outcomes = NULL
-- get outcome_status = 'pending'; existing Decisions with actual_outcomes
-- != NULL get outcome_status = 'observed'.
--
-- P1: lifecycle field only (content columns immutable)
-- P7: PENDING is temporal state before outcome production
-- H6: ExecutionRecord unchanged

-- Add outcome_status column with default value 'pending'
ALTER TABLE decisions
    ADD COLUMN IF NOT EXISTS outcome_status VARCHAR(20) NOT NULL DEFAULT 'pending'
    CHECK (outcome_status IN ('pending', 'observed'));

-- Backward compatibility: set outcome_status = 'observed' for Decisions
-- that already have actual_outcomes
UPDATE decisions
SET outcome_status = 'observed'
WHERE actual_outcomes IS NOT NULL AND outcome_status = 'pending';

-- Index for filtering pending Decisions (Learning Loop, Cognitive Gate)
CREATE INDEX IF NOT EXISTS idx_decisions_outcome_status
    ON decisions (tenant_id, outcome_status);
