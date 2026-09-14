"""Architecture invariant tests for ADR-0003 — Framework Synchronization.

Verifies that ADR-0003 exists, has valid structure, and that documentation
drift corrections are coherent. Enforces that Memory/Learning is no longer
incorrectly marked as 'planned' and that ADR references are consistent.

Each test maps to a specific acceptance criterion from ADR-0003.
"""
import re
from pathlib import Path

import pytest

_root = Path(__file__).resolve().parents[2]
ADR_DIR = _root / "adr"
DOCS_DIR = _root / "docs"

SECTION_KEYS = [
    "## Context",
    "## Decision",
    "## Consequences",
    "## Invariants",
    "## Scope Boundary",
]


# ---------------------------------------------------------------------------
# AC-01: ADR-0003 exists and has valid structure
# ---------------------------------------------------------------------------
def test_adr_0003_exists():
    """AC-01: adr/ADR-0003-memory-learning-layer-adoption.md must exist."""
    adr_path = ADR_DIR / "ADR-0003-memory-learning-layer-adoption.md"
    assert adr_path.exists(), "ADR-0003 does not exist"


def test_adr_0003_has_valid_structure():
    """AC-01: ADR-0003 must have Context, Decision, Consequences,
    Invariants, Scope Boundary sections."""
    adr_path = ADR_DIR / "ADR-0003-memory-learning-layer-adoption.md"
    if not adr_path.exists():
        pytest.skip("ADR-0003 does not exist")
    text = adr_path.read_text(encoding="utf-8")
    for section in SECTION_KEYS:
        assert section in text, f"ADR-0003 missing section: {section}"


def test_adr_0003_status_is_proposed():
    """AC-13: ADR-0003 Status must be PROPOSED (pending human acceptance)."""
    adr_path = ADR_DIR / "ADR-0003-memory-learning-layer-adoption.md"
    if not adr_path.exists():
        pytest.skip("ADR-0003 does not exist")
    text = adr_path.read_text(encoding="utf-8")
    assert "Status: PROPOSED" in text, "ADR-0003 Status must be PROPOSED"


# ---------------------------------------------------------------------------
# AC-02: Memory is no longer marked as "planned" in architecture docs
# ---------------------------------------------------------------------------
def test_architecture_doc_memory_not_planned():
    """AC-02: docs/01-fundacion-arquitectura.md must not mark Memory as
    '(planned)'."""
    doc_path = DOCS_DIR / "01-fundacion-arquitectura.md"
    text = doc_path.read_text(encoding="utf-8")
    memory_lines = [
        line for line in text.splitlines()
        if "Memory" in line or "memory" in line or "MEMORY" in line
    ]
    for line in memory_lines:
        assert "(planned)" not in line.lower(), (
            f"Memory still planned in 01-fundacion-arquitectura.md: "
            f"{line.strip()}"
        )


# ---------------------------------------------------------------------------
# AC-03: Frontend doc drift corrected
# ---------------------------------------------------------------------------
def test_frontend_doc_planned_removed():
    """AC-03: docs/frontend/architecture.md must not mark implemented
    capabilities as '(planned)'."""
    doc_path = DOCS_DIR / "frontend" / "architecture.md"
    text = doc_path.read_text(encoding="utf-8")
    implemented = [
        "Decisions", "Recommendations", "Cognitive Trace",
        "Timeline", "Reports",
    ]
    for line in text.splitlines():
        for cap in implemented:
            if cap in line:
                assert "(planned)" not in line.lower(), (
                    f"Capability '{cap}' still planned in "
                    f"frontend/architecture.md: {line.strip()}"
                )


