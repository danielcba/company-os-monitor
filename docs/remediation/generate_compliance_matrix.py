# ruff: noqa: E501
"""Architecture Compliance Matrix — Company OS Monitor.

Maps each cognitive design rule to its implementation in the product.
Every row documents WHERE and HOW the rule is enforced.

Generated: 2026-08-22
Last updated: Phase 4-17 remediation
"""
from pathlib import Path

MATRIX_PATH = Path("docs/remediation/architecture-compliance-matrix.md")

# All rules from the framework (P1-P7, R1-R7).
RULES = {
    "P1": {
        "name": "Primacy of Observation",
        "description": "Observation captures reality; it never interprets, predicts, or acts.",
        "implementation": [
            {
                "location": "libs/perception/observation.py",
                "enforcement": "Observation model is frozen; no prediction/interpretation fields",
                "test": "tests/architecture/test_cognitive_invariants.py::test_observation_never_executes_action",
            },
            {
                "location": "infrastructure/docker/init-sql/01-schema.sql",
                "enforcement": "All canonical tables have immutability triggers (UPDATE/DELETE blocked)",
                "test": "tests/architecture/test_cognitive_invariants.py::test_canonical_tables_have_immutability_triggers",
            },
            {
                "location": "libs/perception/context.py",
                "enforcement": "Context is append-only; activation lifecycle managed via is_active flag",
                "test": "tests/architecture/test_cognitive_invariants.py::test_one_active_context_per_purpose_constraint",
            },
        ],
    },
    "P2": {
        "name": "Context Activation",
        "description": "Context is activated by coherence competition, never directly generated.",
        "implementation": [
            {
                "location": "libs/perception/context.py",
                "enforcement": "Context activation is atomic (INSERT+DEACTIVATE in single transaction)",
                "test": "Phase 5: save_context uses session.begin() for atomicity",
            },
            {
                "location": "infrastructure/db-migrations/phase5-context-activation-atomicity.sql",
                "enforcement": "UNIQUE partial index: idx_contexts_unique_active on (tenant_id, purpose) WHERE is_active = true",
                "test": "tests/architecture/test_cognitive_invariants.py::test_one_active_context_per_purpose_constraint",
            },
        ],
    },
    "P3": {
        "name": "Evidence is Input Only",
        "description": "Evidence is organized observations; it never mutates existing observations.",
        "implementation": [
            {
                "location": "libs/perception/evidence.py",
                "enforcement": "Evidence model is frozen; insert-only with ON CONFLICT DO NOTHING",
                "test": "Implicit via immutable schema triggers",
            },
        ],
    },
    "P4": {
        "name": "Hypothesis over Conclusion",
        "description": "Explanations of cause are Hypothesis, not Context or Pattern.",
        "implementation": [
            {
                "location": "libs/reasoning/hypothesis.py",
                "enforcement": "Hypothesis model is separate from Pattern/Context; has cause/alternative fields",
                "test": "tests/architecture/test_cognitive_invariants.py::test_each_concept_has_one_store",
            },
        ],
    },
    "P5": {
        "name": "Calibrated Confidence",
        "description": "No conclusion influences action without confidence calibration.",
        "implementation": [
            {
                "location": "libs/learning/confidence.py",
                "enforcement": "Confidence has calibration_justification and calibration_error_estimate",
                "test": "tests/architecture/test_cognitive_invariants.py::test_confidence_requires_provenance",
            },
            {
                "location": "apps/gateway/api-gateway/src/boundary.py",
                "enforcement": "validate_confidence_present requires confidence_id for commit/execute",
                "test": "tests/architecture/test_cognitive_invariants.py::test_decision_requires_confidence",
            },
        ],
    },
    "P6": {
        "name": "Deliberate Action",
        "description": "Recommendation proposes; Decision commits. They are separate.",
        "implementation": [
            {
                "location": "libs/action/recommendation.py + libs/action/decision.py",
                "enforcement": "Separate modules; Decision references confidence_id",
                "test": "tests/architecture/test_cognitive_invariants.py::test_recommendation_is_not_decision",
            },
        ],
    },
    "P7": {
        "name": "Framework Guides Code",
        "description": "The architecture is the authority; code adapts to it, not the reverse.",
        "implementation": [
            {
                "location": "AGENTS.md + docs/remediation/",
                "enforcement": "All references use canonical set (P1-P7, R1-R7) from framework",
                "test": "No rule numbers outside canonical set exist in codebase",
            },
        ],
    },
    "R1": {
        "name": "One Capability per Component",
        "description": "Each cognitive concept implements exactly one capability.",
        "implementation": [
            {
                "location": "libs/ (perception|reasoning|learning|action)",
                "enforcement": "Each directory has exactly one store per concept",
                "test": "tests/architecture/test_cognitive_invariants.py::test_each_concept_has_one_store",
            },
        ],
    },
    "R2": {
        "name": "Cognitive Contract",
        "description": "Each component has a documented contract defining its inputs/outputs.",
        "implementation": [
            {
                "location": "apps/gateway/api-gateway/src/boundary.py",
                "enforcement": "CANONICAL_FLOW defines valid transitions; check_boundary enforces them",
                "test": "tests/architecture/test_cognitive_invariants.py::test_boundary_module_exists",
            },
        ],
    },
    "R3": {
        "name": "Boundary Enforcement",
        "description": "The gateway enforces cognitive boundary rules at ingestion time.",
        "implementation": [
            {
                "location": "apps/gateway/api-gateway/src/boundary.py",
                "enforcement": "check_boundary validates action type + confidence presence",
                "test": "tests/gateway/api-gateway/tests/test_boundary.py",
            },
        ],
    },
    "R4": {
        "name": "Confidence Before Action",
        "description": "No conclusion influences action without confidence.",
        "implementation": [
            {
                "location": "apps/gateway/api-gateway/src/boundary.py",
                "enforcement": "validate_confidence_present blocks commit/execute without confidence_id",
                "test": "tests/gateway/api-gateway/tests/test_gateway_service.py::test_enforce_boundary_*",
            },
        ],
    },
    "R5": {
        "name": "Confidence Provenance",
        "description": "Confidence must include justification and calibration data.",
        "implementation": [
            {
                "location": "libs/learning/confidence.py",
                "enforcement": "Confidence model has calibration_justification, calibration_error_estimate",
                "test": "tests/architecture/test_cognitive_invariants.py::test_confidence_requires_provenance",
            },
        ],
    },
    "R6": {
        "name": "Tenant Isolation",
        "description": "Every query is scoped to a tenant; cross-tenant requires superadmin.",
        "implementation": [
            {
                "location": "libs/access/tenant_scope.py",
                "enforcement": "AuthorizationContext validates tenant match; cross_tenant_allowed checks role",
                "test": "tests/gateway/api-gateway/tests/test_tenant_scope.py",
            },
            {
                "location": "libs/learning/confidence.py",
                "enforcement": "All confidence queries include tenant_id in WHERE clause",
                "test": "tests/architecture/test_cognitive_invariants.py::test_confidence_is_tenant_scoped",
            },
        ],
    },
    "R7": {
        "name": "No Rule Invention",
        "description": "Code must not invent rule numbers outside the canonical set.",
        "implementation": [
            {
                "location": "AGENTS.md + prompt files",
                "enforcement": "Canonical policy: no rule numbers outside P1-P7, R1-R7",
                "test": "Policy enforced by agent instructions; verifiable via grep",
            },
        ],
    },
}


