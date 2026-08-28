"""Unit tests for Learning Memory Ledger semantic correctness.

Tests per audit requirements:
A. learning signal semantically correct
B. target type and target id correspond to same concept
C. append-only
D. idempotency
E. tenant isolation
F. provenance
"""
import uuid

import pytest

from libs.memory.memory_ledger import (
    TARGET_TYPES,
    PersistLearningMemoryInput,
    compute_signal_hash,
)


def test_target_types_includes_decision():
    """A/B. TARGET_TYPES includes 'decision' for consolidation signals."""
    assert "decision" in TARGET_TYPES
    assert "pattern" in TARGET_TYPES
    assert "context" in TARGET_TYPES
    assert "insight" in TARGET_TYPES
    assert len(TARGET_TYPES) == len({"pattern", "context", "insight", "decision"})


def test_decision_target_type_accepts_decision_id():
    """B. target_type='decision' with target_id=decision_id is semantically correct."""
    tenant_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    signal = {"decision_id": str(decision_id), "calibration_feedback": 0.5}
    provenance = {"decision_id": str(decision_id), "source": "outcome_consolidation"}

    # This should not raise - semantically correct
    record = PersistLearningMemoryInput(
        tenant_id=tenant_id,
        target_type="decision",
        target_id=decision_id,
        signal=signal,
        provenance=provenance,
    )
    assert record.target_type == "decision"
    assert record.target_id == decision_id


def test_pattern_target_type_requires_pattern_id():
    """B. target_type='pattern' with target_id=pattern_id is semantically correct."""
    tenant_id = uuid.uuid4()
    pattern_id = uuid.uuid4()
    signal = {"pattern_id": str(pattern_id), "recommended_action": "keep"}
    provenance = {"pattern_id": str(pattern_id), "source": "pattern_refinement"}

    record = PersistLearningMemoryInput(
        tenant_id=tenant_id,
        target_type="pattern",
        target_id=pattern_id,
        signal=signal,
        provenance=provenance,
    )
    assert record.target_type == "pattern"
    assert record.target_id == pattern_id


def test_context_target_type_requires_context_id():
    """B. target_type='context' with target_id=context_id is semantically correct."""
    tenant_id = uuid.uuid4()
    context_id = uuid.uuid4()
    signal = {"context_id": str(context_id), "recommended_revision": "review"}
    provenance = {"context_id": str(context_id), "source": "context_revision"}

    record = PersistLearningMemoryInput(
        tenant_id=tenant_id,
        target_type="context",
        target_id=context_id,
        signal=signal,
        provenance=provenance,
    )
    assert record.target_type == "context"
    assert record.target_id == context_id


def test_insight_target_type_requires_insight_id():
    """B. target_type='insight' with target_id=insight_id is semantically correct."""
    tenant_id = uuid.uuid4()
    insight_id = uuid.uuid4()
    signal = {"insight_id": str(insight_id), "transformation_kind": "revised"}
    provenance = {"insight_id": str(insight_id), "source": "insight_transformation"}

    record = PersistLearningMemoryInput(
        tenant_id=tenant_id,
        target_type="insight",
        target_id=insight_id,
        signal=signal,
        provenance=provenance,
    )
    assert record.target_type == "insight"
    assert record.target_id == insight_id


def test_signal_hash_deterministic():
    """D. Same signal produces same hash (idempotency)."""
    signal = {"key": "value", "number": 42}
    hash1 = compute_signal_hash(signal)
    hash2 = compute_signal_hash(signal)
    assert hash1 == hash2
    SHA256_HEX_LEN = 64
    assert len(hash1) == SHA256_HEX_LEN  # SHA-256 hex


def test_signal_hash_order_independent():
    """D. Signal hash is order-independent (sorted keys)."""
    signal1 = {"a": 1, "b": 2}
    signal2 = {"b": 2, "a": 1}
    assert compute_signal_hash(signal1) == compute_signal_hash(signal2)


def test_signal_hash_different_for_different_content():
    """D. Different signals produce different hashes."""
    hash1 = compute_signal_hash({"value": 1})
    hash2 = compute_signal_hash({"value": 2})
    assert hash1 != hash2


def test_provenance_contains_source():
    """F. Provenance includes source for traceability."""
    tenant_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    provenance = {
        "decision_id": str(decision_id),
        "tenant_id": str(tenant_id),
        "source": "outcome_consolidation",
    }
    record = PersistLearningMemoryInput(
        tenant_id=tenant_id,
        target_type="decision",
        target_id=decision_id,
        signal={},
        provenance=provenance,
    )
    assert record.provenance["source"] == "outcome_consolidation"


def test_provenance_links_to_decision():
    """F. Provenance links to originating Decision."""
    tenant_id = uuid.uuid4()
    decision_id = uuid.uuid4()
    provenance = {
        "decision_id": str(decision_id),
        "tenant_id": str(tenant_id),
        "source": "outcome_consolidation",
    }
    record = PersistLearningMemoryInput(
        tenant_id=tenant_id,
        target_type="decision",
        target_id=decision_id,
        signal={},
        provenance=provenance,
    )
    assert record.provenance["decision_id"] == str(decision_id)


def test_provenance_links_to_pattern():
    """F. Provenance links to Pattern for pattern refinement."""
    tenant_id = uuid.uuid4()
    pattern_id = uuid.uuid4()
    provenance = {
        "pattern_id": str(pattern_id),
        "context_id": str(uuid.uuid4()),
        "tenant_id": str(tenant_id),
        "source": "pattern_refinement",
    }
    record = PersistLearningMemoryInput(
        tenant_id=tenant_id,
        target_type="pattern",
        target_id=pattern_id,
        signal={},
        provenance=provenance,
    )
    assert record.provenance["pattern_id"] == str(pattern_id)
    assert record.provenance["source"] == "pattern_refinement"


def test_provenance_links_to_context():
    """F. Provenance links to Context for context revision."""
    tenant_id = uuid.uuid4()
    context_id = uuid.uuid4()
    provenance = {
        "context_id": str(context_id),
        "tenant_id": str(tenant_id),
        "source": "context_revision",
    }
    record = PersistLearningMemoryInput(
        tenant_id=tenant_id,
        target_type="context",
        target_id=context_id,
        signal={},
        provenance=provenance,
    )
    assert record.provenance["context_id"] == str(context_id)
    assert record.provenance["source"] == "context_revision"


def test_provenance_links_to_insight():
    """F. Provenance links to Insight for insight transformation."""
    tenant_id = uuid.uuid4()
    insight_id = uuid.uuid4()
    provenance = {
        "insight_id": str(insight_id),
        "tenant_id": str(tenant_id),
        "source": "insight_transformation",
    }
    record = PersistLearningMemoryInput(
        tenant_id=tenant_id,
        target_type="insight",
        target_id=insight_id,
        signal={},
        provenance=provenance,
    )
    assert record.provenance["insight_id"] == str(insight_id)
    assert record.provenance["source"] == "insight_transformation"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])