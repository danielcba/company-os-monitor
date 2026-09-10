# H3 Post-Implementation Compliance & Diff Audit Report

**Audit Date:** 2026-08-31  
**Branch:** `main`  
**Base:** `f54e8116` (131 tests) → H3 implementation (379 passed, 31 skipped)  
**Scope:** Read-only compliance audit of H3 Learning Hardening against approved architecture  
**Approved Architecture:** `.opencode/plans/h3-transaction-boundary-proof.md`

---

## 1. Executive Verdict

**CONDITIONAL PASS — 2 Critical Deviations Identified**

The H3 implementation delivers strong functional correctness: 379/379 unit tests pass, the state machine is complete, idempotency is correct, and the advisory lock mechanism is sound. However, two transaction boundary deviations from the approved architecture were found that affect atomicity guarantees under concurrent load. These deviations are mitigated by the `ON CONFLICT DO NOTHING` idempotency on `signal_hash` and the `UNIQUE` partial index on `learning_executions`, but they do not match the approved design's single-transaction guarantees.

**Recommendation:** Approve with mandatory remediation of the two transaction boundary deviations before production deployment.

---

## 2. Design-to-Code Traceability

| Approved Design Requirement | Implementation | Status |
|---|---|---|
| `learning_execution` table with `id`, `tenant_id`, `decision_id`, `status`, `started_at`, `heartbeat_at`, `completed_at`, `signal_count`, `failure_reason`, `created_at` | `libs/learning/learning_execution.py` — `LearningExecution` dataclass with all 11 columns | ✅ |
| `outcome_revisions` table (append-only, immutable) | `libs/learning/outcome_revision.py` — `OutcomeRevision` dataclass, `LearningExecutionStore.create_outcome_revision()` | ✅ |
| `learning_memory.execution_id` FK | `libs/memory/memory_ledger.py:173` — FK in `_INSERT_SQL` (added in F-NEW-1 remediation) | ✅ |
| `learning_memory` UNIQUE on `(tenant_id, target_type, target_id, signal_hash)` | `memory_ledger.py:176-182` — `ON CONFLICT DO NOTHING` | ✅ |
| State machine: `pending → running → completed \| failed \| stale` | `learning_execution.py:121-173` — all 5 states, all transitions valid | ✅ |
| Retry creates NEW execution (never reuses) | `learning_execution_store.py:264-265` — `status = "pending"` on claim | ✅ |
| Advisory lock key: `hashtext("{tenant_id}:{decision_id}")` | `learning_execution_store.py:126` — `pg_advisory_xact_lock(hashtext(:lock_key))` | ✅ |
| Advisory lock scope: per-decision (different decisions → independent locks) | Lock key derivation at `learning_execution_store.py:67-68` — tenant + decision | ✅ |
| Phase 1: lock-free (INSERT `outcome_revisions` + UPDATE `decisions`) | `service.py:469-474` calls `create_outcome_revision()` | ⚠️ Deviation (see §4) |
| Phase 2: single advisory-locked transaction | `begin_execution()` → `persist()` → `complete_execution()` | ❌ Deviation (see §4) |
| Heartbeat: 30s interval | `learning_execution.py:27-28` — `HEARTBEAT_INTERVAL_SECONDS = 30` | ✅ |
| Stale threshold: 300s | `learning_execution.py:29` — `STALE_THRESHOLD_SECONDS = 300` | ✅ |
| Orphan detection: `outcome_revisions` without `learning_executions` | `learning_execution_store.py:300-319` — `find_orphaned_revisions()` | ✅ |
| `ON CONFLICT DO NOTHING` for idempotency | `memory_ledger.py:176-182` — correct | ✅ |
| Framework files untouched | `git diff` shows zero changes outside product repo | ✅ |

---

## 3. Findings

### F-01: Phase 2 Uses Multiple Sessions (CRITICAL)

**Approved Design:**
```
Phase 2 — Learning Execution (single advisory-locked transaction):
  BEGIN
    SELECT pg_advisory_xact_lock(hashtext("{tenant_id}:{decision_id}"))
    CREATE execution (INSERT INTO learning_executions)
    FOR each signal:
      INSERT INTO learning_memory (...) ON CONFLICT DO NOTHING
      (using advisory-locked session, NOT MemoryStore.persist())
    UPDATE execution SET status = 'completed', completed_at = now()
  COMMIT ← lock auto-released
```

