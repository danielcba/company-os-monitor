# PRE-IMPLEMENTATION PLAN

## Candidate Phase

**Cognitive Gate Closure** (tentative name: H6)

Closing the end-to-end Decision → Execution → Observed Outcome → Evaluation → Learning Trigger chain, transitioning the Cognitive Gate from YELLOW to GREEN.

## Purpose

The Cognitive Pipeline is fully implemented end-to-end (Observation → Evidence → Context → Pattern → Anomaly → Hypothesis → Evaluation → Insight → Confidence → Recommendation → Decision → Report → Memory). However, the **Cognitive Gate** (the proof that the system actually learns from its decisions) remains YELLOW (partially verified) per `COGNITIVE_GATE_AUDIT.md`.

The fundamental gap: Decisions are committed with falsifiable expected outcomes, but `actual_outcomes` and `executed_at` are never populated. The learning loop infrastructure exists (152 tests pass) but cannot trigger because it never receives observed outcomes.

Closing this gate proves that Company OS *learns from its own decisions* — the core value proposition of the Cognitive Architecture.

## Evidence

1. **`COGNITIVE_GATE_AUDIT.md`** (verdict: YELLOW — PARTIALLY VERIFIED):
   - Decision → Expected Outcome: **VERIFIED**
   - Expected Outcome → Execution: **NOT VERIFIED** (`commit()` sets `executed_at=None, actual_outcomes=None`)
   - Execution → Observed Outcome: **NOT VERIFIED** (no execution mechanism)
   - Observed Outcome → Evaluation: **VERIFIED (infrastructure)** (functions exist but never receive data)
   - Evaluation → Learning Trigger: **PARTIAL** (infrastructure, no data)

2. **`committer.py:254-287`**: `commit()` sets `executed_at=None, actual_outcomes=None` explicitly.

3. **`learning_loop.py:26-82`**: `compute_outcome_signal()` returns `None` when `actual_outcomes is None` (line 37-38).

4. **`decision.py:390-490`**: `compare_expected_actual_outcomes()` exists and works but is never called with real data.

5. **`decision.py:68-74`**: `EXPECTED_OUTCOME_KEYS = {prediction, verifiable_by, deadline}` and `PREDICTION_THRESHOLD = 0.5` are defined.

6. **`docs/05-negocio-roadmap-backlog.md:47`**: Sprint 10 Cognitive Gate definition: "Primer Decision commitida con expected outcomes falsificables. Learning loop inicia."

7. **`docs/learning/learning-pipeline-status.md`**: Pipeline operational; P7 fully implemented since PR #14.

## Current State

| Component | Status | Evidence |
|-----------|--------|----------|
| Decision Service | COMMITTED decisions with expected outcomes | 53/53 tests pass |
| Expected Outcomes | Structure defined: {prediction, verifiable_by, deadline} | `decision.py:68-70` |
| Comparison Functions | Exist and work: `compare_expected_actual_outcomes()` | `decision.py:390-490` |
| Outcome Signal | Computation exists: `compute_outcome_signal()` | `learning_loop.py:26-82` |
| Learning History | `build_learning_history()` exists | `learning_loop.py:141-190` |
| Memory Ledger | Append-only, idempotent, 4 signal types | `memory_ledger.py` |
| Pattern Refinement | keep/degrade/deactivate signals | `pattern_refinement.py` |
| Context Revision | keep/review/consider_competitor signals | `context_revision.py` |
| Insight Transformation | revised/stable/unchanged signals | `insight_transformation.py` |
| **Execution Layer** | **DOES NOT EXIST** | No component populates `actual_outcomes` |
| **Outcome Observer** | **DOES NOT EXIST** | No component observes execution results |
| **Gate Trigger** | **DOES NOT EXIST** | No component connects Decision commit → Learning |

## Existing Dependencies

| Dependency | Type | Status |
|-----------|------|--------|
| Decision Service | Internal | COMPLETE |
| Learning Loop | Internal | COMPLETE |
| Memory Ledger | Internal | COMPLETE |
| Evaluation Service | Internal | COMPLETE (port 8102) |
| Machine Auth (H5) | Internal | COMPLETE (RS256, kid rotation) |
| Telemetry Pipeline (H4) | Internal | COMPLETE (ingest → outbox → publisher) |
| PostgreSQL | External | AVAILABLE (port 5433) |
| Redis | External | AVAILABLE |

## Required Preconditions

1. H5 remains closed and unmodified
2. H4.0 telemetry pipeline remains functional
3. Evaluation Service remains operational (port 8102)
4. Decision Service remains operational (port 8097)
5. 658/658 regression tests remain GREEN
6. No architectural regressions in existing cognitive chain

## Architectural Questions

### Q1: What is "Decision Execution" in a monitoring system?

**FACT**: In COS-Monitor, Decisions are cognitive judgments, not imperative commands. A Decision says "based on evidence, the system recommends X" — it does not automatically execute X.

**OPEN QUESTION**: Should "execution" mean:
- (a) A human acknowledges the Decision (manual execution)?
- (b) A callback/webhook triggers an external system?
- (c) The system records a simulated/test execution for calibration purposes?
- (d) Something else specific to the monitoring domain?

**EVIDENCE NEEDED**: Architectural decision on the semantics of "execution" in this cognitive system.

### Q2: What constitutes an "observed outcome"?

**FACT**: `EXPECTED_OUTCOME_KEYS = {prediction, verifiable_by, deadline}`. The `verifiable_by` field names a metric to check against.

