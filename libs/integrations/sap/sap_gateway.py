"""SAP R/3 integration — gateway abstraction & adapters (Fase 2).

External, NON-canonical capability (D-2026-08-07 / ADR-0002). This module
defines the SAP gateway contract and two implementations:

* ``RfcSapGateway``: real RFC/BAPI transport via PyRFC (SAP NW RFC SDK).
  Optional dependency: if ``pyrfc`` is not installed, ``available()`` returns
  False and the gateway is never instantiated in production without the SDK.
* ``MockSapGateway``: in-memory implementation for development/tests. It MUST
  never be enabled in production (fail-closed; the factory refuses to build a
  mock when ``environment == "production"``).

Transact semantics follow D-2026-08-07:

* ``post_downtime_cost`` -> ``BAPI_ACC_ACTIVITY_ALLOC_POST`` (activity alloc).
* ``post_weighted_metrics`` -> ``BAPI_ACC_DOCUMENT_POST``.
* ``commit()`` -> ``BAPI_TRANSACTION_COMMIT``.
* ``rollback()`` -> ``BAPI_TRANSACTION_ROLLBACK``.

Framework alignment: this is external, non-canonical input/output plumbing. It
never produces a cognitive judgment, never bypasses the canonical flow (R3), and
holds no notion of confidence (it is transport, not cognition).
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from contextlib import suppress
from dataclasses import dataclass, field
from enum import StrEnum

from libs.integrations.sap.finance import DowntimeCost, WeightedMetric
from libs.shared.structured_logging import get_logger

# Environment marker used to gate the mock (never allowed in production).
_ENV_PRODUCTION = "production"

logger = get_logger(__name__)


class MockInProductionError(ValueError):
    """Raised when the mock gateway is requested in a production environment."""

    def __init__(self) -> None:
        super().__init__("MockSapGateway cannot be used in production")


class SapOutcome(StrEnum):
    """Outcome of a single SAP posting/commit/rollback operation."""

    SUCCESS = "success"
    FAILURE = "failure"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class SapResult:
    """Typed result of a SAP gateway operation.

    Attributes:
        ok: True when the operation succeeded (``SUCCESS``).
        outcome: one of ``SapOutcome``.
        reference: optional external posting reference (e.g. BAPI return id /
            document number) for traceability/idempotence.
        message: human-safe, non-sensitive message (never raw SDK internals).
        errors: structured list of {code, message} for SAP BAPI returns.
    """

    ok: bool
    outcome: SapOutcome = SapOutcome.FAILURE
    reference: str | None = None
    message: str = ""
    errors: list[dict[str, str]] = field(default_factory=list)

    @classmethod
    def success(cls, reference: str | None = None, message: str = "") -> SapResult:
        return cls(ok=True, outcome=SapOutcome.SUCCESS, reference=reference, message=message)

    @classmethod
    def failure(
        cls, message: str, errors: list[dict[str, str]] | None = None
    ) -> SapResult:
        return cls(
            ok=False, outcome=SapOutcome.FAILURE, message=message, errors=errors or []
        )

    @classmethod
    def unavailable(cls, message: str = "SAP gateway unavailable") -> SapResult:
        return cls(ok=False, outcome=SapOutcome.UNAVAILABLE, message=message)


@dataclass(frozen=True)
class SapConfig:
    """Connection + posting configuration for a RFC destination.

    Credentials are intentionally NOT stored here (they live in the secrets
    store / env, never in code). This config only carries routing + behavior
    knobs. ``rfc_destination`` is the SM59 destination name; when using a
    destination the connection details (ashost/sysnr/client/user/passwd) are
    resolved by the RFC SDK from the destination, so no password travels here.

    ``posting_user`` is the SAP user that owns the postings (resolved from
    secrets/config, never hardcoded). It is required for posting; if empty,
    posting fails closed.
    """

    rfc_destination: str = ""
    ashost: str = ""
    sysnr: str = "00"
    client: str = "000"
    language: str = "EN"
    use_destination: bool = True
    request_timeout_s: float = 30.0
    posting_user: str = ""

    def __repr__(self) -> str:
        # Never expose credentials; only class + routing fields (no secrets).
        return (
            f"<SapConfig destination={self.rfc_destination!r} client={self.client!r} "
            f"use_destination={self.use_destination}>"
        )

    def __str__(self) -> str:
        return self.__repr__()


class SapGateway(ABC):
    """Abstract SAP R/3 gateway.

    Contract mirrors D-2026-08-07: transport via RFC/BAPI, with explicit
    commit/rollback. Implementations must keep ``available()`` synchronous and
    non-blocking (returns False instead of raising when SAP is unreachable).
    """

    @abstractmethod
    def available(self) -> bool:
        """Probe connectivity (sync, never raises, never blocks the flow)."""

    @abstractmethod
    async def post_downtime_cost(self, cost: DowntimeCost) -> SapResult:
        """Post a downtime cost (activity allocation)."""

    @abstractmethod
    async def post_weighted_metrics(self, metrics: list[WeightedMetric]) -> SapResult:
        """Post weighted metrics (document posting)."""

    @abstractmethod
    async def commit(self) -> SapResult:
        """BAPI_TRANSACTION_COMMIT — persist the pending posting."""

    @abstractmethod
    async def rollback(self) -> SapResult:
        """BAPI_TRANSACTION_ROLLBACK — abort the pending posting."""

    @abstractmethod
    def close(self) -> None:
        """Release any held connection."""


def build_sap_gateway(
    *,
    config: SapConfig,
    environment: str,
    mock: bool = False,
) -> SapGateway:
    """Factory; never allows the mock in production.

    Args:
        config: SAP connection config.
        environment: deployment environment marker ("production" is special).
        mock: when True, return ``MockSapGateway`` (dev/test only).

    Raises:
        ValueError: if ``mock`` is requested while ``environment == "production"``.
    """
    env = environment.strip().lower()
    if mock:
        if env == _ENV_PRODUCTION:
            raise MockInProductionError()
        return MockSapGateway()
    return RfcSapGateway(config)


class MockSapGateway(SapGateway):
    """In-memory SAP gateway for development/tests.

    Records every operation so tests can assert on the calls and the
    commit/rollback flow. Never reaches a real SAP system.
    """

    def __init__(self) -> None:
        self.posted_costs: list[DowntimeCost] = []
        self.posted_metrics: list[WeightedMetric] = []
        self.committed = False
        self.rolled_back = False
        self._fail_next = False

    def available(self) -> bool:
        return True

    async def post_downtime_cost(self, cost: DowntimeCost) -> SapResult:
        if self._fail_next:
            self._fail_next = False
            return SapResult.failure("mock failure injected")
        self.posted_costs.append(cost)
        return SapResult.success(reference=f"mock-cost-{len(self.posted_costs)}")

    async def post_weighted_metrics(self, metrics: list[WeightedMetric]) -> SapResult:
        if self._fail_next:
            self._fail_next = False
            return SapResult.failure("mock failure injected")
        self.posted_metrics.extend(metrics)
        return SapResult.success(reference=f"mock-metrics-{len(self.posted_metrics)}")

    async def commit(self) -> SapResult:
        self.committed = True
        return SapResult.success(reference="mock-commit")

    async def rollback(self) -> SapResult:
        self.rolled_back = True
        return SapResult.success(reference="mock-rollback")

    def close(self) -> None:
        # No resources to release; present for interface consistency.
        self.committed = False
        self.rolled_back = False


class RfcSapGateway(SapGateway):
    """Real RFC/BAPI transport via PyRFC (SAP NW RFC SDK).

    The ``pyrfc`` package is an optional dependency. If it is not installed,
    ``available()`` returns False and calls produce ``UNAVAILABLE`` results so
    the canonical flow is never blocked (fallback-friendly, ADR-0002).

    Concurrency: all RFC calls are serialized under an ``asyncio.Lock``
    because ``pyrfc`` is not thread-safe (HIGH-1 remediation). Timeouts are
    applied via ``asyncio.wait_for`` (HIGH-2 remediation).
    """

    def __init__(self, config: SapConfig) -> None:
        self._config = config
        self._pyrfc = None
        try:  # optional dependency
            import pyrfc  # noqa: PLC0415 - optional dependency  # type: ignore[import-not-found]

            self._pyrfc = pyrfc
        except Exception:  # noqa: BLE001 - optional dep absence must not raise
            self._pyrfc = None
        self._connection = None
        self._lock = asyncio.Lock()

    def available(self) -> bool:
        if self._pyrfc is None:
            return False
        try:
            # Probe on a throwaway connection so we do not cache/leak it.
            conn = self._pyrfc.Connection(**self._build_connection_params())
        except Exception:  # noqa: BLE001 - availability never raises
            return False
        else:
            with suppress(Exception):  # noqa: BLE001
                conn.close()
            return True

    def _build_connection_params(self) -> dict:
        if self._config.use_destination and self._config.rfc_destination:
            return {"dest": self._config.rfc_destination}
        return {
            "ashost": self._config.ashost,
            "sysnr": self._config.sysnr,
            "client": self._config.client,
            "lang": self._config.language,
        }

    def _open_connection(self):
        if self._connection is not None:
            return self._connection
        if self._pyrfc is None:
            return None
        self._connection = self._pyrfc.Connection(**self._build_connection_params())
        return self._connection

    async def _run_rfc(self, fn, *args) -> SapResult:
        """Run an RFC call under the lock with a timeout."""
        if self._pyrfc is None:
            return SapResult.unavailable("pyrfc SDK not installed")
        async with self._lock:
            try:
                conn = self._open_connection()
                if conn is None:
                    return SapResult.unavailable("SAP connection not available")
                result = await asyncio.wait_for(
                    asyncio.to_thread(fn, conn, *args),
                    timeout=self._config.request_timeout_s,
                )
            except TimeoutError:
                # Connection may be wedged; drop it so the next call reconnects.
                self.close()
                return SapResult.failure("SAP request timed out")
            except Exception as exc:  # noqa: BLE001 - never leak SDK internals
                return SapResult.failure(
                    "SAP call failed",
                    [{"code": "RFC", "message": str(type(exc).__name__)}],
                )
            else:
                return result

    async def post_downtime_cost(self, cost: DowntimeCost) -> SapResult:
        if not self._require_posting_user():
            return SapResult.failure("posting_user not configured")

        async def _call(conn):
            return self._map_bapi_result(
                conn.call(
                    "BAPI_ACC_ACTIVITY_ALLOC_POST",
                    self._build_activity_alloc(cost),
                ),
                "activity_alloc",
            )

        return await self._run_rfc(_call)

    async def post_weighted_metrics(self, metrics: list[WeightedMetric]) -> SapResult:
        if not self._require_posting_user():
            return SapResult.failure("posting_user not configured")

        async def _call(conn):
            return self._map_bapi_result(
                conn.call(
                    "BAPI_ACC_DOCUMENT_POST",
                    self._build_document_post(metrics),
                ),
                "document_post",
            )

        return await self._run_rfc(_call)

    async def commit(self) -> SapResult:
        async def _call(conn):
            return self._map_bapi_result(
                conn.call("BAPI_TRANSACTION_COMMIT", {"WAIT": "X"}),
                "commit",
            )

        return await self._run_rfc(_call)

    async def rollback(self) -> SapResult:
        async def _call(conn):
            return self._map_bapi_result(
                conn.call("BAPI_TRANSACTION_ROLLBACK", {}),
                "rollback",
            )

        return await self._run_rfc(_call)

    def _require_posting_user(self) -> bool:
        return bool(self._config.posting_user and self._config.posting_user.strip())

    @staticmethod
    def _build_activity_alloc(cost: DowntimeCost) -> dict:
        return {
            "COST": str(cost.cost()),
            "CURRENCY": cost.currency,
            "REFERENCE": f"cos-{cost.asset_id}",
        }

    def _build_document_post(self, metrics: list[WeightedMetric]) -> dict:
        return {
            "DOCUMENT_HEADER": {"USERNAME": self._config.posting_user},
            "ITEMS": [
                {
                    "MATERIAL": m.metric_name[:18],
                    "QUANTITY": str(m.value),
                    "WEIGHT": str(m.weight),
                }
                for m in metrics
            ],
        }

    @staticmethod
    def _map_bapi_result(result: dict, op: str) -> SapResult:
        # SAP BAPI returns include an optional "RETURN" table of messages.
        returns = result.get("RETURN") or []
        errors = [
            {"code": str(r.get("TYPE", "")), "message": str(r.get("MESSAGE", ""))}
            for r in returns
            if r.get("TYPE") in ("E", "A")
        ]
        if errors:
            return SapResult.failure(f"SAP {op} returned errors", errors)
        reference = None
        for r in returns:
            if r.get("TYPE") == "S" and r.get("MESSAGE_V1"):
                reference = str(r["MESSAGE_V1"])
                break
        return SapResult.success(reference=reference, message=f"{op} ok")

    def close(self) -> None:
        if self._connection is not None:
            with suppress(Exception):  # noqa: BLE001
                self._connection.close()
            self._connection = None
