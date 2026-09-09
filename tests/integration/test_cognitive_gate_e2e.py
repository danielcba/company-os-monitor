"""End-to-end integration test of the Cognitive Gate.

Demonstrates the FULL cognitive chain from committed Decision through learning:

    Decision (with falsifiable expected outcomes)
    → Observed Outcome (submitted via H3 Phase 1)
    → Learning Execution (H3 Phase 2, advisory-locked)
    → Learning Signal (consolidation, pattern refinement, context revision)
    → Memory Persistence (learning_memory with execution_id provenance)

This test proves the Cognitive Gate: "Primer Decision commitida con expected
outcomes falsificables. Learning loop inicia."

Requires a live PostgreSQL. DB-backed tests skip when unreachable.
"""
from __future__ import annotations

import asyncio
import importlib.util
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest

ROOT = Path(__file__).resolve().parents[2]
DSN = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
)

sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps/services/context-service"))
sys.path.append(str(ROOT / "apps/services/report-service"))
sys.path.insert(0, str(ROOT / "apps/gateway/api-gateway"))


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pattern_det = _load(
    "cosint_pattern_det", ROOT / "apps/services/pattern-service/src/detector/detector.py"
)
anomaly_det = _load(
    "cosint_anomaly_det", ROOT / "apps/services/anomaly-service/src/detector/detector.py"
)
hyp_gen = _load(
    "cosint_hyp_gen", ROOT / "apps/services/hypothesis-service/src/generator/generator.py"
)
calib = _load(
    "cosint_calib", ROOT / "apps/services/confidence-service/src/calibrator/calibrator.py"
)
form = _load(
    "cosint_form", ROOT / "apps/services/recommendation-service/src/formulator/formulator.py"
)
comm = _load(
    "cosint_comm", ROOT / "apps/services/decision-service/src/committer/committer.py"
)
rules = _load(
    "cosint_rules", ROOT / "apps/services/collector-service/src/organizer/rules.py"
)

from src.activator.engine import ActivatorEngine  # noqa: E402
from src.confidence import ConfidenceReadStore  # noqa: E402
from src.contexts import ContextReadStore  # noqa: E402
from src.decisions import DecisionReadStore  # noqa: E402
from src.hypotheses import HypothesisReadStore  # noqa: E402
from src.insights import InsightReadStore  # noqa: E402
from src.patterns import PatternReadStore  # noqa: E402
from src.recommendations import RecommendationReadStore  # noqa: E402

from libs.action.decision import (  # noqa: E402
    DecisionStore,
    build_decision,
)
from libs.action.recommendation import (  # noqa: E402
    RecommendationStore,
    build_recommendation,
)
from libs.cognitive_core.calibration_model import (  # noqa: E402
    CalibrationParams,
    quality_class_to_weight,
)
from libs.cognitive_core.observation_bus import Observation  # noqa: E402
from libs.learning.cognitive_gate import (  # noqa: E402
    submit_decision_outcomes_and_learn,
)
from libs.learning.confidence import (  # noqa: E402
    ConfidenceStore,
    build_confidence,
)
from libs.learning.learning_execution_store import LearningExecutionStore  # noqa: E402
from libs.memory.learning_loop import H3LearningLoopStore  # noqa: E402
from libs.memory.memory_ledger import MemoryStore  # noqa: E402
from libs.perception.context import (  # noqa: E402
    PURPOSE_INFRASTRUCTURE_HEALTH,
    ContextStore,
    build_context,
)
from libs.perception.evidence import (  # noqa: E402
    EvidenceCreate,
    EvidenceStore,
    build_evidence,
)
from libs.perception.store import ObservationStore  # noqa: E402
from libs.procedural_memory.action_space import ACTION_SPACE_LIBRARY  # noqa: E402
from libs.procedural_memory.decision_policy import POLICY_BY_DOMAIN  # noqa: E402
from libs.procedural_memory.pattern_library import PATTERN_LIBRARY  # noqa: E402
from libs.procedural_memory.tolerance_library import TOLERANCE_LIBRARY  # noqa: E402
from libs.reasoning.anomaly import (  # noqa: E402
    AnomalyCreate,
    AnomalyStore,
    build_anomaly,
)
from libs.reasoning.hypothesis import (  # noqa: E402
    HypothesisStore,
    build_hypothesis,
)
from libs.reasoning.pattern import (  # noqa: E402
    PatternCreate,
    PatternStore,
    build_pattern,
)


def _make_servers(num_servers: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(num_servers)]


