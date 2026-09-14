# C4 — Observability Contract: Outcome Status Transitions

**Phase**: C4 — Observability Enhancement
**Status**: PROPOSED
**Date**: 2026-09-14
**Baseline**: `19f6512e55ec4cd91ddc08213ef92617597fb6bd`

## Purpose

Formalize structured logging and metrics for `outcome_status` lifecycle transitions (`pending → observed`) across all three submission routes established by H7/H8.

## Event

```text
outcome_status_transition
```

## Level

```text
INFO
```

## Required Fields

| Field | Type | Value |
|---|---|---|
| `event` | string | `"outcome_status_transition"` |
| `tenant_id` | string (UUID) | Tenant scope |
| `decision_id` | string (UUID) | Decision identifier |
| `previous_status` | string | `"pending"` |
| `new_status` | string | `"observed"` |
| `actual_outcomes_count` | int | `len(actual_outcomes)` |
| `route` | string | One of the three route names below |
| `cognitive_capability` | string | `"outcome_lifecycle"` |
| `timestamp` | ISO 8601 | `datetime.now(UTC).isoformat()` |

## Route Names

Exactly one of:

| Route Constant | File | Method |
|---|---|---|
| `DecisionStore.update_outcomes` | `libs/action/decision.py` | `update_outcomes()` |
| `DecisionReadStore.submit_outcomes` | `apps/gateway/api-gateway/src/decisions.py` | `submit_outcomes()` |
| `LearningExecutionStore.submit_outcomes_with_revision` | `libs/learning/learning_execution_store.py` | `submit_outcomes_with_revision()` |

## Prohibited Data

The following must NEVER appear in log output:

- `actual_outcomes` content (business-sensitive)
- `commitment` (decision content)
- `expected_outcomes` (prediction content)
- tokens
- passwords
- API keys
- secrets
- credentials

`actual_outcomes_count` is derived as `len(actual_outcomes)` only. The actual list content is not stored or logged.

## Metrics

Exposed via existing `/metrics` endpoint (JSON). No new infrastructure.

| Metric | Type | Description |
|---|---|---|
| `outcome_transitions_total` | counter | Total successful `pending → observed` transitions |
| `outcome_transitions_by_route` | counter (by route) | Transitions per submission route |

Counters increment ONLY after a successful database transition. Never on received request, failed attempt, validation failure, missing decision, rollback, or exception.

## Implementation Pattern

```python
from libs.shared.structured_logging import get_logger, LogContext

logger = get_logger(__name__)

logger.info(
    "outcome_status_transition",
    context=LogContext(
        tenant_id=str(tenant_id),
        cognitive_capability="outcome_lifecycle",
    ),
    extra={
        "event": "outcome_status_transition",
        "decision_id": str(decision_id),
        "previous_status": "pending",
        "new_status": "observed",
        "actual_outcomes_count": len(actual_outcomes),
        "route": "<EXACT_ROUTE_NAME>",
    },
)
```

## Compatibility

- Uses existing `StructuredLogger` infrastructure (no modification)
- Uses existing `LogContext` fields
- Uses existing `/metrics` mechanism
- No new dependencies
- No new infrastructure
- No schema changes
- No ADR modifications
- H8 contract preserved
