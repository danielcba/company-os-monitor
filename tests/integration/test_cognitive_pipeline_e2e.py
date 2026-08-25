"""End-to-end integration test of the COS-Monitor cognitive pipeline.

Drives the canonical cognitive chain IN-PROCESS (no microservices) against a
live PostgreSQL, exercising the real lib/contract functions for every stage:

    Observation -> Evidence -> Context (coherence competition)
                -> Pattern -> Anomaly -> Hypothesis
                -> Confidence (S + C + ECE)
                -> Recommendation -> Decision

This satisfies the product requirement (prompt section 22) for an integration
test that walks the full Observation -> Decision chain, plus tenant isolation
and traceability. Redis is NOT required: we persist Observations directly
through the ObservationStore (the ObservationBus boundary is covered elsewhere).

Requires a live PostgreSQL (same DATABASE_URL the services use). When the
database is unreachable the DB-backed tests skip instead of failing, so the
suite stays green in environments without infrastructure.
"""
# ruff: noqa: E402 - imports below are intentional after dynamic sys.path setup.
from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
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

# Make `libs` importable, and the context-service `src` package importable
# (ActivatorEngine uses absolute `from src.activator...` imports).
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps/services/context-service"))
# report-service `src` (ReportService) is appended (not prepended) so it does
# not change the `src.service` precedence that gateway's tests rely on.
sys.path.append(str(ROOT / "apps/services/report-service"))


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
report_svc = _load(
    "cosint_report_service",
    ROOT / "apps/services/report-service/src/service.py",
)

from src.activator.engine import ActivatorEngine  # noqa: E402

from libs.action.decision import (
    DecisionStore,  # noqa: E402
    build_decision,  # noqa: E402
)
from libs.action.recommendation import (  # noqa: E402
    RecommendationCreate,
    RecommendationStore,  # noqa: E402
    build_recommendation,
)
from libs.action.report import REPORT_TYPE_JSON, ReportStore  # noqa: E402
from libs.cognitive_core.calibration_model import (  # noqa: E402
    CalibrationParams,
    quality_class_to_weight,
)
from libs.cognitive_core.observation_bus import Observation  # noqa: E402
from libs.learning.confidence import (  # noqa: E402
    ConfidenceCreate,
    ConfidenceStore,  # noqa: E402
    build_confidence,
)
from libs.perception.context import (  # noqa: E402
    PURPOSE_INFRASTRUCTURE_HEALTH,
    ContextStore,  # noqa: E402
    build_context,
)
from libs.perception.evidence import (  # noqa: E402
    EvidenceCreate,
    EvidenceStore,  # noqa: E402
    build_evidence,
)
from libs.perception.store import ObservationStore  # noqa: E402
from libs.procedural_memory.action_space import ACTION_SPACE_LIBRARY  # noqa: E402
from libs.procedural_memory.decision_policy import POLICY_BY_DOMAIN  # noqa: E402
from libs.procedural_memory.pattern_library import PATTERN_LIBRARY  # noqa: E402
from libs.procedural_memory.tolerance_library import TOLERANCE_LIBRARY  # noqa: E402
from libs.reasoning.anomaly import (  # noqa: E402
    AnomalyCreate,
    AnomalyStore,  # noqa: E402
    build_anomaly,
)
from libs.reasoning.hypothesis import (  # noqa: E402
    HypothesisCreate,
    HypothesisStore,  # noqa: E402
    build_hypothesis,
)
from libs.reasoning.pattern import (  # noqa: E402
    PatternCreate,
    PatternStore,  # noqa: E402
    build_pattern,
)


def _make_servers(num_servers: int) -> list[uuid.UUID]:
    return [uuid.uuid4() for _ in range(num_servers)]


def _server_observations(tenant_id: uuid.UUID, source_id: uuid.UUID) -> list[Observation]:
    """Three Q1 Linux facts that trip the resource_exhaustion_evidence rule."""
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
    """Insert the tenant row so FK constraints on artifact tables are satisfied."""
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