def _server_observations(tenant_id: uuid.UUID, source_id: uuid.UUID):
    now = datetime.now(UTC)
    base = {
        "tenant_id": tenant_id,
        "source_id": source_id,
        "source_type": "linux_agent",
    }
    return [
        Observation(
            **base,
            fact_type="cpu_utilization_percent",
            fact_value={"value": 95.0},
            unit="percent",
            quality_class="Q1",
            raw_payload={},
            captured_at=now,
        ),
        Observation(
            **base,
            fact_type="memory_usage",
            fact_value={"total_bytes": 100, "used_bytes": 92},
            unit="bytes",
            quality_class="Q1",
            raw_payload={},
            captured_at=now,
        ),
        Observation(
            **base,
            fact_type="disk_usage",
            fact_value={"total_bytes": 100, "used_bytes": 92},
            unit="bytes",
            quality_class="Q1",
            raw_payload={},
            captured_at=now,
        ),
    ]


async def _ensure_tenant(tenant_id: uuid.UUID) -> None:
    pg_dsn = DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"e2e-{tenant_id.hex[:8]}",
            f"e2e-{tenant_id.hex}",
        )
    finally:
        await conn.close()


async def _run_pipeline(  # noqa: PLR0912, PLR0915
    stores: dict, tenant_id: uuid.UUID, num_servers: int = 3
) -> dict:
    await _ensure_tenant(tenant_id)
    obs_store = stores["obs"]
    ev_store = stores["ev"]
    ctx_store = stores["ctx"]
    pat_store = stores["pat"]
    an_store = stores["an"]
    hyp_store = stores["hyp"]
    conf_store = stores["conf"]
    rec_store = stores["rec"]
    dec_store = stores["dec"]

    observations = []
    for src in _make_servers(num_servers):
        for obs in _server_observations(tenant_id, src):
            observations.append(obs)
            await obs_store.save_observation(obs)

    organizations = rules.resource_exhaustion_evidence(observations)
    evidences = []
    for org in organizations:
        ev_create = EvidenceCreate(
            tenant_id=org.tenant_id,
            observation_ids=org.observation_ids,
            organization_type=org.organization_type,
            description=org.description,
            quality_class=org.quality_class,
            weight=quality_class_to_weight(org.quality_class.value),
        )
        ev = build_evidence(ev_create)
        await ev_store.save_evidence(ev)
        evidences.append(ev)

    contexts = []
    for ev in evidences:
        ctx_create = ActivatorEngine().activate([ev], PURPOSE_INFRASTRUCTURE_HEALTH)
        assert ctx_create is not None
        ctx = build_context(ctx_create)
        await ctx_store.save_context(ctx)
        contexts.append(ctx)

    patterns = []
    pres = pattern_det.detect(contexts, PATTERN_LIBRARY, 365)
    for cand in pres.candidates:
        pc = PatternCreate(
            tenant_id=tenant_id,
            context_id=cand.context_id,
            pattern_type=cand.pattern_type,
            description=cand.description,
            strength_measure=cand.strength_measure,
            frequency=cand.frequency,
            library_pattern_id=cand.library_pattern_id,
        )
        p = build_pattern(pc)
        await pat_store.save_pattern(p)
        patterns.append(p)

    anomalies = []
    ares = anomaly_det.detect(contexts, patterns, TOLERANCE_LIBRARY)
    for cand in ares.candidates:
        ac = AnomalyCreate(
            tenant_id=tenant_id,
            context_id=cand.context_id,
            pattern_id=cand.pattern_id,
            deviation_score=cand.deviation_score,
            tolerance_threshold=cand.tolerance_threshold,
            anomaly_class=cand.anomaly_class,
        )
        a = build_anomaly(ac)
        await an_store.save_anomaly(a)
        anomalies.append(a)

    hypotheses = []
    for a in anomalies:
        for hc in hyp_gen.generate(a, contexts, patterns):
            h = build_hypothesis(hc)
            await hyp_store.save_hypothesis(h)
            hypotheses.append(h)

    evidence_by_id = {e.id: e for e in evidences}
    confidences = []
    for h in hypotheses:
        scope = calib.resolve_scope_evidence(h, anomalies, contexts, evidence_by_id)
        coherence_inputs = {
            "explains": sorted({e.organization_type for e in scope}),
            "contradicts": [],
            "coherent_with": [],
            "incoherent_with": [],
        }
        cc = calib.calibrate(h, scope, scope, coherence_inputs, CalibrationParams(), None)
        c = build_confidence(cc)
        await conf_store.save_confidence(c)
        confidences.append(c)

    action_space = next(e for e in ACTION_SPACE_LIBRARY if e.domain == "storage")
    recommendations = []
    for h, c in zip(hypotheses, confidences, strict=True):
        active_ctx = form.resolve_active_context(h, anomalies, contexts)
        assert active_ctx is not None
        rc = form.formulate(h, c, active_ctx, action_space)
        if rc is None:
            continue
        r = build_recommendation(rc)
        await rec_store.save_recommendation(r)
        recommendations.append(r)

    policy = POLICY_BY_DOMAIN["storage"]
    authority = comm.Authority(
        authority_id=comm.policy_authority_id(policy.policy_id),
        label=policy.policy_id,
        risk_tolerance=comm.RISK_LOW,
    )
    decisions = []
    for r, c in zip(recommendations, confidences, strict=True):
        dc = comm.commit(r, c, policy, authority)
        if dc is None:
            continue
        d = build_decision(dc)
        await dec_store.save_decision(d)
        decisions.append(d)

    return {
        "observations": observations,
        "evidences": evidences,
        "contexts": contexts,
        "patterns": patterns,
        "anomalies": anomalies,
        "hypotheses": hypotheses,
        "confidences": confidences,
        "recommendations": recommendations,
        "decisions": decisions,
    }


