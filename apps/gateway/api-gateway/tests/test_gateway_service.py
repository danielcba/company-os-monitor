"""Unit tests for GatewayService (auth, authorization, boundary, tenant scope).

Uses a fake JWT + fake stores (no PG). Covers: 401 on missing/invalid token,
403 on unauthorized actions (viewer commit), admin commit allowed, confidence
requirement (R4), tenant isolation (user A cannot read tenant B), service
health probing (mocked HTTP client) and metrics.
"""
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.access.errors import (
    AuthorizationError,
    InvalidTokenError,
    TenantIsolationError,
)
from libs.access.rbac import (
    RISK_HIGH,
    RISK_LOW,
    RISK_MEDIUM,
    ROLE_ADMIN,
    ROLE_SUPERADMIN,
    ROLE_VIEWER,
)
from libs.access.security import JwtService

from src.boundary import BoundaryViolationError
from src.service import GatewayService

SECRET = "dev-secret-key"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
USER_ADMIN = "00000000-0000-0000-0000-0000000000aa"
USER_VIEWER = "00000000-0000-0000-0000-0000000000bb"


class FakeDecision:
    def __init__(self, *, id, tenant_id, authority_id, commitment, risk_tolerance,
                 status="committed", committed_at=None):
        self.id = id
        self.tenant_id = tenant_id
        self.recommendation_id = uuid.uuid4()
        self.confidence_id = uuid.uuid4()
        self.authority_id = authority_id
        self.commitment = commitment
        self.risk_tolerance = risk_tolerance
        self.status = status
        self.committed_at = committed_at or datetime.now(UTC)


class FakeReport:
    def __init__(self, *, id, tenant_id, report_type, title):
        self.id = id
        self.tenant_id = tenant_id
        self.report_type = report_type
        self.title = title
        self.period_start = None
        self.period_end = None
        self.generated_at = datetime.now(UTC)


class FakeDecisionStore:
    def __init__(self, rows):
        self._rows = rows

    async def list_decisions(self, *, tenant_id):
        return [d for d in self._rows if d.tenant_id == tenant_id]


class FakeReportStore:
    def __init__(self, rows):
        self._rows = rows

    async def list_reports(self, *, tenant_id):
        return [r for r in self._rows if r.tenant_id == tenant_id]


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


@pytest.fixture
def service(jwt):
    decisions = [
        FakeDecision(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(TENANT_A),
            authority_id=uuid.UUID(USER_ADMIN),
            commitment="Expandir el volumen.",
            risk_tolerance="low",
        ),
        FakeDecision(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(TENANT_B),
            authority_id=uuid.UUID(USER_ADMIN),
            commitment="Decision de otro tenant.",
            risk_tolerance="high",
        ),
    ]
    reports = [
        FakeReport(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(TENANT_A),
            report_type="executive",
            title="Reporte A",
        ),
        FakeReport(
            id=uuid.uuid4(),
            tenant_id=uuid.UUID(TENANT_B),
            report_type="technical",
            title="Reporte B",
        ),
    ]
    return GatewayService(
        jwt, decision_store=FakeDecisionStore(decisions), report_store=FakeReportStore(reports)
    )


def _token(jwt, *, role=ROLE_ADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A):
    return jwt.create_access_token(
        user_id=user_id, tenant_id=tenant_id, email=f"{role}@x.test", role=role
    )


async def _auth(service, token):
    return service.authenticate(f"Bearer {token}")


# ---------------------------------------------------------------------- auth
def test_authenticate_missing_token_401(service):
    with pytest.raises(InvalidTokenError):
        service.authenticate("")


def test_authenticate_invalid_token_401(service, jwt):
    with pytest.raises(InvalidTokenError):
        service.authenticate("Bearer not-a-jwt")


def test_authenticate_valid_token_returns_payload(service, jwt):
    token = _token(jwt, role=ROLE_ADMIN)
    payload = service.authenticate(f"Bearer {token}")
    assert payload.role == ROLE_ADMIN
    assert payload.tenant_id == TENANT_A


# -------------------------------------------------------------- authorize
def test_authorize_viewer_commit_denied(service, jwt):
    token = _token(jwt, role=ROLE_VIEWER, user_id=USER_VIEWER)
    payload = service.authenticate(f"Bearer {token}")
    with pytest.raises(AuthorizationError):
        service.require_authorized(token=payload, action="commit", risk=RISK_LOW)


def test_authorize_viewer_propose_denied(service, jwt):
    token = _token(jwt, role=ROLE_VIEWER, user_id=USER_VIEWER)
    payload = service.authenticate(f"Bearer {token}")
    with pytest.raises(AuthorizationError):
        service.require_authorized(token=payload, action="propose")


def test_authorize_admin_commit_low_medium_allowed(service, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN)
    payload = service.authenticate(f"Bearer {token}")
    service.require_authorized(token=payload, action="commit", risk=RISK_LOW)
    service.require_authorized(token=payload, action="commit", risk=RISK_MEDIUM)


def test_authorize_admin_commit_high_denied(service, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN)
    payload = service.authenticate(f"Bearer {token}")
    with pytest.raises(AuthorizationError):
        service.require_authorized(token=payload, action="commit", risk=RISK_HIGH)


