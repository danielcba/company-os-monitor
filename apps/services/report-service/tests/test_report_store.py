"""Integration tests for Report persistence, generation and the ADR-0002 boundary.

Requires the sandbox infra (postgres at 127.0.0.1:5433) and the Sprint 11
content trigger applied. Cleanup disables the immutability triggers with
session_replication_role = replica (superuser) and deletes the child tables
first (the triggers block plain DELETEs).
"""
import asyncio
import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import asyncpg
import pytest
from libs.access.security import JwtService
from libs.action.decision import STATUS_COMMITTED, Decision, DecisionStore
from libs.action.recommendation import STATUS_PROPOSED, Recommendation, RecommendationStore
from libs.action.report import (
    REPORT_TYPE_EXECUTIVE,
    REPORT_TYPE_JSON,
    REPORT_TYPE_TECHNICAL,
    ReportCreate,
    ReportStore,
    build_report,
)
from libs.learning.confidence import Confidence, ConfidenceStore
from libs.perception.context import Context, ContextStore
from libs.perception.evidence import EvidenceStore, build_evidence
from libs.perception.observation import EvidenceCreate, QualityClass
from libs.perception.store import ObservationStore
from libs.reasoning.anomaly import Anomaly, AnomalyStore
from libs.reasoning.hypothesis import (
    STATUS_CANDIDATE,
    Hypothesis,
    HypothesisStore,
)
from libs.reasoning.pattern import Pattern, PatternStore

from src.health import ReportServer
from src.service import ReportService

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")

# Phase 20.1: report endpoints are protected by a Bearer JWT; tenant scope is
# derived from the verified token. These tests mint a token signed with a fixed
# dev secret (mirrors the gateway/user-service test pattern).
JWT_SECRET = "test-secret-key-for-report-handler-tests"


def _make_jwt() -> JwtService:
    return JwtService(algorithm="HS256", secret_key=JWT_SECRET)