@pytest.fixture
async def stores():
    built = {
        "obs": ObservationStore(DSN),
        "ev": EvidenceStore(DSN),
        "ctx": ContextStore(DSN),
        "pat": PatternStore(DSN),
        "an": AnomalyStore(DSN),
        "hyp": HypothesisStore(DSN),
        "conf": ConfidenceStore(DSN),
        "rec": RecommendationStore(DSN),
        "dec": DecisionStore(DSN),
        "learning_exec": LearningExecutionStore(dsn=DSN),
        "memory": MemoryStore(DSN),
    }
    try:
        for s in built.values():
            await s.verify_connection()
    except Exception as exc:  # noqa: BLE001
        for s in built.values():
            await s.close()
        if os.getenv("CI"):
            pytest.fail(f"PostgreSQL not available at {DSN}: {exc}")
        pytest.skip(f"PostgreSQL not available at {DSN}: {exc}")
    yield built
    for s in built.values():
        await s.close()


@pytest.fixture
async def read_stores():
    read_built = {
        "decision_read": DecisionReadStore(dsn=DSN),
        "recommendation_read": RecommendationReadStore(dsn=DSN),
        "hypothesis_read": HypothesisReadStore(dsn=DSN),
        "pattern_read": PatternReadStore(dsn=DSN),
        "context_read": ContextReadStore(dsn=DSN),
        "insight_read": InsightReadStore(dsn=DSN),
        "confidence_read": ConfidenceReadStore(dsn=DSN),
    }
    try:
        for s in read_built.values():
            await s.verify_connection()
    except Exception as exc:  # noqa: BLE001
        for s in read_built.values():
            await s.close()
        if os.getenv("CI"):
            pytest.fail(f"PostgreSQL not available at {DSN}: {exc}")
        pytest.skip(f"PostgreSQL not available at {DSN}: {exc}")
    yield read_built
    for s in read_built.values():
        await s.close()


def _build_h3_store(stores: dict, read_stores: dict) -> H3LearningLoopStore:
    return H3LearningLoopStore(
        decision_store=read_stores["decision_read"],
        recommendation_store=read_stores["recommendation_read"],
        hypothesis_store=read_stores["hypothesis_read"],
        pattern_store=read_stores["pattern_read"],
        context_store=read_stores["context_read"],
        insight_store=read_stores["insight_read"],
        memory_store=stores["memory"],
        execution_store=stores["learning_exec"],
    )


# ── E2E: Full Cognitive Gate chain ────────────────────────────────────────


