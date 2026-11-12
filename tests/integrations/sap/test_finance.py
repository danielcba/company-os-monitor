"""SAP integration — Fase 1 unit tests (DTOs + pure computation).

Covers the financial data contract (D-2026-08-07): ``DowntimeCost.cost()``,
``WeightedMetric`` validation, ISO 4217 currency validation and the
 deterministic asset-finance id. No DB required.
"""
from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError

from libs.integrations.sap import (
    DowntimeCost,
    WeightedMetric,
    asset_finance_id,
)

TENANT = uuid.uuid4()
ASSET = uuid.uuid4()


def test_downtime_cost_formula():
    """D-2026-08-07: cost = hours_down * rate_per_hour."""
    c = DowntimeCost(
        tenant_id=TENANT,
        asset_id=ASSET,
        hours_down=2.5,
        rate_per_hour=100.0,
    )
    assert c.cost() == pytest.approx(250.0)


def test_downtime_cost_zero_hours():
    """Zero downtime is zero cost."""
    c = DowntimeCost(
        tenant_id=TENANT,
        asset_id=ASSET,
        hours_down=0.0,
        rate_per_hour=100.0,
    )
    assert c.cost() == 0.0


def test_downtime_cost_zero_rate():
    """Zero rate is zero cost regardless of downtime."""
    c = DowntimeCost(
        tenant_id=TENANT,
        asset_id=ASSET,
        hours_down=10.0,
        rate_per_hour=0.0,
    )
    assert c.cost() == 0.0


def test_downtime_cost_rejects_negative_hours():
    with pytest.raises(ValidationError):
        DowntimeCost(
            tenant_id=TENANT,
            asset_id=ASSET,
            hours_down=-1.0,
            rate_per_hour=10.0,
        )


def test_downtime_cost_rejects_negative_rate():
    with pytest.raises(ValidationError):
        DowntimeCost(
            tenant_id=TENANT,
            asset_id=ASSET,
            hours_down=1.0,
            rate_per_hour=-5.0,
        )


def test_currency_is_upper_cased():
    c = DowntimeCost(
        tenant_id=TENANT,
        asset_id=ASSET,
        hours_down=1.0,
        rate_per_hour=1.0,
        currency="ars",
    )
    assert c.currency == "ARS"


def test_downtime_cost_default_currency():
    c = DowntimeCost(
        tenant_id=TENANT,
        asset_id=ASSET,
        hours_down=1.0,
        rate_per_hour=1.0,
    )
    assert c.currency == "USD"


def test_currency_rejects_non_iso4217():
    with pytest.raises(ValidationError):
        DowntimeCost(
            tenant_id=TENANT,
            asset_id=ASSET,
            hours_down=1.0,
            rate_per_hour=1.0,
            currency="FOO",
        )


def test_currency_accepts_supported_iso4217():
    c = DowntimeCost(
        tenant_id=TENANT,
        asset_id=ASSET,
        hours_down=1.0,
        rate_per_hour=1.0,
        currency="ars",
    )
    assert c.currency == "ARS"


def test_weighted_metric_valid():
    WEIGHT = 0.8
    VALUE = 99.5
    m = WeightedMetric(
        tenant_id=TENANT,
        metric_name="availability",
        weight=WEIGHT,
        value=VALUE,
    )
    assert m.weight == WEIGHT
    assert m.value == VALUE


def test_weighted_metric_rejects_weight_gt_1():
    with pytest.raises(ValidationError):
        WeightedMetric(
            tenant_id=TENANT,
            metric_name="availability",
            weight=1.1,
            value=99.5,
        )


def test_weighted_metric_rejects_negative_weight():
    with pytest.raises(ValidationError):
        WeightedMetric(
            tenant_id=TENANT,
            metric_name="availability",
            weight=-0.1,
            value=99.5,
        )


def test_asset_finance_id_deterministic():
    id1 = asset_finance_id(TENANT, ASSET)
    id2 = asset_finance_id(TENANT, ASSET)
    assert id1 == id2
    # different tenant/asset => different id
    assert id1 != asset_finance_id(uuid.uuid4(), ASSET)
    assert id1 != asset_finance_id(TENANT, uuid.uuid4())
