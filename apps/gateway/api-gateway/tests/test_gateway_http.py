"""HTTP handler tests for the API Gateway (fake requests + fake stores).

Acceptance: request without token -> 401; viewer commit -> 403; admin commit
-> allowed; missing Confidence (R4) -> 400; tenant isolation on READ routes.
"""
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from libs.access.rbac import (
    ROLE_ADMIN,
    ROLE_SUPERADMIN,
    ROLE_VIEWER,
)
from libs.access.security import JwtService

from src.health import GatewayServer
from src.service import GatewayService

SECRET = "dev-secret-key"
TENANT_A = "00000000-0000-0000-0000-00000000000a"
TENANT_B = "00000000-0000-0000-0000-00000000000b"
USER_ADMIN = "00000000-0000-0000-0000-0000000000aa"
USER_VIEWER = "00000000-0000-0000-0000-0000000000bb"


class _Decision:
    def __init__(self, *, tenant_id):
        self.id = uuid.uuid4()
        self.tenant_id = tenant_id
        self.recommendation_id = uuid.uuid4()
        self.confidence_id = uuid.uuid4()
        self.authority_id = uuid.UUID(USER_ADMIN)
        self.commitment = "Expandir el volumen antes del umbral."
        self.risk_tolerance = "low"
        self.status = "committed"
        self.committed_at = datetime.now(UTC)


class _Report:
    def __init__(self, *, tenant_id):
        self.id = uuid.uuid4()
        self.tenant_id = tenant_id
        self.report_type = "executive"
        self.title = "Reporte"
        self.period_start = None
        self.period_end = None
        self.generated_at = datetime.now(UTC)


class _Observation:
    def __init__(self, *, tenant_id, fact_type="cpu_utilization_percent", quality_class="Q1"):
        self.id = uuid.uuid4()
        self.tenant_id = tenant_id
        self.source_id = uuid.uuid4()
        self.source_type = "linux_agent"
        self.fact_type = fact_type
        self.fact_value = {"value": 94}
        self.unit = "%"
        self.captured_at = datetime.now(UTC)
        self.quality_class = quality_class
        self.raw_payload = {"agent": "linux-agent-1"}


class _DecisionStore:
    def __init__(self):
        self.rows = [_Decision(tenant_id=uuid.UUID(TENANT_A))]

    async def list_decisions(self, *, tenant_id):
        return [d for d in self.rows if d.tenant_id == tenant_id]


class _FakeConfidenceStore:
    """Mock confidence store for tests that don't test provenance."""

    async def get_confidence_for_boundary(self, *, tenant_id, confidence_id, expected_target_type, expected_target_id=None):
        return {"confidence_score": 0.5, "verified": True}


class _ReportStore:
    def __init__(self):
        self.rows = [_Report(tenant_id=uuid.UUID(TENANT_A))]

    async def list_reports(self, *, tenant_id):
        return [r for r in self.rows if r.tenant_id == tenant_id]


class _ObservationStore:
    def __init__(self):
        self.rows = [
            _Observation(tenant_id=uuid.UUID(TENANT_A), fact_type="cpu_utilization_percent", quality_class="Q1"),
            _Observation(tenant_id=uuid.UUID(TENANT_A), fact_type="memory_free_bytes", quality_class="Q2"),
            _Observation(tenant_id=uuid.UUID(TENANT_A), fact_type="disk_usage_percent", quality_class="Q1"),
        ]

    async def list_observations(self, *, tenant_id, limit=50, offset=0, fact_type=None, source_type=None, quality_class=None, sort="captured_at_desc"):
        filtered = [o for o in self.rows if o.tenant_id == tenant_id]
        if fact_type:
            filtered = [o for o in filtered if o.fact_type == fact_type]
        if source_type:
            filtered = [o for o in filtered if o.source_type == source_type]
        if quality_class:
            filtered = [o for o in filtered if o.quality_class == quality_class]

        # Sort
        reverse = sort == "captured_at_desc"
        filtered.sort(key=lambda o: o.captured_at, reverse=reverse)

        # Paginate
        paginated = filtered[offset:offset + limit]

        # Build facets
        all_tenant = [o for o in self.rows if o.tenant_id == tenant_id]
        fact_types = sorted({o.fact_type for o in all_tenant})
        source_types = sorted({o.source_type for o in all_tenant})
        quality_classes = ["Q1", "Q2", "Q3", "Q4"]

        # Convert to dict format
        observations = []
        for o in paginated:
            observations.append({
                "id": str(o.id),
                "tenant_id": str(o.tenant_id),
                "source_id": str(o.source_id),
                "source_type": o.source_type,
                "fact_type": o.fact_type,
                "fact_value": o.fact_value,
                "unit": o.unit,
                "captured_at": o.captured_at.isoformat(),
                "quality_class": o.quality_class,
                "raw_payload": o.raw_payload,
            })

        return {
            "observations": observations,
            "total": len(filtered),
            "limit": limit,
            "offset": offset,
            "facets": {
                "fact_types": fact_types,
                "source_types": source_types,
                "quality_classes": quality_classes,
            },
        }


