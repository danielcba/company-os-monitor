## Summary

This PR implements the Learning Loop Hardening per the audit requirements (auditoria_revision_2.md), addressing all 4 major problems:

### Problem #1 - Hypothesis Evaluation (libs/reasoning/hypothesis.py)
- Added `evaluate_hypothesis()` function with explicit evaluation rules:
  - Insufficient evidence -> candidate (no change)
  - Evidence satisfying falsification criterion -> falsified
  - Sufficient evidence corroborating predictions -> confirmed (strict majority)
  - Contradictory but insufficient evidence -> candidate
- **Confidence is NOT the sole criterion** - it supports but doesn't decide
- Evaluation considers: predicted_consequences, falsification_criterion, supporting/contradicting evidence, confidence, evidence sufficiency
- 22 unit tests covering audit requirements A-H

### Problem #2 - Learning Memory Semantics (libs/memory/memory_ledger.py)
- Added 'decision' target_type for consolidation signals (semantically correct: target_type='decision', target_id=decision_id)
- Fixed semantic mismatch: pattern/context/insight now correctly paired with their respective IDs
- 13 unit tests for semantic correctness (audit requirements A-F)

### Problem #3 - Learning Loop Scope (libs/memory/learning_loop.py)
- Changed from tenant-wide to decision-scoped learning
- Added `_trace_decision_to_artifacts_bundle()` to trace Decision -> Recommendation -> Hypothesis -> Pattern/Context/Insight
- Only persist signals for affected artifacts (decision-scoped)
- Read/compute capabilities remain tenant-wide (API), persistence is decision-scoped

### Problem #4 - Failure Semantics (apps/gateway/api-gateway/src/service.py)
- `submit_decision_outcomes()` now returns `learning_loop.status`: 'completed' | 'failed' | 'pending'
- Outcome submission succeeds even when learning fails (decoupled)
- 4 unit tests for failure scenarios

### Additional Improvements
- Enhanced provenance with `decision_id` in all learning signals
- Idempotency preserved (deterministic UUIDs, signal hashes)
- Append-only maintained (P1)
- Tenant isolation enforced
- Documentation updated (README.md, README_EN.md, README_ES.md)

## Test Results
- 462 tests pass (including 39 new tests)
- ruff: clean (our changes)
- mypy: clean
- bandit: no HIGH/MEDIUM issues
- Frontend: 182 tests pass

### Pre-existing CI failures (not introduced by this PR)
- `test_pattern_service_detects_and_persists_with_traceability` in pattern-service: test expects `strength_measure=1.0` but code produces `0.6667` (min_occurrences=3 with 2 occurrences). Introduced in commit `97cb17d`.

## Files Changed
- libs/reasoning/hypothesis.py (evaluation logic)
- libs/memory/memory_ledger.py (decision target_type)
- libs/memory/learning_loop.py (decision-scoped scope, traceability)
- apps/gateway/api-gateway/src/service.py (failure semantics)
- apps/services/evaluation-service/tests/test_evaluation_model.py (B017 fix)
- apps/services/evaluation-service/tests/test_evaluation_policy.py (F821 fix)
- infrastructure/db-migrations/sprint18-hypothesis-evaluation.sql (migration ordering fix)
- README.md, README_EN.md, README_ES.md (documentation)
- tests/reasoning/test_hypothesis_evaluation.py (22 tests)
- tests/memory/test_memory_ledger_semantics.py (13 tests)
- tests/learning/test_learning_loop_failure.py (4 tests)