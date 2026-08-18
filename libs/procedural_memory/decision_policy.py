"""Decision Policy Library - declarative commitment rules (Procedural Memory).

The Decision Policy is procedural memory (P3): a declarative catalogue of the
conditions under which the Commit capability may turn a proposed Recommendation
into a committed Decision. It NEVER reasons by itself - it only declares the
thresholds and constraints; the Committer (Action/Commit) applies them. This
mirrors how the Action Space declares the actions the system may propose: the
Decision Policy declares the commitment rules (confidence threshold, risk
tolerance, authority requirement) the system may apply per domain.

``DecisionPolicyEntry`` is frozen and versioned: revising a policy means
publishing a NEW ``policy_id`` (``*_v1``/``*_v2``), never mutating a published
one. ``min_confidence_for_commit`` is the Confidence threshold to commit
(docs/03: "Decision > 0.75 to commit"); ``min_confidence_irreversible`` is the
higher threshold above which a HIGH risk commitment is permitted (docs/03:
"> 0.9 for irreversible"); ``allowed_risk_tolerance`` declares which risk levels
(low/medium/high) the domain permits; ``requires_authority`` declares whether a
commitment authority is mandatory (true in the MVP: a Decision is a commitment
under authority; real user/RBAC binding is Sprint 12).
"""
from dataclasses import dataclass, field

from libs.procedural_memory.action_space import DOMAINS

# Canonical risk tolerance levels shared with the Decision model.
RISK_LOW = "low"
RISK_MEDIUM = "medium"
RISK_HIGH = "high"
RISK_TOLERANCES: frozenset[str] = frozenset({RISK_LOW, RISK_MEDIUM, RISK_HIGH})


@dataclass(frozen=True)
class DecisionPolicyEntry:
    """Declarative commitment rules for one domain (procedural memory).

    ``policy_id`` is versioned (``*_v1``/``*_v2``): revising a policy means
    publishing a NEW version, never mutating a published one. ``domain`` is one
    of DOMAINS. ``min_confidence_for_commit`` is the minimum calibrated
    Confidence to commit (>= 0.75); ``min_confidence_irreversible`` is the
    threshold for irreversible (high risk) commitments (>= 0.9) and must be
    >= ``min_confidence_for_commit``. ``allowed_risk_tolerance`` is the set of
    permitted risk levels for the domain (must be non-empty). ``requires_authority``
    declares whether the Commitment requires an authority binding. Declarative
    only - never reasoning.
    """

    policy_id: str
    domain: str
    min_confidence_for_commit: float = 0.75
    min_confidence_irreversible: float = 0.9
    allowed_risk_tolerance: frozenset[str] = field(
        default_factory=lambda: frozenset({RISK_LOW})
    )
    requires_authority: bool = True

    def __post_init__(self) -> None:
        if self.domain not in DOMAINS:
            raise ValueError(f"unknown domain: {self.domain}")  # noqa: TRY003
        if not self.policy_id.strip():
            raise ValueError("policy_id must not be empty")  # noqa: TRY003
        if not (0.0 <= self.min_confidence_for_commit <= 1.0):
            raise ValueError("min_confidence_for_commit must be in [0, 1]")  # noqa: TRY003
        if not (0.0 <= self.min_confidence_irreversible <= 1.0):
            raise ValueError("min_confidence_irreversible must be in [0, 1]")  # noqa: TRY003
        if self.min_confidence_irreversible < self.min_confidence_for_commit:
            raise ValueError(  # noqa: TRY003
                "min_confidence_irreversible must be >= min_confidence_for_commit"
            )
        if not self.allowed_risk_tolerance:
            raise ValueError("allowed_risk_tolerance must not be empty")  # noqa: TRY003
        unknown = self.allowed_risk_tolerance - RISK_TOLERANCES
        if unknown:
            raise ValueError(f"unknown risk tolerances: {sorted(unknown)}")  # noqa: TRY003


