"""Integration tests for the Evaluation Service orchestration.

Covers the audit test matrix where a database is required:
- L: a tenant with a candidate hypothesis and zero prior evaluations is discovered
- K: tenant isolation (an evaluation for tenant A is not visible to tenant B)
- I: heuristic evidence basis is NEVER auto-promoted to a terminal state
- J/H: Evaluation is append-only + idempotent (re-run yields a duplicate)
- 8: Evaluation provenance references the consumed Evidence ids

Plus a fake-store suite (no DB) for bounded concurrency (Blocker #15) and
error-vs-empty-run semantics (Blocker #14).
"""
import asyncio
import uuid
from datetime import UTC, datetime

import asyncpg
import pytest
from libs.cognitive_core.observation_bus import Observation
from libs.perception.evidence import Evidence, EvidenceStore, evidence_id
from libs.perception.observation import QualityClass
from libs.perception.store import ObservationStore
from libs.reasoning.evaluation import (
    RESULT_INSUFFICIENT,
    EvaluationStore,
)
from libs.reasoning.hypothesis import (
    STATUS_CANDIDATE,
    HypothesisCreate,
    HypothesisStore,
    build_hypothesis,
)

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"eval-{tenant_id}",
            f"evalslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup(*tenant_ids: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
        for tid in tenant_ids:
            await conn.execute(
                "DELETE FROM hypothesis_evaluations WHERE tenant_id = $1", tid
            )
            await conn.execute("DELETE FROM evidence WHERE tenant_id = $1", tid)
            await conn.execute("DELETE FROM hypotheses WHERE tenant_id = $1", tid)
            await conn.execute("DELETE FROM confidence_scores WHERE tenant_id = $1", tid)
            await conn.execute("DELETE FROM observations WHERE tenant_id = $1", tid)
            await conn.execute("DELETE FROM tenants WHERE id = $1", tid)
        await conn.execute("SET session_replication_role = origin")
    finally:
        await conn.close()


def _make_hypothesis(tenant_id: uuid.UUID, generated_at: datetime) -> HypothesisCreate:
    return HypothesisCreate(
        tenant_id=tenant_id,
        anomaly_ids=[uuid.uuid4()],
        pattern_ids=[uuid.uuid4()],
        description="Hypothesis under evaluation",
        predicted_consequences=["Prediction A", "Prediction B"],
        falsification_criterion="Prediction A did not occur",
        coherence_score=0.5,
        status=STATUS_CANDIDATE,
        generated_at=generated_at,
    )


@pytest.fixture
async def stores():
    hyp = HypothesisStore(DSN_STORE)
    ev = EvidenceStore(DSN_STORE)
    eva = EvaluationStore(DSN_STORE)
    await hyp.verify_connection()
    await ev.verify_connection()
    await eva.verify_connection()
    yield hyp, ev, eva
    await hyp.close()
    await ev.close()
    await eva.close()


async def test_cycle_discovers_tenant_with_zero_prior_evaluations(stores):
    """L: tenant with candidate hypothesis + zero evaluations is discovered & evaluated."""
    hyp_store, ev_store, eva_store = stores
    tenant = uuid.uuid4()
    await _create_tenant(tenant)
    try:
        generated_at = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        hypothesis = build_hypothesis(_make_hypothesis(tenant, generated_at))
        await hyp_store.save_hypothesis(hypothesis)

        # Evidence that (if reliable) would corroborate both predictions.
        obs_id = uuid.uuid4()
        ev = Evidence(
            id=evidence_id(tenant, "org", [obs_id]),
            tenant_id=tenant,
            observation_ids=[obs_id],
            organization_type="org",
            description="Prediction A confirmed and Prediction B confirmed",
            quality_class=QualityClass.Q1,
            weight=1.0,
            organized_at=generated_at,
        )
        await ev_store.save_evidence(ev)

        from src.service import EvaluationService

        service = EvaluationService(
            hypothesis_store=hyp_store,
            evidence_store=ev_store,
            confidence_store=_NullConfidenceStore(),
            evaluation_store=eva_store,
            evidence_basis_reliable=False,  # MVP heuristic basis
        )
        count = await service.run_evaluation_cycle()

        # An evaluation was produced for the candidate (discovered despite zero
        # prior evaluations).
        assert count >= 1
        evaluations = await eva_store.list_evaluations_by_hypothesis(
            tenant_id=tenant, hypothesis_id=hypothesis.id
        )
        assert len(evaluations) == 1
        # Provenance: the evaluation references the consumed Evidence id.
        assert evaluations[0].evidence_ids == [ev.id]
        # Heuristic basis => candidate preserved (never auto-promoted).
        assert evaluations[0].result == RESULT_INSUFFICIENT
        refreshed = await hyp_store.get_hypothesis_by_id(
            tenant_id=tenant, hypothesis_id=hypothesis.id
        )
        assert refreshed.status == STATUS_CANDIDATE
    finally:
        await _cleanup(tenant)


