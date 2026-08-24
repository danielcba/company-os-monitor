"""Action Executor — external execution capability (Phase 11).

Decision NO ejecuta por sí misma. El Action Executor es un componente
externo al capability Decision.

Flujo formal:
    Recommendation → Confidence Gate → Decision → Execution Authorization → Action Executor

Phase 11: Formaliza que:
- Decision es un registro de compromiso, no ejecuta
- Execution Authorization es un paso separado
- Action Executor es un componente externo
- Observation/Reasoning/Hypothesis/Pattern/Anomaly NUNCA ejecutan acciones directamente
"""
from dataclasses import dataclass
from typing import Any, Protocol

from libs.access.rbac import can, commit_risk_allowed


class ActionExecutor(Protocol):
    """Protocol for external action execution.

    The Action Executor is NOT part of the Decision capability.
    It receives an authorized execution request and performs the action.
    Decision records WHAT was committed; Action Executor performs HOW.
    """

    async def execute(
        self,
        *,
        decision_id: str,
        tenant_id: str,
        commitment: str,
        authority_id: str,
    ) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ExecutionAuthorization:
    """Authorization binding for action execution (R5).

    Separates the decision (what to do) from the authorization (who can do it).
    """

    decision_id: str
    authority_id: str
    role: str
    risk_tolerance: str
    tenant_id: str


def validate_execution_authorization(
    *,
    decision_role: str,
    executor_role: str,
    risk_tolerance: str,
) -> bool:
    """Validate that the executor has authority to execute this decision.

    Phase 11: Execution authorization is a separate step from decision commit.
    Only superadmin can execute; admin can commit but not execute.
    """
    # Executor must have execute permission.
    if not can(executor_role, "execute"):
        return False

    # Executor must have commit permission for this risk level.
    return commit_risk_allowed(executor_role, risk_tolerance)


# Capabilities that must NEVER execute actions directly.
# Observation, Reasoning, Hypothesis, Pattern, Anomaly → ejecutar acciones
# directamente is a cognitive violation.
NON_EXECUTING_CAPABILITIES: frozenset[str] = frozenset({
    "observation",
    "evidence",
    "context",
    "pattern",
    "anomaly",
    "hypothesis",
    "insight",
})


class NonExecutingCapabilityError(ValueError):
    """Raised when a non-executing capability attempts to execute actions."""

    def __init__(self, capability: str) -> None:
        super().__init__(
            f"capability {capability!r} must not execute actions directly; "
            f"only Decision → Action Executor may execute"
        )


def validate_no_direct_execution(capability: str) -> None:
    """Phase 11: Observation/Reasoning capabilities must never execute actions.

    Raises:
        NonExecutingCapabilityError: If the capability is in the non-executing set.
    """
    if capability in NON_EXECUTING_CAPABILITIES:
        raise NonExecutingCapabilityError(capability)
