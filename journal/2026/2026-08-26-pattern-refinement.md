# 2026-08-26 — Pattern Refinement: refinamiento de patrones desde outcomes (P7 + P4)

## Objetivo
Implementar **Pattern Refinement** — la extensión de P7 que ajusta el soporte de
los Patterns en función de los outcomes de las Decisions que los usaron. Es la
continuación natural del Learning Loop: una vez que las Decisions se comparan
con la realidad (Outcome Consolidation) y se cierra el loop de calibración, los
verdictos de corroboración/contradicción se atribuyen a los Patterns que
informaron la Decision (vía la cadena de trazabilidad) y producen una señal de
refinamiento: `keep` / `degrade` / `deactivate`.

## Cadena de trazabilidad (verdicto → Pattern)
```
Decision.recommendation_id
  → Recommendation.hypothesis_id
    → Hypothesis.pattern_ids[]
      → Pattern.context_id
```
Cada Pattern recibe el conteo de `corroborated` / `contradicted` / `inconclusive`
de las Decisions enlazadas (solo las que tienen `actual_outcomes`).

## Diseño (conformidad con el marco)
- **P7 (Learning refines Patterns)**: el soporte de un Pattern se reconsidera
  desde outcomes observados de Decisions.
- **P4 (Patterns detectados, no inventados)**: el refinamiento SOLO ajusta el
  soporte (`recommended_strength` / acción). Nunca inventa ni elimina Patterns.
  La función pura `_refine_pattern` solo lee `strength_measure`/`pattern_type`,
  nunca los asigna.
- **P1 (no fabrication)**: outcomes faltantes/`inconclusive` NO se cuentan como
  fallos. `build_consolidation` (fuente única de verdad del verdicto) sigue
  siendo la única autoridad; Pattern Refinement no define su propio clasificador.
- **R1 (single capability)**: `libs/memory/pattern_refinement.py` expone exactamente
  una capacidad — computar la señal de refinamiento desde outcomes.
- **ADR-0002 (read/compute)**: capacidad externa, NO crea entidad persistida.
  Sin `INSERT`/`UPDATE`/`__tablename__`. Memory persistence sigue planificada.

## Boundary del gateway (hallazgo crítico)
La prueba de arquitectura `test_gateway_does_not_import_pipeline_logic` y
`test_raw_observation_cannot_bypass_perception` prohíben que los módulos del
gateway (`src/main.py`, `src/service.py`, `src/health.py`, `src/boundary.py`)
importen `libs.reasoning`/`libs.perception`. Por eso:
- El core se ubica en **`libs/memory`** (junto a Outcome Consolidation), NO en
  `libs/reasoning`.
- El gateway consume los **read stores del gateway** (`DecisionReadStore`,
  `RecommendationReadStore`, `HypothesisReadStore`, `PatternReadStore`) que
  devuelven dict-payloads. El core opera sobre ese contrato de lectura (sin
  importar el pipeline de reasoning).
- `_DecisionView` es un adapter mínimo de atributos para que `build_consolidation`
  (que usa acceso por atributo a `expected_outcomes`/`actual_outcomes`/`id`/
  `tenant_id`) funcione sobre el dict-payload.

## Lógica de la señal
- `total = corroborated + contradicted` (inconclusive no mueve la razón).
- `contradiction_ratio = contradicted / total`.
- `total < MIN_SAMPLES_FOR_REFINEMENT (2)` → `keep` (evita sobre-reaccionar a ruido).
- `contradiction_ratio >= DEACTIVATE_THRESHOLD (0.5)` → `deactivate` (fuerza 0.0).
- `contradicted > 0` → `degrade` (fuerza ∝ fracción corroborada).
- sino → `keep`.

## Archivos
- `libs/memory/pattern_refinement.py` — `PatternRefinementResult`,
  `PatternRefinementReport`, `PatternRefinementStore`, `_attribute_outcomes`,
  `_refine_pattern`, `build_pattern_refinement`, `PatternRefinementStoreProtocol`.
- `apps/gateway/api-gateway/src/service.py` — import de `libs.memory`,
  param `pattern_refinement_store`, método `get_pattern_refinement`.
- `apps/gateway/api-gateway/src/health.py` — `pattern_refinement_handler` +
  ruta `GET /api/v1/tenants/{tenant_id}/patterns/refinement`.
- `apps/gateway/api-gateway/src/main.py` — construye `PatternReadStore(dsn)` y
  `PatternRefinementStore(...)` con los read stores del gateway.
- Tests: `tests/memory/test_pattern_refinement.py`,
  `tests/architecture/test_pattern_refinement_invariants.py`,
  `apps/gateway/api-gateway/tests/test_pattern_refinement.py`.
- `cognitive_contract.md` — fila de Pattern Refinement + estado en Memory.

## Verificación
- 368 tests pasan (backend + gateway); ruff clean; mypy clean (73 archivos).
- Invariantes: P7 (outcomes), P4 (solo ajuste de soporte, sin INSERT/DELETE),
  R1 (una capacidad), ADR-0002 (read/compute, sin entidad, sin importar pipeline).
- PR #6 → merge a `main` → `docker-build` GREEN (pendiente de verificar).

## Próximos pasos (según framework)
1. Context Revision desde outcomes (atribuir Decisions contradicted a Contexts).
2. Insight Transformation journaling (R6): superficie `prior_understanding →
   mental_model_update`.
3. Memory persistence — DEFERIDO (ADR-0002: "remains planned"), hasta que el
   framework lo autorice.