async def _run_pipeline(  # noqa: PLR0915, PLR0912
    stores: dict, tenant_id: uuid.UUID, num_servers: int = 3
) -> dict:
    """Run the full cognitive chain for one tenant and return created artifacts."""
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

    # 1) OBSERVATION - immutable facts, never interpreted.
    observations: list[Observation] = []
    for src in _make_servers(num_servers):
        for obs in _server_observations(tenant_id, src):
            observations.append(obs)
            await obs_store.save_observation(obs)

    # 2) EVIDENCE - organize facts into coherent, factual bodies.
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

    # 3) CONTEXT - coherence competition selects the winning mental model.
    contexts = []
    for ev in evidences:
        ctx_create = ActivatorEngine().activate([ev], PURPOSE_INFRASTRUCTURE_HEALTH)
        assert ctx_create is not None, "evidence must be explainable"
        ctx = build_context(ctx_create)
        await ctx_store.save_context(ctx)
        contexts.append(ctx)

    # 4) PATTERN - detect regularities over the context stream.
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

    # 5) ANOMALY - deviation vs the expected pattern (never absolute).
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

    # 6) HYPOTHESIS - testable, falsifiable candidate explanations.
    hypotheses = []
    for a in anomalies:
        for hc in hyp_gen.generate(a, contexts, patterns):
            h = build_hypothesis(hc)
            await hyp_store.save_hypothesis(h)
            hypotheses.append(h)

    # 7) CONFIDENCE - S + C + ECE, scoped to the hypothesis evidence.
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

    # 8) RECOMMENDATION - advisory offer, traceable to hypothesis + confidence.
    action_space = next(e for e in ACTION_SPACE_LIBRARY if e.domain == "storage")
    recommendations = []
    for h, c in zip(hypotheses, confidences, strict=True):
        active_ctx = form.resolve_active_context(h, anomalies, contexts)
        assert active_ctx is not None, "hypothesis must map to an active context"
        rc = form.formulate(h, c, active_ctx, action_space)
        if rc is None:
            continue
        r = build_recommendation(rc)
        await rec_store.save_recommendation(r)
        recommendations.append(r)

    # 9) DECISION - recorded commitment (R4 gate: needs calibrated confidence).
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
        "rep": ReportStore(DSN),
    }
    try:
        for s in built.values():
            await s.verify_connection()
    except Exception as exc:  # noqa: BLE001 - in CI fail (no silent skip), locally skip
        for s in built.values():
            await s.close()
        if os.getenv("CI"):
            pytest.fail(f"PostgreSQL not available at {DSN}: {exc}")
        pytest.skip(f"PostgreSQL not available at {DSN}: {exc}")
    yield built
    for s in built.values():
        await s.close()


