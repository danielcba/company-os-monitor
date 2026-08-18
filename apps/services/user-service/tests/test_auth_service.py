"""Unit tests for AuthService + HTTP handlers (mocked user store, no PG).

Covers login/refresh flows, token payloads, multi-tenant isolation, RBAC
authorization and the ADR-0002 boundary (no cognitive logic in auth). HTTP
handlers are exercised with a fake aiohttp request; responses are checked via
status + json body.
"""
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.access.errors import (
    AuthenticationError,
    AuthorizationError,
    InvalidTokenError,
    TenantIsolationError,
    UserConflictError,
)
from libs.access.rbac import (
    PERM_COMMIT,
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    ROLE_ADMIN,
    ROLE_OPERATOR,
    ROLE_SUPERADMIN,
    ROLE_VIEWER,
)
from libs.access.security import JwtService, hash_password
from libs.access.users import User

from src.health import UserServer
from src.service import AuthService

SECRET = "dev-secret-key"
TENANT_A = uuid.UUID("00000000-0000-0000-0000-00000000000a")
TENANT_B = uuid.UUID("00000000-0000-0000-0000-00000000000b")


class FakeUserStore:
    """In-memory UserStore implementing the same interface (tests only)."""

    def __init__(self):
        self._by_email: dict[str, User] = {}
        self._by_id: dict[uuid.UUID, User] = {}
        self._seq = 0

    async def create_user(self, *, tenant_id, email, password_hash, name, role,
                          is_active=True):
        if email in self._by_email:
            return None
        self._seq += 1
        user = User(
            id=uuid.UUID(f"00000000-0000-0000-0000-{self._seq:012x}"),
            tenant_id=tenant_id,
            email=email,
            password_hash=password_hash,
            name=name,
            role=role,
            is_active=is_active,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        self._by_email[email] = user
        self._by_id[user.id] = user
        return user

    async def get_by_email(self, *, email):
        return self._by_email.get(email)

    async def get_by_id(self, *, id):
        return self._by_id.get(id)

    async def list_by_tenant(self, *, tenant_id):
        return [u for u in self._by_id.values() if u.tenant_id == tenant_id]

    async def users_by_role(self, *, tenant_id):
        return {}

    async def verify_connection(self):
        return None

    async def close(self):
        return None


@pytest.fixture
def jwt():
    return JwtService(
        algorithm="HS256",
        secret_key=SECRET,
        access_expire_minutes=15,
        refresh_expire_days=7,
    )


@pytest.fixture
def store():
    return FakeUserStore()


@pytest.fixture
def service(store, jwt):
    return AuthService(store, jwt)


@pytest.fixture
def server(service, jwt):
    return UserServer(service, jwt)


async def _seed(store, *, email, password="cosmonitor", role="viewer", tenant_id=TENANT_A):
    return await store.create_user(
        tenant_id=tenant_id,
        email=email,
        password_hash=hash_password(password),
        name=f"name-{email}",
        role=role,
        is_active=True,
    )


class FakeRequest:
    """Minimal aiohttp-request stub for direct handler tests."""

    def __init__(self, *, body=None, headers=None, query=None):
        self._body = body or {}
        self.headers = headers or {}
        self.query = query or {}

    async def json(self):
        return self._body

    @property
    def match_info(self):
        return {}


async def _json(response):
    if response.status == 204:
        return None
    return json.loads(response.body)


# ---------------------------------------------------------------------------
# login / refresh
# ---------------------------------------------------------------------------


async def test_login_success_emits_tokens_with_role_and_tenant(service, store):
    user = await _seed(store, email="admin@a.test", role=ROLE_ADMIN)
    result = await service.login(email="admin@a.test", password="cosmonitor")
    assert result["token_type"] == "bearer"
    assert result["access_token"]
    assert result["refresh_token"]
    assert result["user"]["role"] == ROLE_ADMIN
    assert result["user"]["tenant_id"] == str(TENANT_A)
    assert str(user.id) == result["user"]["id"]
    payload = service.jwt.verify_access_token(result["access_token"])
    assert payload.role == ROLE_ADMIN
    assert payload.tenant_id == str(TENANT_A)
    assert service.total_logins == 1
    assert service.total_tokens_issued == 2
    assert service.metrics()["total_logins"] == 1


async def test_login_wrong_password_rejected(service, store):
    await _seed(store, email="admin@a.test", role=ROLE_ADMIN)
    with pytest.raises(AuthenticationError):
        await service.login(email="admin@a.test", password="wrong")
    assert service.total_login_failures == 1


async def test_login_unknown_email_rejected(service):
    with pytest.raises(AuthenticationError):
        await service.login(email="ghost@a.test", password="cosmonitor")
    assert service.total_login_failures == 1


async def test_login_inactive_user_rejected(service, store):
    await store.create_user(
        tenant_id=TENANT_A,
        email="off@a.test",
        password_hash=hash_password("cosmonitor"),
        name="off",
        role="viewer",
        is_active=False,
    )
    with pytest.raises(AuthenticationError):
        await service.login(email="off@a.test", password="cosmonitor")


async def test_login_tenant_assertion_mismatch_rejected(service, store):
    await _seed(store, email="admin@a.test", role=ROLE_ADMIN, tenant_id=TENANT_A)
    with pytest.raises(AuthenticationError):
        await service.login(
            email="admin@a.test", password="cosmonitor", tenant_id=str(TENANT_B)
        )


async def test_refresh_valid_token_reissues_access(service, store):
    user = await _seed(store, email="admin@a.test", role=ROLE_ADMIN)
    login = await service.login(email="admin@a.test", password="cosmonitor")
    refreshed = await service.refresh(refresh_token=login["refresh_token"])
    assert refreshed["access_token"]
    payload = service.jwt.verify_access_token(refreshed["access_token"])
    assert payload.user_id == str(user.id)
    assert payload.role == ROLE_ADMIN


async def test_refresh_invalid_token_rejected(service):
    with pytest.raises(InvalidTokenError):
        await service.refresh(refresh_token="not-a-token")


async def test_refresh_unknown_user_rejected(service, store, jwt):
    user = await _seed(store, email="admin@a.test", role=ROLE_ADMIN)
    login = await service.login(email="admin@a.test", password="cosmonitor")
    del store._by_id[user.id]
    with pytest.raises(AuthenticationError):
        await service.refresh(refresh_token=login["refresh_token"])


# ---------------------------------------------------------------------------
# create_user / list_users (multi-tenant isolation)
# ---------------------------------------------------------------------------


async def _actor(service, *, role, tenant_id=TENANT_A, email="actor@a.test"):
    return service.jwt.verify_access_token(
        service.jwt.create_access_token(
            user_id="00000000-0000-0000-0000-0000000000ff",
            tenant_id=str(tenant_id),
            email=email,
            role=role,
        )
    )


async def test_create_user_admin_in_own_tenant(service, store):
    actor = await _actor(service, role=ROLE_ADMIN)
    user = await service.create_user(
        actor=actor,
        email="new@a.test",
        password="secret123",
        name="New",
        role=ROLE_VIEWER,
    )
    assert user.tenant_id == TENANT_A
    assert user.role == ROLE_VIEWER
    assert user.password_hash.startswith("$2b$")
    assert store._by_email["new@a.test"].tenant_id == TENANT_A


async def test_create_user_viewer_forbidden(service, store):
    actor = await _actor(service, role=ROLE_VIEWER)
    with pytest.raises(AuthorizationError):
        await service.create_user(
            actor=actor,
            email="x@a.test",
            password="secret123",
            name="x",
            role=ROLE_VIEWER,
        )


async def test_create_user_duplicate_email_conflict(service, store):
    await _seed(store, email="dup@a.test")
    actor = await _actor(service, role=ROLE_ADMIN)
    with pytest.raises(UserConflictError):
        await service.create_user(
            actor=actor,
            email="dup@a.test",
            password="secret123",
            name="dup",
            role=ROLE_VIEWER,
        )


async def test_create_user_superadmin_cross_tenant(service, store):
    actor = await _actor(service, role=ROLE_SUPERADMIN, tenant_id=TENANT_A)
    user = await service.create_user(
        actor=actor,
        email="cross@b.test",
        password="secret123",
        name="cross",
        role=ROLE_OPERATOR,
        tenant_id=str(TENANT_B),
    )
    assert user.tenant_id == TENANT_B


async def test_create_user_admin_cross_tenant_forbidden(service, store):
    actor = await _actor(service, role=ROLE_ADMIN, tenant_id=TENANT_A)
    with pytest.raises(TenantIsolationError):
        await service.create_user(
            actor=actor,
            email="cross@b.test",
            password="secret123",
            name="cross",
            role=ROLE_OPERATOR,
            tenant_id=str(TENANT_B),
        )


async def test_create_user_unknown_role_rejected(service, store):
    actor = await _actor(service, role=ROLE_ADMIN)
    with pytest.raises(Exception) as exc_info:
        await service.create_user(
            actor=actor,
            email="r@a.test",
            password="secret123",
            name="r",
            role="god",
        )
    assert "unknown Decision Authority role" in str(exc_info.value)


async def test_list_users_tenant_isolation(service, store):
    await _seed(store, email="a1@a.test", role=ROLE_VIEWER, tenant_id=TENANT_A)
    await _seed(store, email="a2@a.test", role=ROLE_ADMIN, tenant_id=TENANT_A)
    await _seed(store, email="b1@b.test", role=ROLE_VIEWER, tenant_id=TENANT_B)
    actor = await _actor(service, role=ROLE_ADMIN, tenant_id=TENANT_A)
    users = await service.list_users(actor=actor)
    assert sorted(u.email for u in users) == ["a1@a.test", "a2@a.test"]
    assert "b1@b.test" not in [u.email for u in users]


async def test_list_users_viewer_forbidden(service, store):
    await _seed(store, email="a1@a.test", role=ROLE_VIEWER, tenant_id=TENANT_A)
    actor = await _actor(service, role=ROLE_VIEWER, tenant_id=TENANT_A)
    with pytest.raises(AuthorizationError):
        await service.list_users(actor=actor)


async def test_list_users_superadmin_cross_tenant(service, store):
    await _seed(store, email="b1@b.test", role=ROLE_VIEWER, tenant_id=TENANT_B)
    actor = await _actor(service, role=ROLE_SUPERADMIN, tenant_id=TENANT_A)
    users = await service.list_users(actor=actor, tenant_id=str(TENANT_B))
    assert [u.email for u in users] == ["b1@b.test"]


# ---------------------------------------------------------------------------
# authorize (RBAC -> Decision Authority)
# ---------------------------------------------------------------------------


def test_authorize_commit_matrix(service):
    assert service.authorize(role=ROLE_ADMIN, permission=PERM_COMMIT, risk=RISK_LOW)
    assert service.authorize(role=ROLE_ADMIN, permission=PERM_COMMIT, risk=RISK_MEDIUM)
    assert not service.authorize(
        role=ROLE_ADMIN, permission=PERM_COMMIT, risk=RISK_HIGH
    )
    assert not service.authorize(role=ROLE_VIEWER, permission=PERM_COMMIT, risk=RISK_LOW)
    assert service.authorize(
        role=ROLE_SUPERADMIN, permission=PERM_COMMIT, risk=RISK_HIGH
    )


def test_authorize_cross_tenant_requires_superadmin(service):
    assert service.authorize(
        role=ROLE_SUPERADMIN,
        permission=PERM_COMMIT,
        risk=RISK_HIGH,
        tenant_id="t2",
        actor_tenant_id="t1",
    )
    assert not service.authorize(
        role=ROLE_ADMIN,
        permission=PERM_COMMIT,
        risk=RISK_LOW,
        tenant_id="t2",
        actor_tenant_id="t1",
    )


# ---------------------------------------------------------------------------
# HTTP handlers (fake requests)
# ---------------------------------------------------------------------------


async def test_http_login_success(server, store):
    await _seed(store, email="admin@a.test", role=ROLE_ADMIN)
    response = await server.login_handler(
        FakeRequest(body={"email": "admin@a.test", "password": "cosmonitor"})
    )
    body = await _json(response)
    assert response.status == 200
    assert body["access_token"]
    assert body["user"]["role"] == ROLE_ADMIN


async def test_http_login_wrong_password_401(server, store):
    await _seed(store, email="admin@a.test", role=ROLE_ADMIN)
    response = await server.login_handler(
        FakeRequest(body={"email": "admin@a.test", "password": "wrong"})
    )
    assert response.status == 401


async def test_http_refresh_valid(server, store, service):
    await _seed(store, email="admin@a.test", role=ROLE_ADMIN)
    login = await service.login(email="admin@a.test", password="cosmonitor")
    response = await server.refresh_handler(
        FakeRequest(body={"refresh_token": login["refresh_token"]})
    )
    body = await _json(response)
    assert response.status == 200
    assert body["access_token"]


async def test_http_me_requires_token_401(server):
    response = await server.me_handler(FakeRequest())
    assert response.status == 401


async def test_http_me_with_valid_token(server, store, service):
    user = await _seed(store, email="admin@a.test", role=ROLE_ADMIN)
    token = service.jwt.create_access_token(
        user_id=str(user.id), tenant_id=str(TENANT_A), email=user.email, role=user.role
    )
    response = await server.me_handler(
        FakeRequest(headers={"Authorization": f"Bearer {token}"})
    )
    body = await _json(response)
    assert response.status == 200
    assert body["email"] == "admin@a.test"
    assert body["role"] == ROLE_ADMIN
    assert "password_hash" not in body


async def test_http_create_user_admin_201(server, store, service):
    user = await _seed(store, email="admin@a.test", role=ROLE_ADMIN)
    token = service.jwt.create_access_token(
        user_id=str(user.id), tenant_id=str(TENANT_A), email=user.email, role=user.role
    )
    response = await server.create_user_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            body={
                "email": "new@a.test",
                "password": "secret123",
                "name": "New",
                "role": ROLE_VIEWER,
            },
        )
    )
    body = await _json(response)
    assert response.status == 201
    assert body["email"] == "new@a.test"
    assert "password_hash" not in body


