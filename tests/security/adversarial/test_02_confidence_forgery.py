"""02 - Confidence Forgery: client-supplied confidence_score must be ignored.

Enforces: R4 (no judgment influences action without calibrated confidence).
"""
import sys
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "apps" / "gateway" / "api-gateway"))


async def test_client_confidence_score_is_ignored():
    """The gateway's verify_confidence_provenance IGNORES client confidence_score."""
    # When confidence_store is None, the gateway MUST raise, not return verified=False
    from src.service import GatewayService

    from libs.access.security import JwtService
    from libs.access.token_blacklist import SecurityControlUnavailable

    jwt = JwtService(algorithm="HS256", secret_key="test")
    svc = GatewayService(jwt, confidence_store=None)

    with pytest.raises(SecurityControlUnavailable):
        await svc.verify_confidence_provenance(
            tenant_id=str(uuid.uuid4()),
            confidence_id=str(uuid.uuid4()),
            expected_target_type="hypothesis",
        )


def test_confidence_score_field_validates_range():
    """ConfidenceCreate rejects scores outside [0, 1]."""
    from pydantic import ValidationError

    from libs.learning.confidence import ConfidenceCreate

    base = {
        "tenant_id": uuid.uuid4(),
        "target_type": "hypothesis",
        "target_id": uuid.uuid4(),
        "evidential_support": 0.5,
        "explanatory_coherence": 0.5,
        "historical_calibration": 0.5,
        "confidence_score": 0.5,
        "alpha": 0.5,
        "calibration_justification": "test",
        "calibration_error_estimate": 0.1,
    }
    # Valid
    ConfidenceCreate(**base)
    # Forged high score
    with pytest.raises(ValidationError):
        ConfidenceCreate(**{**base, "confidence_score": 1.5})
    # Forged negative score
    with pytest.raises(ValidationError):
        ConfidenceCreate(**{**base, "confidence_score": -0.1})


def test_evidential_support_validates_range():
    """ConfidenceCreate rejects evidential_support outside [0, 1]."""
    from pydantic import ValidationError

    from libs.learning.confidence import ConfidenceCreate

    base = {
        "tenant_id": uuid.uuid4(),
        "target_type": "hypothesis",
        "target_id": uuid.uuid4(),
        "evidential_support": 0.5,
        "explanatory_coherence": 0.5,
        "historical_calibration": 0.5,
        "confidence_score": 0.5,
        "alpha": 0.5,
        "calibration_justification": "test",
        "calibration_error_estimate": 0.1,
    }
    with pytest.raises(ValidationError):
        ConfidenceCreate(**{**base, "evidential_support": 2.0})