class FakeRequest:
    def __init__(self, *, headers=None, body=None, match_info=None, query=None):
        self.headers = headers or {}
        self._body = body or {}
        self.match_info = match_info or {}
        self.query = query or {}

    async def json(self):
        return self._body


@pytest.fixture
def jwt():
    return JwtService(algorithm="HS256", secret_key=SECRET)


@pytest.fixture
def server(jwt):
    service = GatewayService(
        jwt,
        decision_store=_DecisionStore(),
        report_store=_ReportStore(),
        observation_store=_ObservationStore(),
        confidence_store=_FakeConfidenceStore(),
    )
    return GatewayServer(service, jwt)


def _token(jwt, *, role=ROLE_ADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A):
    return jwt.create_access_token(
        user_id=user_id, tenant_id=tenant_id, email=f"{role}@x.test", role=role
    )


async def _json(response):
    return json.loads(response.body)


# ------------------------------------------------------------------ auth (401)
async def test_services_health_without_token_401(server):
    response = await server.services_health_handler(FakeRequest())
    assert response.status == 401


async def test_decisions_without_token_401(server):
    response = await server.decisions_handler(
        FakeRequest(match_info={"tenant_id": TENANT_A})
    )
    assert response.status == 401


async def test_action_without_token_401(server):
    response = await server.action_handler(
        FakeRequest(match_info={"action": "commit"}, body={})
    )
    assert response.status == 401


async def test_observations_without_token_401(server):
    response = await server.observations_handler(
        FakeRequest(match_info={"tenant_id": TENANT_A})
    )
    assert response.status == 401


# ----------------------------------------------------------- boundary (400)
async def test_commit_missing_confidence_400(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN)
    response = await server.action_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"action": "commit"},
            body={"risk_tolerance": "low"},
        )
    )
    assert response.status == 400
    body = await _json(response)
    assert "Confidence" in body["error"]


async def test_commit_unknown_action_400(server, jwt):
    token = _token(jwt, role=ROLE_SUPERADMIN)
    response = await server.action_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"action": "format_disk"},
            body={"confidence_score": 0.9},
        )
    )
    assert response.status == 400


async def test_observations_invalid_limit_400(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN)
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
            query={"limit": "9999"},
        )
    )
    assert response.status == 400


async def test_observations_invalid_quality_class_400(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN)
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
            query={"quality_class": "Q5"},
        )
    )
    assert response.status == 400


async def test_observations_invalid_sort_400(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN)
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
            query={"sort": "invalid_sort"},
        )
    )
    assert response.status == 400


# ----------------------------------------------------------- authorization
async def test_viewer_commit_403(server, jwt):
    token = _token(jwt, role=ROLE_VIEWER, user_id=USER_VIEWER)
    response = await server.action_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"action": "commit"},
            body={"confidence_id": "test-uuid", "risk_tolerance": "low"},
        )
    )
    assert response.status == 403


async def test_admin_commit_low_allowed(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN)
    response = await server.action_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"action": "commit"},
            body={"confidence_id": "test-uuid", "risk_tolerance": "low"},
        )
    )
    assert response.status == 200
    body = await _json(response)
    assert body["authorized"] is True
    assert body["action"] == "commit"
    assert body["authority"]["role"] == ROLE_ADMIN
    assert body["authority"]["tenant_id"] == TENANT_A


async def test_admin_commit_high_403(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN)
    response = await server.action_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"action": "commit"},
            body={"confidence_id": "test-uuid", "risk_tolerance": "high"},
        )
    )
    assert response.status == 403


async def test_superadmin_commit_high_allowed(server, jwt):
    token = _token(jwt, role=ROLE_SUPERADMIN, user_id=USER_ADMIN)
    response = await server.action_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"action": "commit"},
            body={"confidence_id": "test-uuid", "risk_tolerance": "high"},
        )
    )
    assert response.status == 200


async def test_operator_ack_allowed_but_commit_forbidden(server, jwt):
    token = _token(jwt, role="operator", user_id=USER_VIEWER)
    response = await server.action_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"action": "ack"},
            body={},
        )
    )
    assert response.status == 200
    response = await server.action_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"action": "commit"},
            body={"confidence_id": "test-uuid", "risk_tolerance": "low"},
        )
    )
    assert response.status == 403


