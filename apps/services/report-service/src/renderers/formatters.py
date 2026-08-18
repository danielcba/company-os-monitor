"""Output formatters: to_html (jinja2 templates), to_pdf (weasyprint), to_json.

The formatters are the I/O boundary of the render layer: the pure renderers
produce a document dict, and the formatters serialize it to the requested
format (HTML dashboard page, PDF document, JSON API payload). ``to_html``
selects the template by ``doc["report_type"]`` (executive/technical/json) from
the local ``templates/`` directory; ``to_pdf`` renders the HTML with weasyprint;
``to_json`` serializes the document with JSON-native values. Only the report
document is produced - the formatters never read or write the pipeline tables
(ADR-0002, P1).
"""
import json
import os
from typing import Any

import jinja2
import weasyprint

from src.renderers.common import as_jsonable

DEFAULT_TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "..", "templates")


def to_json(document: dict[str, Any]) -> str:
    """Serialize a rendered document to a JSON string (JSON-native values)."""
    return json.dumps(as_jsonable(document), indent=2, ensure_ascii=False)


def to_html(document: dict[str, Any], template_dir: str | None = None) -> str:
    """Render a document dict into HTML via the local jinja2 templates."""
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(template_dir or DEFAULT_TEMPLATE_DIR),
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template(f"{document['report_type']}.html")
    return template.render(
        report=document, report_json=json.dumps(as_jsonable(document), indent=2)
    )


def to_pdf(html: str) -> bytes:
    """Render an HTML string into a PDF document (weasyprint)."""
    return weasyprint.HTML(string=html).write_pdf()