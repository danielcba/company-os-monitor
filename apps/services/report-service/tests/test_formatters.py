"""Unit tests for the output formatters (to_html / to_json / to_pdf).

The formatters are the I/O boundary of the render layer: they serialize a
rendered document dict into HTML (jinja2 templates), PDF (weasyprint) and JSON.
"""
import json
import uuid
from datetime import UTC, date, datetime

from src.renderers.common import ReportSource
from src.renderers.executive import render_executive
from src.renderers.formatters import to_html, to_json, to_pdf

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
NOW = datetime(2026, 8, 17, 12, 0, tzinfo=UTC)


def make_empty_source() -> ReportSource:
    return ReportSource(
        tenant={"id": TENANT, "name": "Sandbox Tenant", "slug": "sandbox"},
        decisions=(),
        recommendations=(),
        contexts=(),
        confidences=(),
        hypotheses=(),
        anomalies=(),
        patterns=(),
        evidence=(),
        observations=(),
        period_start=date(2026, 8, 10),
        period_end=date(2026, 8, 17),
        generated_at=NOW,
    )


def test_to_json_is_valid_and_contains_data():
    doc = render_executive(make_empty_source())
    payload = to_json(doc)
    parsed = json.loads(payload)
    assert parsed["report_type"] == "executive"
    assert parsed["decision_count"] == 0
    assert parsed["tenant"]["name"] == "Sandbox Tenant"
    assert parsed["period"]["start"] == "2026-08-10"


def test_to_html_contains_document_data():
    doc = render_executive(make_empty_source())
    html = to_html(doc)
    assert "COS-Monitor Executive Summary" in html
    assert "Sandbox Tenant" in html
    assert "No committed decisions in this period." in html


def test_to_pdf_returns_non_empty_pdf_bytes():
    doc = render_executive(make_empty_source())
    html = to_html(doc)
    pdf = to_pdf(html)
    assert isinstance(pdf, bytes)
    assert len(pdf) > 0
    assert pdf[:4] == b"%PDF"


def test_to_html_technical_template():
    from src.renderers.technical import render_technical

    doc = render_technical(make_empty_source())
    html = to_html(doc)
    assert "COS-Monitor Technical Report" in html
    assert "Sandbox Tenant" in html