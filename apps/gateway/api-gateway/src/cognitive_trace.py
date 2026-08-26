"""Cognitive Trace READ model for the API Gateway (external capability, ADR-0002).

A Cognitive Trace is NOT a new cognitive stage and is NOT a persisted entity.
It is a READ MODEL / PROVENANCE VIEW built on top of the canonical cognitive
stores (P1/P3): given a Report (the root), it reconstructs the full chain of
artifacts that justify the conclusions the report formats:

    Report -> Decision -> Recommendation -> Confidence -> Hypothesis
           -> Anomaly -> Pattern -> Context -> Evidence -> Observation

The Report -> Decision link is canonical: a periodic Report aggregates N
Decisions (1:N, ADR-0002), so it is enumerated in ``content["decision_traces"]``
(the Report model intentionally has NO singular ``decision_id`` FK). Every other
relationship is read from the real canonical tables; nothing is invented.

The assembly is a single read/assembly layer:

    canonical stores -> bulk reads (tenant-scoped) -> Trace DTO -> API

It performs a small number of bulk, tenant-scoped queries (no N+1) and emits a
deterministic, serializable Trace DTO (stable ordering of nodes and edges) so
two identical requests always produce the same logical result.

Tenant isolation: every query is scoped by ``tenant_id``; a Report requested by
a different tenant resolves to nothing (the Report read itself is tenant-scoped),
so cross-tenant artifacts can never leak. Provenance that is broken (a referenced
id missing in the canonical tables) is never fabricated: the trace is returned
as ``partial`` with explicit ``warnings``.
"""
import json
import uuid
from collections.abc import Iterable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

# Stable type precedence for deterministic node ordering.
TYPE_ORDER: dict[str, int] = {
    "report": 0,
    "decision": 1,
    "recommendation": 2,
    "confidence": 3,
    "hypothesis": 4,
    "anomaly": 5,
    "pattern": 6,
    "context": 7,
    "evidence": 8,
    "observation": 9,
}

SELECT_REPORT = text(
    """
    SELECT id, tenant_id, report_type, title, summary, content,
           generated_at, period_start, period_end
    FROM reports
    WHERE tenant_id = :tenant_id AND id = :id
    """
)

SELECT_DECISIONS = text(
    """
    SELECT id, tenant_id, recommendation_id, confidence_id, authority_id,
           commitment, expected_outcomes, risk_tolerance, status, committed_at,
           executed_at, actual_outcomes
    FROM decisions
    WHERE tenant_id = :tenant_id AND id = ANY(:ids)
    """
)

SELECT_RECOMMENDATIONS = text(
    """
    SELECT id, tenant_id, hypothesis_id, insight_id, confidence_id,
           action_description, rationale, expected_consequences,
           alternatives_considered, confidence_score, status, proposed_at
    FROM recommendations
    WHERE tenant_id = :tenant_id AND id = ANY(:ids)
    """
)

SELECT_CONFIDENCE = text(
    """
    SELECT id, tenant_id, target_type, target_id, evidential_support,
           explanatory_coherence, historical_calibration, confidence_score,
           alpha, calibration_justification, calibration_error_estimate, computed_at
    FROM confidence_scores
    WHERE tenant_id = :tenant_id AND id = ANY(:ids)
    """
)

SELECT_HYPOTHESES = text(
    """
    SELECT id, tenant_id, anomaly_ids, pattern_ids, description,
           predicted_consequences, falsification_criterion, coherence_score,
           status, generated_at
    FROM hypotheses
    WHERE tenant_id = :tenant_id AND id = ANY(:ids)
    """
)

SELECT_ANOMALIES = text(
    """
    SELECT id, tenant_id, context_id, pattern_id, deviation_score,
           tolerance_threshold, anomaly_class, detected_at
    FROM anomalies
    WHERE tenant_id = :tenant_id AND id = ANY(:ids)
    """
)

SELECT_PATTERNS = text(
    """
    SELECT id, tenant_id, context_id, pattern_type, description,
           strength_measure, frequency, detected_at, is_active
    FROM patterns
    WHERE tenant_id = :tenant_id AND id = ANY(:ids)
    """
)