def _auth_header(jwt: JwtService, tenant_id: str | uuid.UUID) -> dict[str, str]:
    token = jwt.create_access_token(
        user_id="user-test",
        tenant_id=str(tenant_id),
        email="test@x.test",
        role="admin",
    )
    return {"Authorization": f"Bearer {token}"}


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"rpt-{tenant_id}",
            f"rptslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _truncate_cognitive_tables() -> None:
    """Clean slate for isolation: drop all cognitive/report rows left by other
    suites (e.g. the Root-tests e2e writes real decisions and a Report into the
    shared Postgres). ``run_report_cycle`` scans the whole DB, so without this
    the ``ran == 0`` assertion would be polluted by upstream data. Truncating
    here keeps the test deterministic without changing product behaviour.
    """
    tables = [
        "decisions",
        "recommendations",
        "confidence_scores",
        "hypotheses",
        "insights",
        "anomalies",
        "patterns",
        "contexts",
        "evidence",
        "observations",
        "reports",
    ]
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
        await conn.execute(
            "TRUNCATE {} RESTART IDENTITY CASCADE".format(", ".join(tables))
        )
    finally:
        await conn.execute("SET session_replication_role = origin")
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
        await conn.execute("DELETE FROM reports WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM decisions WHERE tenant_id = $1", tenant_id)
        await conn.execute(
            "DELETE FROM recommendations WHERE tenant_id = $1", tenant_id
        )
        await conn.execute(
            "DELETE FROM confidence_scores WHERE tenant_id = $1", tenant_id
        )
        await conn.execute("DELETE FROM hypotheses WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM insights WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM anomalies WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM patterns WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM contexts WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM evidence WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM observations WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
        await conn.execute("SET session_replication_role = origin")
    finally:
        await conn.close()


@pytest.fixture
async def report_store():
    instance = ReportStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def decision_store():
    instance = DecisionStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def recommendation_store():
    instance = RecommendationStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def confidence_store():
    instance = ConfidenceStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def hypothesis_store():
    instance = HypothesisStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def anomaly_store():
    instance = AnomalyStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def pattern_store():
    instance = PatternStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def context_store():
    instance = ContextStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def evidence_store():
    instance = EvidenceStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


@pytest.fixture
async def observation_store():
    instance = ObservationStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


async def _seed_chain(
    tenant_id: uuid.UUID,
    context_store: ContextStore,
    evidence_store: EvidenceStore,
    anomaly_store: AnomalyStore,
    pattern_store: PatternStore,
    hypothesis_store: HypothesisStore,
    confidence_store: ConfidenceStore,
    recommendation_store: RecommendationStore,
    decision_store: DecisionStore,
    confidence_score: float = 0.82,
) -> dict:
    """Seed observation -> evidence -> context -> pattern -> anomaly -> hypothesis
    -> confidence -> recommendation -> decision; returns the created artifacts."""
    conn = await asyncpg.connect(DSN_RAW)
    obs_ids = []
    try:
        for _ in range(2):
            obs_id = uuid.uuid4()
            obs_ids.append(obs_id)
            await conn.execute(
                "INSERT INTO observations ("
                " id, tenant_id, source_id, source_type, fact_type, fact_value,"
                " unit, captured_at, quality_class, raw_payload)"
                " VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9, $10::jsonb)",
                obs_id,
                tenant_id,
                uuid.uuid4(),
                "linux_agent",
                "disk_usage_percent",
                '{"value": 0.88}',
                "percent",
                NOW - timedelta(days=2),
                "Q1",
                '{"raw": true}',
            )
    finally:
        await conn.close()

    evidence = build_evidence(
        EvidenceCreate(
            tenant_id=tenant_id,
            observation_ids=obs_ids,
            organization_type="resource_exhaustion_evidence",
            description="organizacion factual",
            quality_class=QualityClass.Q1,
            weight=0.88,
        )
    )
    await evidence_store.save_evidence(evidence)

    ctx = Context(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        evidence_ids=[evidence.id],
        mental_model_id="resource_pressure",
        purpose="infrastructure_health",
        coherence_score=0.7,
        competing_models=[],
        activated_at=NOW,
        is_active=True,
    )
    await context_store.save_context(ctx)

    pattern = Pattern(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        context_id=ctx.id,
        pattern_type="temporal",
        description="Regularidad detectada.",
        strength_measure=0.9,
        frequency="daily",
        detected_at=NOW,
        is_active=True,
    )
    await pattern_store.save_pattern(pattern)

    anomaly = Anomaly(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        context_id=ctx.id,
        pattern_id=pattern.id,
        deviation_score=2.5,
        tolerance_threshold=1.0,
        anomaly_class="point",
        detected_at=NOW,
    )
    await anomaly_store.save_anomaly(anomaly)

    hypothesis = Hypothesis(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        anomaly_ids=[anomaly.id],
        pattern_ids=[pattern.id],
        description="Hipotesis candidata de saturacion de disco.",
        predicted_consequences=["El volumen persistido seguira creciendo."],
        falsification_criterion="Si no se observa, se descarta.",
        coherence_score=0.5,
        status=STATUS_CANDIDATE,
        generated_at=NOW,
    )
    await hypothesis_store.save_hypothesis(hypothesis)

    confidence = Confidence(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        target_type="hypothesis",
        target_id=hypothesis.id,
        evidential_support=0.7,
        explanatory_coherence=0.8,
        historical_calibration=1.0,
        confidence_score=confidence_score,
        alpha=0.5,
        calibration_justification="S=0.7000, C=0.8000, ECE=0.0000, C_final=0.82.",
        calibration_error_estimate=0.0,
        computed_at=NOW,
    )
    await confidence_store.save_confidence(confidence)

    recommendation = Recommendation(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        hypothesis_id=hypothesis.id,
        insight_id=None,
        confidence_id=confidence.id,
        action_description="Expandir el volumen objetivo del almacenamiento.",
        rationale="Derivada de la hipotesis y su confidence calibrada.",
        expected_consequences=["El espacio libre permanecera por encima del umbral."],
        alternatives_considered=[
            {
                "action": "compress",
                "rationale": "Menor coste inmediato.",
                "rejected_reason": "Puede no acompanar el ritmo de crecimiento.",
                "confidence": confidence_score,
            }
        ],
        confidence_score=confidence_score,
        status=STATUS_PROPOSED,
        proposed_at=NOW,
    )
    await recommendation_store.save_recommendation(recommendation)

    commitment = (
        "Expandir el volumen objetivo del almacenamiento antes del umbral "
        "proyectado. Compromiso registrado bajo autoridad."
    )
    decision = Decision(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        recommendation_id=recommendation.id,
        confidence_id=confidence.id,
        authority_id=uuid.uuid4(),
        commitment=commitment,
        expected_outcomes=[
            {
                "prediction": "El espacio libre permanecera por encima del umbral.",
                "verifiable_by": "disk_free_percent",
                "deadline": "2026-11-15",
            }
        ],
        risk_tolerance="medium",
        status=STATUS_COMMITTED,
        committed_at=NOW,
        executed_at=None,
        actual_outcomes=None,
    )
    await decision_store.save_decision(decision)

    return {
        "evidence": evidence,
        "context": ctx,
        "pattern": pattern,
        "anomaly": anomaly,
        "hypothesis": hypothesis,
        "confidence": confidence,
        "recommendation": recommendation,
        "decision": decision,
        "observation_ids": obs_ids,
    }


async def _artifact_counts(tenant_id: uuid.UUID) -> dict:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        return await conn.fetchrow(
            "SELECT (SELECT count(*) FROM observations WHERE tenant_id = $1) AS obs,"
            "       (SELECT count(*) FROM evidence WHERE tenant_id = $1) AS ev,"
            "       (SELECT count(*) FROM contexts WHERE tenant_id = $1) AS ctx,"
            "       (SELECT count(*) FROM patterns WHERE tenant_id = $1) AS pat,"
            "       (SELECT count(*) FROM anomalies WHERE tenant_id = $1) AS ano,"
            "       (SELECT count(*) FROM hypotheses WHERE tenant_id = $1) AS hyp,"
            "       (SELECT count(*) FROM confidence_scores WHERE tenant_id = $1) AS conf,"
            "       (SELECT count(*) FROM recommendations WHERE tenant_id = $1) AS rec,"
            "       (SELECT count(*) FROM decisions WHERE tenant_id = $1) AS dec",
            tenant_id,
        )
    finally:
        await conn.close()


async def test_report_store_insert_read_back_and_list_filter(report_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        create = ReportCreate(
            tenant_id=tenant_id,
            report_type=REPORT_TYPE_EXECUTIVE,
            title="COS-Monitor Executive Summary",
            summary="Resumen ejecutivo de 1 decision.",
            content={"decision_count": 1, "top_decisions": [{"commitment": "x"}]},
            ai_generated=False,
            model_used=None,
            period_start=NOW.date(),
            period_end=NOW.date(),
            file_path="/tmp/executive.pdf",
        )
        report = build_report(create)
        row = await report_store.save_report(report)
        assert row is not None
        assert row["id"] == report.id
        assert row["report_type"] == REPORT_TYPE_EXECUTIVE
        assert row["ai_generated"] is False
        assert row["model_used"] is None

        conn = await asyncpg.connect(DSN_RAW)
        try:
            selected = await conn.fetchrow(
                "SELECT title, summary, content, ai_generated, model_used, "
                "       period_start, period_end, generated_at, file_path "
                "FROM reports WHERE id = $1",
                report.id,
            )
        finally:
            await conn.close()
        assert selected["title"] == create.title
        assert selected["summary"] == create.summary
        assert selected["ai_generated"] is False
        assert selected["model_used"] is None
        assert str(selected["period_start"]) == NOW.date().isoformat()
        assert str(selected["period_end"]) == NOW.date().isoformat()
        assert selected["file_path"] == "/tmp/executive.pdf"
        content = (
            selected["content"]
            if isinstance(selected["content"], dict)
            else json.loads(selected["content"])
        )
        assert content["decision_count"] == 1
        assert content["top_decisions"][0]["commitment"] == "x"

        listed = await report_store.list_reports(tenant_id=tenant_id)
        assert len(listed) == 1
        assert listed[0].content["decision_count"] == 1
        filtered = await report_store.list_reports(
            tenant_id=tenant_id, report_type=REPORT_TYPE_TECHNICAL
        )
        assert filtered == []
        tenant_info = await report_store.get_tenant(tenant_id=tenant_id)
        assert tenant_info is not None
        assert tenant_info["name"] == f"rpt-{tenant_id}"
    finally:
        await _cleanup_tenant(tenant_id)


async def test_report_save_is_idempotent(report_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        create = ReportCreate(
            tenant_id=tenant_id,
            report_type=REPORT_TYPE_EXECUTIVE,
            title="T",
            content={"decision_count": 0},
            period_start=NOW.date(),
            period_end=NOW.date(),
        )
        report = build_report(create)
        assert (await report_store.save_report(report)) is not None
        # Identical identity (tenant + type + period) -> same deterministic id
        # -> dedup, no new row.
        assert (await report_store.save_report(report)) is None
        rows = await report_store.list_reports(tenant_id=tenant_id)
        assert len(rows) == 1
    finally:
        await _cleanup_tenant(tenant_id)


async def test_report_content_trigger_blocks_update_and_delete(report_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        create = ReportCreate(
            tenant_id=tenant_id,
            report_type=REPORT_TYPE_EXECUTIVE,
            title="T",
            content={"decision_count": 0},
            period_start=NOW.date(),
            period_end=NOW.date(),
            file_path="/tmp/t.pdf",
        )
        report = build_report(create)
        await report_store.save_report(report)

        conn = await asyncpg.connect(DSN_RAW)
        try:
            # Immutability trigger: the row is append-only (ADR-0002 compliance).
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE reports SET title = 'x' WHERE id = $1", report.id
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "UPDATE reports SET content = '{}'::jsonb WHERE id = $1",
                    report.id,
                )
            with pytest.raises(asyncpg.PostgresError, match="immutable"):
                await conn.execute(
                    "DELETE FROM reports WHERE id = $1", report.id
                )
        finally:
            await conn.close()
    finally:
        await _cleanup_tenant(tenant_id)


async def _make_service(
    tmp_path: str, report_store
) -> tuple[ReportService, list]:
    """Build a ReportService over its own store instances (closed by the caller)."""
    internal = [
        DecisionStore(DSN_STORE),
        RecommendationStore(DSN_STORE),
        ContextStore(DSN_STORE),
        ConfidenceStore(DSN_STORE),
        HypothesisStore(DSN_STORE),
        AnomalyStore(DSN_STORE),
        PatternStore(DSN_STORE),
        EvidenceStore(DSN_STORE),
        ObservationStore(DSN_STORE),
    ]
    for store in internal:
        await store.verify_connection()
    service = ReportService(*internal, report_store, output_dir=tmp_path)
    return service, internal


async def test_service_generates_reports_over_real_decisions_and_p1(
    decision_store,
    recommendation_store,
    confidence_store,
    hypothesis_store,
    anomaly_store,
    context_store,
    evidence_store,
    pattern_store,
    report_store,
    tmp_path,
):
    """The report formats EXACTLY the committed Decision data (ADR-0002)."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        chain = await _seed_chain(
            tenant_id,
            context_store,
            evidence_store,
            anomaly_store,
            pattern_store,
            hypothesis_store,
            confidence_store,
            recommendation_store,
            decision_store,
        )
        before = await _artifact_counts(tenant_id)

        service, internal = await _make_service(str(tmp_path), report_store)
        try:
            report, status = await service.generate(tenant_id, REPORT_TYPE_EXECUTIVE)
            assert status == "created"
            assert report.report_type == REPORT_TYPE_EXECUTIVE
            assert report.ai_generated is False
            assert report.model_used is None
            assert report.content["decision_count"] == 1
            top = report.content["top_decisions"][0]
            assert top["commitment"] == chain["decision"].commitment
            assert top["confidence"] == chain["confidence"].confidence_score
            assert top["risk_tolerance"] == chain["decision"].risk_tolerance
            assert report.file_path and Path(report.file_path).exists()

            report_t, _ = await service.generate(tenant_id, REPORT_TYPE_TECHNICAL)
            assert report_t.content["decision_count"] == 1
            s6 = report_t.content["section_6_decision_and_expected_outcomes"][0]
            assert s6["commitment"] == chain["decision"].commitment
            assert s6["expected_outcomes"] == chain["decision"].expected_outcomes
            s4 = report_t.content["section_4_confidence_calibration"][0]["confidence"]
            assert s4["confidence_score"] == chain["confidence"].confidence_score
            s3 = report_t.content["section_3_reasoning_chain"][0]
            assert s3["anomalies"][0]["id"] == str(chain["anomaly"].id)
            assert s3["patterns"][0]["id"] == str(chain["pattern"].id)
            assert report_t.file_path and Path(report_t.file_path).exists()

            report_j, _ = await service.generate(tenant_id, REPORT_TYPE_JSON)
            assert report_j.content["decision_traces"][0]["decision"]["commitment"] == (
                chain["decision"].commitment
            )
            assert report_j.file_path and Path(report_j.file_path).exists()
            assert report_j.file_path.endswith(".json")

            rows = await report_store.list_reports(tenant_id=tenant_id)
            assert len(rows) == 3
            assert {r.report_type for r in rows} == {
                REPORT_TYPE_EXECUTIVE,
                REPORT_TYPE_TECHNICAL,
                REPORT_TYPE_JSON,
            }

            # P1: the Report service never writes to the cognitive tables.
            after = await _artifact_counts(tenant_id)
            assert dict(before) == dict(after)

            # Dedup: re-generating the same report of the same period adds no row.
            _, status2 = await service.generate(tenant_id, REPORT_TYPE_EXECUTIVE)
            assert status2 == "duplicate"
            assert service.total_report_duplicates == 1
            assert service.total_reports == 3
            rows = await report_store.list_reports(tenant_id=tenant_id)
            assert len(rows) == 3
            assert service.total_errors == 0
        finally:
            for store in internal:
                await store.close()
    finally:
        await _cleanup_tenant(tenant_id)


async def test_service_generates_empty_report_without_error(report_store, tmp_path):
    """A tenant without Decisions still produces a clean '0 decisiones' report."""
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        service, internal = await _make_service(str(tmp_path), report_store)
        try:
            report, status = await service.generate(tenant_id, REPORT_TYPE_EXECUTIVE)
            assert status == "created"
            assert report.content["decision_count"] == 0
            assert report.content["top_decisions"] == []
            assert service.total_errors == 0
        finally:
            for store in internal:
                await store.close()
    finally:
        await _cleanup_tenant(tenant_id)


async def test_report_cycle_and_metrics(report_store, tmp_path):
    await _truncate_cognitive_tables()
    service, internal = await _make_service(str(tmp_path), report_store)
    try:
        # No decisions anywhere -> the cycle generates nothing and reports no error.
        ran = await service.run_report_cycle()
        assert ran == 0
        assert service.total_errors == 0
    finally:
        for store in internal:
            await store.close()


def test_report_service_metrics_are_exposed():
    service = ReportService.__new__(ReportService)
    service.total_reports = 3
    service.total_report_duplicates = 1
    service.total_errors = 0
    service.by_type = {"executive": 1, "technical": 1, "json": 1}
    service.render_duration_seconds = 0.123456
    service.last_run_at = NOW
    health = ReportServer(service)

    async def get_metrics():
        response = await health.metrics_handler(SimpleNamespace())
        body = json.loads(response.body)
        assert body["total_reports"] == 3
        assert body["total_report_duplicates"] == 1
        assert body["total_errors"] == 0
        assert body["reports_by_type"] == {"executive": 1, "technical": 1, "json": 1}
        assert body["render_duration_seconds"] == 0.123456
        assert body["last_run_at"] == NOW.isoformat()

    asyncio.run(get_metrics())


async def test_generate_handler_rejects_unsupported_type():
    service = ReportService.__new__(ReportService)
    health = ReportServer(service)
    request = SimpleNamespace(query={"type": "compliance"})
    response = await health.generate_handler(request)
    assert response.status == 400
    body = json.loads(response.body)
    assert "unsupported report type" in body["error"]


async def test_generate_handler_returns_report_payload():
    tenant_id = TENANT
    jwt = _make_jwt()
    service = ReportService.__new__(ReportService)
    service.decision_store = SimpleNamespace(
        list_tenant_ids=async_wrap([tenant_id])
    )
    report = SimpleNamespace(
        id=uuid.uuid4(),
        tenant_id=tenant_id,
        report_type=REPORT_TYPE_EXECUTIVE,
        title="COS-Monitor Executive Summary",
        summary="S",
        content={"decision_count": 1},
        ai_generated=False,
        model_used=None,
        period_start=NOW.date(),
        period_end=NOW.date(),
        generated_at=NOW,
        file_path="/tmp/executive.pdf",
    )

    async def fake_generate(tid, report_type):
        return report, "created"

    service.generate = fake_generate  # type: ignore[method-assign]
    health = ReportServer(service, jwt=jwt)
    # Phase 20.1: tenant scope is taken from the verified token when no
    # tenant_id is requested.
    request = SimpleNamespace(
        query={"type": REPORT_TYPE_EXECUTIVE},
        headers=_auth_header(jwt, tenant_id),
    )
    response = await health.generate_handler(request)
    assert response.status == 200
    body = json.loads(response.body)
    assert len(body["generated"]) == 1
    assert body["generated"][0]["status"] == "created"
    assert body["generated"][0]["report_type"] == REPORT_TYPE_EXECUTIVE
    assert body["generated"][0]["content"]["decision_count"] == 1


async def test_generate_handler_without_token_is_401():
    service = ReportService.__new__(ReportService)
    health = ReportServer(service, jwt=_make_jwt())
    request = SimpleNamespace(
        query={"type": REPORT_TYPE_EXECUTIVE, "tenant_id": str(TENANT)},
        headers={},
    )
    response = await health.generate_handler(request)
    assert response.status == 401


async def test_list_handler_requires_authentication_and_uses_token_tenant():
    tenant_id = TENANT
    jwt = _make_jwt()
    service = ReportService.__new__(ReportService)

    async def fake_list_reports(tid, report_type=None):
        return []

    service.list_reports = fake_list_reports  # type: ignore[method-assign]
    health = ReportServer(service, jwt=jwt)

    # Without a token -> 401 (auth enforced before any tenant scoping).
    response = await health.list_handler(
        SimpleNamespace(query={}, headers={})
    )
    assert response.status == 401

    # With a valid token and no requested tenant_id -> 200, scoped to the
    # token's tenant (tenant isolation, Phase 20).
    response = await health.list_handler(
        SimpleNamespace(query={}, headers=_auth_header(jwt, tenant_id))
    )
    assert response.status == 200
    body = json.loads(response.body)
    assert body["reports"] == []


def async_wrap(values):
    async def _list():
        return values

    return _list