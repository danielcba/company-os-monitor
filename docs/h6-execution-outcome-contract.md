# H6 — Execution & Outcome Contract

## Purpose

H6 formally closes the **Cognitive Gate** by establishing the Execution domain concept: an explicit, auditable, manually/externally-recorded bridge between Decision and Outcome.

**Cognitive Gate: YELLOW → GREEN**

## Architectural Model

```
Recommendation
      ↓
Decision
      ↓
Execution          ← H6 introduces this concept
      ↓
Outcome
      ↓
Memory / Learning
```

## Key Concepts

### Decision

A commitment to a course of action, produced by the cognitive pipeline. A Decision can exist without execution.

- **Model**: `libs/action/decision.py` — `Decision`
- **Table**: `decisions` (lifecycle fields: `status`, `executed_at`, `actual_outcomes`)

### Execution (H6 — NEW)

An explicit, auditable record that a Decision was executed (manually or externally). Does NOT imply that the system executed anything automatically.

- **Model**: `libs/action/execution_record.py` — `ExecutionRecord` (H6)
- **Table**: `execution_records` (append-only, P1) (H6)
- **Endpoint**: `POST /api/v1/tenants/{tenant_id}/decisions/{decision_id}/execution` (H6)

### Outcome (H3 — pre-existing)

The observed result of an Execution. Stored as append-only `OutcomeRevision` records. This concept was implemented in H3 (Learning Hardening), NOT H6.

- **Model**: `libs/learning/outcome_revision.py` — `OutcomeRevision` (H3)
- **Table**: `outcome_revisions` (append-only, P6) (H3)
- **Endpoint**: `POST /api/v1/tenants/{tenant_id}/decisions/{decision_id}/outcomes` (pre-H3)

### Learning Loop (H3 — pre-existing)

The orchestrator that chains Outcome → Learning Execution → Memory. Implemented in H3, NOT H6.

- **Orchestrator**: `libs/learning/cognitive_gate.py` — `submit_decision_outcomes_and_learn()` (H3)
- **Store**: `libs/learning/learning_execution_store.py` — `LearningExecutionStore` (H3)
- **Loop**: `libs/memory/learning_loop.py` — `H3LearningLoopStore.run_for_decision()` (H3)

## Cardinality

```
Decision 1 ─── 0..N ExecutionRecord
ExecutionRecord 1 ─── 0..1 OutcomeRevision
```

## Execution Semantics

**Manual / External-Recording First**: The system records that execution occurred, but does NOT perform the execution. A human operator or external system performs the action, then records the result.

### Execution Statuses

| Status | Meaning |
|--------|---------|
| `executed` | Execution completed successfully |
| `failed` | Execution attempted but failed |
| `cancelled` | Execution was cancelled before completion |
| `unknown` | Execution result is unknown |

### What This Is NOT

- NOT automated execution
- NOT a webhook/external system call
- NOT an internal executor
- NOT a side-effect-producing mechanism

## Files Changed (H6)

| File | Change | Scope |
|------|--------|-------|
| `libs/action/execution_record.py` | NEW — ExecutionRecord model + store | H6 |
| `infrastructure/db-migrations/h6-execution-outcome-contract.sql` | NEW — migration | H6 |
| `infrastructure/docker/init-sql/01-schema.sql` | UPDATED — execution_records table | H6 |
| `apps/gateway/api-gateway/src/decisions.py` | UPDATED — record_execution method | H6 |
| `apps/gateway/api-gateway/src/service.py` | UPDATED — record_decision_execution method | H6 |
| `apps/gateway/api-gateway/src/health.py` | UPDATED — route + handler | H6 |
| `tests/architecture/test_h6_execution_outcome_contract.py` | NEW — 20 architecture invariant tests | H6 |

## Pre-existing Components (H3 — NOT changed by H6)

| File | Component | Scope |
|------|-----------|-------|
| `libs/learning/outcome_revision.py` | OutcomeRevision model | H3 |
| `libs/learning/learning_execution_store.py` | LearningExecutionStore (advisory lock + transaction) | H3 |
| `libs/learning/learning_execution.py` | LearningExecution model + state machine | H3 |
| `libs/learning/cognitive_gate.py` | Cognitive Gate orchestrator | H3 |
| `libs/memory/learning_loop.py` | H3LearningLoopStore (durable execution) | H3 |
| `infrastructure/docker/init-sql/01-schema.sql` | outcome_revisions, learning_executions tables | H3 |
| `apps/gateway/api-gateway/src/decisions.py` | submit_outcomes method | pre-H3 |
| `apps/gateway/api-gateway/src/health.py` | decision_outcomes_handler | pre-H3 |

## API Endpoint

```
POST /api/v1/tenants/{tenant_id}/decisions/{decision_id}/execution
```

### Request Body

```json
{
  "execution_status": "executed",
  "executed_at": "2026-09-12T10:00:00Z",
  "executed_by": "user-uuid",
  "notes": "Human operator performed action externally",
  "metadata": {}
}
```

### Response

```json
{
  "execution_record": {
    "id": "uuid",
    "tenant_id": "uuid",
    "decision_id": "uuid",
    "execution_status": "executed",
    "executed_at": "2026-09-12T10:00:00Z",
    "executed_by": "uuid",
    "notes": "Human operator performed action externally",
    "metadata": {},
    "created_at": "2026-09-12T10:00:00Z"
  },
  "status": "execution_recorded"
}
```

## Out of Scope (H6)

- Frontend Token Security
- Automated Execution
- External Side Effects
- Broker/API Transactions
- Framework Changes
- Memory Redesign
- Learning Loop Redesign
- ADR-0003 (independent, non-blocking)
