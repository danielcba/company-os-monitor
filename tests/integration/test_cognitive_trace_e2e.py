"""Cognitive Trace against the real canonical pipeline (Phase 1 end-to-end).

Reuses the Phase 1 vertical-slice helpers to produce a real Report from the
canonical cognitive flow and asserts the Cognitive Trace read model reconstructs
the SAME artifacts (Report -> Decision -> ... -> Observation). This keeps the
Phase 1 E2E green while adding the Phase 2A verification the prompt invites.

Requires a live PostgreSQL; skips when unreachable.
"""
from __future__ import annotations

import importlib.util
import sys
import tempfile
import uuid
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "apps/gateway/api-gateway"))

from src.cognitive_trace import CognitiveTraceStore  # noqa: E402

# Import the Phase 1 E2E module so we reuse its real pipeline + report builder.
_e2e_spec = importlib.util.spec_from_file_location(
    "test_cognitive_pipeline_e2e",
    ROOT / "tests/integration/test_cognitive_pipeline_e2e.py",
)
e2e = importlib.util.module_from_spec(_e2e_spec)
sys.modules["test_cognitive_pipeline_e2e"] = e2e
_e2e_spec.loader.exec_module(e2e)

DSN = e2e.DSN


@pytest.mark.asyncio
async def test_report_trace_matches_canonical_artifacts():
    try:
        engine = create_async_engine(DSN)
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:  # noqa: BLE001 - skip when no DB
        pytest.skip("PostgreSQL unavailable")

    stores = {
        "obs": e2e.ObservationStore(DSN),
        "ev": e2e.EvidenceStore(DSN),
        "ctx": e2e.ContextStore(DSN),
        "pat": e2e.PatternStore(DSN),
        "an": e2e.AnomalyStore(DSN),
        "hyp": e2e.HypothesisStore(DSN),
        "conf": e2e.ConfidenceStore(DSN),
        "rec": e2e.RecommendationStore(DSN),
        "dec": e2e.DecisionStore(DSN),
        "rep": e2e.ReportStore(DSN),
    }
    tenant = uuid.uuid4()
    res = await e2e._run_pipeline(stores, tenant, num_servers=3)
    report_service = e2e.report_svc.ReportService(
        stores["dec"],
        stores["rec"],
        stores["ctx"],
        stores["conf"],
        stores["hyp"],
        stores["an"],
        stores["pat"],
        stores["ev"],
        stores["obs"],
        stores["rep"],
        output_dir=tempfile.mkdtemp(),
    )
    report, status = await report_service.generate(tenant, e2e.REPORT_TYPE_JSON)
    assert status in ("created", "duplicate")

    trace_store = CognitiveTraceStore(engine)
    trace = await trace_store.get_trace(tenant_id=tenant, report_id=report.id)
    assert trace is not None
    assert trace["completeness"] == "complete"
    assert trace["warnings"] == []

    node_ids = {n["id"] for n in trace["nodes"]}
    # Every canonical artifact the report committed must be reconstructable.
    for d in res["decisions"]:
        assert str(d.id) in node_ids
    for r in res["recommendations"]:
        assert str(r.id) in node_ids
    for c in res["confidences"]:
        assert str(c.id) in node_ids
    for h in res["hypotheses"]:
        assert str(h.id) in node_ids
    for a in res["anomalies"]:
        assert str(a.id) in node_ids
    for p in res["patterns"]:
        assert str(p.id) in node_ids
    for cx in res["contexts"]:
        assert str(cx.id) in node_ids
    for ev in res["evidences"]:
        assert str(ev.id) in node_ids
    for o in res["observations"]:
        assert str(o.id) in node_ids

    await trace_store.close()
    await engine.dispose()