SELECT_CONTEXTS = text(
    """
    SELECT id, tenant_id, evidence_ids, mental_model_id, purpose,
           coherence_score, competing_models, activated_at, is_active
    FROM contexts
    WHERE tenant_id = :tenant_id AND id = ANY(:ids)
    """
)

SELECT_EVIDENCE = text(
    """
    SELECT id, tenant_id, observation_ids, organization_type, description,
           quality_class, weight, organized_at
    FROM evidence
    WHERE tenant_id = :tenant_id AND id = ANY(:ids)
    """
)

SELECT_OBSERVATIONS = text(
    """
    SELECT id, tenant_id, source_id, source_type, fact_type, fact_value,
           unit, captured_at, quality_class, raw_payload
    FROM observations
    WHERE tenant_id = :tenant_id AND id = ANY(:ids)
    """
)


def _as_json(value: Any) -> Any:
    """jsonb can arrive decoded (asyncpg) or as a string; normalize to JSON."""
    if isinstance(value, str):
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value
    return value


class CognitiveTraceStore:
    """Read/assembly layer that reconstructs a Cognitive Trace from canonical stores."""

    def __init__(self, engine: AsyncEngine):
        self._engine = engine
        self._session_factory = sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )

    # ------------------------------------------------------------------ entry
    async def get_trace(
        self, *, tenant_id: uuid.UUID, report_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """Build the Cognitive Trace for ``report_id`` within ``tenant_id``.

        Returns ``None`` when the Report does not exist for the tenant (the
        caller maps this to 404). Broken provenance is returned explicitly as a
        ``partial`` trace with ``warnings``; it is never silently fabricated.
        """
        async with self._session_factory() as session:
            row = (
                await session.execute(
                    SELECT_REPORT,
                    {"tenant_id": tenant_id, "id": report_id},
                )
            ).mappings().one_or_none()
            if row is None:
                return None

            report = self._report_payload(row)
            content = _as_json(row["content"]) or {}
            decision_ids = self._extract_decision_ids(content)

            if not decision_ids:
                return self._assemble(
                    report=report,
                    nodes=[self._node("report", report)],
                    edges=[],
                    warnings=["report has no decision_traces to trace"],
                )

            decisions = await self._bulk_by_ids(
                session, SELECT_DECISIONS, tenant_id, decision_ids
            )
            rec_ids = self._collect(decisions.values(), "recommendation_id")
            conf_ids = self._collect(decisions.values(), "confidence_id")
            recommendations = await self._bulk_by_ids(
                session, SELECT_RECOMMENDATIONS, tenant_id, rec_ids
            )
            conf_ids |= self._collect(recommendations.values(), "confidence_id")
            confidences = await self._bulk_by_ids(
                session, SELECT_CONFIDENCE, tenant_id, conf_ids
            )
            hyp_ids = self._collect(recommendations.values(), "hypothesis_id")
            hypotheses = await self._bulk_by_ids(
                session, SELECT_HYPOTHESES, tenant_id, hyp_ids
            )
            anomaly_ids = self._collect_list_all(hypotheses.values(), "anomaly_ids")
            pattern_ids = self._collect_list_all(hypotheses.values(), "pattern_ids")
            anomalies = await self._bulk_by_ids(
                session, SELECT_ANOMALIES, tenant_id, anomaly_ids
            )
            pattern_ids |= self._collect(anomalies.values(), "pattern_id")
            patterns = await self._bulk_by_ids(
                session, SELECT_PATTERNS, tenant_id, pattern_ids
            )
            context_ids = self._collect(anomalies.values(), "context_id")
            context_ids |= self._collect(patterns.values(), "context_id")
            contexts = await self._bulk_by_ids(
                session, SELECT_CONTEXTS, tenant_id, context_ids
            )
            evidence_ids = self._collect_list_all(contexts.values(), "evidence_ids")
            evidence = await self._bulk_by_ids(
                session, SELECT_EVIDENCE, tenant_id, evidence_ids
            )
            observation_ids = self._collect_list_all(
                evidence.values(), "observation_ids"
            )
            observations = await self._bulk_by_ids(
                session, SELECT_OBSERVATIONS, tenant_id, observation_ids
            )

        warnings = self._validate_provenance(
            decision_ids=decision_ids,
            decisions=decisions,
            recommendations=recommendations,
            confidences=confidences,
            hypotheses=hypotheses,
            anomalies=anomalies,
            patterns=patterns,
            contexts=contexts,
            evidence=evidence,
            observations=observations,
        )

        # Assemble nodes (dedup by type+id) and edges.
        nodes: dict[tuple[str, str], dict[str, Any]] = {}
        edges: set[tuple[str, str, str]] = set()

        self._add_node(nodes, "report", report)
        self._add_edges_report_decisions(edges, report["id"], decision_ids, decisions)

        for d in decisions.values():
            self._add_node(nodes, "decision", d)
            self._add_edges_decision(edges, d, recommendations, confidences)
        for r in recommendations.values():
            self._add_node(nodes, "recommendation", r)
            self._add_edges_recommendation(edges, r, hypotheses, confidences)
        for c in confidences.values():
            self._add_node(nodes, "confidence", c)
            # Confidence calibrates its hypothesis target only (keeps a clean
            # DAG; decision/recommendation targets already link back to it).
            if c["target_type"] == "hypothesis" and str(c["target_id"]) in {
                str(h["id"]) for h in hypotheses.values()
            }:
                edges.add((str(c["id"]), str(c["target_id"]), "calibrates"))
        for h in hypotheses.values():
            self._add_node(nodes, "hypothesis", h)
            self._add_edges_hypothesis(edges, h, anomalies, patterns)
        for a in anomalies.values():
            self._add_node(nodes, "anomaly", a)
            self._add_edges_anomaly(edges, a, patterns, contexts)
        for p in patterns.values():
            self._add_node(nodes, "pattern", p)
            if p.get("context_id") and str(p["context_id"]) in {
                str(c["id"]) for c in contexts.values()
            }:
                edges.add((str(p["id"]), str(p["context_id"]), "contextualized_by"))
        for c in contexts.values():
            self._add_node(nodes, "context", c)
            self._add_edges_context(edges, c, evidence)
        for e in evidence.values():
            self._add_node(nodes, "evidence", e)
            self._add_edges_evidence(edges, e, observations)
        for o in observations.values():
            self._add_node(nodes, "observation", o)

        sorted_nodes = sorted(
            nodes.values(), key=lambda n: (TYPE_ORDER.get(n["type"], 99), n["id"])
        )
        sorted_edges = sorted(edges)
        return self._assemble(
            report=report,
            nodes=sorted_nodes,
            edges=[{"from": f, "to": t, "relation": rel} for (f, t, rel) in sorted_edges],
            warnings=warnings,
        )

    # -------------------------------------------------------------- assembly
    @staticmethod
    def _assemble(
        *,
        report: dict[str, Any],
        nodes: list[dict[str, Any]],
        edges: list[dict[str, Any]],
        warnings: list[str],
    ) -> dict[str, Any]:
        completeness = "complete" if not warnings else "partial"
        return {
            "root": {
                "type": "report",
                "id": report["id"],
                "tenant_id": report["tenant_id"],
            },
            "nodes": nodes,
            "edges": edges,
            "completeness": completeness,
            "warnings": warnings,
        }

    # ----------------------------------------------------------------- reads
    @staticmethod
    async def _bulk_by_ids(
        session: AsyncSession,
        stmt: Any,
        tenant_id: uuid.UUID,
        ids: set[uuid.UUID],
    ) -> dict[uuid.UUID, dict[str, Any]]:
        """Tenant-scoped bulk read keyed by id; empty id set -> no query."""
        if not ids:
            return {}
        rows = await session.execute(stmt, {"tenant_id": tenant_id, "ids": list(ids)})
        return {r["id"]: dict(r) for r in rows.mappings()}

    # ------------------------------------------------------------- extraction
    @staticmethod
    def _extract_decision_ids(content: dict[str, Any]) -> list[uuid.UUID]:
        """Pull the decision ids enumerated by the Report (canonical 1:N link)."""
        traces = content.get("decision_traces")
        if not isinstance(traces, list):
            return []
        ids: list[uuid.UUID] = []
        for trace in traces:
            if not isinstance(trace, dict):
                continue
            decision = trace.get("decision")
            if not isinstance(decision, dict):
                continue
            raw = decision.get("id")
            if raw is None:
                continue
            try:
                ids.append(uuid.UUID(str(raw)))
            except (ValueError, TypeError):
                continue
        return ids

    # -------------------------------------------------------------- validation
    @staticmethod
    def _validate_provenance(
        *,
        decision_ids: list[uuid.UUID],
        decisions: dict[uuid.UUID, dict[str, Any]],
        recommendations: dict[uuid.UUID, dict[str, Any]],
        confidences: dict[uuid.UUID, dict[str, Any]],
        hypotheses: dict[uuid.UUID, dict[str, Any]],
        anomalies: dict[uuid.UUID, dict[str, Any]],
        patterns: dict[uuid.UUID, dict[str, Any]],
        contexts: dict[uuid.UUID, dict[str, Any]],
        evidence: dict[uuid.UUID, dict[str, Any]],
        observations: dict[uuid.UUID, dict[str, Any]],
    ) -> list[str]:
        """Explicitly report broken provenance; never fabricate missing links.

        Validates EVERY canonical reference the read model uses. Any missing
        referenced artifact yields an explicit warning and forces a ``partial``
        trace; broken provenance is never silently dropped.
        """
        warnings: list[str] = []

        # Report -> Decision (canonical 1:N link).
        decision_id_strs = {str(d) for d in decision_ids}
        found_decision_strs = {str(d["id"]) for d in decisions.values()}
        for missing in decision_id_strs - found_decision_strs:
            warnings.append(f"decision {missing} referenced by report not found")

        # Decision -> Recommendation / Confidence.
        for d in decisions.values():
            if d["recommendation_id"] not in recommendations:
                warnings.append(
                    f"recommendation {d['recommendation_id']} for decision "
                    f"{d['id']} not found"
                )
            if d["confidence_id"] not in confidences:
                warnings.append(
                    f"confidence {d['confidence_id']} for decision {d['id']} not found"
                )

        # Recommendation -> Hypothesis / Confidence.
        for r in recommendations.values():
            if r["hypothesis_id"] not in hypotheses:
                warnings.append(
                    f"hypothesis {r['hypothesis_id']} for recommendation "
                    f"{r['id']} not found"
                )
            if r["confidence_id"] not in confidences:
                warnings.append(
                    f"confidence {r['confidence_id']} for recommendation "
                    f"{r['id']} not found"
                )

        # Confidence -> Hypothesis (only when it calibrates a hypothesis).
        for c in confidences.values():
            if c["target_type"] == "hypothesis" and c["target_id"] not in hypotheses:
                warnings.append(
                    f"hypothesis {c['target_id']} for confidence {c['id']} not found"
                )

        # Hypothesis -> Anomaly / Pattern.
        for h in hypotheses.values():
            for a_id in h.get("anomaly_ids") or []:
                if a_id not in anomalies:
                    warnings.append(
                        f"anomaly {a_id} referenced by hypothesis {h['id']} not found"
                    )
            for p_id in h.get("pattern_ids") or []:
                if p_id not in patterns:
                    warnings.append(
                        f"pattern {p_id} referenced by hypothesis {h['id']} not found"
                    )

        # Anomaly -> Pattern / Context.
        for a in anomalies.values():
            if a.get("pattern_id") and a["pattern_id"] not in patterns:
                warnings.append(
                    f"pattern {a['pattern_id']} referenced by anomaly {a['id']} not found"
                )
            if a.get("context_id") and a["context_id"] not in contexts:
                warnings.append(
                    f"context {a['context_id']} referenced by anomaly {a['id']} not found"
                )

        # Pattern -> Context.
        for p in patterns.values():
            if p.get("context_id") and p["context_id"] not in contexts:
                warnings.append(
                    f"context {p['context_id']} referenced by pattern {p['id']} not found"
                )

        # Context -> Evidence.
        for c in contexts.values():
            for e_id in c.get("evidence_ids") or []:
                if e_id not in evidence:
                    warnings.append(
                        f"evidence {e_id} referenced by context {c['id']} not found"
                    )

        # Evidence -> Observation.
        for e in evidence.values():
            for o_id in e.get("observation_ids") or []:
                if o_id not in observations:
                    warnings.append(
                        f"observation {o_id} referenced by evidence {e['id']} not found"
                    )

        return warnings

    # --------------------------------------------------------------- nodes
    def _add_node(
        self,
        nodes: dict[tuple[str, str], dict[str, Any]],
        node_type: str,
        data: dict[str, Any],
    ) -> None:
        node_id = str(data["id"])
        if (node_type, node_id) in nodes:
            return
        nodes[(node_type, node_id)] = self._node(node_type, data)

    def _node(self, node_type: str, data: dict[str, Any]) -> dict[str, Any]:
        return {
            "type": node_type,
            "id": str(data["id"]),
            "tenant_id": str(data["tenant_id"]),
            "timestamp": self._timestamp(node_type, data),
            "data": self._node_data(node_type, data),
        }

    @staticmethod
    def _timestamp(node_type: str, data: dict[str, Any]) -> str | None:
        field = {
            "report": "generated_at",
            "decision": "committed_at",
            "recommendation": "proposed_at",
            "confidence": "computed_at",
            "hypothesis": "generated_at",
            "anomaly": "detected_at",
            "pattern": "detected_at",
            "context": "activated_at",
            "evidence": "organized_at",
            "observation": "captured_at",
        }.get(node_type)
        value = data.get(field) if field else None
        return value.isoformat() if value is not None else None

    @staticmethod
    def _node_data(node_type: str, data: dict[str, Any]) -> dict[str, Any]:
        if node_type == "report":
            return {
                "report_type": data["report_type"],
                "title": data["title"],
                "summary": data["summary"],
                "generated_at": data["generated_at"].isoformat(),
                "period_start": (
                    data["period_start"].isoformat()
                    if data["period_start"] is not None
                    else None
                ),
                "period_end": (
                    data["period_end"].isoformat()
                    if data["period_end"] is not None
                    else None
                ),
            }
        if node_type == "decision":
            expected = _as_json(data["expected_outcomes"])
            actual = _as_json(data["actual_outcomes"])
            return {
                "recommendation_id": str(data["recommendation_id"]),
                "confidence_id": str(data["confidence_id"]),
                "authority_id": str(data["authority_id"]),
                "commitment": data["commitment"],
                "expected_outcomes": list(expected or []),
                "risk_tolerance": data["risk_tolerance"],
                "status": data["status"],
                "committed_at": data["committed_at"].isoformat(),
                "executed_at": (
                    data["executed_at"].isoformat()
                    if data["executed_at"] is not None
                    else None
                ),
                "actual_outcomes": list(actual) if actual is not None else None,
            }
        if node_type == "recommendation":
            expected = _as_json(data["expected_consequences"])
            alternatives = _as_json(data["alternatives_considered"])
            payload: dict[str, Any] = {
                "hypothesis_id": str(data["hypothesis_id"]),
                "confidence_id": str(data["confidence_id"]),
                "action_description": data["action_description"],
                "rationale": data["rationale"],
                "expected_consequences": list(expected or []),
                "alternatives_considered": list(alternatives or []),
                "confidence_score": float(data["confidence_score"]),
                "status": data["status"],
                "proposed_at": data["proposed_at"].isoformat(),
            }
            if data.get("insight_id") is not None:
                payload["insight_id"] = str(data["insight_id"])
            return payload
        if node_type == "confidence":
            return {
                "target_type": data["target_type"],
                "target_id": str(data["target_id"]),
                "evidential_support": float(data["evidential_support"]),
                "explanatory_coherence": float(data["explanatory_coherence"]),
                "historical_calibration": float(data["historical_calibration"]),
                "confidence_score": float(data["confidence_score"]),
                "alpha": float(data["alpha"]),
                "calibration_justification": data["calibration_justification"],
                "calibration_error_estimate": float(
                    data["calibration_error_estimate"]
                ),
                "computed_at": data["computed_at"].isoformat(),
            }
        if node_type == "hypothesis":
            return {
                "anomaly_ids": [str(x) for x in (data["anomaly_ids"] or [])],
                "pattern_ids": [str(x) for x in (data["pattern_ids"] or [])],
                "description": data["description"],
                "predicted_consequences": list(data["predicted_consequences"] or []),
                "falsification_criterion": data["falsification_criterion"],
                "coherence_score": float(data["coherence_score"]),
                "status": data["status"],
                "generated_at": data["generated_at"].isoformat(),
            }
        if node_type == "anomaly":
            return {
                "context_id": str(data["context_id"]),
                "pattern_id": (
                    str(data["pattern_id"]) if data["pattern_id"] else None
                ),
                "anomaly_class": data["anomaly_class"],
                "deviation_score": float(data["deviation_score"]),
                "tolerance_threshold": float(data["tolerance_threshold"]),
                "detected_at": data["detected_at"].isoformat(),
            }
        if node_type == "pattern":
            return {
                "context_id": str(data["context_id"]),
                "pattern_type": data["pattern_type"],
                "description": data["description"],
                "strength_measure": float(data["strength_measure"]),
                "frequency": data["frequency"],
                "detected_at": data["detected_at"].isoformat(),
                "is_active": bool(data["is_active"]),
            }
        if node_type == "context":
            return {
                "evidence_ids": [str(x) for x in (data["evidence_ids"] or [])],
                "mental_model_id": data["mental_model_id"],
                "purpose": data["purpose"],
                "coherence_score": float(data["coherence_score"]),
                "competing_models": _as_json(data["competing_models"]),
                "activated_at": data["activated_at"].isoformat(),
                "is_active": bool(data["is_active"]),
            }
        if node_type == "evidence":
            return {
                "observation_ids": [str(x) for x in (data["observation_ids"] or [])],
                "organization_type": data["organization_type"],
                "description": data["description"],
                "quality_class": data["quality_class"],
                "weight": float(data["weight"]),
                "organized_at": data["organized_at"].isoformat(),
            }
        if node_type == "observation":
            return {
                "source_id": str(data["source_id"]),
                "source_type": data["source_type"],
                "fact_type": data["fact_type"],
                "fact_value": _as_json(data["fact_value"]),
                "unit": data["unit"],
                "captured_at": data["captured_at"].isoformat(),
                "quality_class": data["quality_class"],
                "raw_payload": _as_json(data["raw_payload"]),
            }
        return {}

    # --------------------------------------------------------------- edges
    @staticmethod
    def _add_edges_report_decisions(
        edges: set[tuple[str, str, str]],
        report_id: str,
        decision_ids: list[uuid.UUID],
        decisions: dict[uuid.UUID, dict[str, Any]],
    ) -> None:
        for d_id in decision_ids:
            if d_id in decisions:
                edges.add((report_id, str(d_id), "documents"))

    @staticmethod
    def _add_edges_decision(
        edges: set[tuple[str, str, str]],
        decision: dict[str, Any],
        recommendations: dict[uuid.UUID, dict[str, Any]],
        confidences: dict[uuid.UUID, dict[str, Any]],
    ) -> None:
        d_id = str(decision["id"])
        if decision["recommendation_id"] in recommendations:
            edges.add((d_id, str(decision["recommendation_id"]), "commits"))
        if decision["confidence_id"] in confidences:
            edges.add((d_id, str(decision["confidence_id"]), "calibrated_by"))

    @staticmethod
    def _add_edges_recommendation(
        edges: set[tuple[str, str, str]],
        recommendation: dict[str, Any],
        hypotheses: dict[uuid.UUID, dict[str, Any]],
        confidences: dict[uuid.UUID, dict[str, Any]],
    ) -> None:
        r_id = str(recommendation["id"])
        if recommendation["hypothesis_id"] in hypotheses:
            edges.add((r_id, str(recommendation["hypothesis_id"]), "explains"))
        if recommendation["confidence_id"] in confidences:
            edges.add((r_id, str(recommendation["confidence_id"]), "carries"))

    @staticmethod
    def _add_edges_hypothesis(
        edges: set[tuple[str, str, str]],
        hypothesis: dict[str, Any],
        anomalies: dict[uuid.UUID, dict[str, Any]],
        patterns: dict[uuid.UUID, dict[str, Any]],
    ) -> None:
        h_id = str(hypothesis["id"])
        for a_id in hypothesis["anomaly_ids"] or []:
            if a_id in anomalies:
                edges.add((h_id, str(a_id), "accounts_for"))
        for p_id in hypothesis["pattern_ids"] or []:
            if p_id in patterns:
                edges.add((h_id, str(p_id), "refers_to"))

    @staticmethod
    def _add_edges_anomaly(
        edges: set[tuple[str, str, str]],
        anomaly: dict[str, Any],
        patterns: dict[uuid.UUID, dict[str, Any]],
        contexts: dict[uuid.UUID, dict[str, Any]],
    ) -> None:
        a_id = str(anomaly["id"])
        if anomaly["pattern_id"] and anomaly["pattern_id"] in patterns:
            edges.add((a_id, str(anomaly["pattern_id"]), "deviates_from"))
        if anomaly["context_id"] in contexts:
            edges.add((a_id, str(anomaly["context_id"]), "contextualized_by"))

    @staticmethod
    def _add_edges_context(
        edges: set[tuple[str, str, str]],
        context: dict[str, Any],
        evidence: dict[uuid.UUID, dict[str, Any]],
    ) -> None:
        c_id = str(context["id"])
        for e_id in context["evidence_ids"] or []:
            if e_id in evidence:
                edges.add((c_id, str(e_id), "organizes"))

    @staticmethod
    def _add_edges_evidence(
        edges: set[tuple[str, str, str]],
        evidence: dict[str, Any],
        observations: dict[uuid.UUID, dict[str, Any]],
    ) -> None:
        e_id = str(evidence["id"])
        for o_id in evidence["observation_ids"] or []:
            if o_id in observations:
                edges.add((e_id, str(o_id), "observes"))

    # ------------------------------------------------------------- helpers
    @staticmethod
    def _collect(
        rows: "Iterable[dict[str, Any]]", key: str
    ) -> set[uuid.UUID]:
        out: set[uuid.UUID] = set()
        for row in rows:
            value = row.get(key)
            if value is not None:
                out.add(value)
        return out

    @staticmethod
    def _collect_list_all(
        rows: "Iterable[dict[str, Any]]", key: str
    ) -> set[uuid.UUID]:
        out: set[uuid.UUID] = set()
        for row in rows:
            value = row.get(key)
            if value:
                out.update(value)
        return out

    @staticmethod
    def _report_payload(row: Any) -> dict[str, Any]:
        """JSON-native READ view of the immutable report row (the root)."""
        return {
            "id": str(row["id"]),
            "tenant_id": str(row["tenant_id"]),
            "report_type": row["report_type"],
            "title": row["title"],
            "summary": row["summary"],
            "generated_at": row["generated_at"],
            "period_start": row["period_start"],
            "period_end": row["period_end"],
        }

    async def verify_connection(self) -> None:
        """Fail fast if the database is unreachable."""
        async with self._engine.connect() as conn:
            await conn.execute(text("SELECT 1"))

    async def close(self) -> None:
        await self._engine.dispose()
