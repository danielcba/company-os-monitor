# DATABASE_INTEGRITY_FINAL.md

## Company OS Monitor — Database Integrity Findings (Final)

**Date**: 2026-08-22
**Status**: COMPLETED

---

## Summary

| Finding | Severity | Status |
|---------|----------|--------|
| Context activation not atomic | P1 | ✅ Fixed |
| Missing tenant_id in SQL queries | P1 | ✅ Fixed |
| Confidence evidence scope not tracked | P1 | ✅ Fixed |
| Multiple DB engines per process | P1 | ✅ Fixed |

---

## DB-001: Context Activation Not Atomic

**Component**: Context Store
**Original Pattern**:
```python
# Two separate commits
INSERT context
COMMIT
DEACTIVATE old context
COMMIT
```
**Problem**: Could leave 0 or 2 active contexts if second commit fails.

**Fix**: Single transaction:
```python
async with session.begin():
    INSERT context
    DEACTIVATE old context
```
**Additional**: UNIQUE partial index migration
**File**: `infrastructure/db-migrations/phase5-context-activation-atomicity.sql`

**Tests**: Architecture invariant test

---

## DB-002: Missing Tenant_id in SQL Queries

**Component**: Multiple Stores
**Original Queries**:
1. `SELECT_LATEST_BY_TARGET` (confidence.py) — no tenant_id filter
2. `SET_CONTEXT_ACTIVE` (context.py) — no tenant_id filter
3. `update_outcomes()` (decision.py) — no tenant_id filter

**Fix**:
1. Added `AND tenant_id = :tenant_id` to `SELECT_LATEST_BY_TARGET`
2. Added `AND tenant_id = :tenant_id` to `SET_CONTEXT_ACTIVE`
3. Added `AND tenant_id = :tenant_id` to `update_outcomes()` dynamic SQL

**Tests**: `test_tenant_scoping.py` (6 tests)

---

## DB-003: Confidence Evidence Scope Not Tracked

**Component**: Confidence Store
**Original**: `confidence_scores` table had no `evidence_ids` column
**Problem**: Could not track which evidence was used for calibration
**Fix**: Added `evidence_ids UUID[]` column
**File**: `infrastructure/db-migrations/phase7-confidence-evidence-scope.sql`

**Tests**: `test_confidence_evidence_scope.py` (9 tests)

---

## DB-004: Multiple DB Engines Per Process

**Component**: Multiple Stores
**Original**: Each store created its own `create_async_engine()`
**Problem**: Fragmented connection pools; could exhaust database connections
**Fix**: Enhanced `libs/shared/db.py` with centralized engine factory
**Configuration**:
- `pool_size`: Default 20
- `max_overflow`: Default 40
- `pool_timeout`: Default 30s
- `pool_recycle`: Default 3600s
- `statement_timeout`: Configurable

---

## Schema Changes

### Phase 5: Context Activation Atomicity
```sql
CREATE UNIQUE INDEX IF NOT EXISTS idx_contexts_unique_active
    ON contexts (tenant_id, purpose)
    WHERE is_active = true;
```

### Phase 7: Confidence Evidence Scope
```sql
ALTER TABLE confidence_scores
    ADD COLUMN IF NOT EXISTS evidence_ids UUID[] DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_confidence_evidence_ids
    ON confidence_scores USING GIN (evidence_ids);
```

---

## Immutability Triggers

All canonical cognitive tables have immutability triggers:
- `observations_immutable_trigger`
- `evidence_immutable_trigger`
- `context_immutable_trigger`
- `pattern_immutable_trigger`
- `anomaly_immutable_trigger`
- `hypothesis_immutable_trigger`
- `confidence_content_immutable_trigger`
- `recommendation_immutable_trigger`
- `decision_content_immutable_trigger`
- `audit_log_immutable_trigger`
- `report_immutable_trigger`
