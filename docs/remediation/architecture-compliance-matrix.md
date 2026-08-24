# Architecture Compliance Matrix — Company OS Monitor

Maps each cognitive design rule to its implementation in the product.
Every row documents WHERE and HOW the rule is enforced.

Generated: 2026-08-22
Last updated: Phase 4-17 remediation

---

## P1 — Primacy of Observation

*Observation captures reality; it never interprets, predicts, or acts.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `libs/perception/observation.py` | Observation model is frozen; no prediction/interpretation fields | `tests/architecture/test_cognitive_invariants.py::test_observation_never_executes_action` |
| `infrastructure/docker/init-sql/01-schema.sql` | All canonical tables have immutability triggers (UPDATE/DELETE blocked) | `tests/architecture/test_cognitive_invariants.py::test_canonical_tables_have_immutability_triggers` |
| `libs/perception/context.py` | Context is append-only; activation lifecycle managed via is_active flag | `tests/architecture/test_cognitive_invariants.py::test_one_active_context_per_purpose_constraint` |

## P2 — Context Activation

*Context is activated by coherence competition, never directly generated.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `libs/perception/context.py` | Context activation is atomic (INSERT+DEACTIVATE in single transaction) | `Phase 5: save_context uses session.begin() for atomicity` |
| `infrastructure/db-migrations/phase5-context-activation-atomicity.sql` | UNIQUE partial index: idx_contexts_unique_active on (tenant_id, purpose) WHERE is_active = true | `tests/architecture/test_cognitive_invariants.py::test_one_active_context_per_purpose_constraint` |

## P3 — Evidence is Input Only

*Evidence is organized observations; it never mutates existing observations.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `libs/perception/evidence.py` | Evidence model is frozen; insert-only with ON CONFLICT DO NOTHING | `Implicit via immutable schema triggers` |

## P4 — Hypothesis over Conclusion

*Explanations of cause are Hypothesis, not Context or Pattern.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `libs/reasoning/hypothesis.py` | Hypothesis model is separate from Pattern/Context; has cause/alternative fields | `tests/architecture/test_cognitive_invariants.py::test_each_concept_has_one_store` |

## P5 — Calibrated Confidence

*No conclusion influences action without confidence calibration.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `libs/learning/confidence.py` | Confidence has calibration_justification and calibration_error_estimate | `tests/architecture/test_cognitive_invariants.py::test_confidence_requires_provenance` |
| `apps/gateway/api-gateway/src/boundary.py` | validate_confidence_present requires confidence_id for commit/execute | `tests/architecture/test_cognitive_invariants.py::test_decision_requires_confidence` |

## P6 — Deliberate Action

*Recommendation proposes; Decision commits. They are separate.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `libs/action/recommendation.py + libs/action/decision.py` | Separate modules; Decision references confidence_id | `tests/architecture/test_cognitive_invariants.py::test_recommendation_is_not_decision` |

## P7 — Framework Guides Code

*The architecture is the authority; code adapts to it, not the reverse.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `AGENTS.md + docs/remediation/` | All references use canonical set (P1-P7, R1-R7) from framework | `No rule numbers outside canonical set exist in codebase` |

## R1 — One Capability per Component

*Each cognitive concept implements exactly one capability.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `libs/ (perception|reasoning|learning|action)` | Each directory has exactly one store per concept | `tests/architecture/test_cognitive_invariants.py::test_each_concept_has_one_store` |

## R2 — Cognitive Contract

*Each component has a documented contract defining its inputs/outputs.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `apps/gateway/api-gateway/src/boundary.py` | CANONICAL_FLOW defines valid transitions; check_boundary enforces them | `tests/architecture/test_cognitive_invariants.py::test_boundary_module_exists` |

## R3 — Boundary Enforcement

*The gateway enforces cognitive boundary rules at ingestion time.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `apps/gateway/api-gateway/src/boundary.py` | check_boundary validates action type + confidence presence | `tests/gateway/api-gateway/tests/test_boundary.py` |

## R4 — Confidence Before Action

*No conclusion influences action without confidence.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `apps/gateway/api-gateway/src/boundary.py` | validate_confidence_present blocks commit/execute without confidence_id | `tests/gateway/api-gateway/tests/test_gateway_service.py::test_enforce_boundary_*` |

## R5 — Confidence Provenance

*Confidence must include justification and calibration data.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `libs/learning/confidence.py` | Confidence model has calibration_justification, calibration_error_estimate | `tests/architecture/test_cognitive_invariants.py::test_confidence_requires_provenance` |

## R6 — Tenant Isolation

*Every query is scoped to a tenant; cross-tenant requires superadmin.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `libs/access/tenant_scope.py` | AuthorizationContext validates tenant match; cross_tenant_allowed checks role | `tests/gateway/api-gateway/tests/test_tenant_scope.py` |
| `libs/learning/confidence.py` | All confidence queries include tenant_id in WHERE clause | `tests/architecture/test_cognitive_invariants.py::test_confidence_is_tenant_scoped` |

## R7 — No Rule Invention

*Code must not invent rule numbers outside the canonical set.*

| Location | Enforcement | Test |
|----------|-------------|------|
| `AGENTS.md + prompt files` | Canonical policy: no rule numbers outside P1-P7, R1-R7 | `Policy enforced by agent instructions; verifiable via grep` |
