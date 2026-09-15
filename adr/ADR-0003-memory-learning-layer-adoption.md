# Architecture Decision Record 0003

Title: Adopt Monitor Memory & Learning Layer as Framework Memory Capability

Status: Accepted
Approved: 2026-08-30
Approved-by: Framework (company-os-main)

Date: 2026-08-30
Supersedes: ADR-0002 (regarding "Memory remains planned" restriction)

---

## Context

The Company OS Framework (cognitive-architecture.md) defines Memory as "planned" within P7: Learning Through Outcome. The Framework declares Memory as a future capability with no concrete specification for entity, lifecycle, or persistence.

Meanwhile, the Monitor (COS-Monitor) has implemented a complete Memory/Learning layer since PR #14 (learning loop) and PR #10 (learning memory ledger):

- **Memory Consolidation** (`libs/memory/consolidation.py`): Expected vs actual outcome comparison with Brier score, ECE, calibration feedback
- **Pattern Refinement** (`libs/memory/pattern_refinement.py`): Outcome attribution to Patterns via traceability chain; keep/degrade/deactivate signals
- **Context Revision** (`libs/memory/context_revision.py`): Outcome attribution to Contexts; keep/review/consider_competitor signals; P2 compliant (never auto-activates)
- **Insight Transformation** (`libs/memory/insight_transformation.py`): Transformation journaling; revised/stable/unchanged classification
- **Learning Loop** (`libs/memory/learning_loop.py`): Orchestration of Decision → Outcome → Consolidation → Learning Signal → Memory
- **Memory Ledger** (`libs/memory/memory_ledger.py`): Append-only persistence by signal hash; tenant-scoped; idempotent (UNIQUE index)
- **Hypothesis Evaluation** (`libs/learning/evaluation.py`): Formal policy + append-only hypothesis_evaluations + deterministic evaluation_id

The Framework-Monitor Sync Audit (`docs/framework-monitor-sync-audit.md`) identified this gap as HIGH RISK: "Framework Memory labeled 'planned' while Monitor has shipped it: risk of divergence if Framework later defines Memory without reference to Monitor implementation."

## Problem

The Framework lacks a formal Memory entity specification while the Monitor has shipped a complete Memory/Learning implementation. This creates:

1. **Documentation drift**: Framework marks Memory as "planned"; Monitor has it operational
2. **Traceability gap**: ADR-0004 and ADR-0008 reference ADR-0003 as existing, but it does not
3. **Divergence risk**: Future Framework evolution could define Memory incompatible with Monitor implementation

## Decision

Adopt the Monitor's existing Memory/Learning layer as the concrete realization of the Framework's Memory capability (P7: Learning Through Outcome).

### Framework Role

The Framework remains the architectural source of truth. It defines:

- Memory entity lifecycle (what is Memory, when does it exist)
- Memory Ledger semantics (append-only, idempotent, tenant-scoped)
- Learning Through Outcome contract (Decision → Outcome → Consolidation → Learning Signal → Memory)

### Monitor Role

The Monitor is the reference implementation (per ADR-0002). It realizes the Framework's Memory capability through:

- Memory Consolidation (expected vs actual comparison)
- Pattern Refinement (outcome attribution to patterns)
- Context Revision (outcome attribution to contexts)
- Insight Transformation (transformation journaling)
- Learning Memory Ledger (append-only persistence)
- Learning Loop (orchestration)

### Scope

This ADR formalizes the following components as Framework Memory:

| Component | Location | Framework Mapping |
|-----------|----------|-------------------|
| Memory Consolidation | `libs/memory/consolidation.py` | P7: Expected vs actual comparison |
| Pattern Refinement | `libs/memory/pattern_refinement.py` | Learning sub-capability |
| Context Revision | `libs/memory/context_revision.py` | Learning sub-capability |
| Insight Transformation | `libs/memory/insight_transformation.py` | Learning sub-capability |
| Learning Loop | `libs/memory/learning_loop.py` | P7: Orchestration |
| Memory Ledger | `libs/memory/memory_ledger.py` | P7: Persistence |
| Hypothesis Evaluation | `libs/learning/evaluation.py` | Reasoning → Learning bridge |

## Consequences

### Positive

- Resolves Framework "planned" status for Memory
- Establishes traceability: Framework defines, Monitor implements
- Prevents divergence: Future Framework Memory evolution must remain compatible with Monitor's append-only, tenant-scoped, Evidence-boundary-respecting design
- Corrects documentation drift in both Framework and Monitor
- Resolves broken ADR-0003 references in ADR-0004 and ADR-0008

### Negative

- Framework Memory is now tied to Monitor's implementation choices
- Future Framework Memory evolution may require Monitor-compatible extensions
- Creates a dependency: Framework Memory spec must be informed by Monitor capabilities

### Neutral

- No behavioral change in Monitor code
- No schema changes
- No API changes
- No security changes

## Invariants

