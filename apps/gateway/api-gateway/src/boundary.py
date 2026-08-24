"""Cognitive Boundary rules (R3) - pure, tested, no I/O.

Encodes ``procedural_memory/cognitive_boundary.yaml`` (docs/04) as data +
pure functions: the canonical flow adjacency, the flows the gateway permits,
the confidence requirement (R4) and the authority requirement (R5) for action
execution. This is the enforcement contract of the Cognitive Boundary (R3) -
perception and reasoning inform action but never execute it without explicit
authorization (P6).

Phase 2 (Confidence Provenance Hardening): ``validate_confidence_present``
now requires ``confidence_id`` and validates it through a store adapter.
Client-supplied ``confidence_score`` is IGNORED — the store returns the
authoritative score. This prevents a client from fabricating a high confidence
score to bypass calibration (R4).
"""
from typing import Any, Protocol

from libs.access.errors import AccessError

# Canonical cognitive flow (cognitive-architecture.md). Each concept may only
# advance to its DIRECT successor in the pipeline: any other transition is a
# shortcut and is blocked by the gateway.
CANONICAL_FLOW: dict[str, frozenset[str]] = {
    "observation": frozenset({"evidence"}),
    "evidence": frozenset({"context"}),
    "context": frozenset({"pattern"}),
    "pattern": frozenset({"anomaly"}),
    "anomaly": frozenset({"hypothesis"}),
    "hypothesis": frozenset({"insight"}),
    "insight": frozenset({"recommendation"}),
    "recommendation": frozenset({"decision"}),
    "decision": frozenset({"execution"}),
}

# Boundary: raw observations are NEVER exposed to Reasoning/Action directly
# (perception_to_reasoning: ONLY Evidence -> Context).
RAW_OBSERVATIONS_NEVER_EXPOSED = True

# Boundary: reasoning_to_action - only Recommendation (with Confidence) ->
# Decision. Pattern/Anomaly/Hypothesis never trigger alerts/actions directly.
REASONING_TO_ACTION_ALLOWED_SOURCE = "recommendation"
REASONING_TO_ACTION_ALLOWED_TARGET = "decision"

# R4: every Recommendation -> Decision transition must carry a calibrated
# Confidence (Sprint 8). The gateway validates its presence in the payload.
CONFIDENCE_REQUIRED_ACTIONS: frozenset[str] = frozenset({"propose", "commit"})

# R5 / action_execution: every execution requires explicit authority binding
# (the token's role). Allowed actions the gateway validates (never executes).
ACTIONS: frozenset[str] = frozenset({"read", "propose", "ack", "commit", "execute"})

# Action -> required Decision Authority permission (libs.access.rbac).
ACTION_PERMISSION: dict[str, str] = {
    "read": "read",
    "propose": "propose",
    "ack": "ack",
    "commit": "commit",
    "execute": "execute",
}


class BoundaryViolationError(AccessError):
    """A structural Cognitive Boundary rule was violated (R3)."""


class ConfidenceProvenanceError(AccessError):
    """Confidence could not be verified against the store (R4)."""


class ConfidenceStoreAdapter(Protocol):
    """Protocol for the confidence store used by the boundary gate.

    The gateway injects this adapter so the boundary module stays pure
    (no direct DB imports — ADR-0002: external capability). The adapter
    returns the authoritative confidence record or None if not found.
    """

    async def get_confidence_for_boundary(
        self,
        *,
        tenant_id: str,
        confidence_id: str,
        expected_target_type: str,
        expected_target_id: str | None = None,
    ) -> dict[str, Any] | None: ...


def is_canonical_flow(source: str, target: str) -> bool:
    """Whether a transition between pipeline concepts follows the canonical flow.

    Blocking shortcuts implements the boundary: observation -> action, pattern ->
    alert, anomaly -> recommendation, etc. are all FALSE here.
    """
    return target in CANONICAL_FLOW.get(source, frozenset())


def validate_confidence_present(payload: dict[str, Any] | None) -> bool:
    """R4: the payload carries a confidence_id (required for provenance).

    Client-supplied confidence_score is NOT sufficient — it must be verified
    against the store. This function only checks structural presence.
    """
    payload = payload or {}
    return bool(payload.get("confidence_id"))


async def validate_confidence_binding(
    *,
    store: ConfidenceStoreAdapter,
    tenant_id: str,
    confidence_id: str,
    expected_target_type: str,
    expected_target_id: str | None = None,
) -> dict[str, Any]:
    """R4: verify confidence exists, belongs to tenant, and matches target.

    Returns the authoritative confidence record from the store.
    Raises ConfidenceProvenanceError if verification fails.

    The client's confidence_score is IGNORED — the store provides the
    authoritative score. This prevents score fabrication.
    """
    record = await store.get_confidence_for_boundary(
        tenant_id=tenant_id,
        confidence_id=confidence_id,
        expected_target_type=expected_target_type,
        expected_target_id=expected_target_id,
    )
    if record is None:
        raise ConfidenceProvenanceError(
            f"confidence_id {confidence_id!r} not found or does not match "
            f"tenant={tenant_id!r} target_type={expected_target_type!r}"
        )
    return record


def boundary_gate(action: str, payload: dict[str, Any] | None) -> str:
    """Classify an action against the boundary rules (pure).

    Returns "ok" or a short reason string (missing_confidence /
    unknown_action). Role authorization is a separate check (the gateway's
    authorization step); this only enforces the STRUCTURAL boundary.
    """
    if action not in ACTIONS:
        return "unknown_action"
    if action in CONFIDENCE_REQUIRED_ACTIONS and not validate_confidence_present(
        payload
    ):
        return "missing_confidence"
    return "ok"


def check_boundary(action: str, payload: dict[str, Any] | None) -> None:
    """Raise BoundaryViolationError when the boundary is violated (R3)."""
    reason = boundary_gate(action, payload)
    if reason == "unknown_action":
        raise BoundaryViolationError(
            f"action {action!r} is not a declared pipeline action "
            f"(declared: {sorted(ACTIONS)})"
        )
    if reason == "missing_confidence":
        raise BoundaryViolationError(
            "Recommendation -> Decision requires a calibrated Confidence "
            "(R4): payload must carry confidence_id (verified against store)"
        )