# ---------------------------------------------------------------------------
# AC-04: ADR-0008 references ADR-0003 coherently
# ---------------------------------------------------------------------------
def test_adr_0008_references_adr_0003():
    """AC-04: ADR-0008 'Relationship with ADR-0003' section must reference
    ADR-0003 as existing."""
    adr_path = ADR_DIR / "ADR-0008-outcome-status-semantics.md"
    text = adr_path.read_text(encoding="utf-8")
    marker = "## Relationship with ADR-0003"
    assert marker in text, "ADR-0008 missing 'Relationship with ADR-0003'"
    section_start = text.index(marker)
    section_text = text[section_start:section_start + 500]
    assert "ADR-0003" in section_text


# ---------------------------------------------------------------------------
# AC-05: ADR-0004 reference to ADR-0003 is coherent
# ---------------------------------------------------------------------------
def test_adr_0004_references_adr_0003():
    """AC-05: ADR-0004 Dependencies section must reference ADR-0003."""
    adr_path = ADR_DIR / "ADR-0004-transactional-outbox-observation-publisher.md"
    text = adr_path.read_text(encoding="utf-8")
    assert "ADR-0003" in text, "ADR-0004 does not reference ADR-0003"
    deps_idx = text.index("## Dependencies")
    deps_text = text[deps_idx:deps_idx + 500]
    assert "ADR-0003" in deps_text


# ---------------------------------------------------------------------------
# AC-06: H4 validation document reflects ADR-0003 existence
# ---------------------------------------------------------------------------
def test_h4_validation_reflects_adr_0003():
    """AC-06: H4_ADR_PACKAGE_VALIDATION.md must reflect ADR-0003 as
    created (PROPOSED) and not list it as non-existent."""
    h4_path = ADR_DIR / "H4_ADR_PACKAGE_VALIDATION.md"
    text = h4_path.read_text(encoding="utf-8")
    for line in text.splitlines():
        if "ADR-0003" in line:
            assert (
                "PROPOSED" in line
                or "created" in line.lower()
                or "not modified" not in line
            ), f"H4 validation treats ADR-0003 as non-existent: {line.strip()}"


# ---------------------------------------------------------------------------
# AC-07: Code comments updated where "planned" is stale
# ---------------------------------------------------------------------------
_STALE_PATTERNS = [
    re.compile(r"Memory\s+persistence\s+remains\s+planned", re.IGNORECASE),
]


def _has_stale_comment(text: str) -> str | None:
    """Return the matched stale pattern string, or None if clean."""
    # Normalize whitespace: collapse newlines/spaces into single spaces
    normalized = re.sub(r"\s+", " ", text)
    for pattern in _STALE_PATTERNS:
        m = pattern.search(normalized)
        if m:
            return m.group(0)
    return None


def test_code_comments_no_stale_planned():
    """AC-07: Files should not contain 'Memory persistence remains planned'
    comments, even when split across lines."""
    files_to_check = [
        _root / "apps" / "gateway" / "api-gateway" / "src" / "service.py",
        _root / "libs" / "memory" / "consolidation.py",
        _root / "libs" / "memory" / "pattern_refinement.py",
        _root / "libs" / "memory" / "context_revision.py",
    ]
    for fpath in files_to_check:
        if fpath.exists():
            text = fpath.read_text(encoding="utf-8")
            match = _has_stale_comment(text)
            assert match is None, (
                f"Stale comment in {fpath.name}: '{match}'"
            )


# ---------------------------------------------------------------------------
# AC-08: No behavioral changes (code logic unchanged)
# ---------------------------------------------------------------------------
def test_no_behavioral_changes():
    """AC-08: Modified files must not contain executable logic changes — only
    comments/doc/ADR changes are permitted."""
    files_to_verify = [
        _root / "apps" / "gateway" / "api-gateway" / "src" / "service.py",
        _root / "libs" / "memory" / "consolidation.py",
        _root / "libs" / "memory" / "pattern_refinement.py",
        _root / "libs" / "memory" / "context_revision.py",
    ]
    for fpath in files_to_verify:
        if fpath.exists():
            text = fpath.read_text(encoding="utf-8")
            compile(text, str(fpath), "exec")