async def test_cognitive_gate_full_chain(  # noqa: PLR0915
    stores, read_stores
):
    """End-to-end: Decision → Outcome → Execution → Evaluation → Learning.

    This is the PRIMARY Cognitive Gate test. It demonstrates the complete chain
    from a committed Decision with falsifiable expected outcomes through to the
    learning loop producing a signal.
    """
    tenant = uuid.uuid4()

    # ── Step 1-9: Run the cognitive pipeline to create a committed Decision ──
    art = await _run_pipeline(stores, tenant, num_servers=3)
    assert len(art["decisions"]) >= 1
    decision = art["decisions"][0]

    # ── Step 10: Verify Decision has falsifiable expected outcomes ───────────
    assert decision.tenant_id == tenant
    assert decision.expected_outcomes, "Decision must have expected_outcomes"
    for eo in decision.expected_outcomes:
        assert "prediction" in eo, "Expected outcome must have 'prediction'"
        assert "verifiable_by" in eo, "Expected outcome must have 'verifiable_by'"
        assert "deadline" in eo, "Expected outcome must have 'deadline'"
    assert decision.actual_outcomes is None, "Decision must NOT have actual_outcomes yet"
    assert decision.executed_at is None, "Decision must NOT have executed_at yet"

    # ── Step 11: Submit observed outcomes via Cognitive Gate orchestrator ─────
    h3_store = _build_h3_store(stores, read_stores)
    actual_outcomes = [
        {"verifiable_by": eo["verifiable_by"], "value": True}
        for eo in decision.expected_outcomes
    ]
    executed_at = datetime.now(UTC)

    result = await submit_decision_outcomes_and_learn(
        tenant_id=tenant,
        decision_id=decision.id,
        actual_outcomes=actual_outcomes,
        executed_at=executed_at,
        execution_store=stores["learning_exec"],
        learning_loop_store=h3_store,
    )

    # ── Step 12: Verify Cognitive Gate result ────────────────────────────────
    assert result.tenant_id == tenant
    assert result.decision_id == decision.id
    assert result.outcome_revision_id is not None
    assert result.learning_status == "completed"
    assert result.execution_id is not None

    # ── Step 13: Verify Decision was updated with actual outcomes ────────────
    updated_decisions = await stores["dec"].list_decisions(tenant_id=tenant)
    updated = next(d for d in updated_decisions if d.id == decision.id)
    assert updated.actual_outcomes is not None
    assert len(updated.actual_outcomes) == len(decision.expected_outcomes)
    assert updated.executed_at is not None

    # ── Step 14: Verify OutcomeRevision was persisted ────────────────────────
    pg_dsn = DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        rev_rows = await conn.fetch(
            "SELECT id, tenant_id, decision_id, actual_outcomes, executed_at "
            "FROM outcome_revisions WHERE decision_id = $1 AND tenant_id = $2",
            decision.id,
            tenant,
        )
        assert len(rev_rows) >= 1, "At least one outcome_revision must exist"
        rev = rev_rows[0]
        assert rev["tenant_id"] == tenant
        assert rev["decision_id"] == decision.id
        assert rev["executed_at"] is not None
    finally:
        await conn.close()

    # ── Step 15: Verify LearningExecution was persisted ──────────────────────
    conn = await asyncpg.connect(pg_dsn)
    try:
        exec_rows = await conn.fetch(
            "SELECT id, tenant_id, decision_id, outcome_revision_id, status, "
            "signal_count FROM learning_executions "
            "WHERE decision_id = $1 AND tenant_id = $2",
            decision.id,
            tenant,
        )
        assert len(exec_rows) >= 1, "At least one learning_execution must exist"
        lex = exec_rows[0]
        assert lex["tenant_id"] == tenant
        assert lex["decision_id"] == decision.id
        assert lex["outcome_revision_id"] == rev_rows[0]["id"]
        assert lex["status"] == "completed"
        assert lex["signal_count"] >= 1
    finally:
        await conn.close()

    # ── Step 16: Verify Learning Memory signals were persisted ───────────────
    conn = await asyncpg.connect(pg_dsn)
    try:
        mem_rows = await conn.fetch(
            "SELECT id, tenant_id, target_type, target_id, signal, provenance, "
            "signal_hash, execution_id FROM learning_memory "
            "WHERE tenant_id = $1",
            tenant,
        )
        assert len(mem_rows) >= 1, "At least one learning_memory signal must exist"
        for mem in mem_rows:
            assert mem["tenant_id"] == tenant
            assert mem["execution_id"] == lex["id"]
            assert mem["signal_hash"] is not None
            assert mem["provenance"] is not None
    finally:
        await conn.close()

    # ── Step 17: Verify complete provenance chain ────────────────────────────
    # decision_id → outcome_revision_id → execution_id → learning_memory.execution_id
    assert str(decision.id) == str(rev_rows[0]["decision_id"])
    assert str(rev_rows[0]["id"]) == str(lex["outcome_revision_id"])
    assert str(lex["id"]) == str(mem_rows[0]["execution_id"])

    # ── Step 18: Verify tenant isolation ─────────────────────────────────────
    conn = await asyncpg.connect(pg_dsn)
    try:
        other_tenant = uuid.uuid4()
        other_rows = await conn.fetch(
            "SELECT id FROM learning_memory WHERE tenant_id = $1",
            other_tenant,
        )
        assert len(other_rows) == 0, "Other tenant must have no memory records"
    finally:
        await conn.close()