| Invariant | Verification | Status |
|-----------|-------------|--------|
| Memory Ledger is append-only (P1) | `memory_ledger.py` — UNIQUE index on signal_hash, no UPDATE/DELETE on content | PRESERVED |
| Memory is tenant-scoped | All Memory tables have `tenant_id` column with FK | PRESERVED |
| Evidence boundary enforced | Pattern Refinement operates on Patterns (not raw Observations); Context Revision operates on Contexts | PRESERVED |
| Reasoning operates on Evidence, not raw Observations | Hypothesis Evaluation consumes Evidence (not Observation) | PRESERVED |
| Context is never auto-activated (P2) | Context Revision signals are advisory; never auto-activate Context | PRESERVED |
| Deterministic IDs | All Memory entities use uuid5 deterministic IDs | PRESERVED |
| Idempotency | Memory Ledger uses UNIQUE(tenant_id, target_type, target_id, signal_hash) | PRESERVED |
| Learning Loop skips pending Decisions | `learning_loop.py` — `compute_outcome_signal()` returns None when `actual_outcomes is None` | PRESERVED |

## Scope Boundary

### IN SCOPE

1. Memory entity formalization (what is Memory in the Framework)
2. Memory Ledger semantics (append-only, idempotent, tenant-scoped)
3. Memory Consolidation (expected vs actual comparison)
4. Pattern Refinement (keep/degrade/deactivate signals)
5. Context Revision (keep/review/consider_competitor signals)
6. Insight Transformation (revised/stable/unchanged classification)
7. Learning Loop orchestration
8. Hypothesis Evaluation integration (Evidence-boundary compliant)
9. Documentation drift correction
10. ADR reference correction

### OUT OF SCOPE

- Evaluation result lifecycle (confirmed/falsified/insufficient) — future ADR
- Calibration Monitoring — future phase
- Learning Hardening — future phase
- Scalability — future phase
- Operations — future phase
- Product/UX — future phase
- Framework repository modifications (read-only per ADR-0002)
- Schema changes
- API changes
- Security changes
- New capabilities

## Relationship with ADR-0001

**ADR-0001**: Company OS is the Brain (cognitive architecture authority)

**Analysis**: This ADR recognizes the Monitor's Memory/Learning layer as the concrete realization of P7 within the Framework's architectural authority. The Framework defines Memory; the Monitor implements it. ADR-0001 is preserved.

## Relationship with ADR-0002

**ADR-0002**: COS-Monitor is the Product (external capabilities pattern)

**Analysis**: ADR-0002 establishes the Monitor as the reference implementation. This ADR formalizes Memory/Learning as part of that reference implementation. ADR-0002 is preserved.

## Relationship with ADR-0008

**ADR-0008**: Outcome Status Semantics — Formalizing Missing Outcome Handling

**Analysis**: ADR-0008 extends the Learning Layer semantics by formally defining the outcome lifecycle (`pending` → `observed`). This ADR provides the foundational Memory/Learning specification that ADR-0008 builds upon. The two are complementary and backward compatible.

---

## Acceptance Criteria

| ID | Statement | Verification Method | PASS Condition | FAIL Condition |
|----|-----------|---------------------|----------------|----------------|
| AC-01 | ADR-0003 exists and has valid structure | File existence + structure check | File exists with Context/Decision/Consequences/Invariants/Scope sections | File missing or incomplete structure |
| AC-02 | Memory is no longer marked as "planned" in architecture docs | Documentation review | `docs/01-fundacion-arquitectura.md` has no "(planned)" on Memory lines | "(planned)" still present |
| AC-03 | Frontend doc drift corrected | Documentation review | `docs/frontend/architecture.md` has no "(planned)" on implemented capabilities | "(planned)" still present on implemented items |
| AC-04 | ADR-0008 references ADR-0003 coherently | ADR review | ADR-0008 "Relationship with ADR-0003" section reflects ADR-0003 as existing | Reference still treats ADR-0003 as non-existent |
| AC-05 | ADR-0004 reference to ADR-0003 is coherent | ADR review | ADR-0004 line 267 reference is consistent with ADR-0003 | Reference contradicts ADR-0003 |
| AC-06 | H4 validation document reflects ADR-0003 existence | Document review | H4_ADR_PACKAGE_VALIDATION.md updated to reflect ADR-0003 created | Still lists ADR-0003 as non-existent |
| AC-07 | Code comments updated where "planned" is stale | Code review | "Memory persistence remains planned" comments updated in 4 files | Stale comments remain |
| AC-08 | No behavioral changes | Code review + tests | No logic changes in modified files | Logic changed |
| AC-09 | No schema changes | Schema review | No new migrations, no altered columns | Schema modified |
| AC-10 | No API changes | API review | No endpoint changes, no payload changes | API modified |
| AC-11 | Framework repository unchanged | File review | No files modified in `/home/dcordoba/Documents/Default Project/company/company-os-main/` | Framework files modified |
| AC-12 | All existing tests pass | Test execution | 722/722 or more tests pass | Regression detected |
| AC-13 | ADR-0003 is Accepted (Framework acceptance synchronized) | Status check | Status = Accepted | Status = PROPOSED (desynchronized from Framework) |