async def test_end_to_end_cognitive_chain(stores):
    tenant = uuid.uuid4()
    art = await _run_pipeline(stores, tenant, num_servers=3)

    # Every stage produced artifacts.
    assert len(art["observations"]) == 9  # noqa: PLR2004
    assert len(art["evidences"]) == 3  # noqa: PLR2004
    assert len(art["contexts"]) == 3  # noqa: PLR2004
    assert len(art["patterns"]) >= 1
    assert len(art["anomalies"]) >= 1
    assert len(art["hypotheses"]) >= 2  # noqa: PLR2004 - competing hypotheses required
    assert len(art["confidences"]) == len(art["hypotheses"])
    assert len(art["recommendations"]) >= 1
    assert len(art["decisions"]) >= 1

    # Confidence is calibrated (C_final in [0,1]) and above the commit gate.
    for c in art["confidences"]:
        assert 0.0 <= c.confidence_score <= 1.0
    committed = list(art["decisions"])
    assert committed, "at least one decision must be committed when confidence is high"

    # TRACEABILITY: Decision -> Recommendation -> Hypothesis -> Anomaly ->
    # Context -> Evidence -> Observations, all within the same tenant.
    d = art["decisions"][0]
    assert d.tenant_id == tenant
    rec = next(r for r in art["recommendations"] if r.id == d.recommendation_id)
    assert rec.tenant_id == tenant
    assert rec.confidence_id == d.confidence_id
    hyp = next(h for h in art["hypotheses"] if h.id == rec.hypothesis_id)
    assert hyp.tenant_id == tenant
    an = next(a for a in art["anomalies"] if a.id == hyp.anomaly_ids[0])
    assert an.tenant_id == tenant
    ctx = next(c for c in art["contexts"] if c.id == an.context_id)
    assert ctx.tenant_id == tenant
    for eid in ctx.evidence_ids:
        ev = next(e for e in art["evidences"] if e.id == eid)
        assert ev.tenant_id == tenant
        for oid in ev.observation_ids:
            obs = next(o for o in art["observations"] if o.id == oid)
            assert obs.tenant_id == tenant

    # All artifacts carry the same tenant.
    for key in ("evidences", "contexts", "patterns", "anomalies", "hypotheses"):
        assert all(a.tenant_id == tenant for a in art[key])

    # 10) REPORT - non-canonical output document that formats the committed
    # flow (reads the real cognitive tables, writes only the `reports` table).
    report_service = report_svc.ReportService(
        stores["dec"],
        stores["rec"],
        stores["ctx"],
        stores["conf"],
        stores["hyp"],
        stores["an"],
        stores["pat"],
        stores["ev"],
        stores["obs"],
        stores["rep"],
        output_dir=tempfile.mkdtemp(),
    )
    report, status = await report_service.generate(tenant, REPORT_TYPE_JSON)
    assert report.tenant_id == tenant
    assert status in ("created", "duplicate")
    assert report.content["decision_count"] >= 1

    # Report -> Decision traceability, following the REAL stored data (no mocks).
    trace = next(
        t for t in report.content["decision_traces"] if t["decision"]["id"] == str(d.id)
    )
    assert trace["decision"]["id"] == str(d.id)
    assert trace["recommendation"]["id"] == str(d.recommendation_id)
    assert trace["confidence"]["id"] == str(d.confidence_id)
    rec = next(r for r in art["recommendations"] if r.id == d.recommendation_id)
    assert trace["hypothesis"]["id"] == str(rec.hypothesis_id)
    hyp = next(h for h in art["hypotheses"] if h.id == rec.hypothesis_id)
    assert trace["anomalies"] and trace["anomalies"][0]["id"] == str(hyp.anomaly_ids[0])
    an = next(a for a in art["anomalies"] if a.id == hyp.anomaly_ids[0])
    assert trace["contexts"] and trace["contexts"][0]["id"] == str(an.context_id)
    # Every observation the report cites belongs to this tenant's pipeline.
    reported_obs_ids = {
        o["id"] for t in report.content["decision_traces"] for o in t["observations"]
    }
    assert reported_obs_ids <= {str(o.id) for o in art["observations"]}
    assert all(o.tenant_id == tenant for o in art["observations"])