def _policy(  # noqa: PLR0913, PLR0917 - declarative factory for the catalogue
    policy_id: str,
    domain: str,
    min_confidence_for_commit: float,
    min_confidence_irreversible: float,
    risk_tolerances: tuple[str, ...],
    requires_authority: bool = True,
) -> DecisionPolicyEntry:
    return DecisionPolicyEntry(
        policy_id=policy_id,
        domain=domain,
        min_confidence_for_commit=min_confidence_for_commit,
        min_confidence_irreversible=min_confidence_irreversible,
        allowed_risk_tolerance=frozenset(risk_tolerances),
        requires_authority=requires_authority,
    )


# Initial declarative Decision Policy catalogue (docs/03 thresholds:
# "Decision > 0.75 to commit; > 0.9 for irreversible"). Per domain the permitted
# risk tolerance is declared explicitly: e.g. compute only tolerates up to
# medium risk, while storage/security declare all three levels.
DECISION_POLICY_LIBRARY: tuple[DecisionPolicyEntry, ...] = (
    _policy(
        "storage_commit_v1",
        "storage",
        0.75,
        0.9,
        (RISK_LOW, RISK_MEDIUM, RISK_HIGH),
    ),
    _policy(
        "compute_commit_v1",
        "compute",
        0.75,
        0.9,
        (RISK_LOW, RISK_MEDIUM),
    ),
    _policy(
        "security_commit_v1",
        "security",
        0.75,
        0.9,
        (RISK_LOW, RISK_MEDIUM, RISK_HIGH),
    ),
    _policy(
        "backup_commit_v1",
        "backup",
        0.75,
        0.9,
        (RISK_LOW, RISK_MEDIUM),
    ),
    _policy(
        "network_commit_v1",
        "network",
        0.75,
        0.9,
        (RISK_LOW, RISK_MEDIUM),
    ),
    _policy(
        "observability_commit_v1",
        "observability",
        0.75,
        0.9,
        (RISK_LOW, RISK_MEDIUM, RISK_HIGH),
    ),
)

DECISION_POLICIES: dict[str, DecisionPolicyEntry] = {
    entry.policy_id: entry for entry in DECISION_POLICY_LIBRARY
}

# Declarative mapping domain -> policy id (procedural memory, never reasoning).
POLICY_BY_DOMAIN: dict[str, DecisionPolicyEntry] = {
    entry.domain: entry for entry in DECISION_POLICY_LIBRARY
}


def select_policy(
    policies: dict[str, DecisionPolicyEntry] | None = None,
    domain: str | None = None,
) -> DecisionPolicyEntry | None:
    """The Decision Policy of a domain (None if the domain has no declared policy).

    Only policies declared in the catalogue qualify; the Committer never invents
    a policy for an undeclared domain.
    """
    if domain is None:
        return None
    source = policies if policies is not None else POLICY_BY_DOMAIN
    return source.get(domain)


def apply_threshold_overrides(
    policy: DecisionPolicyEntry,
    min_confidence_for_commit: float | None = None,
    min_confidence_irreversible: float | None = None,
) -> DecisionPolicyEntry:
    """Re-publish a policy with per-deployment Confidence thresholds.

    Procedural memory stays canonical; ``DECISION_MIN_CONFIDENCE`` /
    ``DECISION_MIN_CONFIDENCE_IRREVERSIBLE`` (env, with the canonical defaults)
    override the published thresholds for a deployment without mutating the
    catalogue entry (a NEW frozen entry is returned).
    """
    if min_confidence_for_commit is None and min_confidence_irreversible is None:
        return policy
    return DecisionPolicyEntry(
        policy_id=policy.policy_id,
        domain=policy.domain,
        min_confidence_for_commit=(
            policy.min_confidence_for_commit
            if min_confidence_for_commit is None
            else min_confidence_for_commit
        ),
        min_confidence_irreversible=(
            policy.min_confidence_irreversible
            if min_confidence_irreversible is None
            else min_confidence_irreversible
        ),
        allowed_risk_tolerance=policy.allowed_risk_tolerance,
        requires_authority=policy.requires_authority,
    )