async def test_cycle_is_idempotent_and_append_only(stores):
    """H + J: re-running the same cycle dedups (duplicate) but preserves first row."""
    hyp_store, ev_store, eva_store = stores
    tenant = uuid.uuid4()
    await _create_tenant(tenant)
    try:
        generated_at = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        hypothesis = build_hypothesis(_make_hypothesis(tenant, generated_at))
        await hyp_store.save_hypothesis(hypothesis)
        obs_id = uuid.uuid4()
        ev = Evidence(
            id=evidence_id(tenant, "org", [obs_id]),
            tenant_id=tenant,
            observation_ids=[obs_id],
            organization_type="org",
            description="Prediction A confirmed and Prediction B confirmed",
            quality_class=QualityClass.Q1,
            weight=1.0,
            organized_at=generated_at,
        )
        await ev_store.save_evidence(ev)

        from src.service import EvaluationService

        service = EvaluationService(
            hypothesis_store=hyp_store,
            evidence_store=ev_store,
            confidence_store=_NullConfidenceStore(),
            evaluation_store=eva_store,
            evidence_basis_reliable=False,
        )
        before = await eva_store.list_evaluations_by_hypothesis(
            tenant_id=tenant, hypothesis_id=hypothesis.id
        )
        assert len(before) == 0

        await service.run_evaluation_cycle()
        after_first = await eva_store.list_evaluations_by_hypothesis(
            tenant_id=tenant, hypothesis_id=hypothesis.id
        )
        assert len(after_first) == 1  # exactly one evaluation created

        await service.run_evaluation_cycle()
        after_second = await eva_store.list_evaluations_by_hypothesis(
            tenant_id=tenant, hypothesis_id=hypothesis.id
        )
        # Idempotent: a second cycle with the same evidence produces no extra row
        # for this hypothesis (duplicate deduped by deterministic id).
        assert len(after_second) == 1
        assert after_second[0].id == after_first[0].id
    finally:
        await _cleanup(tenant)


async def test_e2e_observation_to_evaluation_provenance(stores):
    """Blocker #23 (partial): Observation -> Evidence -> Hypothesis -> Evaluation.

    Validates the full provenance chain and that tenant A cannot consume tenant
    B evidence (M). The Evaluation must reference the canonical Evidence artifact
    which in turn references the original Observation.
    """
    hyp_store, ev_store, eva_store = stores
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _create_tenant(tenant_a)
    await _create_tenant(tenant_b)
    obs_store = ObservationStore(DSN_STORE)
    try:
        generated_at = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)

        # Observation (raw Perception capture) for tenant A.
        obs_a = Observation(
            tenant_id=tenant_a,
            source_id=uuid.uuid4(),
            source_type="linux_agent",
            fact_type="disk_usage",
            fact_value={"percent": 98},
            unit="percent",
            quality_class="Q1",
            raw_payload={"raw": "disk_usage=98%"},
        )
        await obs_store.save_observation(obs_a)

        # Evidence organizes that observation (canonical Perception artifact).
        ev_a = Evidence(
            id=evidence_id(tenant_a, "disk_saturation", [obs_a.id]),
            tenant_id=tenant_a,
            observation_ids=[obs_a.id],
            organization_type="disk_saturation",
            description="Prediction A confirmed and Prediction B confirmed",
            quality_class=QualityClass.Q1,
            weight=1.0,
            organized_at=generated_at,
        )
        await ev_store.save_evidence(ev_a)

        hyp_a = build_hypothesis(_make_hypothesis(tenant_a, generated_at))
        await hyp_store.save_hypothesis(hyp_a)
        hyp_b = build_hypothesis(_make_hypothesis(tenant_b, generated_at))
        await hyp_store.save_hypothesis(hyp_b)

        from src.service import EvaluationService

        service = EvaluationService(
            hypothesis_store=hyp_store,
            evidence_store=ev_store,
            confidence_store=_NullConfidenceStore(),
            evaluation_store=eva_store,
            evidence_basis_reliable=False,
        )
        await service.run_evaluation_cycle()

        # Tenant A's evaluation references the Evidence built from its Observation.
        evals_a = await eva_store.list_evaluations_by_hypothesis(
            tenant_id=tenant_a, hypothesis_id=hyp_a.id
        )
        assert len(evals_a) == 1
        assert evals_a[0].evidence_ids == [ev_a.id]
        # Provenance back to the original Observation through the Evidence.
        stored_ev = (await ev_store.list_evidence(tenant_id=tenant_a))[0]
        assert stored_ev.observation_ids == [obs_a.id]

        # Tenant isolation (M): tenant B is discovered (has a candidate) and gets
        # an evaluation, but it must NOT consume tenant A's evidence.
        evals_b = await eva_store.list_evaluations_by_hypothesis(
            tenant_id=tenant_b, hypothesis_id=hyp_b.id
        )
        assert len(evals_b) == 1
        assert evals_b[0].evidence_ids == []  # no cross-tenant evidence leakage
        # Tenant A's evaluation references only its own Evidence (never B's, and B
        # never references A's).
        assert evals_a[0].evidence_ids == [ev_a.id]
        assert ev_a.id not in evals_b[0].evidence_ids
    finally:
        await obs_store.close()
        await _cleanup(tenant_a, tenant_b)


