"""SAP integration — Fase 4 orchestrator tests.

Covers the ``SapOrchestrator`` (R3/R4 wiring): it only processes committed
Decisions, refuses unknown/not-committed ones, passes the context through to
the bridge, and returns per-request results. Uses the mock gateway and a live
DB (decision store + posting log + finance store); skips when DB is down.
"""
from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import asyncpg
import pytest

from tests._config import TEST_DATABASE_URL

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))  # noqa: E402

from libs.action.decision import DecisionCreate, DecisionStore, build_decision  # noqa: E402
from libs.integrations.sap import (  # noqa: E402
    AssetFinanceCreate,
    AssetFinanceStore,
    MockSapGateway,
    SapBridge,
    SapOrchestrator,
    SapPostingLogStore,
    SapPostRequest,
    build_asset_finance,
)

DSN = TEST_DATABASE_URL


async def _ensure_tenant(tenant_id: uuid.UUID) -> None:
    pg_dsn = DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"sap4-{tenant_id.hex[:8]}",
            f"sap4-{tenant_id.hex}",
        )
    finally:
        await conn.close()


async def _seed_committed_decision(
    decision_store: DecisionStore, tenant_id: uuid.UUID, decision_id: uuid.UUID
) -> None:
    """Insert the minimal canonical FK chain (hypothesis -> confidence ->
    recommendation -> decision) so the decision row satisfies all constraints."""
    pg_dsn = DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        hypothesis_id = uuid.uuid4()
        confidence_id = uuid.uuid4()
        recommendation_id = uuid.uuid4()
        await conn.execute(
            "INSERT INTO hypotheses (id, tenant_id, anomaly_ids, description, "
            "predicted_consequences, falsification_criterion, coherence_score) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7)",
            hypothesis_id,
            tenant_id,
            [],
            "test hypothesis",
            '{"p": "x"}',
            "criterion",
            0.5,
        )
        await conn.execute(
            "INSERT INTO confidence_scores (id, tenant_id, target_type, target_id, "
            "evidential_support, explanatory_coherence, historical_calibration, "
            "confidence_score, alpha, calibration_justification, "
            "calibration_error_estimate) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11)",
            confidence_id,
            tenant_id,
            "hypothesis",
            hypothesis_id,
            0.8,
            0.8,
            0.9,
            0.85,
            0.5,
            "test calibration",
            0.05,
        )
        await conn.execute(
            "INSERT INTO recommendations (id, tenant_id, hypothesis_id, confidence_id, "
            "action_description, rationale, expected_consequences, confidence_score) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, $8)",
            recommendation_id,
            tenant_id,
            hypothesis_id,
            confidence_id,
            "post downtime",
            "rationale",
            '{"c": "x"}',
            0.85,
        )
        create = DecisionCreate(
            tenant_id=tenant_id,
            recommendation_id=recommendation_id,
            confidence_id=confidence_id,
            authority_id=uuid.uuid4(),
            commitment="post downtime cost",
            expected_outcomes=[
                {"prediction": "0.9", "verifiable_by": "sap_posting", "deadline": "2026-12-01"}
            ],
            risk_tolerance="low",
            status="committed",
        )
        decision = build_decision(create).model_copy(update={"id": decision_id})
        await decision_store.save_decision(decision)
    finally:
        await conn.close()


@pytest.fixture
async def stores():
    decision_store = DecisionStore(DSN)
    finance = AssetFinanceStore(DSN)
    log = SapPostingLogStore(DSN)
    try:
        await decision_store.verify_connection()
        await finance.verify_connection()
        await log.verify_connection()
    except Exception as exc:  # noqa: BLE001
        await decision_store.close()
        await finance.close()
        await log.close()
        if os.getenv("CI"):
            pytest.fail(f"PostgreSQL not available at {DSN}: {exc}")
        pytest.skip(f"PostgreSQL not available at {DSN}: {exc}")
    yield decision_store, finance, log
    await decision_store.close()
    await finance.close()
    await log.close()


async def test_orchestrator_processes_committed_and_skips_not_committed(stores):
    decision_store, finance, log = stores
    tenant = uuid.uuid4()
    await _ensure_tenant(tenant)

    committed_id = uuid.uuid4()
    await _seed_committed_decision(decision_store, tenant, committed_id)
    missing_id = uuid.uuid4()

    asset = uuid.uuid4()
    create = AssetFinanceCreate(
        tenant_id=tenant, asset_id=asset, rate_per_hour=100.0, currency="USD"
    )
    await finance.save(build_asset_finance(create))

    gw = MockSapGateway()
    bridge = SapBridge(
        gateway=gw, finance_store=finance, posting_log_store=log, gateway_kind="mock"
    )
    orch = SapOrchestrator(
        decision_store=decision_store, bridge=bridge, posting_log_store=log
    )

    result = await orch.process(
        tenant_id=tenant,
        requests=[
            SapPostRequest(decision_id=committed_id, asset_id=asset, hours_down=2.0),
            SapPostRequest(decision_id=missing_id, asset_id=asset, hours_down=1.0),
        ],
        authority_id=uuid.uuid4(),
    )
    results = result["results"]
    assert len(results) == 2  # noqa: PLR2004
    # committed => posted
    assert results[0]["ok"] is True
    assert results[0]["outcome"] == "success"
    assert results[0]["decision_id"] == str(committed_id)
    # missing/not committed => refused, no post
    assert results[1]["ok"] is False
    assert results[1]["outcome"] == "not_committed"
    # only one posting went out
    assert len(gw.posted_costs) == 1

    await orch.close()


async def test_orchestrator_list_postings(stores):
    decision_store, finance, log = stores
    tenant = uuid.uuid4()
    await _ensure_tenant(tenant)

    committed_id = uuid.uuid4()
    await _seed_committed_decision(decision_store, tenant, committed_id)
    asset = uuid.uuid4()
    create = AssetFinanceCreate(
        tenant_id=tenant, asset_id=asset, rate_per_hour=50.0, currency="USD"
    )
    await finance.save(build_asset_finance(create))

    gw = MockSapGateway()
    bridge = SapBridge(
        gateway=gw, finance_store=finance, posting_log_store=log, gateway_kind="mock"
    )
    orch = SapOrchestrator(
        decision_store=decision_store, bridge=bridge, posting_log_store=log
    )
    await orch.process(
        tenant_id=tenant,
        requests=[SapPostRequest(decision_id=committed_id, asset_id=asset, hours_down=1.0)],
        authority_id=uuid.uuid4(),
    )

    rows = await orch.list_postings(tenant_id=tenant)
    assert len(rows) == 1
    assert str(rows[0]["decision_id"]) == str(committed_id)
    assert rows[0]["outcome"] == "success"

    await orch.close()
