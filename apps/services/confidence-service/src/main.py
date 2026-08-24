"""Confidence Service Entry Point - Confidence Calibrator (Learning/Calibrate).

The Learning Layer's Calibrate capability: reads each tenant's Hypotheses
(judgments), their Anomalies/Contexts/Evidence (the P1 immutable knowledge
stream) from Postgres, computes the calibrated Confidence (S + C + ECE +
C_final) for every candidate Hypothesis and writes the rows into
``confidence_scores`` (append-only, idempotent dedup). It never writes to
previous artifacts (P1), never reads the observation bus and produces no
actions (R3): the output enables the Action Layer (R4).
"""
import asyncio
import logging
import os
import signal
from typing import Any

from libs.cognitive_core.calibration_model import CalibrationParams
from libs.learning.confidence import ConfidenceStore
from libs.perception.context import ContextStore
from libs.perception.evidence import EvidenceStore
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore

from src.health import HealthServer
from src.service import ConfidenceService

log = logging.getLogger(__name__)


def load_params() -> CalibrationParams:
    """Fixed-a-priori calibration parameters from env (published per report).

    alpha and M are configurable per deployment but always documented in the
    calibration_justification; L0 stays 0 (uniform prior, no documented base
    rate available). They are NEVER tuned to justify a particular confidence.
    """
    alpha = float(os.getenv("CALIBRATION_ALPHA", "0.5"))
    bins = int(os.getenv("CALIBRATION_ECE_BINS", "10"))
    return CalibrationParams(alpha=alpha, M=bins, L0=0.0)


class GracefulShutdown:
    """Handles SIGTERM/SIGINT for graceful shutdown of the service."""

    def __init__(self) -> None:
        self._shutdown = asyncio.Event()
        self._stores: list[Any] = []

    def register_store(self, store: Any) -> None:
        """Register a store to be closed on shutdown."""
        self._stores.append(store)

    def signal_handler(self, signum: int, frame: Any) -> None:
        """Signal handler that triggers shutdown."""
        log.info("Received signal %s, initiating graceful shutdown...", signum)
        self._shutdown.set()

    async def wait_for_shutdown(self) -> None:
        """Wait for shutdown signal."""
        await self._shutdown.wait()

    async def close_stores(self) -> None:
        """Close all registered stores."""
        for store in self._stores:
            try:
                await store.close()
                log.info("Closed store: %s", store.__class__.__name__)
            except Exception:
                log.exception("Error closing store %s", store.__class__.__name__)


async def main():
    import logging

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("CONFIDENCE_HEALTH_PORT", "8095"))
    cycle_seconds = float(os.getenv("CONFIDENCE_CYCLE_SECONDS", "60"))

    hypothesis_store = HypothesisStore(dsn)
    anomaly_store = AnomalyStore(dsn)
    context_store = ContextStore(dsn)
    evidence_store = EvidenceStore(dsn)
    confidence_store = ConfidenceStore(dsn)

    shutdown = GracefulShutdown()
    for store in (
        hypothesis_store,
        anomaly_store,
        context_store,
        evidence_store,
        confidence_store,
    ):
        shutdown.register_store(store)

    # Register signal handlers
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, shutdown.signal_handler, sig, None)

    await hypothesis_store.verify_connection()
    await anomaly_store.verify_connection()
    await context_store.verify_connection()
    await evidence_store.verify_connection()
    await confidence_store.verify_connection()

    service = ConfidenceService(
        hypothesis_store,
        anomaly_store,
        context_store,
        evidence_store,
        confidence_store,
        params=load_params(),
    )
    health = HealthServer(service, confidence_store)

    await health.start(port)
    log.info("Confidence service started on port %s", port)

    try:
        while not shutdown._shutdown.is_set():
            await asyncio.wait(
                [
                    asyncio.create_task(service.run_calibration_cycle()),
                    asyncio.create_task(shutdown.wait_for_shutdown()),
                ],
                return_when=asyncio.FIRST_COMPLETED,
            )
            if not shutdown._shutdown.is_set():
                await asyncio.sleep(cycle_seconds)
    finally:
        log.info("Shutting down...")
        await health.runner.cleanup() if health.runner else None
        await shutdown.close_stores()
        log.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass