#!/usr/bin/env python3
"""QA data re-seed for the sandbox tenant (backup-pressure scenario).

Replays what the observation agents would have captured during a capacity/backup
incident: four batches of backup-failure observations, each from a DISTINCT
source, so the collector organizes four immutable Evidence rows and the context
activator produces one superseding activation per batch (four activations per
scope). Everything downstream is computed by the pipeline itself - pattern,
anomaly, hypotheses, confidence, recommendations, decisions, reports. The seed
ONLY publishes immutable Observations (P1): it never writes a conclusion, a
judgment or a confidence score.

Usage:
    python3 scripts/qa_seed.py [--watch] [--max-minutes 15]
"""
import argparse
import asyncio
import os
import sys
import uuid
from datetime import UTC, datetime

import asyncpg
from redis.asyncio import Redis

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from libs.cognitive_core.observation_bus import Observation, ObservationBus  # noqa: E402

TENANT_ID = uuid.UUID(
    os.getenv("QA_TENANT_ID", "00000000-0000-0000-0000-000000000001")
)
REDIS_URL = os.getenv("OBSERVATION_BUS_URL", "redis://localhost:6379")
DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
)

# Four distinct backup sources (a new source per batch -> a new deterministic
# Evidence row -> a new superseding Context activation per scope).
BATCH_SOURCES = [
    uuid.UUID("00000000-0000-0000-0000-00000000000d"),
    uuid.UUID("00000000-0000-0000-0000-00000000000e"),
    uuid.UUID("00000000-0000-0000-0000-00000000000f"),
    uuid.UUID("00000000-0000-0000-0000-000000000010"),
]

TABLES = (
    "observations",
    "evidence",
    "contexts",
    "patterns",
    "anomalies",
    "hypotheses",
    "confidence_scores",
    "recommendations",
    "decisions",
    "reports",
)

POLL_SECONDS = 5.0


def _batch(source_id: uuid.UUID, captured_at: datetime) -> list[Observation]:
    """One backup-failure batch: job failed + repo below 10% (same source)."""
    return [
        Observation(
            tenant_id=TENANT_ID,
            source_id=source_id,
            source_type="backup_agent",
            fact_type="backup_job_status",
            fact_value={"job": "weekly-full", "status": "Failed"},
            unit="",
            captured_at=captured_at,
            quality_class="Q1",
            raw_payload={"repository": f"repo-{source_id.hex[-2:]}"},
        ),
        Observation(
            tenant_id=TENANT_ID,
            source_id=source_id,
            source_type="backup_agent",
            fact_type="repo_free_bytes",
            fact_value={"value": 5},
            unit="bytes",
            captured_at=captured_at,
            quality_class="Q1",
            raw_payload={"repository": f"repo-{source_id.hex[-2:]}"},
        ),
        Observation(
            tenant_id=TENANT_ID,
            source_id=source_id,
            source_type="backup_agent",
            fact_type="repo_capacity_bytes",
            fact_value={"value": 100},
            unit="bytes",
            captured_at=captured_at,
            quality_class="Q1",
            raw_payload={"repository": f"repo-{source_id.hex[-2:]}"},
        ),
    ]


async def _counts(pool: asyncpg.Pool) -> dict[str, int]:
    rows = await pool.fetch(
        """
        SELECT
          (SELECT COUNT(*) FROM observations WHERE tenant_id=$1) AS observations,
          (SELECT COUNT(*) FROM evidence WHERE tenant_id=$1) AS evidence,
          (SELECT COUNT(*) FROM contexts WHERE tenant_id=$1) AS contexts,
          (SELECT COUNT(*) FROM patterns WHERE tenant_id=$1) AS patterns,
          (SELECT COUNT(*) FROM anomalies WHERE tenant_id=$1) AS anomalies,
          (SELECT COUNT(*) FROM hypotheses WHERE tenant_id=$1) AS hypotheses,
          (SELECT COUNT(*) FROM confidence_scores WHERE tenant_id=$1) AS confidence_scores,
          (SELECT COUNT(*) FROM recommendations WHERE tenant_id=$1) AS recommendations,
          (SELECT COUNT(*) FROM decisions WHERE tenant_id=$1) AS decisions,
          (SELECT COUNT(*) FROM reports WHERE tenant_id=$1) AS reports
        """,
        TENANT_ID,
    )
    return dict(rows[0])


