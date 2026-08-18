"""Report renderers - pure document builders + output formatters.

The renderers are pure functions over data ALREADY READ from the cognitive
tables (single responsibility: the orchestrator reads, the renderer formats).
They never touch the database, never write to the pipeline tables (P1) and
never invent judgments (ADR-0002).
"""
from src.renderers.common import ReportSource
from src.renderers.executive import render_executive
from src.renderers.formatters import to_html, to_json, to_pdf
from src.renderers.json_render import render_json
from src.renderers.technical import render_technical

__all__ = [
    "ReportSource",
    "render_executive",
    "render_json",
    "render_technical",
    "to_html",
    "to_json",
    "to_pdf",
]