"""SAP R/3 integration — financial data models (Fase 1).

External, NON-canonical capability (D-2026-08-07 / ADR-0002). This module owns
the *financial* data needed to price downtime for the SAP integration:

* ``DowntimeCost``: the cost of an asset/service being down,
  ``cost = hours_down * rate_per_hour`` (from D-2026-08-07).
* ``WeightedMetric``: a weighted metric sent to SAP with per-asset/service
  weights.

These are DTOs + pure computation; they do NOT touch the cognitive pipeline
(no observation/reasoning/confidence/action artifact). The persistence
(``AssetFinanceStore``) is a non-canonical support table, read by the SAP
bridge (Fase 3) — never consumed as cognitive input.

This module is framework-aligned: it introduces no cognitive concept (E2),
never bypasses the canonical flow (R3) and never produces a judgment or action
(no confidence required — it is data, not cognition).
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Default currency when none is supplied by the asset config.
DEFAULT_CURRENCY = "USD"

# Canonical ISO 4217 currency codes accepted by the SAP integration. This is
# a curated subset of the most common codes; extend as needed. Kept small to
# avoid shipping the full ISO list, but strict enough to reject junk like
# "FOO" or "ABC".
ISO4217_CURRENCIES: frozenset[str] = frozenset(
    {
        "USD", "EUR", "GBP", "JPY", "ARS", "BRL", "MXN", "CLP",
        "COP", "PEN", "UYU", "CAD", "AUD", "CHF", "CNY", "INR",
        "RUB", "KRW", "SGD", "HKD", "NZD", "SEK", "NOK", "DKK",
        "TRY", "ZAR", "ILS", "AED", "SAR", "MYR", "THB", "IDR",
        "PHP", "VND", "HUF", "PLN", "CZK", "RON", "BGN", "HRK",
    }
)


class CurrencyNotSupportedError(ValueError):
    """Raised when a currency code is not a supported ISO 4217 code."""

    def __init__(self, currency: str) -> None:
        super().__init__(f"unsupported currency code: {currency!r}")
        self.currency = currency


def _validate_currency(v: str) -> str:
    v = v.upper()
    if v not in ISO4217_CURRENCIES:
        raise CurrencyNotSupportedError(v)
    return v


class DowntimeCost(BaseModel):
    """Financial cost of an asset being down (DTO for the SAP post).

    Mirrors D-2026-08-07: ``cost = hours_down * rate_per_hour``.

    Attributes:
        tenant_id: owning tenant.
        asset_id: the monitored asset (server/service) id.
        hours_down: hours the asset was unavailable (>= 0).
        rate_per_hour: hourly rate for the asset (>= 0).
        currency: ISO 4217 currency code (default USD).
        reason: optional short reason/label for the cost event.
    """

    tenant_id: uuid.UUID
    asset_id: uuid.UUID
    hours_down: float = Field(ge=0.0)
    rate_per_hour: float = Field(ge=0.0)
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)
    reason: str | None = None

    model_config = ConfigDict(frozen=True)

    @field_validator("currency")
    @classmethod
    def _validate_currency_field(cls, v: str) -> str:
        return _validate_currency(v)

    def cost(self) -> float:
        """Downtime cost (D-2026-08-07): hours_down * rate_per_hour."""
        return self.hours_down * self.rate_per_hour


class WeightedMetric(BaseModel):
    """A metric weighted per asset/service for the SAP post.

    Attributes:
        metric_name: canonical metric key (e.g. "availability").
        weight: weight for this asset/service (0..1).
        value: the metric value.
        unit: optional unit label for the value.
    """

    tenant_id: uuid.UUID
    metric_name: str
    weight: float = Field(ge=0.0, le=1.0)
    value: float
    unit: str | None = None

    model_config = ConfigDict(frozen=True)


class AssetFinanceRecord(BaseModel):
    """A persisted asset-finance row (support table, non-canonical).

    ``asset_finance`` is a *support* table for the SAP integration (counterpart
    of the DTO above), not a cognitive table. It is INSERT-only (append-only
    trail) keyed by a deterministic id so re-saving the same asset config is
    idempotent.
    """

    id: uuid.UUID
    tenant_id: uuid.UUID
    asset_id: uuid.UUID
    rate_per_hour: float = Field(ge=0.0)
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)
    business_value: float | None = Field(default=None, ge=0.0)
    updated_by: uuid.UUID | None = None
    updated_at: datetime = Field(default_factory=datetime.now)

    model_config = ConfigDict(frozen=True)


ASSET_FINANCE_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000a1")


def asset_finance_id(tenant_id: uuid.UUID, asset_id: uuid.UUID) -> uuid.UUID:
    """Deterministic id for an asset-finance row (content-addressed)."""
    return uuid.uuid5(
        ASSET_FINANCE_NAMESPACE, f"{tenant_id}:{asset_id}"
    )


def build_asset_finance(create: AssetFinanceCreate) -> AssetFinanceRecord:
    """Materialize an AssetFinanceRecord from a creation request."""
    return AssetFinanceRecord(
        id=asset_finance_id(create.tenant_id, create.asset_id),
        tenant_id=create.tenant_id,
        asset_id=create.asset_id,
        rate_per_hour=create.rate_per_hour,
        currency=create.currency,
        business_value=create.business_value,
        updated_by=create.updated_by,
    )


class AssetFinanceCreate(BaseModel):
    """Creation request for an asset-finance row (content only)."""

    tenant_id: uuid.UUID
    asset_id: uuid.UUID
    rate_per_hour: float = Field(ge=0.0)
    currency: str = Field(default=DEFAULT_CURRENCY, min_length=3, max_length=3)
    business_value: float | None = Field(default=None, ge=0.0)
    updated_by: uuid.UUID | None = None

    model_config = ConfigDict(frozen=True)

    @field_validator("currency")
    @classmethod
    def _validate_currency_field(cls, v: str) -> str:
        return _validate_currency(v)


INSERT_ASSET_FINANCE = text(
    """
    INSERT INTO asset_finance (
        id, tenant_id, asset_id, rate_per_hour, currency, business_value,
        updated_by, updated_at
    )
    VALUES (
        :id, :tenant_id, :asset_id,
        CAST(:rate_per_hour AS numeric),
        CAST(:currency AS varchar),
        CAST(:business_value AS numeric),
        CAST(:updated_by AS uuid),
        :updated_at
    )
    ON CONFLICT (id) DO NOTHING
    RETURNING id, tenant_id, asset_id, rate_per_hour, currency,
              business_value, updated_by, updated_at
    """
)

SELECT_ASSET_FINANCE = text(
    """
    SELECT id, tenant_id, asset_id, rate_per_hour, currency, business_value,
           updated_by, updated_at
    FROM asset_finance
    WHERE tenant_id = :tenant_id AND asset_id = :asset_id
    """
)

SELECT_TENANT_ASSET_FINANCE = text(
    """
    SELECT id, tenant_id, asset_id, rate_per_hour, currency, business_value,
           updated_by, updated_at
    FROM asset_finance
    WHERE tenant_id = :tenant_id
    ORDER BY asset_id
    """
)

CHECK_ASSET_FINANCE_EXISTS = text(
    "SELECT 1 FROM asset_finance WHERE id = :id"
)


class AssetFinanceStore:
    """Persistence for the asset-finance support table (non-canonical).

    INSERT-only (append-only trail) keyed by the deterministic
    content-addressed id; read-only for the SAP bridge. It never touches the
    canonical cognitive tables (P1). Follows the ``ReportStore`` pattern
    (read-only over cognition, INSERT-only over its own support table).
    """

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def save(
        self, record: AssetFinanceRecord
    ) -> dict[str, Any] | None:
        """Insert one finance row; None if idempotently already present."""
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_ASSET_FINANCE,
                {
                    "id": record.id,
                    "tenant_id": record.tenant_id,
                    "asset_id": record.asset_id,
                    "rate_per_hour": record.rate_per_hour,
                    "currency": record.currency,
                    "business_value": record.business_value,
                    "updated_by": record.updated_by,
                    "updated_at": record.updated_at,
                },
            )
            await session.commit()
            row = result.mappings().one_or_none()
            return dict(row) if row is not None else None

    async def get(
        self, *, tenant_id: uuid.UUID, asset_id: uuid.UUID
    ) -> AssetFinanceRecord | None:
        """Read a finance row for an asset (SAP bridge / display)."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_ASSET_FINANCE,
                {"tenant_id": tenant_id, "asset_id": asset_id},
            )
            row = result.mappings().one_or_none()
            return AssetFinanceRecord(**dict(row)) if row is not None else None

    async def list_for_tenant(
        self, *, tenant_id: uuid.UUID
    ) -> list[AssetFinanceRecord]:
        """List all finance rows for a tenant (tenant-scoped read)."""
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_TENANT_ASSET_FINANCE, {"tenant_id": tenant_id}
            )
            return [AssetFinanceRecord(**dict(r)) for r in result.mappings()]

    async def exists(self, *, id: uuid.UUID) -> bool:
        """Check whether a finance row exists (idempotence guard)."""
        async with self._session_factory() as session:
            result = await session.execute(CHECK_ASSET_FINANCE_EXISTS, {"id": id})
            return result.scalar() is not None

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()