async def _wait_for(
    pool: asyncpg.Pool,
    predicate,
    *,
    label: str,
    timeout_seconds: float,
    initial: dict[str, int] | None = None,
) -> dict[str, int]:
    """Poll the canonical tables until ``predicate(counts)`` holds."""
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    counts = initial or await _counts(pool)
    while asyncio.get_running_loop().time() < deadline:
        counts = await _counts(pool)
        if predicate(counts):
            return counts
        await asyncio.sleep(POLL_SECONDS)
    raise TimeoutError(
        f"timed out waiting for: {label} "
        f"(last counts: {json_dumps(counts)})"
    )


def json_dumps(obj: dict) -> str:
    import json

    return json.dumps(obj)


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-minutes", type=float, default=15.0, help="overall time budget"
    )
    args = parser.parse_args()

    budget = args.max_minutes * 60.0
    started = asyncio.get_running_loop().time()

    redis = Redis.from_url(REDIS_URL, decode_responses=True)
    bus = ObservationBus(redis)
    pool = await asyncpg.create_pool(DSN)

    def remaining() -> float:
        return max(1.0, budget - (asyncio.get_running_loop().time() - started))

    try:
        print(f"[seed] tenant={TENANT_ID}")
        base = await _counts(pool)
        print(f"[seed] baseline: {json_dumps(base)}")

        # Phase A-C: three batches -> three Evidence rows -> three activations
        # per scope -> a pattern per scope (>=3 occurrences in the window).
        for index, source in enumerate(BATCH_SOURCES[:3], start=1):
            now = datetime.now(UTC)
            for obs in _batch(source, now):
                await bus.publish(obs)
            print(f"[seed] batch {index} published (source {source.hex[-4:]})")
            await _wait_for(
                pool,
                lambda c, target=base["contexts"] + 3 * index: (
                    c["contexts"] >= target
                ),
                label=f"{index} context activation(s) for the batch",
                timeout_seconds=remaining(),
            )

        counts = await _wait_for(
            pool,
            lambda c: c["patterns"] >= 3,
            label="a pattern per scope (capacity_risk x2 + auth_compromise)",
            timeout_seconds=remaining(),
        )
        print(f"[seed] patterns formed: {json_dumps(counts)}")

        # Phase D: a fourth batch -> superseding activation off the pattern
        # cadence -> anomaly (relative to the expected pattern, never absolute).
        source = BATCH_SOURCES[3]
        for obs in _batch(source, datetime.now(UTC)):
            await bus.publish(obs)
        print(f"[seed] batch 4 published (source {source.hex[-4:]})")
        counts = await _wait_for(
            pool,
            lambda c: c["anomalies"] >= 3,
            label="anomaly per scope (deviation vs expected pattern)",
            timeout_seconds=remaining(),
        )
        print(f"[seed] anomalies detected: {json_dumps(counts)}")

        # Phase E: downstream cascade - hypotheses -> confidence ->
        # recommendations -> decisions -> reports (each service cycle).
        counts = await _wait_for(
            pool,
            lambda c: c["decisions"] >= 1
            and c["reports"] >= base["reports"] + 1,
            label="decisions committed and a new report rendered",
            timeout_seconds=remaining(),
        )
        print(f"[seed] cascade complete: {json_dumps(counts)}")

        print(f"[seed] done in {asyncio.get_running_loop().time() - started:.0f}s")
        print("[seed] final counts:")
        for table in TABLES:
            print(f"  {table:20s} {counts[table]:>6}")
        return 0
    finally:
        await pool.close()
        await redis.aclose()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))