"""SAP integration — Fase 2 gateway tests.

Covers the gateway contract (D-2026-08-07): ``SapResult`` semantics, the
factory fail-closed rule (mock never in production), ``MockSapGateway``
behavior (post/commit/rollback) and ``RfcSapGateway`` degradation when the
optional ``pyrfc`` SDK is absent (returns ``UNAVAILABLE``, never raises).
No real SAP connection is needed.
"""
from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))  # noqa: E402

from libs.integrations.sap import (  # noqa: E402
    DowntimeCost,
    MockSapGateway,
    RfcSapGateway,
    SapConfig,
    SapOutcome,
    SapResult,
    WeightedMetric,
    build_sap_gateway,
)

TENANT = uuid.uuid4()
ASSET = uuid.uuid4()


def _cost(hours: float = 2.0, rate: float = 100.0) -> DowntimeCost:
    return DowntimeCost(
        tenant_id=TENANT,
        asset_id=ASSET,
        hours_down=hours,
        rate_per_hour=rate,
    )


def _metrics() -> list[WeightedMetric]:
    return [
        WeightedMetric(tenant_id=TENANT, metric_name="availability", weight=0.8, value=99.5)
    ]


# --- SapResult ----------------------------------------------------------------


def test_sap_result_success():
    r = SapResult.success(reference="REF-1", message="ok")
    assert r.ok
    assert r.outcome == SapOutcome.SUCCESS
    assert r.reference == "REF-1"
    assert r.errors == []


def test_sap_result_failure():
    r = SapResult.failure("boom", [{"code": "E", "message": "x"}])
    assert not r.ok
    assert r.outcome == SapOutcome.FAILURE
    assert r.errors[0]["code"] == "E"


def test_sap_result_unavailable():
    r = SapResult.unavailable()
    assert not r.ok
    assert r.outcome == SapOutcome.UNAVAILABLE


# --- SapConfig (no secrets) ---------------------------------------------------


def test_sap_config_repr_excludes_credentials():
    cfg = SapConfig(rfc_destination="SM59_DEST", client="100", posting_user="sapbot")
    text = repr(cfg)
    # no password fields exist, and repr never prints them
    assert "passwd" not in text.lower()
    assert "password" not in text.lower()
    assert "sapbot" not in text.lower()  # posting_user is not exposed either
    assert "SM59_DEST" in text
    assert "100" in text


# --- Factory (fail-closed mock) ------------------------------------------------


def test_build_mock_forbidden_in_production():
    with pytest.raises(ValueError, match="MockSapGateway cannot be used in production"):
        build_sap_gateway(config=SapConfig(), environment="production", mock=True)


def test_build_mock_allowed_outside_production():
    gw = build_sap_gateway(config=SapConfig(), environment="dev", mock=True)
    assert isinstance(gw, MockSapGateway)


def test_build_rfc_when_not_mock():
    gw = build_sap_gateway(config=SapConfig(), environment="dev", mock=False)
    assert isinstance(gw, RfcSapGateway)


# --- MockSapGateway -------------------------------------------------------------


async def test_mock_posts_downtime_cost():
    gw = MockSapGateway()
    assert gw.available()
    result = await gw.post_downtime_cost(_cost())
    assert result.ok
    assert result.reference.startswith("mock-cost-")
    assert len(gw.posted_costs) == 1


async def test_mock_posts_weighted_metrics():
    gw = MockSapGateway()
    result = await gw.post_weighted_metrics(_metrics())
    assert result.ok
    assert len(gw.posted_metrics) == 1


async def test_mock_commit_and_rollback():
    gw = MockSapGateway()
    await gw.commit()
    await gw.rollback()
    assert gw.committed
    assert gw.rolled_back


async def test_mock_failure_injection():
    gw = MockSapGateway()
    gw._fail_next = True
    result = await gw.post_downtime_cost(_cost())
    assert not result.ok
    assert result.outcome == SapOutcome.FAILURE
    # not recorded on failure
    assert gw.posted_costs == []


# --- RfcSapGateway (no pyrfc -> unavailable, never raises) ----------------------


def test_rfc_available_false_without_sdk():
    gw = RfcSapGateway(SapConfig())
    # pyrfc is an optional dependency; in CI it is not installed.
    assert gw.available() is False


async def test_rfc_post_returns_unavailable_without_sdk():
    gw = RfcSapGateway(SapConfig(posting_user="sapbot"))
    result = await gw.post_downtime_cost(_cost())
    assert not result.ok
    assert result.outcome == SapOutcome.UNAVAILABLE


async def test_rfc_post_fails_closed_without_posting_user():
    # Without a configured posting_user, posting must fail closed (MED-3).
    gw = RfcSapGateway(SapConfig())
    result = await gw.post_downtime_cost(_cost())
    assert not result.ok
    assert result.outcome == SapOutcome.FAILURE
    assert "posting_user" in result.message

    result2 = await gw.post_weighted_metrics(_metrics())
    assert not result2.ok
    assert "posting_user" in result2.message


async def test_rfc_commit_returns_unavailable_without_sdk():
    gw = RfcSapGateway(SapConfig(posting_user="sapbot"))
    result = await gw.commit()
    assert result.outcome == SapOutcome.UNAVAILABLE


# --- pure mapping helpers (no SDK needed) ---------------------------------------


def test_map_bapi_result_errors():
    result = {"RETURN": [{"TYPE": "E", "MESSAGE": "not posted"}]}
    mapped = RfcSapGateway._map_bapi_result(result, "document_post")
    assert not mapped.ok
    assert mapped.errors[0]["code"] == "E"


def test_map_bapi_result_success_with_reference():
    result = {"RETURN": [{"TYPE": "S", "MESSAGE_V1": "DOC123"}]}
    mapped = RfcSapGateway._map_bapi_result(result, "commit")
    assert mapped.ok
    assert mapped.reference == "DOC123"


def test_build_activity_alloc_shape():
    payload = RfcSapGateway._build_activity_alloc(_cost(hours=2.0, rate=100.0))
    assert payload["COST"] == "200.0"
    assert payload["CURRENCY"] == "USD"
    assert payload["REFERENCE"] == f"cos-{ASSET}"


def test_build_document_post_uses_configured_posting_user():
    gw = RfcSapGateway(SapConfig(posting_user="sapbot"))
    payload = gw._build_document_post(_metrics())
    assert payload["DOCUMENT_HEADER"]["USERNAME"] == "sapbot"