async def test_tenant_isolation(stores):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    res_a = await _run_pipeline(stores, tenant_a, num_servers=3)
    res_b = await _run_pipeline(stores, tenant_b, num_servers=3)

    ev_a = await stores["ev"].list_evidence(tenant_id=tenant_a)
    ev_b = await stores["ev"].list_evidence(tenant_id=tenant_b)
    dec_a = await stores["dec"].list_decisions(tenant_id=tenant_a)
    dec_b = await stores["dec"].list_decisions(tenant_id=tenant_b)

    ids_a = {e.id for e in ev_a}
    ids_b = {e.id for e in ev_b}
    assert ids_a and ids_b
    assert ids_a.isdisjoint(ids_b)
    assert {d.id for d in dec_a}.isdisjoint({d.id for d in dec_b})

    # Tenant B must never surface in tenant A's query results.
    assert all(e.tenant_id == tenant_a for e in ev_a)
    assert all(e.tenant_id == tenant_b for e in ev_b)
    assert all(d.tenant_id == tenant_a for d in dec_a)
    assert all(d.tenant_id == tenant_b for d in dec_b)

    # No tenant A artifact references a tenant B recommendation, and vice versa.
    rec_ids_b = {r.id for r in res_b["recommendations"]}
    assert all(d.recommendation_id not in rec_ids_b for d in dec_a)

    # Reports must also respect tenant scope end-to-end (Report -> Decision).
    report_service = report_svc.ReportService(
        stores["dec"],
        stores["rec"],
        stores["ctx"],
        stores["conf"],
        stores["hyp"],
        stores["an"],
        stores["pat"],
        stores["ev"],
        stores["obs"],
        stores["rep"],
        output_dir=tempfile.mkdtemp(),
    )
    report_a, _ = await report_service.generate(tenant_a, REPORT_TYPE_JSON)
    report_b, _ = await report_service.generate(tenant_b, REPORT_TYPE_JSON)
    assert report_a.tenant_id == tenant_a
    assert report_b.tenant_id == tenant_b

    rep_a = await stores["rep"].list_reports(tenant_id=tenant_a)
    rep_b = await stores["rep"].list_reports(tenant_id=tenant_b)
    ids_rep_a = {r.id for r in rep_a}
    ids_rep_b = {r.id for r in rep_b}
    assert ids_rep_a and ids_rep_b
    # Tenant B cannot retrieve tenant A's Report (and vice versa).
    assert ids_rep_a.isdisjoint(ids_rep_b)
    assert all(r.tenant_id == tenant_a for r in rep_a)
    assert all(r.tenant_id == tenant_b for r in rep_b)
    # Every trace in tenant A's report references only tenant A's decisions.
    dec_ids_a = {str(d.id) for d in res_a["decisions"]}
    for r in rep_a:
        assert all(
            t["decision"]["id"] in dec_ids_a for t in r.content["decision_traces"]
        )


def test_no_action_without_confidence_and_evidence():
    """R4 gate + empty-evidence validation (pure, no DB needed)."""
    tenant = uuid.uuid4()

    # calibrate must refuse to run without evidence (scope isolation / validity).
    hc = HypothesisCreate(
        tenant_id=tenant,
        anomaly_ids=[uuid.uuid4()],
        pattern_ids=[],
        description="test hypothesis",
        predicted_consequences=["observable prediction"],
        falsification_criterion="if X then false",
        coherence_score=0.5,
    )
    h = build_hypothesis(hc)
    with pytest.raises(ValueError):
        calib.calibrate(
            h,
            [],
            [],
            {
                "explains": [],
                "contradicts": [],
                "coherent_with": [],
                "incoherent_with": [],
            },
            CalibrationParams(),
            None,
        )

    # A low-confidence judgment must NOT produce a committed decision (R4).
    cc = ConfidenceCreate(
        tenant_id=tenant,
        target_type="hypothesis",
        target_id=uuid.uuid4(),
        evidential_support=0.1,
        explanatory_coherence=0.1,
        historical_calibration=1.0,
        confidence_score=0.1,
        alpha=0.5,
        calibration_justification="synthetic low-confidence judgment",
        calibration_error_estimate=0.0,
    )
    conf = build_confidence(cc)
    rc = RecommendationCreate(
        tenant_id=tenant,
        hypothesis_id=uuid.uuid4(),
        confidence_id=conf.id,
        action_description="expand_volume",
        rationale="test",
        expected_consequences=["free space stays above threshold"],
        alternatives_considered=[],
        confidence_score=0.1,
        status="proposed",
    )
    rec = build_recommendation(rc)
    policy = POLICY_BY_DOMAIN["storage"]
    authority = comm.Authority(
        authority_id=comm.policy_authority_id(policy.policy_id),
        label=policy.policy_id,
        risk_tolerance=comm.RISK_LOW,
    )
    assert (
        comm.commit_eligibility(rec, conf, policy, authority)
        == comm.BELOW_CONFIDENCE
    )
    assert comm.commit(rec, conf, policy, authority) is None
