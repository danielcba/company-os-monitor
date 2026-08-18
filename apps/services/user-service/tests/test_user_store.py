"""Integration tests for User persistence (multi-tenant, external ADR-0002).

Requires the sandbox infra (postgres at 127.0.0.1:5433) and the Sprint 12
migration applied (users table). Verifies INSERT/read-back, bcrypt hashing
(never plaintext), password verification, email uniqueness (dedup) and strict
tenant isolation in queries.
"""
import sys
import uuid
from pathlib import Path

import asyncpg
import pytest
import sqlalchemy

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.access.security import hash_password, verify_password
from libs.access.users import UserStore

DSN_STORE = "postgresql+asyncpg://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"
DSN_RAW = "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor"


async def _create_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute(
            "INSERT INTO tenants (id, name, slug) VALUES ($1, $2, $3) "
            "ON CONFLICT (id) DO NOTHING",
            tenant_id,
            f"usr-{tenant_id}",
            f"usrslug-{tenant_id}",
        )
    finally:
        await conn.close()


async def _cleanup_tenant(tenant_id: uuid.UUID) -> None:
    conn = await asyncpg.connect(DSN_RAW)
    try:
        await conn.execute("SET session_replication_role = replica")
        await conn.execute("DELETE FROM users WHERE tenant_id = $1", tenant_id)
        await conn.execute("DELETE FROM tenants WHERE id = $1", tenant_id)
        await conn.execute("SET session_replication_role = origin")
    finally:
        await conn.close()


@pytest.fixture
async def user_store():
    instance = UserStore(DSN_STORE)
    await instance.verify_connection()
    yield instance
    await instance.close()


async def test_user_insert_read_back_hash_not_plaintext(user_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        user = await user_store.create_user(
            tenant_id=tenant_id,
            email=f"admin-{tenant_id}@sandbox.local",
            password_hash=hash_password("cosmonitor"),
            name="Test Admin",
            role="superadmin",
            is_active=True,
        )
        assert user is not None
        assert user.role == "superadmin"
        assert user.password_hash != "cosmonitor"
        assert user.password_hash.startswith("$2b$")
        assert verify_password("cosmonitor", user.password_hash)
        assert not verify_password("wrong", user.password_hash)

        fetched = await user_store.get_by_email(
            email=f"admin-{tenant_id}@sandbox.local"
        )
        assert fetched == user
        assert fetched.tenant_id == tenant_id
        assert fetched.is_active is True
    finally:
        await _cleanup_tenant(tenant_id)


async def test_user_email_unique_dedup(user_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        email = f"dup-{tenant_id}@sandbox.local"
        first = await user_store.create_user(
            tenant_id=tenant_id,
            email=email,
            password_hash=hash_password("a"),
            name="One",
            role="viewer",
        )
        second = await user_store.create_user(
            tenant_id=tenant_id,
            email=email,
            password_hash=hash_password("b"),
            name="Two",
            role="admin",
        )
        assert first is not None
        assert second is None  # ON CONFLICT (email) DO NOTHING -> dedup
        conn = await asyncpg.connect(DSN_RAW)
        try:
            count = await conn.fetchval(
                "SELECT count(*) FROM users WHERE email = $1", email
            )
        finally:
            await conn.close()
        assert count == 1
    finally:
        await _cleanup_tenant(tenant_id)


async def test_user_tenant_isolation_in_queries(user_store):
    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    await _create_tenant(tenant_a)
    await _create_tenant(tenant_b)
    try:
        await user_store.create_user(
            tenant_id=tenant_a,
            email=f"a-{tenant_a}@x.test",
            password_hash=hash_password("x"),
            name="A",
            role="viewer",
        )
        await user_store.create_user(
            tenant_id=tenant_b,
            email=f"b-{tenant_b}@x.test",
            password_hash=hash_password("x"),
            name="B",
            role="admin",
        )
        list_a = await user_store.list_by_tenant(tenant_id=tenant_a)
        list_b = await user_store.list_by_tenant(tenant_id=tenant_b)
        assert len(list_a) == 1 and list_a[0].email.endswith("@x.test")
        assert f"a-{tenant_a}" in list_a[0].email
        assert f"b-{tenant_b}" not in [u.email for u in list_a]
        assert len(list_b) == 1
        assert f"a-{tenant_a}" not in [u.email for u in list_b]
        # get_by_id only returns the user of the tenant that owns it.
        fetched_b = await user_store.get_by_id(id=list_b[0].id)
        assert fetched_b.tenant_id == tenant_b
    finally:
        await _cleanup_tenant(tenant_a)
        await _cleanup_tenant(tenant_b)


async def test_user_schema_check_rejects_unknown_role(user_store):
    tenant_id = uuid.uuid4()
    await _create_tenant(tenant_id)
    try:
        with pytest.raises(sqlalchemy.exc.IntegrityError, match="users_role_check"):
            await user_store.create_user(
                tenant_id=tenant_id,
                email=f"bad-{tenant_id}@x.test",
                password_hash=hash_password("x"),
                name="Bad",
                role="god",
            )
    finally:
        await _cleanup_tenant(tenant_id)