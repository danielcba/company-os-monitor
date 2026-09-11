"""Deterministic Observation ID generator (ADR-0007 §4).

Each sample in a batch becomes one Observation. The Observation ID is
deterministic: same input → same ID, enabling idempotent Collector dedup
without distributed coordination.
"""
import uuid

OBSERVATION_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8")


def observation_id(
    tenant_id: uuid.UUID,
    installation_id: uuid.UUID,
    batch_id: uuid.UUID,
    sequence: int,
    fact_type: str,
) -> uuid.UUID:
    """UUIDv5 deterministic ID per ADR-0007 §4.

    ``name = f"{tenant_id}:{installation_id}:{batch_id}:{sequence}:{fact_type}"``
    """
    name = f"{tenant_id}:{installation_id}:{batch_id}:{sequence}:{fact_type}"
    return uuid.uuid5(OBSERVATION_NAMESPACE, name)
