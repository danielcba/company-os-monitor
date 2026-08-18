"""Decision Committer - Action/Commit capability (pure, no I/O).

Implements the Decision concept's Cognitive Contract for the MVP:
Input = Recommendation + its calibrated Confidence + Decision Policy + Authority;
Transform = validate the commitment conditions (R4: calibrated Confidence above
the policy threshold; risk tolerance allowed by the policy; authority bound) and
select the course of action; Output = a DecisionCreate with a DEFINITIVE
``commitment``, falsifiable ``expected_outcomes`` (prediction + verifiable_by +
deadline, declared BEFORE execution per the Decision spec) and the authority
under which it was taken. All functions here are pure and deterministic: same
inputs always produce the same Decision (the deterministic decision_id then
makes re-committing idempotent).

"A decision ends deliberation. It does not end learning." and "This rule
converts every decision from an act of authority into an experiment." The
Committer RECORDS the Decision; it NEVER executes real-world actions (P6:
execution, authorization and the expected vs actual Learning loop are future
phases - Sprints 11/12 and the Learning layer).

Anti-indefinition: ``commitment`` is a definitive sentence (the concept: "A
decision is a commitment with an owner, a timeline, and expected outcomes");
a vague intention ("Let's keep an eye on it.", "We should probably ...") is a
Non-example and never produced here.
"""
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from libs.action.decision import (
    RISK_HIGH,
    RISK_LOW,
    STATUS_COMMITTED,
    DecisionCreate,
)
from libs.action.recommendation import Recommendation
from libs.learning.confidence import Confidence
from libs.procedural_memory.action_space import ACTION_SPACE_LIBRARY
from libs.procedural_memory.decision_policy import DecisionPolicyEntry

# Fixed namespace for the deterministic policy-derived commitment authority
# (MVP: no user/auth yet; Sprint 12 replaces this with real user roles).
DECISION_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-000000000082")

# Eligibility outcomes of a Recommendation for commitment (pure classification).
COMMITTABLE = "committable"
BELOW_CONFIDENCE = "below_confidence"
RISK_NOT_ALLOWED = "risk_not_allowed"
NO_AUTHORITY = "no_authority"
NO_POLICY = "no_policy"

# Declarative verification metric per domain (docs/04 Decision Schema:
# ``verifiable_by`` is the observable metric the prediction is checked against).
VERIFICATION_METRIC_BY_DOMAIN: dict[str, str] = {
    "storage": "disk_free_percent",
    "compute": "service_status",
    "security": "auth_failure_rate",
    "backup": "backup_job_status",
    "network": "traffic_rule_status",
    "observability": "alert_threshold_status",
}

# Declarative evaluation window per domain (docs/05: the Learning loop compares
# expected vs actual at 30/60/90 days; MVP uses one declared deadline per domain).
DEADLINE_DAYS_BY_DOMAIN: dict[str, int] = {
    "storage": 90,
    "compute": 30,
    "security": 30,
    "backup": 90,
    "network": 30,
    "observability": 30,
}

# Declarative action key -> domain, built from the explicit Action Space
# catalogue (procedural memory): all permitted actions of one formulation come
# from a SINGLE Action Space entry, so the domain of a proposed Recommendation
# is recoverable from any of its considered alternatives.
ACTION_DOMAIN: dict[str, str] = {
    action: entry.domain
    for entry in ACTION_SPACE_LIBRARY
    for action in entry.allowed_actions
}


@dataclass(frozen=True)
class Authority:
    """The commitment authority under which a Decision is taken (MVP).

    ``authority_id`` is the bound authority (a user_id or a policy_id; in the
    MVP it is the deterministic policy-derived id - Sprint 12 replaces it with
    real user roles/RBAC). ``label`` names the authority for the recorded
    rationale. ``risk_tolerance`` is the declared risk level the authority
    commits under (low/medium/high), validated against the Decision Policy.
    """

    authority_id: uuid.UUID
    label: str
    risk_tolerance: str = RISK_LOW


def policy_authority_id(policy_id: str) -> uuid.UUID:
    """Deterministic commitment authority derived from a Decision Policy.

    MVP: there is no user/auth yet (Sprint 12). The commitment authority is the
    policy itself - a deterministic UUID derived from the ``policy_id`` - so
    every Decision carries an ``authority_id`` and the trace is complete.
    """
    return uuid.uuid5(DECISION_NAMESPACE, f"policy:{policy_id}")


def recommendation_domain(recommendation: Recommendation) -> str | None:
    """Resolve the Action Space domain of a proposed Recommendation (declarative).

    All permitted actions of one formulation come from a SINGLE Action Space
    entry (the Formulator chooses within one domain), so the domain is derived
    from any of the considered alternatives' action keys. Returns None when no
    declared binding applies: no Decision Policy -> no commit (the system never
    invents a policy).
    """
    for alternative in recommendation.alternatives_considered:
        domain = ACTION_DOMAIN.get(alternative.get("action"))
        if domain is not None:
            return domain
    return None


def resolve_risk_tolerance(
    confidence_score: float, policy: DecisionPolicyEntry
) -> str | None:
    """Declarative Confidence -> risk tolerance mapping, constrained by policy.

    docs/03: "Decision > 0.75 to commit; > 0.9 for irreversible". Below the
    commit threshold returns None (no commit). Otherwise the candidate level is
    ``high`` at/above ``min_confidence_irreversible`` and ``medium`` below it;
    the effective level is the MOST demanding one allowed by the policy without
    exceeding the candidate's risk ceiling (e.g. a compute policy that excludes
    high risk steps ``high`` down to ``medium``).
    """
    if confidence_score < policy.min_confidence_for_commit:
        return None
    candidate = (
        RISK_HIGH
        if confidence_score >= policy.min_confidence_irreversible
        else "medium"
    )
    order = {RISK_HIGH: 2, "medium": 1, RISK_LOW: 0}
    ceiling = order[candidate]
    best = None
    for level in policy.allowed_risk_tolerance:
        if order[level] <= ceiling and (best is None or order[level] > order[best]):
            best = level
    return best