async def test_http_create_user_viewer_403(server, store, service):
    user = await _seed(store, email="viewer@a.test", role=ROLE_VIEWER)
    token = service.jwt.create_access_token(
        user_id=str(user.id), tenant_id=str(TENANT_A), email=user.email, role=user.role
    )
    response = await server.create_user_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            body={"email": "x@a.test", "password": "s", "name": "x",
                  "role": ROLE_VIEWER},
        )
    )
    assert response.status == 403


async def test_http_list_users_admin_200_tenant_scoped(server, store, service):
    admin = await _seed(store, email="admin@a.test", role=ROLE_ADMIN, tenant_id=TENANT_A)
    await _seed(store, email="v1@a.test", role=ROLE_VIEWER, tenant_id=TENANT_A)
    await _seed(store, email="v2@b.test", role=ROLE_VIEWER, tenant_id=TENANT_B)
    token = service.jwt.create_access_token(
        user_id=str(admin.id), tenant_id=str(TENANT_A), email=admin.email, role=admin.role
    )
    response = await server.list_users_handler(
        FakeRequest(headers={"Authorization": f"Bearer {token}"})
    )
    body = await _json(response)
    assert response.status == 200
    emails = [u["email"] for u in body["users"]]
    assert emails == ["admin@a.test", "v1@a.test"]
    assert "v2@b.test" not in emails


