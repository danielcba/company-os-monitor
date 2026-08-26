"""Cognitive Trace READ model tests (controlled, deterministic scenarios).

Builds a fully controlled cognitive chain directly in PostgreSQL (no microservice
pipeline) so the read model can be asserted precisely:

  A. happy path (Report -> Decision -> ... -> Observation)
  B. multiple Decisions under one Report (1:N)
  C. tenant isolation (cross-tenant Report resolves to nothing)
  D. missing Report (-> None / 404)
  E. determinism (two identical calls are equal)
  F. broken provenance (referenced artifact missing -> partial + warning)

Requires a live PostgreSQL (same DATABASE_URL the services use). When the
database is unreachable the DB-backed tests skip instead of failing.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import asyncpg
import pytest
from sqlalchemy.ext.asyncio import create_async_engine

# Make `src` importable when run from this directory.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.cognitive_trace import CognitiveTraceStore

DSN = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
)
PG_DSN = DSN.replace("postgresql+asyncpg://", "postgresql://")

FIXED_NOW = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)


def _pg() -> asyncpg.Connection:
    return asyncpg.connect(PG_DSN)


async def _ensure_tenant(conn: asyncpg.Connection, tenant_id: uuid.UUID) -> None:
    await conn.execute(
        "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
        "ON CONFLICT (id) DO NOTHING",
        tenant_id,
        f"trace-{tenant_id.hex[:8]}",
        f"trace-{tenant_id.hex}",
    )


async def _seed_chain(conn: asyncpg.Connection, tenant_id: uuid.UUID, n: int) -> dict:
    """Insert ``n`` independent full provenance chains for ``tenant_id``.

    Returns the generated ids (including the Report id and its decision ids).
    """
    await _ensure_tenant(conn, tenant_id)
    decision_ids: list[uuid.UUID] = []
    for _ in range(n):
        obs1, obs2 = uuid.uuid4(), uuid.uuid4()
        ev = uuid.uuid4()
        ctx = uuid.uuid4()
        pat = uuid.uuid4()
        an = uuid.uuid4()
        hyp = uuid.uuid4()
        conf = uuid.uuid4()
        rec = uuid.uuid4()
        dec = uuid.uuid4()
        decision_ids.append(dec)

        # Observations (composite PK id + captured_at).
        for oid in (obs1, obs2):
            await conn.execute(
                """
                INSERT INTO observations
                    (id, tenant_id, source_id, source_type, fact_type, fact_value,
                     unit, captured_at, quality_class, raw_payload)
                VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
                """,
                oid,
                tenant_id,
                uuid.uuid4(),
                "linux_agent",
                "cpu_utilization_percent",
                json.dumps({"value": 95.0}),
                "percent",
                FIXED_NOW,
                "Q1",
                json.dumps({}),
            )
        # Evidence.
        await conn.execute(
            """
            INSERT INTO evidence
                (id, tenant_id, observation_ids, organization_type, description,
                 quality_class, weight, organized_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            ev,
            tenant_id,
            [obs1, obs2],
            "resource_exhaustion_evidence",
            "high cpu/mem/disk",
            "Q1",
            0.9,
            FIXED_NOW,
        )
        # Context.
        await conn.execute(
            """
            INSERT INTO contexts
                (id, tenant_id, evidence_ids, mental_model_id, purpose,
                 coherence_score, competing_models, activated_at, is_active)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            """,
            ctx,
            tenant_id,
            [ev],
            "resource_pressure",
            "infrastructure_health",
            0.8,
            json.dumps([]),
            FIXED_NOW,
            False,
        )
        # Pattern.
        await conn.execute(
            """
            INSERT INTO patterns
                (id, tenant_id, context_id, pattern_type, description,
                 strength_measure, frequency, detected_at, is_active)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
            """,
            pat,
            tenant_id,
            ctx,
            "threshold",
            "sustained resource pressure",
            0.95,
            "daily",
            FIXED_NOW,
            True,
        )
        # Anomaly.
        await conn.execute(
            """
            INSERT INTO anomalies
                (id, tenant_id, context_id, pattern_id, deviation_score,
                 tolerance_threshold, anomaly_class, detected_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
            """,
            an,
            tenant_id,
            ctx,
            pat,
            0.9,
            0.7,
            "resource_exhaustion",
            FIXED_NOW,
        )
        # Hypothesis.
        await conn.execute(
            """
            INSERT INTO hypotheses
                (id, tenant_id, anomaly_ids, pattern_ids, description,
                 predicted_consequences, falsification_criterion,
                 coherence_score, status, generated_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """,
            hyp,
            tenant_id,
            [an],
            [pat],
            "capacity saturation",
            json.dumps(["latency rise"]),
            "if latency stays flat",
            0.8,
            "candidate",
            FIXED_NOW,
        )
        # Confidence (targets the hypothesis).
        await conn.execute(
            """
            INSERT INTO confidence_scores
                (id, tenant_id, target_type, target_id, evidential_support,
                 explanatory_coherence, historical_calibration, confidence_score,
                 alpha, calibration_justification, calibration_error_estimate,
                 computed_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            conf,
            tenant_id,
            "hypothesis",
            hyp,
            0.8,
            0.8,
            0.8,
            0.85,
            0.5,
            "S+C+ECE",
            0.05,
            FIXED_NOW,
        )
        # Recommendation.
        await conn.execute(
            """
            INSERT INTO recommendations
                (id, tenant_id, hypothesis_id, insight_id, confidence_id,
                 action_description, rationale, expected_consequences,
                 alternatives_considered, confidence_score, status, proposed_at)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            rec,
            tenant_id,
            hyp,
            None,
            conf,
            "add capacity",
            "saturation risk",
            json.dumps(["throughput restored"]),
            json.dumps([]),
            0.85,
            "proposed",
            FIXED_NOW,
        )
        # Decision.
        await conn.execute(
            """
            INSERT INTO decisions
                (id, tenant_id, recommendation_id, confidence_id, authority_id,
                 commitment, expected_outcomes, risk_tolerance, status,
                 committed_at, executed_at, actual_outcomes)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            dec,
            tenant_id,
            rec,
            conf,
            uuid.uuid4(),
            "scale out cluster",
            json.dumps(["p99 < 200ms"]),
            "low",
            "committed",
            FIXED_NOW,
            None,
            None,
        )

    report_id = uuid.uuid4()
    content = {
        "decision_traces": [
            {"decision": {"id": str(did)}} for did in decision_ids
        ],
        "decision_count": n,
    }
    await conn.execute(
        """
        INSERT INTO reports
            (id, tenant_id, report_type, title, summary, content, ai_generated,
             model_used, period_start, period_end, generated_at, file_path)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        """,
        report_id,
        tenant_id,
        "json",
        "Capacity report",
        "summary",
        json.dumps(content),
        False,
        None,
        None,
        None,
        FIXED_NOW,
        None,
    )
    return {"report_id": report_id, "decision_ids": decision_ids}


# Canonical relations whose broken form the read model must report explicitly.
GAP_KINDS = (
    "report_decision",  # Report -> missing Decision
    "decision_rec",     # Decision -> missing Recommendation
    "decision_conf",    # Decision -> missing Confidence
    "rec_hyp",          # Recommendation -> missing Hypothesis
    "rec_conf",         # Recommendation -> missing Confidence
    "conf_hyp",         # Confidence -> missing Hypothesis
    "hyp_anomaly",      # Hypothesis -> missing Anomaly
    "hyp_pattern",      # Hypothesis -> missing Pattern
    "anomaly_pattern",  # Anomaly -> missing Pattern
    "anomaly_context",  # Anomaly -> missing Context
    "pattern_context",  # Pattern -> missing Context
    "context_evidence", # Context -> missing Evidence
    "evidence_observation",  # Evidence -> missing Observation
)


async def _seed_chain_with_gap(
    conn: asyncpg.Connection, tenant_id: uuid.UUID, gap: str
) -> dict:
    """Insert one full provenance chain but make ``gap`` resolve to a missing
    artifact *within the trace's tenant*.

    The referenced artifact (e.g. a Recommendation) is inserted under a SECOND
    tenant, so the foreign key holds (the id exists) but the tenant-scoped read
    for ``tenant_id`` returns nothing -> the read model reports broken provenance
    (``partial`` + warning) rather than fabricating it. This mirrors the realistic
    cross-tenant / inconsistent-write case without violating DB constraints.
    """
    await _ensure_tenant(conn, tenant_id)
    tenant_b = uuid.uuid4()
    await _ensure_tenant(conn, tenant_b)

    obs1, obs2 = uuid.uuid4(), uuid.uuid4()
    ev = uuid.uuid4()
    ctx = uuid.uuid4()
    pat = uuid.uuid4()
    an = uuid.uuid4()
    hyp = uuid.uuid4()
    conf = uuid.uuid4()
    rec = uuid.uuid4()
    dec = uuid.uuid4()
    g = {k: uuid.uuid4() for k in GAP_KINDS}

    # Which artifact is "missing" from the trace's tenant (seeded in tenant_b).
    gap_missing = {
        "decision_rec": "rec",
        "decision_conf": "conf",
        "rec_hyp": "hyp",
        "rec_conf": "conf",
        "conf_hyp": "hyp",
        "hyp_anomaly": "an",
        "hyp_pattern": "pat",
        "anomaly_pattern": "pat",
        "anomaly_context": "ctx",
        "pattern_context": "ctx",
        "context_evidence": "ev",
        "evidence_observation": "ob",
    }
    missing = gap_missing.get(gap)

    def _t(artifact: str) -> uuid.UUID:
        return tenant_b if missing == artifact else tenant_id

    def _id(artifact: str, local: uuid.UUID) -> uuid.UUID:
        # The missing artifact must be stored under its ghost id (g[gap]) so the
        # parent's reference resolves to a real row (FK holds) yet stays absent
        # from the trace's tenant.
        return g[gap] if missing == artifact else local

    def _ref(artifact: str, local: uuid.UUID) -> uuid.UUID:
        # Any reference to the missing artifact must point at its ghost id too.
        return g[gap] if missing == artifact else local

    rec_ref = _ref("rec", rec)
    dec_conf_ref = _ref("conf", conf)
    hyp_ref = _ref("hyp", hyp)
    rec_conf_ref = _ref("conf", conf)
    conf_target = _ref("hyp", hyp)
    hyp_anomaly_refs = [_ref("an", an)]
    hyp_pattern_refs = [_ref("pat", pat)]
    an_pattern_ref = _ref("pat", pat)
    an_context_ref = _ref("ctx", ctx)
    pat_context_ref = _ref("ctx", ctx)
    ev_observation_refs = (
        [g["evidence_observation"]] if gap == "evidence_observation" else [obs1, obs2]
    )

    for oid in (obs1, obs2):
        await conn.execute(
            """
            INSERT INTO observations
                (id, tenant_id, source_id, source_type, fact_type, fact_value,
                 unit, captured_at, quality_class, raw_payload)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """,
            oid, tenant_id, uuid.uuid4(), "linux_agent", "cpu_utilization_percent",
            json.dumps({"value": 95.0}), "percent", FIXED_NOW, "Q1", json.dumps({}),
        )
    # Ghost observation (only for the evidence_observation gap, in tenant_b).
    if missing == "ob":
        await conn.execute(
            """
            INSERT INTO observations
                (id, tenant_id, source_id, source_type, fact_type, fact_value,
                 unit, captured_at, quality_class, raw_payload)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
            """,
            g["evidence_observation"], tenant_b, uuid.uuid4(), "linux_agent",
            "cpu_utilization_percent", json.dumps({"value": 1.0}), "percent",
            FIXED_NOW, "Q1", json.dumps({}),
        )
    await conn.execute(
        """
        INSERT INTO evidence
            (id, tenant_id, observation_ids, organization_type, description,
             quality_class, weight, organized_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """,
        _id("ev", ev), _t("ev"), ev_observation_refs, "resource_exhaustion_evidence",
        "high cpu/mem/disk", "Q1", 0.9, FIXED_NOW,
    )
    await conn.execute(
        """
        INSERT INTO contexts
            (id, tenant_id, evidence_ids, mental_model_id, purpose,
             coherence_score, competing_models, activated_at, is_active)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """,
        _id("ctx", ctx), _t("ctx"), [_id("ev", ev)], "resource_pressure", "infrastructure_health",
        0.8, json.dumps([]), FIXED_NOW, False,
    )
    await conn.execute(
        """
        INSERT INTO patterns
            (id, tenant_id, context_id, pattern_type, description,
             strength_measure, frequency, detected_at, is_active)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9)
        """,
        _id("pat", pat), _t("pat"), pat_context_ref, "threshold", "sustained resource pressure",
        0.95, "daily", FIXED_NOW, True,
    )
    await conn.execute(
        """
        INSERT INTO anomalies
            (id, tenant_id, context_id, pattern_id, deviation_score,
             tolerance_threshold, anomaly_class, detected_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8)
        """,
        _id("an", an), _t("an"), an_context_ref, an_pattern_ref, 0.9, 0.7,
        "resource_exhaustion", FIXED_NOW,
    )
    await conn.execute(
        """
        INSERT INTO hypotheses
            (id, tenant_id, anomaly_ids, pattern_ids, description,
             predicted_consequences, falsification_criterion,
             coherence_score, status, generated_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10)
        """,
        _id("hyp", hyp), _t("hyp"), hyp_anomaly_refs, hyp_pattern_refs, "capacity saturation",
        json.dumps(["latency rise"]), "if latency stays flat", 0.8,
        "candidate", FIXED_NOW,
    )
    await conn.execute(
        """
        INSERT INTO confidence_scores
            (id, tenant_id, target_type, target_id, evidential_support,
             explanatory_coherence, historical_calibration, confidence_score,
             alpha, calibration_justification, calibration_error_estimate,
             computed_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        """,
        _id("conf", conf), _t("conf"), "hypothesis", conf_target, 0.8, 0.8, 0.8, 0.85,
        0.5, "S+C+ECE", 0.05, FIXED_NOW,
    )
    await conn.execute(
        """
        INSERT INTO recommendations
            (id, tenant_id, hypothesis_id, insight_id, confidence_id,
             action_description, rationale, expected_consequences,
             alternatives_considered, confidence_score, status, proposed_at)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        """,
        _id("rec", rec), _t("rec"), hyp_ref, None, rec_conf_ref, "add capacity",
        "saturation risk", json.dumps(["throughput restored"]),
        json.dumps([]), 0.85, "proposed", FIXED_NOW,
    )
    if gap != "report_decision":
        await conn.execute(
            """
            INSERT INTO decisions
                (id, tenant_id, recommendation_id, confidence_id, authority_id,
                 commitment, expected_outcomes, risk_tolerance, status,
                 committed_at, executed_at, actual_outcomes)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            dec, tenant_id, rec_ref, dec_conf_ref, uuid.uuid4(), "scale out cluster",
            json.dumps(["p99 < 200ms"]), "low", "committed", FIXED_NOW, None, None,
        )

    report_decision_refs = (
        [g["report_decision"]] if gap == "report_decision" else [str(dec)]
    )
    report_id = uuid.uuid4()
    content = {
        "decision_traces": [{"decision": {"id": str(did)}} for did in report_decision_refs],
        "decision_count": 1,
    }
    await conn.execute(
        """
        INSERT INTO reports
            (id, tenant_id, report_type, title, summary, content, ai_generated,
             model_used, period_start, period_end, generated_at, file_path)
        VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
        """,
        report_id, tenant_id, "json", "Capacity report", "summary",
        json.dumps(content), False, None, None, None, FIXED_NOW, None,
    )
    return {"report_id": report_id, "gap": gap, "ghost": g[gap]}


@pytest.fixture
async def engine():
    eng = create_async_engine(DSN)
    try:
        yield eng
    finally:
        await eng.dispose()


@pytest.fixture
async def trace_store(engine):
    store = CognitiveTraceStore(engine)
    try:
        yield store
    finally:
        await store.close()


async def _pg() -> asyncpg.Connection | None:
    try:
        return await asyncpg.connect(PG_DSN)
    except Exception:  # noqa: BLE001 - skip when no DB
        return None


async def _conn() -> asyncpg.Connection | None:
    return await _pg()


@pytest.mark.asyncio
async def test_happy_path_and_multi_decision(trace_store):
    conn = await _conn()
    if conn is None:
        pytest.skip("PostgreSQL unavailable")
    try:
        tenant = uuid.uuid4()
        seeded = await _seed_chain(conn, tenant, n=2)
        trace = await trace_store.get_trace(
            tenant_id=tenant, report_id=seeded["report_id"]
        )
        assert trace is not None
        assert trace["root"]["type"] == "report"
        assert trace["root"]["id"] == str(seeded["report_id"])

        nodes = trace["nodes"]
        by_type = {}
        for node in nodes:
            by_type.setdefault(node["type"], []).append(node["id"])

        assert len(by_type.get("report", [])) == 1
        assert len(by_type.get("decision", [])) == 2
        assert len(by_type.get("recommendation", [])) == 2
        assert len(by_type.get("confidence", [])) == 2
        assert len(by_type.get("hypothesis", [])) == 2
        assert len(by_type.get("anomaly", [])) == 2
        assert len(by_type.get("pattern", [])) == 2
        assert len(by_type.get("context", [])) == 2
        assert len(by_type.get("evidence", [])) == 2
        assert len(by_type.get("observation", [])) == 4  # 2 per evidence

        # Edges reconstruct the canonical provenance chain.
        edge_set = {(e["from"], e["to"], e["relation"]) for e in trace["edges"]}
        for did in seeded["decision_ids"]:
            ds = str(did)
            assert (str(seeded["report_id"]), ds, "documents") in edge_set
        # Confidence calibrates the hypothesis target.
        assert any(rel == "calibrates" for _, _, rel in edge_set)
        assert any(rel == "accounts_for" for _, _, rel in edge_set)
        assert any(rel == "observes" for _, _, rel in edge_set)

        assert trace["completeness"] == "complete"
        assert trace["warnings"] == []
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_determinism(trace_store):
    conn = await _conn()
    if conn is None:
        pytest.skip("PostgreSQL unavailable")
    try:
        tenant = uuid.uuid4()
        seeded = await _seed_chain(conn, tenant, n=2)
        t1 = await trace_store.get_trace(
            tenant_id=tenant, report_id=seeded["report_id"]
        )
        t2 = await trace_store.get_trace(
            tenant_id=tenant, report_id=seeded["report_id"]
        )
        assert t1 == t2
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_missing_report(trace_store):
    conn = await _conn()
    if conn is None:
        pytest.skip("PostgreSQL unavailable")
    try:
        tenant = uuid.uuid4()
        await _ensure_tenant(conn, tenant)
        result = await trace_store.get_trace(
            tenant_id=tenant, report_id=uuid.uuid4()
        )
        assert result is None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_tenant_isolation(trace_store):
    conn = await _conn()
    if conn is None:
        pytest.skip("PostgreSQL unavailable")
    try:
        tenant_a = uuid.uuid4()
        tenant_b = uuid.uuid4()
        seeded = await _seed_chain(conn, tenant_a, n=1)
        await _ensure_tenant(conn, tenant_b)
        # Tenant B must not resolve Tenant A's report.
        result = await trace_store.get_trace(
            tenant_id=tenant_b, report_id=seeded["report_id"]
        )
        assert result is None
    finally:
        await conn.close()


@pytest.mark.asyncio
async def test_broken_provenance(trace_store):
    conn = await _conn()
    if conn is None:
        pytest.skip("PostgreSQL unavailable")
    try:
        tenant = uuid.uuid4()
        await _ensure_tenant(conn, tenant)
        ghost_decision = uuid.uuid4()
        report_id = uuid.uuid4()
        content = {
            "decision_traces": [{"decision": {"id": str(ghost_decision)}}],
            "decision_count": 1,
        }
        await conn.execute(
            """
            INSERT INTO reports
                (id, tenant_id, report_type, title, summary, content, ai_generated,
                 model_used, period_start, period_end, generated_at, file_path)
            VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)
            """,
            report_id,
            tenant,
            "json",
            "Broken report",
            "summary",
            json.dumps(content),
            False,
            None,
            None,
            None,
            FIXED_NOW,
            None,
        )
        trace = await trace_store.get_trace(tenant_id=tenant, report_id=report_id)
        assert trace is not None
        assert trace["completeness"] == "partial"
        assert any("not found" in w for w in trace["warnings"])
        # The report node still appears; the ghost decision does not.
        node_types = {n["type"] for n in trace["nodes"]}
        assert "report" in node_types
        assert "decision" not in node_types
    finally:
        await conn.close()


@pytest.mark.parametrize("gap", sorted(GAP_KINDS))
@pytest.mark.asyncio
async def test_broken_provenance_each_relation(trace_store, gap):
    conn = await _conn()
    if conn is None:
        pytest.skip("PostgreSQL unavailable")
    try:
        tenant = uuid.uuid4()
        seeded = await _seed_chain_with_gap(conn, tenant, gap)
        ghost = seeded["ghost"]
        trace = await trace_store.get_trace(
            tenant_id=tenant, report_id=seeded["report_id"]
        )
        assert trace is not None
        # Broken reference -> explicit warning -> partial, never fabricated.
        assert trace["completeness"] == "partial"
        assert any("not found" in w for w in trace["warnings"])
        # The specific broken reference (ghost id) must be reported.
        assert str(ghost) in " ".join(trace["warnings"])
    finally:
        await conn.close()
