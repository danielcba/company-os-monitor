# 2026-08-26 — Insight Transformation journaling (R6) + atribución de outcomes

## Objetivo
Implementar **Insight Transformation journaling** — la expresión de R6 ("Insight
restructures existing knowledge; it journals the transformation from a prior
understanding to a new mental-model update"). Cada Insight es, por construcción,
una transformación registrada (`prior_understanding` → `mental_model_update`).
Esta capacidad la superficializa para revisión y, cuando los readers de outcomes
están disponibles, atribuye los verdictos de outcomes de Decisions al Insight que
informó la Recommendation (trazabilidad
`Decision → Recommendation[insight_id] → Insight`).

## Diseño (conformidad con el marco)
- **R6 (Insight restructures knowledge)**: superficializa la transformación
  prior → updated mental-model como un journal. `transformation_kind` es
  `revised` (prior ≠ updated), `stable` (repr igual) o `unchanged` (ambos vacíos).
- **P4 (sin explicación causal)**: la clasificación es descriptiva (prior ≠
  updated); el módulo NO inventa una causa para la transformación (no hay
  helpers de "root_cause"/"explain_cause").
- **P1 (no fabrication)**: outcomes faltantes/`inconclusive` NO se cuentan como
  fallos; `build_consolidation` sigue siendo la única autoridad de verdicto.
- **R1 (single capability)**: `libs/memory/insight_transformation.py` expone una
  sola capacidad — computar el journal de transformaciones de Insights.
- **ADR-0002 (read/compute)**: capacidad externa, NO crea entidad persistida. Sin
  `INSERT`/`UPDATE`/`__tablename__`. Memory persistence sigue planificada.

## Boundary del gateway (igual que las anteriores)
La prueba de arquitectura prohíbe que el gateway importe `libs.reasoning`/
`libs.perception`. Por eso el core vive en `libs/memory` y el gateway consume
los read stores (`InsightReadStore`, y opcionalmente `DecisionReadStore` /
`RecommendationReadStore`) que devuelven dict-payloads. `_DecisionView`
(reutilizado) adapta el dict al acceso por atributo de `build_consolidation`.

## Lógica
- `_classify_transformation(prior, updated)`: descriptiva (P4).
- `_attribute_outcomes_to_insights(decisions, recommendations)`: mapea
  verdictos a `insight_id` vía `recommendation.insight_id`.
- `_journal_insight`: construye el registro puro (transformation_kind + conteos).
- `build_insight_transformation`: lee Insights; si Decision/Recommendation
  readers presentes, atribuye outcomes. Devuelve `InsightTransformationReport`.
- `InsightTransformationStore`: envuelve los read stores; `journal_for_tenant`.

## Archivos
- `libs/memory/insight_transformation.py` — `InsightTransformationResult`,
  `InsightTransformationReport`, `InsightTransformationStore`,
  `_classify_transformation`, `_attribute_outcomes_to_insights`,
  `_journal_insight`, `build_insight_transformation`,
  `InsightTransformationStoreProtocol` (+ Protocols de lectura).
- `apps/gateway/api-gateway/src/service.py` — import de `libs.memory`, param
  `insight_transformation_store`, método `get_insight_transformation`.
- `apps/gateway/api-gateway/src/health.py` — `insight_transformation_handler` +
  ruta `GET /api/v1/tenants/{tid}/insights/transformations`.
- `apps/gateway/api-gateway/src/main.py` — construye `InsightTransformationStore(
  insight_store=insight_store, decision_store=decision_read_store,
  recommendation_store=recommendation_read_store)`.
- Tests: `tests/memory/test_insight_transformation.py`,
  `tests/architecture/test_insight_transformation_invariants.py`,
  `apps/gateway/api-gateway/tests/test_insight_transformation.py`.
- `cognitive_contract.md` — fila de Insight Transformation + estado en Memory.

## Verificación
- 401 tests pasan (backend + gateway); ruff clean; mypy clean (75 archivos).
- Invariantes: R6 (journal prior→updated), P4 (clasificación descriptiva, sin
  causa), P1 (no fabricación), R1 (una capacidad), ADR-0002 (read/compute, sin
  entidad, sin importar pipeline).
- PR #8 → merge a `main` → `docker-build` GREEN (pendiente de verificar).

## Estado del Learning Loop / P7
Con PR #4 (Outcome Consolidation), PR #5 (Learning Loop), PR #6 (Pattern
Refinement), PR #7 (Context Revision) y PR #8 (Insight Transformation), el
cierre del loop P7 queda completo a nivel read/compute:
`Decision.outcomes → Consolidation → Confidence calibration → Pattern
Refinement → Context Revision → Insight Transformation journaling`.

Pendiente (DEFERIDO, ADR-0002): **Memory persistence** — sigue planificada
hasta que el framework lo autorice explícitamente.
