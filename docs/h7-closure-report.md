# H7 — Closure Report

**Phase**: H7 — Outcome Status Semantics
**Status**: CLOSED
**Date**: 2026-09-13
**Baseline**: `631216810502e8c9ccc378d4f1268466edcf68dc`

## Objective

Formalize `outcome_status` as a lifecycle field on Decision to define what happens
when an Outcome is absent or indefinitely deferred. Addresses the framework's
declared gap: "The behavior when an Outcome is absent or indefinitely deferred is
not yet formally defined."

## What Was Resolved

1. **`outcome_status` lifecycle field** on Decision: `pending` (default) → `observed`
2. **Guard-at-source filtering**: Learning Loop and Consolidation skip pending Decisions
3. **Schema migration**: `h7-outcome-status-semantics.sql` with CHECK constraint
4. **ADR-0008**: ACCEPTED (2026-09-13), 18 acceptance criteria
5. **23 architecture invariant tests**: `test_h7_outcome_status.py`
6. **H8 Consistency Remediation**: All outcome submission routes now transition `pending → observed`

## Implementation

| File | Change |
|------|--------|
| `libs/action/decision.py` | `outcome_status` field, constants, `update_outcomes()` transition |
| `libs/learning/learning_execution_store.py` | `submit_outcomes_with_revision()` transition |
| `libs/learning/learning_loop.py` | Skip pending in `compute_outcome_signal()` |
| `libs/memory/consolidation.py` | Skip pending in `build_consolidation()` |
| `apps/gateway/api-gateway/src/decisions.py` | `submit_outcomes()` transition, SELECT queries, payload |
| `infrastructure/db-migrations/h7-outcome-status-semantics.sql` | Schema migration |
| `infrastructure/docker/init-sql/01-schema.sql` | `outcome_status` column + index |
| `tests/architecture/test_h7_outcome_status.py` | 30+ invariant tests |

## H6 Compatibility

- `ExecutionRecord` model unchanged
- No `outcome_status` on ExecutionRecord
- ExecutionRecord append-only semantics preserved

## P7 Compatibility

- PENDING is a temporal state before outcome production
- PENDING does not contradict P7 ("Every decision produces an observable outcome")
- PENDING → OBSERVED fulfills P7

## ADR-0008 Compliance

All 18 acceptance criteria (AC-01 through AC-18) satisfied:
- State model: pending / observed
- Semantic rules: PENDING ≠ SUCCESS/FAILURE/UNKNOWN
- No timeout, retry, archival, notifications
- No scope expansion
- Deterministic identity preserved
- Tenant isolation preserved
- Append-only semantics preserved

## Residual Risks

- None identified. All gaps addressed by H8 Consistency Remediation.