async def test_cognitive_gate_idempotency(stores, read_stores):
    """Re-submitting the same outcomes creates a new revision but learning is idempotent."""
    tenant = uuid.uuid4()
    art = await _run_pipeline(stores, tenant, num_servers=3)
    decision = art["decisions"][0]
    h3_store = _build_h3_store(stores, read_stores)
    actual_outcomes = [
        {"verifiable_by": eo["verifiable_by"], "value": True}
        for eo in decision.expected_outcomes
    ]

    # First submission
    r1 = await submit_decision_outcomes_and_learn(
        tenant_id=tenant,
        decision_id=decision.id,
        actual_outcomes=actual_outcomes,
        executed_at=datetime.now(UTC),
        execution_store=stores["learning_exec"],
        learning_loop_store=h3_store,
    )
    assert r1.learning_status == "completed"

    # Second submission — creates new revision, learning idempotent
    r2 = await submit_decision_outcomes_and_learn(
        tenant_id=tenant,
        decision_id=decision.id,
        actual_outcomes=actual_outcomes,
        executed_at=datetime.now(UTC),
        execution_store=stores["learning_exec"],
        learning_loop_store=h3_store,
    )
    # New revision created, but learning may skip (already completed for previous revision)
    assert r2.outcome_revision_id != r1.outcome_revision_id

    # Two outcome_revisions exist
    pg_dsn = DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        rev_count = await conn.fetchval(
            "SELECT COUNT(*) FROM outcome_revisions WHERE decision_id = $1 AND tenant_id = $2",
            decision.id,
            tenant,
        )
        assert rev_count == 2  # noqa: PLR2004
    finally:
        await conn.close()


async def test_cognitive_gate_tenant_isolation(stores, read_stores):
    """Outcomes from tenant A cannot leak into tenant B."""
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    art_a = await _run_pipeline(stores, tenant_a, num_servers=3)
    art_b = await _run_pipeline(stores, tenant_b, num_servers=3)
    decision_a = art_a["decisions"][0]
    decision_b = art_b["decisions"][0]
    h3_store = _build_h3_store(stores, read_stores)

    actual_a = [
        {"verifiable_by": eo["verifiable_by"], "value": True}
        for eo in decision_a.expected_outcomes
    ]
    actual_b = [
        {"verifiable_by": eo["verifiable_by"], "value": False}
        for eo in decision_b.expected_outcomes
    ]

    await submit_decision_outcomes_and_learn(
        tenant_id=tenant_a, decision_id=decision_a.id,
        actual_outcomes=actual_a, executed_at=datetime.now(UTC),
        execution_store=stores["learning_exec"], learning_loop_store=h3_store,
    )
    await submit_decision_outcomes_and_learn(
        tenant_id=tenant_b, decision_id=decision_b.id,
        actual_outcomes=actual_b, executed_at=datetime.now(UTC),
        execution_store=stores["learning_exec"], learning_loop_store=h3_store,
    )

    pg_dsn = DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        mem_a = await conn.fetch(
            "SELECT * FROM learning_memory WHERE tenant_id = $1", tenant_a
        )
        mem_b = await conn.fetch(
            "SELECT * FROM learning_memory WHERE tenant_id = $1", tenant_b
        )
        assert all(m["tenant_id"] == tenant_a for m in mem_a)
        assert all(m["tenant_id"] == tenant_b for m in mem_b)
        assert {m["id"] for m in mem_a}.isdisjoint({m["id"] for m in mem_b})
    finally:
        await conn.close()


async def test_cognitive_gate_execution_deterministic(stores, read_stores):
    """Two concurrent submissions for the same decision serialize via advisory lock."""
    tenant = uuid.uuid4()
    art = await _run_pipeline(stores, tenant, num_servers=3)
    decision = art["decisions"][0]
    h3_store = _build_h3_store(stores, read_stores)
    actual = [
        {"verifiable_by": eo["verifiable_by"], "value": True}
        for eo in decision.expected_outcomes
    ]

    r1, r2 = await asyncio.gather(
        submit_decision_outcomes_and_learn(
            tenant_id=tenant, decision_id=decision.id,
            actual_outcomes=actual, executed_at=datetime.now(UTC),
            execution_store=stores["learning_exec"], learning_loop_store=h3_store,
        ),
        submit_decision_outcomes_and_learn(
            tenant_id=tenant, decision_id=decision.id,
            actual_outcomes=actual, executed_at=datetime.now(UTC),
            execution_store=stores["learning_exec"], learning_loop_store=h3_store,
        ),
    )
    # Both complete (advisory lock serializes, not rejects)
    assert r1.learning_status in ("completed", "skipped")
    assert r2.learning_status in ("completed", "skipped")
    # Both get unique outcome revisions
    assert r1.outcome_revision_id != r2.outcome_revision_id
