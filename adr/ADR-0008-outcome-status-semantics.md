# Architecture Decision Record 0008

Title: Outcome Status Semantics — Formalizing Missing Outcome Handling

Status: ACCEPTED
Approved: 2026-09-13
Approved-by: Human Review

Date: 2026-09-13

---

## Context

The Learning Loop (P7) assumes Decision → Outcome is always available. The framework formally declares: "The behavior when an Outcome is absent or indefinitely deferred is not yet formally defined." (cognitive-architecture.md:205-208).

The system produces consistent but undeclared behavior when `actual_outcomes` is None or empty:
- `has_actuals = False`
- `calibration_feedback = 0.0`
- `brier = None`
- `ece = None`

This behavior is CONSISTENT but NOT DECLARED as an intentional architectural decision.

## Problem

The architectural gap is UNDECLARED SEMANTICS: the system has undefined semantics for missing outcomes.

## Decision

Formalize `outcome_status` as a lifecycle field on Decision with two states:

### State Model

| State | Definition | Required |
|-------|------------|----------|
| **pending** | Outcome expected but not received | REQUIRED |
| **observed** | Outcome submitted and processed | REQUIRED |
| unknown | Outcome cannot be determined | NOT REQUIRED (future) |
| failed | Outcome evaluation failed | NOT REQUIRED (existing "inconclusive" covers this) |

### State Transitions

| Source | Trigger | Destination | Invariant | Audit | Idempotency |
|--------|---------|-------------|-----------|-------|-------------|
| `NULL` (new Decision) | Decision committed with `expected_outcomes > 0` AND `actual_outcomes = None` | `pending` | Decision must have `expected_outcomes` | Logged | N/A |
| `pending` | `submit_outcomes_with_revision()` succeeds | `observed` | `actual_outcomes` must be non-None | Logged | Idempotent |
| `observed` | `submit_outcomes_with_revision()` with new outcomes | `observed` | Append-only on OutcomeRevision | New revision logged | Idempotent |

### Semantic Rules

| Rule | Definition | Classification |
|------|------------|----------------|
| PENDING = temporal state before outcome production | Decision committed, outcome expected but not received | PROPOSED SEMANTIC RULE |
| PENDING ≠ SUCCESS | PENDING never produces `corroborated > 0` | EXISTING BEHAVIOR |
| PENDING ≠ FAILURE | PENDING never produces `contradicted > 0` | EXISTING BEHAVIOR |
| PENDING ≠ UNKNOWN | PENDING is "expected but not received"; UNKNOWN is "cannot be determined" | PROPOSED SEMANTIC RULE |
| PENDING ≠ TIMEOUT | No timeout semantics | PROPOSED SEMANTIC RULE |
| PENDING ≠ RETRY | No retry semantics | PROPOSED SEMANTIC RULE |
| PENDING ≠ ARCHIVAL | No archival semantics | PROPOSED SEMANTIC RULE |
| PENDING ≠ permanent incompleteness | PENDING is non-terminal | PROPOSED SEMANTIC RULE |

## Consequences

### Positive
- Completes P7 semantics with formally defined states
- Enables correct behavior of Learning Loop, Consolidation, and Cognitive Gate when outcomes are missing
- Provides auditable trail of outcome lifecycle
- Backward compatible (existing Decisions → pending)

### Negative
- Adds a new lifecycle field to the Decision model
- Requires schema migration (new column)
- Increases complexity of Decision model

## Invariants

| Invariant | Status |
|-----------|--------|
| P7 | PRESERVED (temporal interpretation) |
| P1 | PRESERVED (no fabrication) |
| R7 | PRESERVED (architecture guides code) |
| H6 | PRESERVED (ExecutionRecord unchanged) |
| Cognitive Gate | PRESERVED (extended, not replaced) |
| Tenant isolation | PRESERVED |
| Append-only | PRESERVED (lifecycle field only) |
| Idempotency | PRESERVED |
| Auditability | PRESERVED (transitions logged) |
| Deterministic identity | PRESERVED |
| Failure semantics | PRESERVED |

## Scope Boundary