**Actual Implementation (`learning_loop.py:700-824`):**
1. `begin_execution()` — opens session A, acquires advisory lock, inserts execution, **commits** (lock released)
2. `memory_store.persist()` — opens session B per signal (via `session_factory`), inserts, **commits** (no lock)
3. `complete_execution()` — opens session C, updates status, **commits** (no lock)

**Impact:** Signal persistence occurs without advisory lock protection. Two concurrent workers for the same decision could both write signals simultaneously. The `ON CONFLICT DO NOTHING` on `signal_hash` prevents duplicate signals, but does not guarantee serialized execution of the learning loop's compute-and-persist phase.

**Root Cause:** `memory_store.persist()` at `memory_ledger.py:173` opens its own `async with self._session_factory() as session` — it cannot receive an external session. The approved design explicitly says "using advisory-locked session, NOT MemoryStore.persist()".

### F-02: Phase 1 Not Atomic (CRITICAL)

**Approved Design:**
```
Phase 1 — Outcome Revision (lock-free, append-only):
  BEGIN
    INSERT INTO outcome_revisions
    UPDATE decisions SET actual_outcomes = ..., executed_at = ...
  COMMIT
```

**Actual Implementation (`service.py:469-474`):**
1. `create_outcome_revision()` — opens session, INSERT `outcome_revisions`, commits
2. `submit_outcomes()` in `decisions.py:229-297` — opens separate session, UPDATE `decisions`, commits

**Impact:** If the UPDATE `decisions` succeeds but the INSERT `outcome_revisions` fails (or vice versa), the data is inconsistent. The `submit_outcomes()` call happens before `create_outcome_revision()` in the `submit_decision_outcomes` flow, so in practice the revision is always created after the decision update. However, the two operations are not in a single transaction as the approved design requires.

### F-03: All DB-Level Tests Skipped (HIGH)

6 of 6 database-level tests in `tests/learning/test_h3_transaction.py` are **SKIPPED** because PostgreSQL is not running on port 5433:
- `test_advisory_lock_released_on_rollback`
- `test_concurrent_advisory_lock_blocks`
- `test_different_decisions_no_contention`
- `test_outcome_revision_immutable`
- `test_learning_execution_invalid_status_rejected`
- `test_partial_unique_index_prevents_concurrent_active`

**Impact:** The advisory lock behavior, trigger enforcement, partial unique index, and constraint rejection are not validated at runtime. All concurrency tests that passed used mocked sessions, not real database connections.

### F-04: No Structured Logging for Key Events (MEDIUM)

The approved design recommends structured logging for lock acquisition, state transitions, and concurrency events. The implementation has:
- A `logger.exception()` in the catch block at `learning_loop.py:841-843` (only on failure)
- No logging for lock acquisition, lock wait, heartbeat, stale detection, or state transitions

### F-05: Legacy Path Bypasses H3 (LOW)

`service.py:504-519` contains a legacy learning loop path that bypasses the execution store entirely:
```python
elif self._learning_loop_store is not None:
    # Legacy path: no execution store, use original learning loop
    loop_result = await self._learning_loop_store.run_for_decision(...)
```

If `execution_store` is `None` but `learning_loop_store` is set, the system falls back to the pre-H3 learning loop with no advisory lock, no execution tracking, and no outcome revision.

### F-06: `create_outcome_revision` Does Not Validate Decision Exists (LOW)

`learning_execution_store.py:147-172` inserts an `outcome_revisions` row without first checking if the referenced `decision_id` exists in the `decisions` table. There is no foreign key constraint between `outcome_revisions.decision_id` and `decisions.id`. The approved design does not specify this constraint, but it means orphaned revisions can be created.

---

## 4. Transaction Proof

### Phase 2 — Advisory Lock Scope

**Lock derivation:** `hashtext("{tenant_id}:{decision_id}")` → `pg_advisory_xact_lock(...)` in `learning_execution_store.py:126`

| Scenario | Expected | Actual | Verdict |
|---|---|---|---|
| Same decision, same tenant | Same lock key → serialize | ✅ Same `hashtext` key | PASS |
| Same decision, different tenant | Different lock key → independent | ✅ Different key due to tenant prefix | PASS |
| Different decision, same tenant | Different lock key → independent | ✅ Different key due to decision suffix | PASS |
| Lock released on rollback | `pg_advisory_xact_lock` is transaction-scoped | ✅ `session.rollback()` in `fail_execution` releases lock | PASS (theoretical — DB test skipped) |
| Lock released on commit | `pg_advisory_xact_lock` is transaction-scoped | ⚠️ Lock is released when `begin_execution` commits, BEFORE signal persistence | DEVIATION (see F-01) |

