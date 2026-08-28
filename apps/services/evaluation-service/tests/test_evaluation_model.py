"""Unit tests for the Evaluation model and store (pure, no I/O)."""
import uuid

import pytest
from libs.reasoning.evaluation import (
    EVALUATION_RESULTS,
    RESULT_CONFIRMED,
    RESULT_FALSIFIED,
    RESULT_INSUFFICIENT,
    EvaluationCreate,
    build_evaluation,
    create_evaluation,
    evaluation_id,
)
from pydantic import ValidationError


def test_evaluation_id_is_deterministic_and_content_addressed():
    tenant_id = uuid.uuid4()
    hypothesis_id = uuid.uuid4()
    evidence_ids = [uuid.uuid4(), uuid.uuid4()]
    result = RESULT_CONFIRMED

    first = evaluation_id(tenant_id, hypothesis_id, evidence_ids, result)
    second = evaluation_id(tenant_id, hypothesis_id, evidence_ids, result)
    assert first == second
    assert first.version == 5


def test_evaluation_id_changes_with_different_evidence():
    tenant_id = uuid.uuid4()
    hypothesis_id = uuid.uuid4()
    evidence_ids_1 = [uuid.uuid4(), uuid.uuid4()]
    evidence_ids_2 = [uuid.uuid4(), uuid.uuid4()]
    result = RESULT_CONFIRMED

    id1 = evaluation_id(tenant_id, hypothesis_id, evidence_ids_1, result)
    id2 = evaluation_id(tenant_id, hypothesis_id, evidence_ids_2, result)
    assert id1 != id2


def test_evaluation_id_changes_with_different_result():
    tenant_id = uuid.uuid4()
    hypothesis_id = uuid.uuid4()
    evidence_ids = [uuid.uuid4()]

    id_confirmed = evaluation_id(tenant_id, hypothesis_id, evidence_ids, RESULT_CONFIRMED)
    id_falsified = evaluation_id(tenant_id, hypothesis_id, evidence_ids, RESULT_FALSIFIED)
    id_insufficient = evaluation_id(tenant_id, hypothesis_id, evidence_ids, RESULT_INSUFFICIENT)

    assert id_confirmed != id_falsified
    assert id_confirmed != id_insufficient
    assert id_falsified != id_insufficient


def test_evaluation_id_excludes_evaluated_at():
    """evaluated_at is deliberately excluded: re-evaluating with same inputs produces same id."""
    tenant_id = uuid.uuid4()
    hypothesis_id = uuid.uuid4()
    evidence_ids = [uuid.uuid4()]
    result = RESULT_CONFIRMED

    id1 = evaluation_id(tenant_id, hypothesis_id, evidence_ids, result)
    id2 = evaluation_id(tenant_id, hypothesis_id, evidence_ids, result)
    assert id1 == id2


def test_evaluation_create_defaults():
    create = EvaluationCreate(
        tenant_id=uuid.uuid4(),
        hypothesis_id=uuid.uuid4(),
        result=RESULT_CONFIRMED,
        rationale="Test rationale",
    )
    assert create.result == RESULT_CONFIRMED
    assert create.evidence_ids == []
    assert create.observed_outcomes == []
    assert create.support_count == 0
    assert create.contradiction_count == 0
    assert create.confidence_id is None


def test_evaluation_model_is_frozen():
    create = EvaluationCreate(
        tenant_id=uuid.uuid4(),
        hypothesis_id=uuid.uuid4(),
        result=RESULT_CONFIRMED,
        rationale="Test rationale",
    )
    evaluation = build_evaluation(create)
    with pytest.raises(ValidationError):  # Pydantic frozen model
        evaluation.result = "falsified"


def test_build_evaluation_mirrors_create_with_deterministic_id():
    tenant_id = uuid.uuid4()
    hypothesis_id = uuid.uuid4()
    evidence_ids = [uuid.uuid4()]
    create = EvaluationCreate(
        tenant_id=tenant_id,
        hypothesis_id=hypothesis_id,
        evidence_ids=evidence_ids,
        observed_outcomes=[{"metric": "test", "value": 1}],
        support_count=2,
        contradiction_count=0,
        confidence_id=uuid.uuid4(),
        result=RESULT_CONFIRMED,
        rationale="Test rationale",
    )
    evaluation = build_evaluation(create)

    assert evaluation.id == evaluation_id(tenant_id, hypothesis_id, evidence_ids, RESULT_CONFIRMED)
    assert evaluation.tenant_id == tenant_id
    assert evaluation.hypothesis_id == hypothesis_id
    assert evaluation.evidence_ids == evidence_ids
    assert evaluation.support_count == 2
    assert evaluation.contradiction_count == 0
    assert evaluation.result == RESULT_CONFIRMED
    assert evaluation.rationale == "Test rationale"


def test_create_evaluation_convenience_function():
    tenant_id = uuid.uuid4()
    hypothesis_id = uuid.uuid4()
    evidence_ids = [uuid.uuid4()]

    evaluation = create_evaluation(
        tenant_id=tenant_id,
        hypothesis_id=hypothesis_id,
        evidence_ids=evidence_ids,
        observed_outcomes=[{"metric": "test"}],
        support_count=1,
        contradiction_count=0,
        confidence_id=uuid.uuid4(),
        result=RESULT_FALSIFIED,
        rationale="Falsified",
    )

    assert evaluation.tenant_id == tenant_id
    assert evaluation.hypothesis_id == hypothesis_id
    assert evaluation.result == RESULT_FALSIFIED


def test_evaluation_results_constants():
    assert RESULT_CONFIRMED in EVALUATION_RESULTS
    assert RESULT_FALSIFIED in EVALUATION_RESULTS
    assert RESULT_INSUFFICIENT in EVALUATION_RESULTS
    assert len(EVALUATION_RESULTS) == 3


def test_evaluation_create_validation():
    """Test that result must be one of the valid results."""
    with pytest.raises(ValidationError):
        EvaluationCreate(
            tenant_id=uuid.uuid4(),
            hypothesis_id=uuid.uuid4(),
            result="invalid_result",
            rationale="Test",
        )