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
import os

from libs.cognitive_core.calibration_model import CalibrationParams
from libs.learning.confidence import ConfidenceStore
from libs.perception.context import ContextStore
from libs.perception.evidence import EvidenceStore
from libs.reasoning.anomaly import AnomalyStore
from libs.reasoning.hypothesis import HypothesisStore

from src.health import HealthServer
from src.service import ConfidenceService


def load_params() -> CalibrationParams:
    """Fixed-a-priori calibration parameters from env (published per report).

    alpha and M are configurable per deployment but always documented in the
    calibration_justification; L0 stays 0 (uniform prior, no documented base
    rate available). They are NEVER tuned to justify a particular confidence.
    """
    alpha = float(os.getenv("CALIBRATION_ALPHA", "0.5"))
    bins = int(os.getenv("CALIBRATION_ECE_BINS", "10"))
    return CalibrationParams(alpha=alpha, M=bins, L0=0.0)


async def main():
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
    health = HealthServer(service)

    await health.start(port)

    while True:
        await service.run_calibration_cycle()
        await asyncio.sleep(cycle_seconds)


if __name__ == "__main__":
    asyncio.run(main())