### IN SCOPE
1. Semantic definition (`pending`, `observed`)
2. Schema migration (new column `outcome_status`)
3. State transitions (`pending → observed`)
4. Consolidation filtering (exclude `pending`)
5. Learning Loop precondition (skip `pending`)
6. Cognitive Gate check (return `skipped` for `pending`)
7. Backward compatibility (existing Decisions → `pending`)
8. ADR (this document)

### OUT OF SCOPE
- Timeout policy
- Retry semantics
- Scheduling
- Archival
- Notifications
- Frontend
- API redesign
- Database redesign
- Changes to R7
- Changes to P1-P7
- Reinterpretation of old ADRs
- Broad Learning Loop redesign
- Unrelated security changes
- Outcome UNKNOWN state
- Outcome FAILED state
- Deferred outcome semantics

## Relationship with P7

**P7 Statement**: "Every decision produces an observable outcome."

**Analysis**: PENDING does NOT contradict P7. PENDING is the temporal state BEFORE outcome production. P7 describes the eventual outcome, not the timing. When outcome is submitted, status transitions to OBSERVED, fulfilling P7.

**Recommendation**: This ADR documents this interpretation. P7 does not need modification.

## Relationship with H6

**H6 Definition**: Decision → Execution → Outcome

**Analysis**: PENDING is a state PRE-Outcome that formalizes the gap between Decision commitment and Outcome observation. H6 is unchanged. H7 adds semantics to the gap.

**Conclusion**: No conflict. H6 remains intact.

## Relationship with ADR-0003

ADR-0003 (Accepted) defines the Memory & Learning Layer, formalizing the Monitor's Memory/Learning components as the Framework's Memory capability (P7). This ADR extends the Learning Layer semantics by formally defining the outcome lifecycle. The extension is backward compatible and does not modify ADR-0003.

---

## Acceptance Criteria

| ID | Statement | Verification Method | PASS Condition | FAIL Condition |
|----|-----------|---------------------|----------------|----------------|
| AC-01 | `outcome_status` is defined as a lifecycle field on Decision | Schema inspection | Column exists with values `pending`/`observed` | Column missing or wrong values |
| AC-02 | PENDING ≠ SUCCESS | Code review + test | PENDING state never produces `corroborated > 0` | PENDING state produces success signal |
| AC-03 | PENDING ≠ FAILURE | Code review + test | PENDING state never produces `contradicted > 0` | PENDING state produces failure signal |
| AC-04 | PENDING ≠ UNKNOWN | Code review | No `unknown` state exists in scope | Unknown state introduced |
| AC-05 | No implicit timeout policy | Code review | No timeout logic for `outcome_status` | Timeout logic found |
| AC-06 | No implicit retry policy | Code review | No retry logic for `outcome_status` | Retry logic found |
| AC-07 | Learning Loop behavior defined | Code review + test | Learning Loop skips `pending` Decisions | Learning Loop processes `pending` Decisions |
| AC-08 | Cognitive Gate behavior defined | Code review + test | Cognitive Gate returns `skipped` for `pending` | Cognitive Gate fails or returns wrong status |
| AC-09 | H6 compatibility preserved | Code review | ExecutionRecord model unchanged | ExecutionRecord modified |
| AC-10 | P7 compatibility explicitly addressed | ADR review | ADR documents P7 interpretation | No P7 documentation |
| AC-11 | Idempotency preserved | Test | Setting `pending` on `pending` is idempotent | Idempotency broken |
| AC-12 | Auditability preserved | Code review | `outcome_status` transitions logged | Transitions not logged |
| AC-13 | Deterministic identity preserved | Code review | Decision ID generation unchanged | ID generation modified |
| AC-14 | Tenant isolation preserved | Code review + test | `outcome_status` scoped to tenant | Tenant leak possible |
| AC-15 | Append-only semantics preserved | Code review | `outcome_status` is lifecycle field only | Content fields modified |
| AC-16 | Failure semantics preserved | Code review | Failed submission leaves status as `pending` | Status changes on failure |
| AC-17 | State transitions deterministic | Test | Same input produces same transition | Non-deterministic transitions |
| AC-18 | No unauthorized scope expansion | Scope review | Only IN SCOPE items implemented | Out of scope items modified |