def _validate(recommendation: Recommendation, confidence: Confidence) -> None:
    """Guard traceability invariants before committing (fail loudly)."""
    if confidence.id != recommendation.confidence_id:
        raise ValueError(
            "confidence must be the calibrated Confidence bound to the recommendation"
        )
    if confidence.tenant_id != recommendation.tenant_id:
        raise ValueError(
            "tenant mismatch across recommendation/confidence"
        )


def commit_eligibility(
    recommendation: Recommendation,
    confidence: Confidence,
    policy: DecisionPolicyEntry | None,
    authority: Authority | None,
) -> str:
    """Classify whether a Recommendation may be committed (pure, no I/O).

    Returns one of COMMITTABLE / BELOW_CONFIDENCE / RISK_NOT_ALLOWED /
    NO_AUTHORITY / NO_POLICY. Raises ValueError on traceability violations
    (confidence not bound to the recommendation, tenant mismatch).
    """
    if policy is None:
        return NO_POLICY
    _validate(recommendation, confidence)
    if policy.requires_authority and authority is None:
        return NO_AUTHORITY
    if confidence.confidence_score < policy.min_confidence_for_commit:
        return BELOW_CONFIDENCE
    if authority is None or authority.risk_tolerance not in policy.allowed_risk_tolerance:
        return RISK_NOT_ALLOWED
    if (
        authority.risk_tolerance == RISK_HIGH
        and confidence.confidence_score < policy.min_confidence_irreversible
    ):
        return RISK_NOT_ALLOWED
    return COMMITTABLE


def _definitive_clause(description: str) -> str:
    """The definitive directive of a proposed action, stripped of alternatives.

    The Recommendation templates may state an offer with a secondary option
    ("...o mover los datos a un destino..."); a Decision selects a DEFINITE
    course of action, so the commitment keeps the first (leading) directive and
    drops the trailing alternative clause.
    """
    clause = description.strip().split(" o ", maxsplit=1)[0].strip()
    return clause.rstrip(".,; ") + "."


def _deadline_iso(committed_at: datetime, domain: str) -> str:
    """ISO date of the declared evaluation window for the domain's outcomes."""
    days = DEADLINE_DAYS_BY_DOMAIN.get(domain, 30)
    return (committed_at + timedelta(days=days)).date().isoformat()


def build_commitment(
    recommendation: Recommendation, authority: Authority, deadline: str
) -> str:
    """The DEFINITIVE commitment statement (owner + timeline + outcomes).

    The concept: "A decision is a commitment with an owner, a timeline, and
    expected outcomes." The commitment names the selected course of action, the
    authority that binds it and the deadline when the expected outcomes are
    evaluated. Never a vague intention.
    """
    clause = _definitive_clause(recommendation.action_description)
    return (
        f"{clause} Compromiso registrado bajo la autoridad {authority.label} "
        f"(id {authority.authority_id}); outcomes esperados evaluados en {deadline}."
    )


def build_expected_outcomes(
    recommendation: Recommendation, policy: DecisionPolicyEntry, committed_at: datetime
) -> list[dict[str, str]]:
    """Falsifiable expected outcomes, declared BEFORE execution (R5 / Popper).

    Each recommendation consequence becomes an outcome with its ``prediction``
    (observable statement), ``verifiable_by`` (the observable metric) and
    ``deadline`` (the declared evaluation date). The comparison expected vs
    actual is the primary learning signal (P7, Learning loop - future phases).
    """
    consequences = list(recommendation.expected_consequences)
    if not consequences:
        raise ValueError(
            "cannot commit without falsifiable expected outcomes "
            "(recommendation has no expected_consequences)"
        )
    metric = VERIFICATION_METRIC_BY_DOMAIN.get(policy.domain, "system_metric")
    deadline = _deadline_iso(committed_at, policy.domain)
    return [
        {"prediction": consequence, "verifiable_by": metric, "deadline": deadline}
        for consequence in consequences
    ]


def commit(
    recommendation: Recommendation,
    confidence: Confidence,
    policy: DecisionPolicyEntry,
    authority: Authority,
) -> DecisionCreate | None:
    """Commit the best course of action (pure, no I/O).

    Validates the commitment conditions (confidence above the policy threshold,
    risk tolerance allowed, authority bound) and returns a ``DecisionCreate``
    with a DEFINITIVE ``commitment``, falsifiable ``expected_outcomes``
    (prediction + verifiable_by + deadline) and ``status='committed'`` - the
    Decision is RECORDED, never executed (P6). Returns None when the
    Recommendation is not eligible (the caller classifies the reason with
    ``commit_eligibility``). Deterministic: same inputs -> same Decision (the
    deterministic decision_id then makes re-committing idempotent).
    """
    if commit_eligibility(recommendation, confidence, policy, authority) != COMMITTABLE:
        return None
    committed_at = datetime.now(UTC)
    deadline = _deadline_iso(committed_at, policy.domain)
    return DecisionCreate(
        tenant_id=recommendation.tenant_id,
        recommendation_id=recommendation.id,
        confidence_id=recommendation.confidence_id,
        authority_id=authority.authority_id,
        commitment=build_commitment(recommendation, authority, deadline),
        expected_outcomes=build_expected_outcomes(recommendation, policy, committed_at),
        risk_tolerance=authority.risk_tolerance,
        status=STATUS_COMMITTED,
        committed_at=committed_at,
        executed_at=None,
        actual_outcomes=None,
    )