def test_authorize_superadmin_commit_high_allowed(service, jwt):
    token = _token(jwt, role=ROLE_SUPERADMIN, user_id=USER_ADMIN)
    payload = service.authenticate(f"Bearer {token}")
    service.require_authorized(token=payload, action="commit", risk=RISK_HIGH)


def test_authorize_ack_allowed_for_operator_admin(service, jwt):
    token = _token(jwt, role=ROLE_ADMIN)
    payload = service.authenticate(f"Bearer {token}")
    service.require_authorized(token=payload, action="ack")


def test_authorize_execute_only_superadmin(service, jwt):
    token = _token(jwt, role=ROLE_ADMIN)
    payload = service.authenticate(f"Bearer {token}")
    with pytest.raises(AuthorizationError):
        service.require_authorized(token=payload, action="execute")
    super_token = _token(jwt, role=ROLE_SUPERADMIN)
    super_payload = service.authenticate(f"Bearer {super_token}")
    service.require_authorized(token=super_payload, action="execute")


# ---------------------------------------------------------------- boundary
def test_enforce_boundary_missing_confidence_raises(service, jwt):
    with pytest.raises(BoundaryViolationError):
        service.enforce_boundary("commit", {})


def test_enforce_boundary_commit_with_confidence_ok(service, jwt):
    service.enforce_boundary("commit", {"confidence_score": 0.85})


def test_enforce_boundary_unknown_action_raises(service, jwt):
    with pytest.raises(BoundaryViolationError):
        service.enforce_boundary("format_disk", {})


# -------------------------------------------------------------- tenant scope
async def test_list_decisions_only_own_tenant(service, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    payload = service.authenticate(f"Bearer {token}")
    decisions = await service.list_decisions(payload, TENANT_A)
    assert len(decisions) == 1
    assert decisions[0]["tenant_id"] == TENANT_A
    assert "Decision de otro tenant" not in [
        d["commitment"] for d in decisions
    ]


async def test_list_decisions_cross_tenant_admin_denied(service, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    payload = service.authenticate(f"Bearer {token}")
    with pytest.raises(TenantIsolationError):
        await service.list_decisions(payload, TENANT_B)


async def test_list_decisions_cross_tenant_superadmin_allowed(service, jwt):
    token = _token(jwt, role=ROLE_SUPERADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    payload = service.authenticate(f"Bearer {token}")
    decisions = await service.list_decisions(payload, TENANT_B)
    assert len(decisions) == 1
    assert decisions[0]["tenant_id"] == TENANT_B


async def test_list_reports_tenant_isolation(service, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    payload = service.authenticate(f"Bearer {token}")
    reports = await service.list_reports(payload, TENANT_A)
    assert len(reports) == 1
    assert reports[0]["title"] == "Reporte A"


async def test_decision_payload_includes_authority_binding(service, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    payload = service.authenticate(f"Bearer {token}")
    decisions = await service.list_decisions(payload, TENANT_A)
    assert decisions[0]["authority_id"] == USER_ADMIN
    assert decisions[0]["confidence_id"]
    assert decisions[0]["risk_tolerance"] == "low"


# ------------------------------------------------------------- service health
async def test_check_service_health_forwards_and_reports(service):
    class FakeClient:
        def __init__(self, responses):
            self._responses = responses

        async def get(self, url):
            status = self._responses.get(url, 200)
            return SimpleNamespace(status_code=status)

        async def aclose(self):
            return None

    service.service_health = {
        "decision": "http://localhost:8097/health",
        "report": "http://localhost:8098/health",
    }
    client = FakeClient(
        {"http://localhost:8097/health": 200, "http://localhost:8098/health": 503}
    )
    results = await service.check_service_health(client=client)
    by_service = {r["service"]: r for r in results}
    assert by_service["decision"]["healthy"] is True
    assert by_service["decision"]["status"] == 200
    assert by_service["report"]["healthy"] is False
    assert service.total_forwarded == 1


# ------------------------------------------------------------------- metrics
def test_metrics_exposed(service):
    service.total_requests = 5
    service.total_rejected_401 = 1
    service.total_rejected_403 = 2
    service.total_boundary_violations = 1
    metrics = service.metrics()
    assert metrics["total_requests"] == 5
    assert metrics["total_rejected_401"] == 1
    assert metrics["total_rejected_403"] == 2
    assert metrics["total_boundary_violations"] == 1


# ------------------------------------------------------- ADR-0002 (structural)
def test_gateway_does_not_import_pipeline_logic():
    """The gateway enforces the boundary; it never embeds pipeline logic.

    It consumes the access layer (JWT/RBAC) and READ-only stores for
    decisions/reports; it must not import the pipeline capability packages
    (perception/reasoning) that would let an external capability bypass the
    canonical flow (R3 enforced at dependency level).
    """
    import src.boundary
    import src.health
    import src.main
    import src.service

    for module in (src.boundary, src.health, src.main, src.service):
        text = Path(module.__file__).read_text(encoding="utf-8")
        for blocked in ("libs.perception", "libs.reasoning"):
            assert blocked not in text, (
                f"{module.__name__} imports {blocked} (ADR-0002 boundary)"
            )