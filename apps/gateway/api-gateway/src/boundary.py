"""Cognitive Boundary rules (R3) - pure, tested, no I/O.

Encodes ``procedural_memory/cognitive_boundary.yaml`` (docs/04) as data +
pure functions: the canonical flow adjacency, the flows the gateway permits,
the confidence requirement (R4) and the authority requirement (R5) for action
execution. This is the enforcement contract of the Cognitive Boundary (R3) -
perception and reasoning inform action but never execute it without explicit
authorization (P6).
"""
from typing import Any

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


def is_canonical_flow(source: str, target: str) -> bool:
    """Whether a transition between pipeline concepts follows the canonical flow.

    Blocking shortcuts implements the boundary: observation -> action, pattern ->
    alert, anomaly -> recommendation, etc. are all FALSE here.
    """
    return target in CANONICAL_FLOW.get(source, frozenset())


def validate_confidence_present(payload: dict[str, Any] | None) -> bool:
    """R4: the payload carries a calibrated Confidence (id or score)."""
    payload = payload or {}
    return bool(
        payload.get("confidence_id") or payload.get("confidence_score") is not None
    )


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
            "(R4): payload must carry confidence_id or confidence_score"
        )