def generate_matrix_markdown() -> str:
    """Generate the compliance matrix as markdown."""
    lines = [
        "# Architecture Compliance Matrix — Company OS Monitor",
        "",
        "Maps each cognitive design rule to its implementation in the product.",
        "Every row documents WHERE and HOW the rule is enforced.",
        "",
        "Generated: 2026-08-22",
        "Last updated: Phase 4-17 remediation",
        "",
        "---",
        "",
    ]

    for rule_id, rule in RULES.items():
        lines.append(f"## {rule_id} — {rule['name']}")
        lines.append("")
        lines.append(f"*{rule['description']}*")
        lines.append("")
        lines.append("| Location | Enforcement | Test |")
        lines.append("|----------|-------------|------|")
        for impl in rule["implementation"]:
            lines.append(
                f"| `{impl['location']}` | {impl['enforcement']} | `{impl['test']}` |"
            )
        lines.append("")

    return "\n".join(lines)


def write_matrix() -> None:
    """Write the compliance matrix to docs."""
    MATRIX_PATH.parent.mkdir(parents=True, exist_ok=True)
    MATRIX_PATH.write_text(generate_matrix_markdown(), encoding="utf-8")
    print(f"Compliance matrix written to {MATRIX_PATH}")  # noqa: T201


if __name__ == "__main__":
    write_matrix()