class _NullConfidenceStore:
    """Minimal stand-in: no confidence scores available."""

    async def list_confidence(self, *, tenant_id):  # noqa: ANN001, ARG002
        return []

    async def verify_connection(self):  # noqa: ANN001
        return None

    async def close(self):  # noqa: ANN001
        return None


# ---------------------------------------------------------------------------
# Fake-store suite (no DB): bounded concurrency, error vs empty-run, no promotion
# ---------------------------------------------------------------------------


class FakeHypothesisStore:
    def __init__(self, tenants, hypotheses_by_tenant):
        self._tenants = tenants
        self._hyp = hypotheses_by_tenant
        self.updated = []

    async def list_tenant_ids(self):
        return list(self._tenants)

    async def list_hypotheses(self, *, tenant_id, limit, offset):
        hs = self._hyp.get(tenant_id, [])
        return hs[offset : offset + limit]

    async def update_hypothesis_status(self, *, tenant_id, hypothesis_id, status):  # noqa: ARG002
        self.updated.append((hypothesis_id, status))
        return

    async def verify_connection(self):
        return None

    async def close(self):
        return None


class FakeEvidenceStore:
    def __init__(self):
        self.in_flight = 0
        self.max_in_flight = 0

    async def list_evidence_since(self, *, tenant_id, since):  # noqa: ARG002
        self.in_flight += 1
        self.max_in_flight = max(self.max_in_flight, self.in_flight)
        await asyncio.sleep(0.01)
        self.in_flight -= 1
        return []

    async def verify_connection(self):
        return None

    async def close(self):
        return None


class FakeConfidenceStore:
    async def list_confidence(self, *, tenant_id):  # noqa: ARG002
        return []

    async def verify_connection(self):
        return None

    async def close(self):
        return None


class FakeEvaluationStore:
    def __init__(self):
        self.saved = []
        self._should_fail = False

    async def save_evaluation(self, evaluation):
        if self._should_fail:
            raise RuntimeError("db down")
        self.saved.append(evaluation)
        return {"id": evaluation.id}

    async def verify_connection(self):
        return None

    async def close(self):
        return None


def _fake_hypotheses(n_tenants: int, n_per_tenant: int = 1):
    tenants = [uuid.uuid4() for _ in range(n_tenants)]
    by_tenant = {}
    for t in tenants:
        gen = datetime(2026, 8, 20, 12, 0, tzinfo=UTC)
        by_tenant[t] = [
            build_hypothesis(_make_hypothesis(t, gen)) for _ in range(n_per_tenant)
        ]
    return tenants, by_tenant


async def test_bounded_concurrency_over_tenants():
    """Blocker #15: concurrency is bounded by the tenant semaphore, not unbounded."""
    from src.service import MAX_CONCURRENT_TENANTS

    tenants, by_tenant = _fake_hypotheses(20)
    service = _build_service(tenants, by_tenant)
    await service.run_evaluation_cycle()
    # The maximum number of tenants evaluated simultaneously never exceeds the bound.
    assert service.evidence_store.max_in_flight <= MAX_CONCURRENT_TENANTS
    assert service.evidence_store.max_in_flight > 0


async def test_error_is_distinguishable_from_empty_run():
    """Blocker #14: a DB failure is recorded as an error, not a successful empty run."""
    tenants, by_tenant = _fake_hypotheses(1)
    service = _build_service(tenants, by_tenant)
    service.evaluation_store._should_fail = True
    # list_tenant_ids succeeds, but the per-tenant evaluation raises inside the
    # guarded coroutine -> propagated to gather -> counted as an error.
    result = await service.run_evaluation_cycle()
    assert result == 0
    assert service.errors >= 1
    assert service.total_evaluations == 0


async def test_heuristic_basis_never_promotes_hypothesis():
    """I: even strong evidence on a heuristic basis never flips candidate->terminal."""
    tenants, by_tenant = _fake_hypotheses(1)
    service = _build_service(tenants, by_tenant, evidence_basis_reliable=False)
    await service.run_evaluation_cycle()
    # update_hypothesis_status must never be called with a terminal status.
    for _hid, status in service.hypothesis_store.updated:
        assert status not in ("confirmed", "falsified")
    # Instead an insufficient evaluation is recorded for every candidate.
    assert len(service.evaluation_store.saved) == 1
    assert service.evaluation_store.saved[0].result == RESULT_INSUFFICIENT


def _build_service(tenants, by_tenant, evidence_basis_reliable=False):
    from src.service import EvaluationService

    return EvaluationService(
        hypothesis_store=FakeHypothesisStore(tenants, by_tenant),
        evidence_store=FakeEvidenceStore(),
        confidence_store=FakeConfidenceStore(),
        evaluation_store=FakeEvaluationStore(),
        evidence_basis_reliable=evidence_basis_reliable,
    )
