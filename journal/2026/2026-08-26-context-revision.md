# 2026-08-26 — Context Revision: revisión de contextos desde outcomes (P7 + P2)

## Objetivo
Implementar **Context Revision** — la extensión de P7 que atribuye los verdictos
de outcomes de las Decisions a los Contexts que las enmarcaron, produciendo una
señal de revisión (`keep` / `review` / `consider_competitor`). Continúa la cadena
de cierre del Learning Loop tras Outcome Consolidation y Pattern Refinement.

## Cadena de trazabilidad (verdicto → Context)
```
Decision.recommendation_id
  → Recommendation.hypothesis_id
    → Hypothesis.pattern_ids[]
      → Pattern.context_id
        → Context
```
Cada Context acumula los conteos de `corroborated` / `contradicted` /
`inconclusive` de las Decisions enlazadas (vía sus Patterns).

## Diseño (conformidad con el marco)
- **P7 (Learning refines Context)**: el soporte/validez de un Context se
  reconsidera desde outcomes observados de Decisions.
- **P2 (Context Competition)**: la revisión SOLO *sugiere* reconsiderar un modelo
  competidor (`consider_competitor` + `suggested_competitor`); NUNCA activa ni
  genera un Context. No hay `INSERT`/`UPDATE`/`is_active` en el módulo.
- **P1 (no fabrication)**: outcomes faltantes/`inconclusive` NO se cuentan como
  fallos; `build_consolidation` sigue siendo la única autoridad de verdicto.
- **R1 (single capability)**: `libs/memory/context_revision.py` expone una sola
  capacidad — computar la señal de revisión desde outcomes.
- **ADR-0002 (read/compute)**: capacidad externa, NO crea entidad persistida. Sin
  `INSERT`/`UPDATE`/`__tablename__`. Memory persistence sigue planificada.

## Boundary del gateway (igual que Pattern Refinement)
La prueba de arquitectura prohíbe que el gateway importe `libs.reasoning`/
`libs.perception`. Por eso:
- El core vive en **`libs/memory`** (junto a Consolidation y Pattern Refinement).
- El gateway consume los read stores (`DecisionReadStore`,
  `RecommendationReadStore`, `HypothesisReadStore`, `PatternReadStore`,
  `ContextReadStore`) que devuelven dict-payloads.
- `_DecisionView` (reutilizado desde `pattern_refinement`) adapta el dict al
  acceso por atributo que usa `build_consolidation`.
- El `ContextReadStore` expone `competing_models` (lista de dicts); se usa el
  primer modelo competidor como `suggested_competitor` (nunca auto-activado).

## Lógica de la señal
- `total = corroborated + contradicted` (inconclusive no mueve la razón).
- `contradiction_ratio = contradicted / total`.
- `total < MIN_SAMPLES_FOR_REVISION (2)` → `keep`.
- `contradicted == 0` → `keep`.
- `contradiction_ratio >= REVISION_THRESHOLD (0.5)` y hay `competing_models`
  → `consider_competitor` (sugiere el 1º competidor).
- `contradiction_ratio >= 0.5` sin competidores → `review`.
- sino → `review`.

## Archivos
- `libs/memory/context_revision.py` — `ContextRevisionResult`,
  `ContextRevisionReport`, `ContextRevisionStore`,
  `_attribute_outcomes_to_contexts`, `_revise_context`, `_first_competitor_id`,
  `build_context_revision`, `ContextRevisionStoreProtocol`.
- `apps/gateway/api-gateway/src/service.py` — import de `libs.memory`,
  param `context_revision_store`, método `get_context_revision`.
- `apps/gateway/api-gateway/src/health.py` — `context_revision_handler` + ruta
  `GET /api/v1/tenants/{tid}/contexts/revision`.
- `apps/gateway/api-gateway/src/main.py` — construye `ContextReadStore(dsn)` y
  `ContextRevisionStore(...)` con los read stores del gateway.
- Tests: `tests/memory/test_context_revision.py`,
  `tests/architecture/test_context_revision_invariants.py`,
  `apps/gateway/api-gateway/tests/test_context_revision.py`.
- `cognitive_contract.md` — fila de Context Revision + estado en Memory.

## Verificación
- 385 tests pasan (backend + gateway); ruff clean; mypy clean (74 archivos).
- Invariantes: P7 (outcomes), P2 (solo sugiere, nunca activa), P1 (no fabricación),
  R1 (una capacidad), ADR-0002 (read/compute, sin entidad, sin importar pipeline).
- PR #7 → merge a `main` → `docker-build` GREEN (pendiente de verificar).

## Próximos pasos (según framework)
1. Insight Transformation journaling (R6): superficie
   `prior_understanding → mental_model_update`.
2. Memory persistence — DEFERIDO (ADR-0002: "remains planned"), hasta que el
   framework lo autorice.
