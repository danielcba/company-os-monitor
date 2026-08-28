"""Architecture boundary tests (Blocker #19).

Enforce the Cognitive Boundary (cognitive-architecture.md R3/R7):
- Reasoning/Evaluate must NOT import ObservationStore (raw Perception data). It
  must consume Evidence (the canonical Perception artifact).
- Perception must not reach Action directly (general invariant).
These tests fail the build if a future change re-introduces a forbidden import.
"""
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[4]
POLICY = (
    REPO_ROOT
    / "libs"
    / "reasoning"
    / "evaluation_policy.py"
)
SERVICE = (
    REPO_ROOT
    / "apps"
    / "services"
    / "evaluation-service"
    / "src"
    / "service.py"
)


def _source(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_evaluation_policy_does_not_import_observation_store():
    """Reasoning/Evaluate must consume Evidence, never the raw Observation store."""
    src = _source(POLICY)
    assert "from libs.perception.store import" not in src
    assert "ObservationStore" not in src


def test_evaluation_service_does_not_import_observation_store():
    """The Evaluate service must not read Observations directly."""
    src = _source(SERVICE)
    assert "from libs.perception.store import" not in src
    assert "ObservationStore" not in src


def test_evaluation_policy_consumes_evidence():
    """The Evaluate policy's canonical input is Evidence (Perception artifact)."""
    src = _source(POLICY)
    assert "from libs.perception.evidence import Evidence" in src


def test_perception_store_does_not_import_action():
    """General invariant: Perception layer must not import the Action layer."""
    perception_files = list((REPO_ROOT / "libs" / "perception").rglob("*.py"))
    for f in perception_files:
        if f.name == "__init__.py" or f.name == "__pycache__":
            continue
        src = f.read_text(encoding="utf-8")
        assert "libs.action" not in src, f"Perception must not import Action: {f}"


def test_decision_service_port_is_not_reused_by_evaluation():
    """Evaluation Service must not collide with the decision-service port (8097)."""
    import re

    main_src = (
        REPO_ROOT
        / "apps"
        / "services"
        / "evaluation-service"
        / "src"
        / "main.py"
    ).read_text(encoding="utf-8")
    # Parse the default port from the env-get call; it must not be 8097.
    match = re.search(r'EVALUATION_HEALTH_PORT",\s*"(\d+)"', main_src)
    assert match is not None, "EVALUATION_HEALTH_PORT default not found in main.py"
    assert match.group(1) != "8097"
    assert "EVALUATION_HEALTH_PORT" in main_src


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
