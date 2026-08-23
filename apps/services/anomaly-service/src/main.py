"""Anomaly Service Entry Point - Anomaly Detector (Context + Pattern -> Anomaly).

The Reasoning Layer's Detect Deviation capability: reads the tenant Active
Contexts and their expected Patterns from Postgres (knowledge, never raw
observations), measures the magnitude of each deviation against the explicit
Tolerance Library, and writes Candidate Anomalies into ``anomalies``
(append-only, idempotent dedup).

Tolerance thresholds are declarative (procedural memory); operators may tune
them per deployment via ``TOLERANCE_*_THRESHOLD`` env vars (documented in
.env.example). The canonical defaults live in
``libs/procedural_memory/tolerance_library.py``.
"""
import asyncio
import logging
import os
from dataclasses import replace

from libs.perception.context import ContextStore
from libs.procedural_memory.tolerance_library import (
    TOLERANCE_LIBRARY,
    ToleranceDefinition,
)
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.pattern import PatternStore
from libs.shared.graceful_shutdown import GracefulShutdown

from src.health import HealthServer
from src.service import AnomalyService

logger = logging.getLogger(__name__)

# env var name -> tolerance_id it overrides (threshold, auditable per deployment).
TOLERANCE_ENV_OVERRIDES: dict[str, str] = {
    "TOLERANCE_SCHEDULE_DEVIATION_CAPACITY_RISK_THRESHOLD": "schedule_deviation_capacity_risk_v1",
    "TOLERANCE_CLUSTERING_DEVIATION_SERVICE_FAILURE_THRESHOLD": "clustering_deviation_service_failure_v1",
    "TOLERANCE_SCHEDULE_DEVIATION_RESOURCE_PRESSURE_THRESHOLD": "schedule_deviation_resource_pressure_v1",
    "TOLERANCE_CLUSTERING_DEVIATION_AUTH_COMPROMISE_THRESHOLD": "clustering_deviation_auth_compromise_v1",
    "TOLERANCE_SCHEDULE_DEVIATION_CONNECTIVITY_DEGRADATION_THRESHOLD": "schedule_deviation_connectivity_degradation_v1",
}


def tolerances_from_env(
    library: tuple[ToleranceDefinition, ...] = TOLERANCE_LIBRARY,
) -> tuple[ToleranceDefinition, ...]:
    """Apply optional env threshold overrides on top of the canonical library."""
    overrides = {
        tolerance_id: float(os.getenv(env_name))
        for env_name, tolerance_id in TOLERANCE_ENV_OVERRIDES.items()
        if os.getenv(env_name) is not None
    }
    if not overrides:
        return library
    return tuple(
        replace(t, threshold=overrides[t.tolerance_id])
        if t.tolerance_id in overrides
        else t
        for t in library
    )


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("ANOMALY_HEALTH_PORT", "8093"))
    cycle_seconds = float(os.getenv("ANOMALY_CYCLE_SECONDS", "60"))

    context_store = ContextStore(dsn)
    pattern_store = PatternStore(dsn)
    anomaly_store = AnomalyStore(dsn)
    await context_store.verify_connection()
    await pattern_store.verify_connection()
    await anomaly_store.verify_connection()

    service = AnomalyService(
        context_store,
        pattern_store,
        anomaly_store,
        tolerances=tolerances_from_env(),
    )
    health = HealthServer(service)

    await health.start(port)

    shutdown = GracefulShutdown()
    shutdown.install()

    while not shutdown.should_exit.is_set():
        try:
            await service.run_detection_cycle()
        except Exception:
            logger.exception("Error in anomaly detection cycle")
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())