### Phase 2 — Actual Transaction Flow

```
Session A (begin_execution):
  BEGIN → ADVISORY LOCK → INSERT execution → COMMIT  [lock released here]

Session B (memory_store.persist, per signal):
  BEGIN → INSERT learning_memory ON CONFLICT DO NOTHING → COMMIT  [no lock]

Session C (complete_execution):
  BEGIN → UPDATE execution SET status='completed' → COMMIT  [no lock]
```

**Verdict:** The advisory lock protects the execution creation (INSERT) but NOT the signal persistence or completion. The approved design requires all three to be within the lock scope.

---

## 5. Lock Proof

| Property | Status |
|---|---|
| Lock key is deterministic for same (tenant, decision) | ✅ `hashtext` is deterministic |
| Different decisions produce different keys | ✅ Decision UUID in key |
| Different tenants produce different keys | ✅ Tenant UUID in key |
| Lock is transaction-scoped (not session-scoped) | ✅ `pg_advisory_xact_lock` used (not `pg_advisory_lock`) |
| Lock auto-releases on commit/rollback | ✅ By PostgreSQL guarantee |
| Lock scope: blocks concurrent `begin_execution` for same decision | ✅ Advisory lock blocks `BEGIN` → `INSERT` for same key |

---

## 6. Idempotency Proof

| Mechanism | Implementation | Verdict |
|---|---|---|
| `ON CONFLICT DO NOTHING` on `signal_hash` | `memory_ledger.py:176-182` | ✅ Identical signals are silently deduplicated |
| `UNIQUE (tenant_id, outcome_revision_id) WHERE status IN ('pending','running')` | Migration `04-h3-learning-execution.sql` | ✅ Prevents concurrent active executions per revision |
| `UNIQUE (tenant_id, outcome_revision_id) WHERE status = 'completed'` | Migration `04-h3-learning-execution.sql` | ✅ Prevents duplicate completed executions |
| `begin_execution` returns `None` if already completed | `learning_execution_store.py:260-261` | ✅ Skip path works correctly |
| State machine rejects invalid transitions | `learning_execution.py:121-173` | ✅ All invalid transitions raise `ValueError` |
| Retry creates NEW execution (never reuses) | `learning_execution_store.py:264-265` | ✅ `status = "pending"` on claim |

---

## 7. Recovery Proof

| Scenario | Behavior | Verdict |
|---|---|---|
| Worker crashes after `begin_execution` (before signals) | Execution stuck at `running`, heartbeat expires → `stale`, reconciliation resets to `pending` | ✅ (theoretical — DB test skipped) |
| Worker crashes during signal writes | Some signals committed, execution still `running`, heartbeat expires → stale | ⚠️ Partial signals written without lock (F-01) |
| Worker crashes after `complete_execution` | Execution at `completed`, no recovery needed | ✅ |
| Stale execution detected by new worker | `reconcile_stale_execution()` resets to `pending`, creates new execution | ✅ `learning_execution_store.py:282-297` |
| Orphaned outcome revision detected | `find_orphaned_revisions()` returns revision without execution | ✅ `learning_execution_store.py:300-319` |

---

## 8. Provenance Proof

| Property | Status |
|---|---|
| `execution_id` stored on `learning_memory` | ✅ FK in `_INSERT_SQL` (added in F-NEW-1 remediation) |
| `outcome_revision_id` stored on `learning_executions` | ✅ Column in `learning_executions` table |
| `signal_hash` computed deterministically | ✅ `compute_signal_hash()` in `memory_ledger.py` |
| Append-only: `OutcomeRevision` has no UPDATE/DELETE methods | ✅ `OutcomeRevision` dataclass is read-only |
| No UPDATE/DELETE on `learning_executions` (except status transitions) | ✅ Only `UPDATE` for status/heartbeat/completion/failure |

---

## 9. Database Integrity

| Constraint | Status |
|---|---|
| `outcome_revisions` PK on `id` | ✅ Migration `04-h3-learning-execution.sql` |
| `learning_executions` PK on `id` | ✅ Migration `04-h3-learning-execution.sql` |
| `learning_executions.outcome_revision_id` FK → `outcome_revisions.id` | ✅ Migration `04-h3-learning-execution.sql` |
| `learning_executions.tenant_id` NOT NULL | ✅ |
| `learning_executions.status` NOT NULL DEFAULT 'pending' | ✅ |
| Partial unique index: `(tenant_id, outcome_revision_id) WHERE status IN ('pending','running')` | ✅ |
| Partial unique index: `(tenant_id, outcome_revision_id) WHERE status = 'completed'` | ✅ |
| `learning_memory.execution_id` FK → `learning_executions.id` | ✅ |
| `learning_memory.signal_hash` UNIQUE per (tenant, target_type, target_id) | ✅ `ON CONFLICT DO NOTHING` |
| CHECK: `status IN ('pending','running','completed','failed','stale')` | ✅ |
| CHECK: `execution_id IS NOT NULL OR memory_type = 'pending'` | ✅ (state machine enforces) |
| CHECK: `execution_id IS NULL OR memory_type != 'pending'` | ✅ (state machine enforces) |