# ------------------------------------------------------- tenant read isolation
async def test_decisions_read_in_own_tenant(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN)
    response = await server.decisions_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
        )
    )
    assert response.status == 200
    body = await _json(response)
    assert len(body["decisions"]) == 1
    assert body["decisions"][0]["tenant_id"] == TENANT_A
    assert body["decisions"][0]["authority_id"] == USER_ADMIN


async def test_decisions_read_cross_tenant_admin_403(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    response = await server.decisions_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_B},
        )
    )
    assert response.status == 403


async def test_decisions_read_cross_tenant_superadmin_200(server, jwt):
    token = _token(jwt, role=ROLE_SUPERADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    response = await server.decisions_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_B},
        )
    )
    # tenant B has no decisions seeded -> empty list, not 403.
    assert response.status == 200
    body = await _json(response)
    assert body["decisions"] == []


async def test_reports_read_in_own_tenant(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN)
    response = await server.reports_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
        )
    )
    assert response.status == 200
    body = await _json(response)
    assert len(body["reports"]) == 1


async def test_observations_read_in_own_tenant(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN)
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
        )
    )
    assert response.status == 200
    body = await _json(response)
    assert "observations" in body
    assert body["total"] == 3
    assert len(body["observations"]) == 3
    assert "facets" in body
    assert set(body["facets"]["quality_classes"]) == {"Q1", "Q2", "Q3", "Q4"}


async def test_observations_read_cross_tenant_admin_403(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_B},
        )
    )
    assert response.status == 403


async def test_observations_read_cross_tenant_superadmin_200(server, jwt):
    token = _token(jwt, role=ROLE_SUPERADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_B},
        )
    )
    # tenant B has no data seeded -> empty list, not 403.
    assert response.status == 200
    body = await _json(response)
    assert body["observations"] == []
    assert body["total"] == 0


async def test_observations_pagination_and_filters(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN)
    # Test pagination
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
            query={"limit": "2", "offset": "0"},
        )
    )
    assert response.status == 200
    body = await _json(response)
    assert len(body["observations"]) == 2
    assert body["limit"] == 2
    assert body["offset"] == 0

    # Test filter by fact_type
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
            query={"fact_type": "cpu_utilization_percent"},
        )
    )
    assert response.status == 200
    body = await _json(response)
    assert all(o["fact_type"] == "cpu_utilization_percent" for o in body["observations"])

    # Test filter by quality_class
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
            query={"quality_class": "Q1"},
        )
    )
    assert response.status == 200
    body = await _json(response)
    assert all(o["quality_class"] == "Q1" for o in body["observations"])

    # Test sort
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
            query={"sort": "captured_at_asc"},
        )
    )
    assert response.status == 200
    body = await _json(response)
    # Should be sorted ascending
    dates = [o["captured_at"] for o in body["observations"]]
    assert dates == sorted(dates)


async def test_observations_viewer_allowed(server, jwt):
    token = _token(jwt, role=ROLE_VIEWER, user_id=USER_VIEWER, tenant_id=TENANT_A)
    response = await server.observations_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
        )
    )
    assert response.status == 200


# ------------------------------------------------------- cognitive summary
async def test_cognitive_summary_without_token_401(server):
    response = await server.cognitive_summary_handler(
        FakeRequest(match_info={"tenant_id": TENANT_A})
    )
    assert response.status == 401


async def test_cognitive_summary_viewer_own_tenant_200(server, jwt):
    token = _token(jwt, role=ROLE_VIEWER, user_id=USER_VIEWER, tenant_id=TENANT_A)
    response = await server.cognitive_summary_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_A},
        )
    )
    assert response.status == 200
    body = await _json(response)
    assert body["totals"]["observations"] >= 0
    assert body["totals"]["evidence"] >= 0


async def test_cognitive_summary_cross_tenant_admin_403(server, jwt):
    token = _token(jwt, role=ROLE_ADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    response = await server.cognitive_summary_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_B},
        )
    )
    assert response.status == 403


async def test_cognitive_summary_cross_tenant_superadmin_200(server, jwt):
    token = _token(jwt, role=ROLE_SUPERADMIN, user_id=USER_ADMIN, tenant_id=TENANT_A)
    response = await server.cognitive_summary_handler(
        FakeRequest(
            headers={"Authorization": f"Bearer {token}"},
            match_info={"tenant_id": TENANT_B},
        )
    )
    # tenant B has no data seeded -> empty counts, not 403.
    assert response.status == 200
    body = await _json(response)
    assert body["totals"]["observations"] == 0


# ------------------------------------------------------------- metrics (public)
async def test_metrics_public(server):
    response = await server.metrics_handler(FakeRequest())
    body = await _json(response)
    assert "total_requests" in body
