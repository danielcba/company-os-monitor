"""SAP R/3 integration — orchestrator (Fase 4).

External, NON-canonical capability (D-2026-08-07 / ADR-0002). The
``SapOrchestrator`` is the coordination layer that wires committed Decisions to
the ``SapBridge`` (Fase 3), driven by an authorized API endpoint (see the
gateway module). It is the "when/how to post" logic.

Framework alignment:

* **R3 (Cognitive Boundary):** reads committed Decisions via ``DecisionStore``
  (read-only, P1) and writes outward via ``SapBridge``. It never injects data
  into the pipeline and never posts from Perception/Reasoning.
* **R4 (No Action Without Confidence):** only processes Decisions whose
  ``status == committed`` (already gated by calibrated confidence). It does not
  compute confidence.
* **R5 / authority:** the orchestrator is invoked only from an authorized
  endpoint; it requires an ``authority_id`` that is passed through to the
  bridge for audit.
* **Fail-closed:** without an explicit ``SapPostContext`` (asset + hours) the
  request is refused — the orchestrator never fabricates data.

Idempotence is provided by ``SapBridge`` (Fase 3) via ``sap_posting_log``:
re-submitting the same decision+asset does not double-post.
"""
from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from libs.action.decision import DecisionStore
from libs.integrations.sap.sap_bridge import (
    SapBridge,
    SapPostContext,
    SapPostingLogStore,
)

# Sane upper bound for downtime hours (avoids absurd values).
_MAX_HOURS_DOWN = 10000.0

# Upper bound for the number of requests per batch (abuse/DoS protection).
_MAX_BATCH_SIZE = 100


class SapPostRequestError(ValueError):
    """Raised when a SAP posting request is invalid."""

    def __init__(self) -> None:
        super().__init__("hours_down exceeds sane bounds")


class SapPostRequest(BaseModel):
    """One explicit request to post a decision to SAP.

    The client/service-of-record supplies the mapping data explicitly (asset +
    hours down). The orchestrator refuses to infer these (fail-closed).
    """

    decision_id: uuid.UUID
    asset_id: uuid.UUID
    hours_down: float = Field(ge=0.0)

    model_config = ConfigDict(frozen=True)

    @field_validator("hours_down")
    @classmethod
    def _finite_hours(cls, v: float) -> float:
        if v > _MAX_HOURS_DOWN:
            raise SapPostRequestError()
        return v


class SapPostRequestBatch(BaseModel):
    """Batch of SAP posting requests for one tenant (bounded)."""

    requests: list[SapPostRequest]

    model_config = ConfigDict(frozen=True)

    @field_validator("requests")
    @classmethod
    def _bound_size(cls, v: list[SapPostRequest]) -> list[SapPostRequest]:
        if len(v) > _MAX_BATCH_SIZE:
            raise SapPostRequestError()
        return v


class SapOrchestrator:
    """Coordinates posting committed Decisions to SAP via the bridge."""

    def __init__(
        self,
        *,
        decision_store: DecisionStore,
        bridge: SapBridge,
        posting_log_store: SapPostingLogStore,
    ) -> None:
        self._decision_store = decision_store
        self._bridge = bridge
        self._posting_log_store = posting_log_store

    async def process(
        self,
        *,
        tenant_id: uuid.UUID,
        requests: list[SapPostRequest],
        authority_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Process a batch of posting requests for a tenant.

        For each request:
          1. Reads the Decision (read-only) and verifies ``status == committed``
             (R4). Not found or not committed -> per-request error, no post.
          2. Builds ``SapPostContext`` and invokes ``SapBridge.execute()``.
          3. Collects the result.

        Returns ``{"results": [...]}`` with one entry per request.
        """
        # Read committed Decisions for the tenant in one query (read-only, R4).
        committed = await self._decision_store.list_decisions_by_status(
            tenant_id=tenant_id, status="committed"
        )
        by_id = {str(d.id): d for d in committed}

        results: list[dict[str, Any]] = []
        for req in requests:
            decision = by_id.get(str(req.decision_id))
            if decision is None:
                results.append(
                    {
                        "decision_id": str(req.decision_id),
                        "ok": False,
                        "outcome": "not_committed",
                        "message": "decision not found or not committed (R4)",
                    }
                )
                continue

            context = SapPostContext(
                asset_id=req.asset_id, hours_down=req.hours_down
            )
            commitment = getattr(decision, "commitment", "") or ""
            result = await self._bridge.execute(
                decision_id=str(req.decision_id),
                tenant_id=str(tenant_id),
                commitment=commitment,
                authority_id=str(authority_id),
                context=context,
            )
            outcome = result.get("outcome", "failure")
            results.append(
                {
                    "decision_id": str(req.decision_id),
                    "ok": bool(result.get("ok", False)),
                    "outcome": outcome,
                    "reference": result.get("reference"),
                    "message": result.get("message"),
                    "posting_key": result.get("posting_key"),
                    "deduplicated": result.get("deduplicated", False),
                }
            )
        return {"results": results}

    async def list_postings(
        self, *, tenant_id: uuid.UUID
    ) -> list[dict[str, Any]]:
        """Read the posting log for a tenant (audit, read-only)."""
        # The posting log store exposes existence/record; for listing we read
        # the supported query. To keep this read-only and simple, we return the
        # rows via a dedicated SELECT exposed below.
        return await self._posting_log_store.list_for_tenant(tenant_id=tenant_id)

    async def close(self) -> None:
        await self._bridge.close()
        await self._posting_log_store.close()