---

## 10. Test Adequacy

| Category | Tests | Passed | Skipped | Quality |
|---|---|---|---|---|
| State machine (model) | 10 | 10 | 0 | **Strong** — all transitions tested |
| Lock key derivation | 4 | 4 | 0 | **Strong** — deterministic key verification |
| Advisory lock store (mocked) | 9 | 9 | 0 | **Medium** — mocked sessions, no real DB |
| Transaction boundary (mocked) | 3 | 3 | 0 | **Medium** — verifies flow, not isolation |
| Concurrency (mocked) | 3 | 3 | 0 | **Medium** — verifies serialization logic |
| Idempotency (mocked) | 3 | 3 | 0 | **Strong** — tests skip, dedup, retry |
| DB-level (real PostgreSQL) | 6 | 0 | 6 | **WEAK** — all skipped, no real validation |
| Provenance chain | 15 | 15 | 0 | **Strong** — comprehensive |
| Recovery (mocked) | 27 | 27 | 0 | **Medium** — heartbeat, stale, orphan detection |
| Learning signals | 14 | 14 | 0 | **Strong** — all signal types tested |
| Schema DDL (real PostgreSQL) | 10 | 0 | 10 | **WEAK** — all skipped |
| **Total** | **104** | **88** | **16** | |

**Critical Gap:** 16 tests (all DB-level) are skipped. The most important property — advisory lock serialization under concurrent load — is not validated.

---

## 11. Regression Results

| Metric | Before H3 | After H3 | Delta |
|---|---|---|---|
| Tests passed | 131 | 379 | +248 |
| Tests skipped | 0 | 31 | +31 |
| Tests failed | 0 | 0 | 0 |
| Lint (production) | clean | clean | 0 |

All new tests pass. No existing tests were broken.

---

## 12. Framework Boundary

| Rule | Status |
|---|---|
| Framework is read-only | ✅ Zero changes to framework files |
| Product implements cognitive contracts | ✅ H3 is a product-level capability |
| No framework code modified | ✅ `git diff` shows changes only in product repo |

---

## 13. Security

| Property | Status |
|---|---|
| `execution_id` FK prevents orphaned memory | ✅ FK constraint in migration |
| No secrets logged | ✅ Only decision/execution UUIDs logged |
| No unsafe `text()` injection in SQL | ✅ Parameterized queries used throughout |
| `outcome_revisions` are append-only | ✅ No UPDATE/DELETE methods |

---

## 14. Remaining Risks

| Risk | Severity | Mitigation |
|---|---|---|
| Phase 2 signals written without advisory lock (F-01) | **CRITICAL** | `ON CONFLICT DO NOTHING` prevents duplicates; `UNIQUE` partial index prevents concurrent active executions |
| Phase 1 not atomic (F-02) | **CRITICAL** | In practice, `submit_outcomes()` succeeds before `create_outcome_revision()` is called; failure of either is caught by the outer `try/except` |
| DB-level tests not run (F-03) | **HIGH** | Must run full suite with PostgreSQL before production |
| No structured logging for concurrency events (F-04) | **MEDIUM** | Add `logger.info()` for lock acquisition, heartbeat, stale detection |
| Legacy path bypasses H3 (F-05) | **LOW** | Remove legacy path once H3 is validated |
| No FK between `outcome_revisions.decision_id` and `decisions.id` (F-06) | **LOW** | Add FK constraint in next migration |

---

## 15. Conclusion

The H3 Learning Hardening implementation is functionally correct and passes all available tests. The state machine, advisory lock mechanism, idempotency, and provenance chain are well-designed and correctly implemented. The two transaction boundary deviations (F-01, F-02) are the primary concern — they reduce the atomicity guarantees from the approved design's single-transaction model to a multi-session model with idempotency-based safety. This is an acceptable trade-off for the current codebase, but should be remediated before production deployment.

**Recommendation:** APPROVE with mandatory remediation of F-01 and F-02 before production.
