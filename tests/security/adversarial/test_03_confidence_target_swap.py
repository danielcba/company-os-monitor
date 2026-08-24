"""03 - Confidence Target Swap: confidence for R1 must not be used for D2.

Enforces: R4 (provenance binding), target_type + target_id verification.
"""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "gateway" / "api-gateway"))


class FakeConfidenceStore:
    """Store that only returns confidence for the original target."""

    def __init__(self, confidence_id, target_type, target_id, tenant_id):
        self._record = {
            "id": confidence_id,
            "tenant_id": tenant_id,
            "target_type": target_type,
            "target_id": target_id,
            "confidence_score": 0.8,
        }

    async def get_confidence_for_boundary(
        self, *, tenant_id, confidence_id, expected_target_type, expected_target_id=None
    ):
        if (
            confidence_id == str(self._record["id"])
            and tenant_id == str(self._record["tenant_id"])
            and expected_target_type == self._record["target_type"]
            and (expected_target_id is None or expected_target_id == self._record["target_id"])
        ):
            return self._record
        return None


async def test_target_type_mismatch_rejected():
    """Confidence for hypothesis must not validate for recommendation."""
    cid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    tenant = str(uuid.uuid4())
    store = FakeConfidenceStore(cid, "hypothesis", tid, tenant)

    from src.boundary import ConfidenceProvenanceError, validate_confidence_binding

    # Correct target_type -> succeeds
    result = await validate_confidence_binding(
        store=store, tenant_id=tenant, confidence_id=cid,
        expected_target_type="hypothesis", expected_target_id=tid,
    )
    assert result is not None

    # Wrong target_type -> fails
    with pytest.raises(ConfidenceProvenanceError):
        await validate_confidence_binding(
            store=store, tenant_id=tenant, confidence_id=cid,
            expected_target_type="recommendation", expected_target_id=tid,
        )


async def test_target_id_mismatch_rejected():
    """Confidence for hypothesis A must not validate for hypothesis B."""
    cid = str(uuid.uuid4())
    tid_a = str(uuid.uuid4())
    tid_b = str(uuid.uuid4())
    tenant = str(uuid.uuid4())
    store = FakeConfidenceStore(cid, "hypothesis", tid_a, tenant)

    from src.boundary import ConfidenceProvenanceError, validate_confidence_binding

    with pytest.raises(ConfidenceProvenanceError):
        await validate_confidence_binding(
            store=store, tenant_id=tenant, confidence_id=cid,
            expected_target_type="hypothesis", expected_target_id=tid_b,
        )


async def test_tenant_mismatch_rejected():
    """Confidence from tenant A must not validate for tenant B."""
    cid = str(uuid.uuid4())
    tid = str(uuid.uuid4())
    tenant_a = str(uuid.uuid4())
    tenant_b = str(uuid.uuid4())
    store = FakeConfidenceStore(cid, "hypothesis", tid, tenant_a)

    from src.boundary import ConfidenceProvenanceError, validate_confidence_binding

    with pytest.raises(ConfidenceProvenanceError):
        await validate_confidence_binding(
            store=store, tenant_id=tenant_b, confidence_id=cid,
            expected_target_type="hypothesis", expected_target_id=tid,
        )
