"""Cognitive Capability Policy — declarative boundary definitions (Phase 10).

Instead of a rigid successor list, this module defines a declarative policy
for each cognitive capability. This separates:

1. Capability transition
2. Boundary protection
3. Confidence gate
4. Decision authority
5. Execution authorization

The policy is the single source of truth. Runtime adapters consume it.

Phase 10: The Boundary is no longer a rigid state machine. Reasoning can:
- revisit stages
- compete between hypotheses/models
- branch
- return to earlier stages
- skip stages when the architecture allows

The boundary protects capabilities and prevents illegitimate bypasses,
but does NOT impede legitimate internal Reasoning cycles.
"""
from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class CapabilityPolicy:
    """Declarative policy for a single cognitive capability.

    Each field maps to a specific concern:
    - capability: the concept name (observation, evidence, etc.)
    - family: which cognitive family (perception, reasoning, learning, action)
    - allowed_inputs: concepts that can feed into this capability
    - allowed_outputs: concepts this capability can produce
    - confidence_required: whether this capability needs confidence before acting
    - authority_required: RBAC permission needed to invoke this capability
    - tenant_scoped: whether the capability is tenant-isolated
    - execution_authority: permission needed to execute (action layer only)
    """

    capability: str
    family: str
    allowed_inputs: frozenset[str]
    allowed_outputs: frozenset[str]
    confidence_required: bool = False
    authority_required: str = "read"
    tenant_scoped: bool = True
    execution_authority: str | None = None


# ---------------------------------------------------------------------------
# Canonical capability policies (single source of truth)
# ---------------------------------------------------------------------------

CAPABILITY_POLICIES: dict[str, CapabilityPolicy] = {
    # --- Perception ---
    "observation": CapabilityPolicy(
        capability="observation",
        family="perception",
        allowed_inputs=frozenset(),  # external data sources
        allowed_outputs=frozenset({"evidence"}),
        confidence_required=False,
        authority_required="read",
        tenant_scoped=True,
    ),
    "evidence": CapabilityPolicy(
        capability="evidence",
        family="perception",
        allowed_inputs=frozenset({"observation"}),
        allowed_outputs=frozenset({"context"}),
        confidence_required=False,
        authority_required="read",
        tenant_scoped=True,
    ),
    "context": CapabilityPolicy(
        capability="context",
        family="perception",
        allowed_inputs=frozenset({"evidence"}),
        allowed_outputs=frozenset({"pattern"}),
        confidence_required=False,
        authority_required="read",
        tenant_scoped=True,
    ),
    # --- Reasoning ---
    "pattern": CapabilityPolicy(
        capability="pattern",
        family="reasoning",
        allowed_inputs=frozenset({"context"}),
        allowed_outputs=frozenset({"anomaly"}),
        confidence_required=False,
        authority_required="read",
        tenant_scoped=True,
    ),
    "anomaly": CapabilityPolicy(
        capability="anomaly",
        family="reasoning",
        allowed_inputs=frozenset({"pattern"}),
        allowed_outputs=frozenset({"hypothesis"}),
        confidence_required=False,
        authority_required="read",
        tenant_scoped=True,
    ),
    "hypothesis": CapabilityPolicy(
        capability="hypothesis",
        family="reasoning",
        allowed_inputs=frozenset({"anomaly"}),
        allowed_outputs=frozenset({"insight"}),
        confidence_required=False,
        authority_required="read",
        tenant_scoped=True,
    ),
    "insight": CapabilityPolicy(
        capability="insight",
        family="reasoning",
        allowed_inputs=frozenset({"hypothesis"}),
        allowed_outputs=frozenset({"recommendation"}),
        confidence_required=False,
        authority_required="read",
        tenant_scoped=True,
    ),
    # --- Learning ---
    "confidence": CapabilityPolicy(
        capability="confidence",
        family="learning",
        allowed_inputs=frozenset({"hypothesis", "recommendation", "decision"}),
        allowed_outputs=frozenset(),  # confidence is a transversal capability
        confidence_required=False,
        authority_required="read",
        tenant_scoped=True,
    ),
    # --- Action ---
    "recommendation": CapabilityPolicy(
        capability="recommendation",
        family="action",
        allowed_inputs=frozenset({"insight"}),
        allowed_outputs=frozenset({"decision"}),
        confidence_required=True,  # R4: requires confidence
        authority_required="propose",
        tenant_scoped=True,
    ),
    "decision": CapabilityPolicy(
        capability="decision",
        family="action",
        allowed_inputs=frozenset({"recommendation"}),
        allowed_outputs=frozenset({"execution"}),
        confidence_required=True,  # R4: requires confidence
        authority_required="commit",
        tenant_scoped=True,
        execution_authority="execute",
    ),
    "execution": CapabilityPolicy(
        capability="execution",
        family="action",
        allowed_inputs=frozenset({"decision"}),
        allowed_outputs=frozenset(),  # terminal state
        confidence_required=True,
        authority_required="execute",
        tenant_scoped=True,
    ),
}


class CognitivePolicyStore(Protocol):
    """Protocol for accessing capability policies at runtime."""

    def get_policy(self, capability: str) -> CapabilityPolicy | None: ...

    def get_all_policies(self) -> dict[str, CapabilityPolicy]: ...


class DefaultPolicyStore:
    """Default in-memory policy store using CAPABILITY_POLICIES."""

    def get_policy(self, capability: str) -> CapabilityPolicy | None:
        return CAPABILITY_POLICIES.get(capability)

    def get_all_policies(self) -> dict[str, CapabilityPolicy]:
        return dict(CAPABILITY_POLICIES)


# ---------------------------------------------------------------------------
# Boundary validation functions
# ---------------------------------------------------------------------------


class CognitiveBoundaryViolation(Exception):
    """A cognitive boundary rule was violated."""


def validate_capability_transition(
    source: str,
    target: str,
    *,
    policy_store: CognitivePolicyStore | None = None,
) -> bool:
    """Check if a transition from source to target capability is allowed.

    Phase 10: Uses the declarative policy instead of a rigid adjacency list.
    Reasoning capabilities can have multiple allowed outputs and inputs.
    """
    store = policy_store or DefaultPolicyStore()
    source_policy = store.get_policy(source)
    if source_policy is None:
        return False
    return target in source_policy.allowed_outputs


def validate_confidence_requirement(
    capability: str,
    *,
    policy_store: CognitivePolicyStore | None = None,
) -> bool:
    """Check if a capability requires confidence before acting.

    Phase 10: Confidence requirement is part of the declarative policy.
    """
    store = policy_store or DefaultPolicyStore()
    policy = store.get_policy(capability)
    if policy is None:
        return False
    return policy.confidence_required


def validate_authority(
    capability: str,
    role: str,
    *,
    policy_store: CognitivePolicyStore | None = None,
) -> bool:
    """Check if a role has authority to invoke a capability.

    Phase 10: Authority is part of the declarative policy.
    Uses the existing RBAC module (libs.access.rbac).
    """
    from libs.access.rbac import can

    store = policy_store or DefaultPolicyStore()
    policy = store.get_policy(capability)
    if policy is None:
        return False
    return can(role, policy.authority_required)
