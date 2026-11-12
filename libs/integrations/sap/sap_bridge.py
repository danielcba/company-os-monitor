"""SAP R/3 integration — bridge from the canonical flow (Fase 3).

External, NON-canonical capability (D-2026-08-07 / ADR-0002). The ``SapBridge``
is the *outward* adapter that turns a committed ``Decision`` (Action layer) into
a SAP posting, via the ``SapGateway``.

Framework alignment (the critical part):

* **R3 (Cognitive Boundary):** the bridge is an external ``ActionExecutor``
  (Phase 11). It only *reads* committed Decisions from the canonical store and
  *writes* outward to SAP. It never injects data into the pipeline, never posts
  from Perception/Reasoning, and never bypasses the canonical flow.
* **R4 (No Action Without Confidence):** the bridge react to Decisions that are
  already ``committed`` (the pipeline already gated them through calibrated
  confidence). The bridge does not compute any confidence — it consumes the
  committed artifact.
* **P1:** the bridge never mutates cognitive tables; it persists its own
  append-only ``sap_posting_log`` (support table, ADR-0002).

Idempotence (audit MED-4): each posting is keyed by a deterministic
``posting_key`` (tenant + decision + asset + window), recorded in
``sap_posting_log`` with a UNIQUE constraint, so a retry never double-posts.

The bridge does NOT invent financial data: it needs an explicit ``SapPostContext``
(asset + hours down) and reads the hourly rate from ``AssetFinanceStore`` (Fase 1).
If the rate is missing, the post fails closed (no fabricated figures).
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from libs.action.executor import ActionExecutor
from libs.integrations.sap.finance import (
    AssetFinanceStore,
    DowntimeCost,
)
from libs.integrations.sap.sap_gateway import (
    SapGateway,
    SapOutcome,
    SapResult,
)
from libs.shared.structured_logging import LogContext, get_logger

_logger = get_logger(__name__)

SAP_POSTING_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000a2")


class SapPostContextError(ValueError):
    """Raised when a SAP post context is invalid."""

    def __init__(self) -> None:
        super().__init__("hours_down must be >= 0")


class InvalidGatewayKindError(ValueError):
    """Raised when an unsupported gateway kind is provided to the bridge."""

    def __init__(self) -> None:
        super().__init__("unsupported gateway_kind")


def sap_posting_key(
    tenant_id: uuid.UUID,
    decision_id: uuid.UUID,
    asset_id: uuid.UUID,
) -> str:
    """Deterministic key to de-duplicate SAP postings (idempotence).

    Anchors on the tenant + decision + asset. A retry of the SAME logical
    posting (same decision for the same asset) reuses the key, so the log's
    UNIQUE constraint prevents double-posting. The downtime window/hours are
    part of the payload, not the identity (assumes one posting per
    decision+asset).
    """
    return f"{tenant_id}:{decision_id}:{asset_id}"


def sap_posting_id(posting_key: str) -> uuid.UUID:
    """Content-addressed id for a posting log row."""
    return uuid.uuid5(SAP_POSTING_NAMESPACE, posting_key)


@dataclass(frozen=True)
class SapPostContext:
    """Explicit, domain-provided context to map a Decision to a SAP post.

    The bridge does NOT infer asset/hours (that would invent data). The caller
    (a service that knows the domain) supplies the asset and the downtime
    window. ``hours_down`` and ``rate`` are validated at construction.
    """

    asset_id: uuid.UUID
    hours_down: float = Field(ge=0.0)  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self.hours_down < 0:
            raise SapPostContextError()


class SapPostingLogRecord(BaseModel):
    """An append-only row in ``sap_posting_log``."""

    id: uuid.UUID
    tenant_id: uuid.UUID
    posting_key: str
    decision_id: uuid.UUID
    gateway_kind: str
    outcome: str
    reference: str | None = None
    message: str = ""
    posted_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


INSERT_POSTING_LOG = text(
    """
    INSERT INTO sap_posting_log (
        id, tenant_id, posting_key, decision_id, gateway_kind, outcome,
        reference, message, posted_at
    )
    VALUES (
        :id, :tenant_id, :posting_key, :decision_id, :gateway_kind, :outcome,
        CAST(:reference AS varchar), CAST(:message AS varchar), :posted_at
    )
    ON CONFLICT (tenant_id, posting_key) DO NOTHING
    RETURNING id, tenant_id, posting_key, decision_id, gateway_kind, outcome,
              reference, message, posted_at
    """
)

SELECT_POSTING_BY_KEY = text(
    """
    SELECT id, tenant_id, posting_key, decision_id, gateway_kind, outcome,
           reference, message, posted_at
    FROM sap_posting_log
    WHERE tenant_id = :tenant_id AND posting_key = :posting_key
    """
)


class SapPostingLogStore:
    """Append-only store for ``sap_posting_log`` (idempotent, tenant-scoped).

    Atomic idempotence (HIGH-1 remediation): ``claim`` is an INSERT with
    ``ON CONFLICT (tenant_id, posting_key) DO NOTHING``. It returns True only
    if THIS caller reserved the posting; False means the key already exists
    (dedup). ``claim`` is the gate used BEFORE posting to SAP, so two
    concurrent callers cannot both post. ``finalize`` then records the real
    outcome via UPDATE of the lifecycle result fields (allowed by the trigger).
    """

    def __init__(self, dsn: str):
        self._engine = create_async_engine(dsn)
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    async def claim(self, record: SapPostingLogRecord) -> bool:
        """Atomically reserve a posting key; True if claimed by this caller.

        The record is inserted with a provisional ``outcome="pending"``. If
        the key already exists, nothing is inserted (False) and the caller
        must NOT post. Outcome fields are set by ``finalize`` afterwards.
        """
        async with self._session_factory() as session:
            result = await session.execute(
                INSERT_POSTING_LOG,
                {
                    "id": record.id,
                    "tenant_id": record.tenant_id,
                    "posting_key": record.posting_key,
                    "decision_id": record.decision_id,
                    "gateway_kind": record.gateway_kind,
                    "outcome": "pending",
                    "reference": None,
                    "message": "posting started",
                    "posted_at": record.posted_at,
                },
            )
            await session.commit()
            return result.mappings().one_or_none() is not None

    async def finalize(
        self,
        *,
        tenant_id: uuid.UUID,
        posting_key: str,
        outcome: str,
        reference: str | None,
        message: str,
    ) -> None:
        """Record the real result of a claimed posting (UPDATE of lifecycle
        result fields, allowed by the trigger)."""
        async with self._session_factory() as session:
            await session.execute(
                text(
                    "UPDATE sap_posting_log SET outcome = :outcome, "
                    "reference = :reference, message = :message "
                    "WHERE tenant_id = :tenant_id AND posting_key = :posting_key"
                ),
                {
                    "outcome": outcome,
                    "reference": reference,
                    "message": message,
                    "tenant_id": tenant_id,
                    "posting_key": posting_key,
                },
            )
            await session.commit()

    async def exists(self, *, tenant_id: uuid.UUID, posting_key: str) -> bool:
        async with self._session_factory() as session:
            result = await session.execute(
                SELECT_POSTING_BY_KEY,
                {"tenant_id": tenant_id, "posting_key": posting_key},
            )
            return result.mappings().one_or_none() is not None

    async def verify_connection(self) -> None:
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()


class SapBridge(ActionExecutor):
    """ActionExecutor that posts committed Decisions to SAP.

    Implements the ``ActionExecutor`` protocol (Phase 11): it receives an
    authorized execution request (decision + commitment) and performs the
    external action (SAP posting). It is invoked by the orchestrator only for
    committed Decisions (R4) and never feeds the pipeline back (R3).
    """

    _GATEWAY_KINDS = frozenset({"rfc", "mock"})

    def __init__(
        self,
        *,
        gateway: SapGateway,
        finance_store: AssetFinanceStore,
        posting_log_store: SapPostingLogStore,
        gateway_kind: str = "rfc",
    ) -> None:
        if gateway_kind not in self._GATEWAY_KINDS:
            raise InvalidGatewayKindError()
        self._gateway = gateway
        self._finance_store = finance_store
        self._posting_log_store = posting_log_store
        self._gateway_kind = gateway_kind

    async def execute(
        self,
        *,
        decision_id: str,
        tenant_id: str,
        commitment: str,
        authority_id: str,
        context: SapPostContext | None = None,
    ) -> dict[str, Any]:
        """Execute a SAP posting for a committed Decision.

        Args:
            decision_id: the committed Decision id (must already be committed).
            tenant_id: tenant scope.
            commitment: the committed action text (from the Decision row).
            authority_id: the authority under which the decision was taken.
            context: explicit mapping data (asset + hours down). If None, the
                post is refused (the bridge does not invent data).

        Returns:
            A dict describing the outcome:
            {ok, outcome, reference, message, posting_key}.
        """
        tenant = uuid.UUID(str(tenant_id))
        decision = uuid.UUID(str(decision_id))

        if context is None:
            # No mapping data => fail closed; we never fabricate an asset/hours.
            _logger.warning(
                "sap_bridge_no_context",
                context=LogContext(tenant_id=str(tenant)),
                extra={"decision_id": decision_id},
            )
            return _result_dict(SapResult.failure("sap_post_context required"), None)

        # Resolve the hourly rate from the finance store (Fase 1).
        finance = await self._finance_store.get(
            tenant_id=tenant, asset_id=context.asset_id
        )
        if finance is None:
            return _result_dict(
                SapResult.failure("no finance rate configured for asset"), None
            )

        # Deterministic idempotence key for this posting. NOTE (MED-1): the
        # key ignores the payload (hours), so a retry of the SAME decision+asset
        # is de-duplicated. If a caller retries with DIFFERENT hours, we warn
        # (the corrected value is NOT re-posted; documented limitation).
        key = sap_posting_key(tenant, decision, context.asset_id)
        cost = DowntimeCost(
            tenant_id=tenant,
            asset_id=context.asset_id,
            hours_down=context.hours_down,
            rate_per_hour=finance.rate_per_hour,
            currency=finance.currency,
            reason=f"decision:{decision}",
        )

        # Atomic idempotence gate (HIGH-1): claim the key BEFORE posting.
        # If another caller already claimed it, we must NOT post.
        claimed = await self._posting_log_store.claim(
            SapPostingLogRecord(
                id=sap_posting_id(key),
                tenant_id=tenant,
                posting_key=key,
                decision_id=decision,
                gateway_kind=self._gateway_kind,
                outcome="pending",
            )
        )
        if not claimed:
            _logger.warning(
                "sap_posting_dedup",
                context=LogContext(tenant_id=str(tenant)),
                extra={"decision_id": decision_id, "posting_key": key},
            )
            return {
                "ok": True,
                "outcome": SapOutcome.SUCCESS.value,
                "reference": None,
                "message": "already posted (idempotent)",
                "posting_key": key,
                "deduplicated": True,
            }

        try:
            result = await self._gateway.post_downtime_cost(cost)
            if result.ok:
                # Only commit the BAPI transaction if the posting succeeded.
                commit_result = await self._gateway.commit()
                final = commit_result if commit_result.ok else result
            else:
                await self._gateway.rollback()
                final = result
        except Exception:  # noqa: BLE001 - never leave a stuck pending record
            final = SapResult.failure("sap bridge execution error")
        outcome = final.outcome.value
        reference = final.reference
        message = final.message

        # Persist the real result (lifecycle fields, allowed by the trigger).
        await self._posting_log_store.finalize(
            tenant_id=tenant,
            posting_key=key,
            outcome=outcome,
            reference=reference,
            message=message,
        )

        _logger.info(
            "sap_posting",
            context=LogContext(tenant_id=str(tenant)),
            extra={
                "decision_id": decision_id,
                "posting_key": key,
                "outcome": outcome,
                "reference": reference,
            },
        )
        return _result_dict(final, key)

    async def close(self) -> None:
        await self._finance_store.close()
        await self._posting_log_store.close()
        self._gateway.close()


def _result_dict(result: SapResult, posting_key: str | None) -> dict[str, Any]:
    return {
        "ok": result.ok,
        "outcome": result.outcome.value,
        "reference": result.reference,
        "message": result.message,
        "posting_key": posting_key,
    }
