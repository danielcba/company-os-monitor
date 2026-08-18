"""Unit tests for the Report model (external non-canonical output, ADR-0002).

Covers the deterministic content-addressed ``report_id`` (idempotent dedup by
tenant + type + period), the frozen model, the build espejo, the MVP defaults
(ai_generated=False, model_used=None) and the ReportStore read surface.
No DB I/O: pure model tests.
"""
import uuid
from datetime import date

import pytest
from libs.action.report import (
    REPORT_NAMESPACE,
    REPORT_TYPE_EXECUTIVE,
    REPORT_TYPE_TECHNICAL,
    Report,
    ReportCreate,
    build_report,
    report_id,
)
from pydantic import ValidationError

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
PERIOD_START = date(2026, 8, 17)
PERIOD_END = date(2026, 8, 17)


def make_create(**overrides) -> ReportCreate:
    base = {
        "tenant_id": TENANT,
        "report_type": REPORT_TYPE_EXECUTIVE,
        "title": "COS-Monitor Executive Summary",
        "summary": "Resumen ejecutivo de 1 decision.",
        "content": {"decision_count": 1},
        "ai_generated": False,
        "model_used": None,
        "period_start": PERIOD_START,
        "period_end": PERIOD_END,
        "file_path": "/tmp/executive.pdf",
    }
    base.update(overrides)
    return ReportCreate(**base)


def test_report_id_is_deterministic_and_content_addressed():
    first = report_id(TENANT, REPORT_TYPE_EXECUTIVE, PERIOD_START, PERIOD_END)
    second = report_id(TENANT, REPORT_TYPE_EXECUTIVE, PERIOD_START, PERIOD_END)
    assert first == second
    assert first.version == 5
    assert first == uuid.uuid5(
        REPORT_NAMESPACE,
        f"{TENANT}:{REPORT_TYPE_EXECUTIVE}:{PERIOD_START.isoformat()}:{PERIOD_END.isoformat()}",
    )


def test_report_id_changes_with_tenant_type_or_period():
    base = report_id(TENANT, REPORT_TYPE_EXECUTIVE, PERIOD_START, PERIOD_END)
    assert report_id(uuid.uuid4(), REPORT_TYPE_EXECUTIVE, PERIOD_START, PERIOD_END) != base
    assert report_id(TENANT, REPORT_TYPE_TECHNICAL, PERIOD_START, PERIOD_END) != base
    assert (
        report_id(
            TENANT, REPORT_TYPE_EXECUTIVE, date(2026, 8, 18), date(2026, 8, 18)
        )
        != base
    )


def test_report_id_excludes_generated_at_and_content():
    """generated_at and the rendered content are NOT part of the id: the same
    report of the same period dedups even if re-rendered at a later instant."""
    first = report_id(TENANT, REPORT_TYPE_EXECUTIVE, PERIOD_START, PERIOD_END)
    second = report_id(TENANT, REPORT_TYPE_EXECUTIVE, PERIOD_START, PERIOD_END)
    assert first == second


def test_report_models_are_frozen():
    with pytest.raises(ValidationError):
        make_create().title = "otra"  # type: ignore[misc]
    report = build_report(make_create())
    with pytest.raises(ValidationError):
        report.title = "otra"  # type: ignore[misc]


def test_report_create_mvp_defaults():
    create = make_create()
    assert create.ai_generated is False
    assert create.model_used is None
    assert create.content == {"decision_count": 1}
    assert create.summary


def test_build_report_mirrors_create_with_deterministic_id():
    create = make_create()
    report = build_report(create)
    assert report.id == report_id(
        create.tenant_id, create.report_type, create.period_start, create.period_end
    )
    assert report.tenant_id == TENANT
    assert report.report_type == REPORT_TYPE_EXECUTIVE
    assert report.title == create.title
    assert report.summary == create.summary
    assert report.content == create.content
    assert report.ai_generated is False
    assert report.model_used is None
    assert report.file_path == create.file_path
    assert report.generated_at.tzinfo is not None


def test_report_fields_are_json_round_trippable():
    report = build_report(make_create())
    payload = report.model_dump(mode="json")
    assert isinstance(payload["id"], str)
    assert isinstance(payload["period_start"], str)
    assert payload["report_type"] == REPORT_TYPE_EXECUTIVE
    reconstructed = Report(**payload)
    assert reconstructed.id == report.id
    assert reconstructed.content == report.content