**OPEN QUESTION**: Where do actual outcome values come from?
- (a) From real infrastructure metrics (e.g., actual CPU usage at deadline)?
- (b) From simulated/test scenarios for calibration?
- (c) From human input?
- (d) From a new "Outcome Observer" service?

### Q3: Does the Learning Loop need a trigger from Decision commit?

**FACT**: `build_learning_history()` exists but requires decisions with `actual_outcomes` populated. `compute_outcome_signal()` requires both expected and actual outcomes.

**OPEN QUESTION**: Should the trigger be:
- (a) Automatic on Decision commit (async background task)?
- (b) Periodic batch evaluation (e.g., daily cron)?
- (c) Manual trigger by operator?

## Security Questions

1. If "execution" involves external system callbacks, what authentication is required?
2. If outcomes come from infrastructure metrics, how is data integrity verified?
3. Can observed outcomes be tampered with? What prevents fabrication?
4. Does the outcome observer need machine auth (H5) or human auth?
5. Are outcomes tenant-scoped (P1)?

## Data Questions

1. Should `actual_outcomes` be a new column on `decisions` or a separate table?
2. Should `executed_at` be a lifecycle field on `decisions` or on a separate `executions` table?
3. What is the retention policy for observed outcomes?
4. How are outcomes linked to the provenance chain (Decision → Recommendation → Confidence → ...)?
5. Should outcome observations be append-only (P1)?

## Operational Questions

1. What is the SLA for outcome observation after Decision commit?
2. How is the Learning Loop triggered in production?
3. What monitoring/observability is needed for the outcome pipeline?
4. How are outcome discrepancies (actual ≠ expected) surfaced to operators?
5. What is the rollback strategy if the outcome pipeline introduces regressions?

## Testing Expectations

1. Unit tests for outcome observation and comparison
2. Integration test: Decision → Execution → Observed Outcome → Evaluation → Learning Trigger (end-to-end)
3. Architecture invariant tests: outcomes cannot bypass the cognitive chain
4. Security tests: outcomes are tenant-scoped, append-only, tamper-evident
5. Regression: all 658 existing tests remain GREEN
6. Adversarial tests: can a malicious actor fabricate outcomes?
7. Concurrency tests: parallel outcome observations don't corrupt state

## Files / Modules Potentially Affected

| Path | Impact | Reason |
|------|--------|--------|
| `libs/action/decision.py` | MAYBE | `commit()` may need to accept execution results |
| `libs/learning/learning_loop.py` | LIKELY | `compute_outcome_signal()` may need real data flow |
| `libs/memory/consolidation.py` | LIKELY | Needs actual outcomes to compute Brier/ECE |
| `apps/services/decision-service/` | MAYBE | May need execution endpoint |
| `apps/services/evaluation-service/` | MAYBE | May need outcome-aware evaluation |
| `infrastructure/db-migrations/` | LIKELY | New migration for outcome tables/columns |
| `tests/` | DEFINITELY | New tests for end-to-end gate |

## Files Explicitly Out of Scope

- `libs/access/security.py` — H5 machine auth, no changes
- `libs/access/` — Auth/RBAC, no changes
- `apps/agents/` — Agent code, no changes
- `apps/web/` — Frontend, no changes (unless gate requires UI)
- Framework repository — READ-ONLY, never modified
- ADR-0004..0007 — Existing ADRs, no modification
- H4.0 infrastructure — No changes
- H5 infrastructure — No changes

## ADRs Potentially Required

1. **ADR-0003** (Framework Synchronization) — Referenced in `docs/framework-monitor-sync-audit.md` as proposed but not yet created. May be needed to formalize Memory/Learning in the Framework before or alongside Cognitive Gate closure.

2. **New ADR for Decision Execution semantics** — The meaning of "execution" in a cognitive monitoring system needs formal definition.

3. **New ADR for Outcome Observation** — How outcomes are captured, stored, and linked to the provenance chain.

## Risks

| Risk | Severity | Mitigation |
|------|----------|------------|
| "Execution" semantics undefined | HIGH | ADR required before implementation |
| Outcome data source unclear | HIGH | Architecture decision needed |
| Premature hypothesis promotion | MEDIUM | `evidence_basis_reliable=False` guard exists |
| Learning loop triggers false calibrations | MEDIUM | Start with simulated/test outcomes only |
| Migration complexity for outcome tables | LOW | Idempotent migrations per existing pattern |
| Cognitive Gate becomes a scope creep | MEDIUM | Strict boundary: only close the gate, no new capabilities |

## Unknowns

1. Is the Cognitive Gate closure the highest-priority next phase, or should Framework Sync (ADR-0003) come first?
2. Does the human want "execution" to be real (external system callbacks) or simulated (test/calibration only)?
3. Should the gate be closed in a single phase or across multiple phases?
4. Are there external stakeholders (e.g., customers) waiting for this capability?
5. What is the target date for Cognitive Gate GREEN?

## Human Decisions Required

1. **Scope Approval**: Is Cognitive Gate Closure the correct next phase?
2. **Execution Semantics**: What does "Decision Execution" mean in this system?
3. **Outcome Source**: Where do observed outcomes come from?
4. **ADR-0003**: Should Framework Sync happen before, after, or in parallel?
5. **Phase Naming**: Should this be called H6 or a different naming convention?
6. **Acceptance Criteria**: What specific conditions make the gate GREEN?
7. **Timeline**: What is the expected completion timeframe?

## Implementation Authorization

STATUS = NOT AUTHORIZED
