# Phase 20 -- Migration Integrity

**Date:** 2026-08-24
**Scope:** Database migration safety verification
**Reference:** `tests/security/adversarial/test_11_migration_integrity.py`

---

## 1. Overview

Database migrations in this project must preserve:
1. Immutability triggers on all canonical tables
2. The UNIQUE partial index for one-active-context-per-purpose
3. The `evidence_scope` column on `confidence_scores`
4. No data loss or corruption
5. Idempotent re-runs

Phase 20 did not introduce new migrations. The migration integrity test validates that existing migrations maintain these invariants.

---

## 2. Migration Inventory

### Phase 5 -- Context Activation Atomicity

**File:** `infrastructure/db-migrations/phase5-context-activation-atomicity.sql`
**Purpose:** Adds UNIQUE partial index `idx_contexts_unique_active` to enforce one-active-context-per-purpose.

**Safety:**
- Idempotent: `CREATE INDEX IF NOT EXISTS`
- No data loss: Index creation on existing data
- Atomic: Single DDL statement

### Phase 7 -- Confidence Evidence Scope

**File:** `infrastructure/db-migrations/phase7-confidence-evidence-scope.sql`
**Purpose:** Adds `evidence_scope` column to `confidence_scores` for scope validation.

**Safety:**
- Idempotent: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS`
- No data loss: New column with NULL default
- Atomic: Single DDL statement

### Sprint Migrations (Content Triggers)

**Files:** `infrastructure/db-migrations/sprint4-*.sql` through `sprint13-*.sql`
**Purpose:** Immutability triggers on canonical tables (observation, evidence, context, pattern, hypothesis, anomaly, confidence, recommendation, decision, report, insight, users).

**Safety:**
- Idempotent: `CREATE OR REPLACE TRIGGER`
- No data loss: Triggers only prevent future writes
- Atomic: Each trigger is a single DDL statement

### Audit Migration

**File:** `infrastructure/db-migrations/audit-2026-08-18-schema-alignment.sql`
**Purpose:** Schema alignment audit. No destructive changes.

---

## 3. Test Results

**File:** `tests/security/adversarial/test_11_migration_integrity.py`
**Status:** 5/5 pass

| Test | Description | Status |
|------|-------------|--------|
| `test_immutability_triggers_present` | All canonical tables have immutability triggers | Pass |
| `test_unique_active_index_exists` | UNIQUE partial index for active contexts exists | Pass |
| `test_evidence_scope_column_exists` | `evidence_scope` column exists on confidence_scores | Pass |
| `test_migration_idempotent` | Migrations can be re-run without error | Pass |
| `test_no_data_loss` | Migrations do not delete existing rows | Pass |

---

## 4. Invariant Verification

### Immutability Triggers

Verified tables with immutability triggers:
- `observations` -- `sprint4-context-content-trigger.sql`
- `evidence` -- `sprint4-context-content-trigger.sql`
- `contexts` -- `sprint4-context-content-trigger.sql`
- `patterns` -- `sprint5-pattern-content-trigger.sql`
- `hypotheses` -- `sprint7-hypothesis-content-trigger.sql`
- `anomalies` -- `sprint6-anomaly-content-trigger.sql`
- `confidence_scores` -- `sprint8-confidence-content-trigger.sql`
- `recommendations` -- `sprint9-recommendation-content-trigger.sql`
- `decisions` -- `sprint10-decision-content-trigger.sql`
- `reports` -- `sprint11-report-content-trigger.sql`
- `insights` -- `sprint13-insight-content-trigger.sql`
- `users` -- `sprint12-users-tables.sql`

### UNIQUE Partial Index

`idx_contexts_unique_active` enforces at most one active context per (tenant_id, purpose). Implemented in Phase 5.

### Evidence Scope Column

`evidence_scope` column on `confidence_scores` stores the hypothesis-scoped evidence IDs. Implemented in Phase 7.

---

## 5. Safety Guarantees

1. **No destructive migrations:** All migrations are additive (new columns, indexes, triggers)
2. **Idempotent:** All migrations use `IF NOT EXISTS` or `CREATE OR REPLACE`
3. **Atomic:** Each migration is a single DDL statement
4. **Reversible:** Migrations can be rolled back by dropping indexes/triggers/columns
5. **Tested:** Adversarial tests validate invariants after migration

---

## 6. Conclusion

All database migrations are safe and maintain the invariants required by the Company OS Cognitive Architecture. The adversarial test suite validates immutability triggers, UNIQUE constraints, and evidence scope columns. No data loss or corruption risk identified.
