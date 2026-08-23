"""User model + persistence (external, ADR-0002, multi-tenant).

Users belong to exactly one tenant (``tenant_id`` FK -> tenants): multi-tenant
isolation is enforced by scoping every query by ``tenant_id`` (a user of tenant
A can never list or read a user/data of tenant B; the gateway enforces the same
scope). ``email`` is globally unique (login resolves the tenant from the user
row). ``password_hash`` is a bcrypt hash, never the plaintext.

This is external capability data (ADR-0002): ``users`` is NOT a cognitive
artifact, so rows are MUTABLE by design (password/role/name changes, is_active
deactivation) - there is no P1 immutability trigger, unlike the canonical
pipeline tables. ``decisions.authority_id`` (Sprint 10) may reference a real
``users.id``; the user-service guarantees consistency of who emits tokens.
"""
import uuid
from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

INSERT_USER = text(
    """
    INSERT INTO users (
        id, tenant_id, email, password_hash, name, role, is_active
    )
    VALUES (
        :id, :tenant_id, :email, :password_hash, :name, :role, :is_active
    )
    ON CONFLICT (email) DO NOTHING
    RETURNING id, tenant_id, email, password_hash, name, role, is_active,
              created_at, updated_at
    """
)

SELECT_USER_BY_EMAIL = text(
    """
    SELECT id, tenant_id, email, password_hash, name, role, is_active,
           created_at, updated_at
    FROM users
    WHERE email = :email
    """
)

SELECT_USER_BY_ID = text(
    """
    SELECT id, tenant_id, email, password_hash, name, role, is_active,
           created_at, updated_at
    FROM users
    WHERE id = :id
    """
)

SELECT_USERS_BY_TENANT = text(
    """
    SELECT id, tenant_id, email, password_hash, name, role, is_active,
           created_at, updated_at
    FROM users
    WHERE tenant_id = :tenant_id
    ORDER BY created_at, email
    """
)

SELECT_USERS_BY_TENANT_ROLE = text(
    """
    SELECT role, count(*) AS n
    FROM users
    WHERE tenant_id = :tenant_id
    GROUP BY role
    ORDER BY role
    """
)

SELECT_ALL_TENANTS = text(
    """
    SELECT id, name, slug, plan, settings, created_at, updated_at
    FROM tenants
    ORDER BY created_at, name
    """
)

SELECT_TENANT_BY_ID = text(
    """
    SELECT id, name, slug, plan, settings, created_at, updated_at
    FROM tenants
    WHERE id = :id
    """
)

UPDATE_USER = text(
    """
    UPDATE users
    SET name = COALESCE(:name, name),
        role = COALESCE(:role, role),
        is_active = COALESCE(:is_active, is_active),
        updated_at = now()
    WHERE id = :id
    RETURNING id, tenant_id, email, password_hash, name, role, is_active,
              created_at, updated_at
    """
)

DEACTIVATE_USER = text(
    """
    UPDATE users
    SET is_active = FALSE, updated_at = now()
    WHERE id = :id
    RETURNING id, tenant_id, email, password_hash, name, role, is_active,
              created_at, updated_at
    """
)


class User(BaseModel):
    """A tenant-scoped identity with its Decision Authority role (external)."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    email: str
    password_hash: str
    name: str | None = None
    role: str = "viewer"
    is_active: bool = True
    created_at: datetime = datetime.now(UTC)
    updated_at: datetime = datetime.now(UTC)

    model_config = ConfigDict(frozen=True)


class Tenant(BaseModel):
    """A tenant scope for multi-tenant isolation."""

    id: uuid.UUID
    name: str
    slug: str
    plan: str
    settings: dict = {}
    created_at: datetime = datetime.now(UTC)
    updated_at: datetime = datetime.now(UTC)

    model_config = ConfigDict(frozen=True)


class UserStore:
    """Persistence gateway for tenant-scoped users (PostgreSQL)."""

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def create_user(  # noqa: PLR0913 - user creation fields bundle
        self,
        *,
        tenant_id: uuid.UUID,
        email: str,
        password_hash: str,
        name: str | None,
        role: str,
        is_active: bool = True,
    ) -> User | None:
        """Insert one user. Returns the persisted row or None if the email
        already exists (global unique email -> the tenant is derived on login)."""
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_USER,
                {
                    "id": uuid.uuid4(),
                    "tenant_id": tenant_id,
                    "email": email,
                    "password_hash": password_hash,
                    "name": name,
                    "role": role,
                    "is_active": is_active,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return self._row_to_user(row) if row is not None else None

    async def get_by_email(self, *, email: str) -> User | None:
        async with self._session_factory() as session:
            result = await session.execute(SELECT_USER_BY_EMAIL, {"email": email})
            return self._row_to_user(result.mappings().one_or_none())

    async def get_by_id(self, *, id: uuid.UUID) -> User | None:
        async with self._session_factory() as session:
            result = await session.execute(SELECT_USER_BY_ID, {"id": id})
            return self._row_to_user(result.mappings().one_or_none())

    async def list_by_tenant(self, *, tenant_id: uuid.UUID) -> list[User]:
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_USERS_BY_TENANT, {"tenant_id": tenant_id}
            )
            return [self._row_to_user(row) for row in result.mappings()]

    async def users_by_role(self, *, tenant_id: uuid.UUID) -> dict[str, int]:
        """Count of users per role within a tenant (for /metrics)."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_USERS_BY_TENANT_ROLE, {"tenant_id": tenant_id}
            )
            return {row["role"]: row["n"] for row in result.mappings()}

    async def list_tenants(self) -> list[Tenant]:
        """List all tenants (superadmin only)."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_ALL_TENANTS)
            return [Tenant(**dict(row)) for row in result.mappings()]

    async def get_tenant_by_id(self, *, id: uuid.UUID) -> Tenant | None:
        """Get a single tenant by ID."""
        async with self._session_factory() as session:
            result = await session.execute(SELECT_TENANT_BY_ID, {"id": id})
            row = result.mappings().one_or_none()
            return Tenant(**dict(row)) if row is not None else None

    async def update_user(
        self,
        *,
        id: uuid.UUID,
        name: str | None = None,
        role: str | None = None,
        is_active: bool | None = None,
    ) -> User | None:
        """Update user fields (admin/superadmin only)."""
        async with self._session_factory() as session:
            result = await session.execute(
                UPDATE_USER,
                {"id": id, "name": name, "role": role, "is_active": is_active},
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return self._row_to_user(row) if row is not None else None

    async def deactivate_user(self, *, id: uuid.UUID) -> User | None:
        """Soft-deactivate a user (admin/superadmin only)."""
        async with self._session_factory() as session:
            result = await session.execute(DEACTIVATE_USER, {"id": id})
            await session.commit()
            row = result.mappings().one_or_none()
            return self._row_to_user(row) if row is not None else None

    async def verify_connection(self) -> None:
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()

    @staticmethod
    def _row_to_user(row) -> User | None:
        if row is None:
            return None
        return User(**dict(row))