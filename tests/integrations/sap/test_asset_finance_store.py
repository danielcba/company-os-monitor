"""SAP integration — Fase 1 store integration tests (live PostgreSQL).

Exercises ``AssetFinanceStore`` against a live database, following the same
pattern as the cognitive pipeline e2e tests: when the DB is unreachable the
DB-backed tests skip instead of failing (suite stays green without
infrastructure). Uses the project test DSN. Tenants are created first so the
FK from ``asset_finance.tenant_id`` → ``tenants.id`` is satisfied.
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
    build_asset_finance,
)

DSN = TEST_DATABASE_URL


async def _ensure_tenant(tenant_id: uuid.UUID) -> None:
    """Insert a tenant row so the FK on asset_finance.tenant_id is satisfied."""
    pg_dsn = DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"sap-{tenant_id.hex[:8]}",
            f"sap-{tenant_id.hex}",
        )
    finally:
        await conn.close()


@pytest.fixture
async def store():
    s = AssetFinanceStore(DSN)
    try:
        await s.verify_connection()
    except Exception as exc:  # noqa: BLE001
        await s.close()
        if os.getenv("CI"):
            pytest.fail(f"PostgreSQL not available at {DSN}: {exc}")
        pytest.skip(f"PostgreSQL not available at {DSN}: {exc}")
    yield s
    await s.close()


async def test_save_and_get(store):
    tenant = uuid.uuid4()
    await _ensure_tenant(tenant)
    asset = uuid.uuid4()
    create = AssetFinanceCreate(
        tenant_id=tenant,
        asset_id=asset,
        rate_per_hour=RATE,
        currency="usd",
        business_value=BUSINESS_VALUE,
    )
    record = build_asset_finance(create)
    row = await store.save(record)
    assert row is not None
    assert row["id"] == record.id
    assert row["currency"] == "USD"  # normalized upper

    got = await store.get(tenant_id=tenant, asset_id=asset)
    assert got is not None
    assert got.asset_id == asset
    assert got.rate_per_hour == RATE
    assert got.currency == "USD"
    assert got.business_value == BUSINESS_VALUE


async def test_save_idempotent(store):
    tenant = uuid.uuid4()
    await _ensure_tenant(tenant)
    asset = uuid.uuid4()
    create = AssetFinanceCreate(
        tenant_id=tenant, asset_id=asset, rate_per_hour=80.0
    )
    record = build_asset_finance(create)
    first = await store.save(record)
    second = await store.save(record)
    assert first is not None
    assert second is None  # idempotent: already present -> no new row


async def test_list_for_tenant_scoped(store):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _ensure_tenant(tenant_a)
    await _ensure_tenant(tenant_b)
    for tid, asset in (
        (tenant_a, uuid.uuid4()),
        (tenant_a, uuid.uuid4()),
        (tenant_b, uuid.uuid4()),
    ):
        create = AssetFinanceCreate(
            tenant_id=tid, asset_id=asset, rate_per_hour=50.0
        )
        await store.save(build_asset_finance(create))

    rows_a = await store.list_for_tenant(tenant_id=tenant_a)
    rows_b = await store.list_for_tenant(tenant_id=tenant_b)
    assert len(rows_a) == 2  # noqa: PLR2004
    assert len(rows_b) == 1
    # tenant isolation: a's rows never contain b's assets
    a_assets = {r.asset_id for r in rows_a}
    b_assets = {r.asset_id for r in rows_b}
    assert a_assets.isdisjoint(b_assets)


async def test_exists(store):
    tenant = uuid.uuid4()
    await _ensure_tenant(tenant)
    asset = uuid.uuid4()
    create = AssetFinanceCreate(
        tenant_id=tenant, asset_id=asset, rate_per_hour=10.0
    )
    record = build_asset_finance(create)
    assert not await store.exists(id=record.id)
    await store.save(record)
    assert await store.exists(id=record.id)


async def test_updated_by_is_persisted(store):
    tenant = uuid.uuid4()
    await _ensure_tenant(tenant)
    asset = uuid.uuid4()
    author = uuid.uuid4()
    create = AssetFinanceCreate(
        tenant_id=tenant,
        asset_id=asset,
        rate_per_hour=25.0,
        updated_by=author,
    )
    await store.save(build_asset_finance(create))
    got = await store.get(tenant_id=tenant, asset_id=asset)
    assert got is not None
    assert got.updated_by == author


async def test_immutability_trigger_blocks_update_and_delete(store):
    tenant = uuid.uuid4()
    await _ensure_tenant(tenant)
    asset = uuid.uuid4()
    create = AssetFinanceCreate(
        tenant_id=tenant, asset_id=asset, rate_per_hour=10.0
    )
    record = build_asset_finance(create)
    await store.save(record)

    pg_dsn = DSN.replace("postgresql+asyncpg://", "postgresql://")
    conn = await asyncpg.connect(pg_dsn)
    try:
        # UPDATE must be rejected by the immutability trigger.
        with pytest.raises(Exception) as excinfo:
            await conn.execute(
                "UPDATE asset_finance SET rate_per_hour = 99.0 "
                "WHERE id = $1",
                record.id,
            )
        assert "immutable" in str(excinfo.value).lower()

        # DELETE must be rejected by the immutability trigger.
        with pytest.raises(Exception) as excinfo:
            await conn.execute(
                "DELETE FROM asset_finance WHERE id = $1", record.id
            )
        assert "immutable" in str(excinfo.value).lower()
    finally:
        await conn.close()


RATE = 120.0
BUSINESS_VALUE = 50000.0