async def test_http_list_users_viewer_403(server, store, service):
    viewer = await _seed(store, email="viewer@a.test", role=ROLE_VIEWER, tenant_id=TENANT_A)
    token = service.jwt.create_access_token(
        user_id=str(viewer.id), tenant_id=str(TENANT_A), email=viewer.email, role=viewer.role
    )
    response = await server.list_users_handler(
        FakeRequest(headers={"Authorization": f"Bearer {token}"})
    )
    assert response.status == 403


# ---------------------------------------------------------------------------
# ADR-0002: auth must not contain cognitive pipeline logic
# ---------------------------------------------------------------------------


def test_adr0002_auth_modules_do_not_import_cognitive_pipeline():
    """Auth/RBAC modules (external, ADR-0002) never import the cognitive flow.

    Guarantees the boundary: authorization code cannot bypass the canonical
    pipeline because it has no access to it (R3 enforced at dependency level).
    """
    cognitive_modules = (
        "libs.perception",
        "libs.reasoning",
        "libs.learning",
        "libs.procedural_memory",
        "libs.action",
    )
    from libs.access import errors, rbac, security, users

    for module in (errors, rbac, security, users):
        text = Path(module.__file__).read_text(encoding="utf-8")
        for blocked in cognitive_modules:
            assert blocked not in text, (
                f"{module.__name__} imports cognitive module {blocked} (ADR-0002)"
            )