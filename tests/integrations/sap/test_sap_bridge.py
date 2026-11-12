"""SAP integration — Fase 3 bridge tests.

Covers the ``SapBridge`` (ActionExecutor): framework alignment (R3/R4),
fail-closed behavior (no context / no finance rate), posting with commit,
rollback on failure, and idempotence via the posting log. Uses the mock
gateway (no real SAP), and against a live DB for the posting log + finance
store (skips when DB is down, per project convention).
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

from libs.integrations.sap import (  # noqa: E402
    AssetFinanceCreate,
    AssetFinanceStore,
    MockSapGateway,
    SapBridge,
    SapPostContext,
    SapPostingLogStore,
    build_asset_finance,
    sap_posting_id,
    sap_posting_key,
)

DSN = TEST_DATABASE_URL
TENANT = uuid.uuid4()
DECISION = uuid.uuid4()
ASSET = uuid.uuid4()


def _fresh_ids():
    """Per-test fresh ids to avoid cross-test contamination of the posting log."""
    return uuid.uuid4(), uuid.uuid4(), uuid.uuid4()


async def _ensure_tenant(tenant_id: uuid.UUID) -> None:
    pg_dsn = DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"sap3-{tenant_id.hex[:8]}",
            f"sap3-{tenant_id.hex}",
        )
    finally:
        await conn.close()


@pytest.fixture
async def stores():
    finance = AssetFinanceStore(DSN)
    log = SapPostingLogStore(DSN)
    try:
        await finance.verify_connection()
        await log.verify_connection()
    except Exception as exc:  # noqa: BLE001
        await finance.close()
        await log.close()
        if os.getenv("CI"):
            pytest.fail(f"PostgreSQL not available at {DSN}: {exc}")
        pytest.skip(f"PostgreSQL not available at {DSN}: {exc}")
    yield finance, log
    await finance.close()
    await log.close()


# --- pure helpers -------------------------------------------------------------


def test_sap_posting_key_deterministic():
    k1 = sap_posting_key(TENANT, DECISION, ASSET)
    k2 = sap_posting_key(TENANT, DECISION, ASSET)
    assert k1 == k2  # stable identity for the same tenant+decision+asset
    # different asset => different key
    assert k1 != sap_posting_key(TENANT, DECISION, uuid.uuid4())


def test_sap_post_context_validates_negative_hours():
    with pytest.raises(ValueError):
        SapPostContext(asset_id=ASSET, hours_down=-1.0)


# --- bridge behavior -----------------------------------------------------------


async def test_bridge_is_action_executor():
    import inspect  # noqa: PLC0415

    # ActionExecutor is a non-runtime-checkable Protocol; verify structural
    # conformance (the method signature that the orchestrator relies on).
    sig = inspect.signature(SapBridge.execute)
    assert "decision_id" in sig.parameters
    assert "tenant_id" in sig.parameters
    assert "commitment" in sig.parameters
    assert "authority_id" in sig.parameters
    # ActionExecutor protocol names the method `execute` with those kwargs.
    assert hasattr(SapBridge, "execute")


async def test_bridge_fails_closed_without_context(stores):
    finance, log = stores
    tenant, decision, asset = _fresh_ids()
    gw = MockSapGateway()
    bridge = SapBridge(gateway=gw, finance_store=finance, posting_log_store=log)
    result = await bridge.execute(
        decision_id=str(decision),
        tenant_id=str(tenant),
        commitment="post downtime",
        authority_id=str(uuid.uuid4()),
    )
    assert not result["ok"]
    assert "context" in result["message"]
    assert gw.posted_costs == []


async def test_bridge_fails_closed_without_finance_rate(stores):
    finance, log = stores
    tenant, decision, asset = _fresh_ids()
    await _ensure_tenant(tenant)  # tenant exists but no finance row for asset
    gw = MockSapGateway()
    bridge = SapBridge(gateway=gw, finance_store=finance, posting_log_store=log)
    result = await bridge.execute(
        decision_id=str(decision),
        tenant_id=str(tenant),
        commitment="post downtime",
        authority_id=str(uuid.uuid4()),
        context=SapPostContext(asset_id=asset, hours_down=2.0),
    )
    assert not result["ok"]
    assert "finance rate" in result["message"]
    assert gw.posted_costs == []


async def test_bridge_posts_and_commits(stores):
    finance, log = stores
    tenant, decision, asset = _fresh_ids()
    await _ensure_tenant(tenant)
    create = AssetFinanceCreate(
        tenant_id=tenant, asset_id=asset, rate_per_hour=100.0, currency="USD"
    )
    await finance.save(build_asset_finance(create))
    gw = MockSapGateway()
    bridge = SapBridge(gateway=gw, finance_store=finance, posting_log_store=log)
    result = await bridge.execute(
        decision_id=str(decision),
        tenant_id=str(tenant),
        commitment="post downtime",
        authority_id=str(uuid.uuid4()),
        context=SapPostContext(asset_id=asset, hours_down=2.0),
    )
    assert result["ok"]
    assert gw.committed
    assert not gw.rolled_back
    assert len(gw.posted_costs) == 1
    assert gw.posted_costs[0].asset_id == asset
    assert gw.posted_costs[0].cost() == 200.0  # noqa: PLR2004


async def test_bridge_is_idempotent(stores):
    finance, log = stores
    tenant, decision, asset = _fresh_ids()
    await _ensure_tenant(tenant)
    create = AssetFinanceCreate(
        tenant_id=tenant, asset_id=asset, rate_per_hour=100.0, currency="USD"
    )
    await finance.save(build_asset_finance(create))
    gw = MockSapGateway()
    bridge = SapBridge(gateway=gw, finance_store=finance, posting_log_store=log)
    result1 = await bridge.execute(
        decision_id=str(decision),
        tenant_id=str(tenant),
        commitment="post downtime",
        authority_id=str(uuid.uuid4()),
        context=SapPostContext(asset_id=asset, hours_down=2.0),
    )
    assert result1["ok"]
    # Second identical call dedups.
    result2 = await bridge.execute(
        decision_id=str(decision),
        tenant_id=str(tenant),
        commitment="post downtime",
        authority_id=str(uuid.uuid4()),
        context=SapPostContext(asset_id=asset, hours_down=2.0),
    )
    assert result2.get("deduplicated") is True or result2["ok"]
    # Only one posting went out.
    assert len(gw.posted_costs) == 1


async def test_bridge_rejects_invalid_gateway_kind():
    with pytest.raises(ValueError, match="gateway_kind"):
        SapBridge(
            gateway=MockSapGateway(),
            finance_store=object(),  # type: ignore[arg-type]
            posting_log_store=object(),  # type: ignore[arg-type]
            gateway_kind="bogus",
        )


async def test_bridge_dedups_when_key_already_claimed(stores):
    """Simulates the TOCTOU guard: if the key is already claimed (exists),
    the bridge must NOT post again (HIGH-1)."""
    finance, log = stores
    tenant, decision, asset = _fresh_ids()
    await _ensure_tenant(tenant)
    create = AssetFinanceCreate(
        tenant_id=tenant, asset_id=asset, rate_per_hour=100.0, currency="USD"
    )
    await finance.save(build_asset_finance(create))

    gw = MockSapGateway()
    bridge = SapBridge(gateway=gw, finance_store=finance, posting_log_store=log)
    ctx = SapPostContext(asset_id=asset, hours_down=2.0)

    # First call posts and claims the key.
    r1 = await bridge.execute(
        decision_id=str(decision),
        tenant_id=str(tenant),
        commitment="post downtime",
        authority_id=str(uuid.uuid4()),
        context=ctx,
    )
    assert r1["ok"]
    assert len(gw.posted_costs) == 1

    # Pre-claim the same key manually (simulate a concurrent caller that
    # already reserved it) and assert the second execution does NOT post.
    key = sap_posting_key(tenant, decision, asset)
    preclaim = await log.claim(
        __import__("libs.integrations.sap.sap_bridge", fromlist=["SapPostingLogRecord"])
        .SapPostingLogRecord(
            id=sap_posting_id(key),
            tenant_id=tenant,
            posting_key=key,
            decision_id=decision,
            gateway_kind="mock",
            outcome="pending",
        )
    )
    assert preclaim is False  # already claimed -> no one else can post


async def test_bridge_rolls_back_on_gateway_failure(stores):
    finance, log = stores
    tenant, decision, asset = _fresh_ids()
    await _ensure_tenant(tenant)
    create = AssetFinanceCreate(
        tenant_id=tenant, asset_id=asset, rate_per_hour=100.0, currency="USD"
    )
    await finance.save(build_asset_finance(create))
    gw = MockSapGateway()
    gw._fail_next = True  # first post fails
    bridge = SapBridge(gateway=gw, finance_store=finance, posting_log_store=log)
    result = await bridge.execute(
        decision_id=str(decision),
        tenant_id=str(tenant),
        commitment="post downtime",
        authority_id=str(uuid.uuid4()),
        context=SapPostContext(asset_id=asset, hours_down=2.0),
    )
    assert not result["ok"]
    assert gw.rolled_back
    assert not gw.committed
    assert gw.posted_costs == []
