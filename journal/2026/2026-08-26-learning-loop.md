# 2026-08-26 — Learning Loop: cierre del loop de aprendizaje (P7)

## Objetivo
Cerrar el **Learning Loop** — el gap estructural más grande del proyecto —
reinyectando los resultados de la consolidación de outcomes en el modelo de
Confidence calibration. Esto convierte el ECE de estático/vacío a dinámico
basado en outcomes reales, completando P7: "The comparison of expected and
actual outcomes is the primary input to the Confidence calibration model."

## Diseño (conformidad con el marco)
- **P7 (Learning Through Outcome)**: el loop ahora cierra:
  `Decision → actual_outcomes → compute_outcome_signal → (confidence, outcome)
  pairs → ece_score → historical_calibration = 1-ECE → calibrate()`
- **R1 (single capability)**: `libs/learning/learning_loop.py` implementa UNA
  capacidad — computar el learning signal desde outcomes. No calibra, no
  decide, no ejecuta.
- **P1 (no fabrication)**: outcomes faltantes producen None (inconclusive), nunca
  un fallo fabricado.
- **ADR-0002 (read/compute)**: el módulo lee Decisions y Confidence scores
  existentes; no crea entidades persistidas ni escribe a la DB.
- **R7 (architecture guides code)**: reusa `ece_score` de
  `libs/cognitive_core/calibration_model.py`; el confidence-service orquesta
  el flujo sin reimplementar lógica cognitiva.

## Trabajo realizado

### Nuevo módulo: `libs/learning/learning_loop.py`
- `compute_outcome_signal(decision)` — determina si los outcomes de una Decision
  fueron corroborados (1) o contradichidos (0). Sin fabricación: faltantes → None.
- `build_learning_history(tenant_id, decisions, confidence_scores)` — construye
  (confidence_score, outcome) pairs para cómputo de ECE. Retorna `LearningHistory`
  con pairs, ECE y historical_calibration (1-ECE).
- Protocolos inyectables: `DecisionReader`, `ConfidenceScoreReader`.

### Modificación: confidence service
- `service.py`: `_calibrate_tenant()` ahora carga Decisions con actual_outcomes
  y Confidence scores del tenant, construye learning history, y pasa
  `historical=[(confidence, outcome), ...]` al calibrator (antes era `None`).
- `main.py`: construye `DecisionStore` y lo inyecta en `ConfidenceService`.
- El calibrator existente (`historical_calibration_factor`) ya soportaba datos
  reales; solo necesitaba ser alimentado.

### Tests
- `tests/learning/test_learning_loop.py` — 13 tests puros: outcome signal,
  learning history, ECE computation, frozen models, no-fabrication.
- `tests/architecture/test_learning_loop_invariants.py` — 4 invariantes:
  R1 (single capability), P1 (no fabrication), ADR-0002 (no persisted entity),
  P7 (ECE computation).

## Verificación (Done gate)
- Backend: `pytest tests/ apps/gateway/api-gateway/tests/` = **350 passed**.
- Lint: `ruff check` = **All checks passed**.
- Tipos: `mypy` = **no issues found**.
- Alineación al marco revisada línea a línea.

## Impacto
- **Antes**: `historical_calibration` era siempre 1.0 (sin historial). El factor
  `(1-ECE)` no contribuía al score. El sistema no aprendía de sus outcomes.
- **Ahora**: cuando existen Decisions con actual_outcomes, el ECE se computa
  desde datos reales. El `(1-ECE)` penaliza calibraciones historically
  imprecisas. El sistema cierra el loop P7.

## Criterio de Done (Learning Loop)
- [x] `compute_outcome_signal` determina outcomes desde Decisions.
- [x] `build_learning_history` construye (confidence, outcome) pairs.
- [x] Confidence service alimenta `historical` al calibrator.
- [x] Tests puros + invariantes de arquitectura verdes.
- [x] Lint + mypy clean.
- [x] Journal + PR/merge a `main`.

## Residuales
- El flujo actual carga TODAS las Confidence del tenant para el join. Para
  tenants con muchos scores, optimizar con query filtrado por target_type.
- La señal de outcome es binaria (corroborated/contradicted). Una señal
  ponderada por strength del pattern es futura.
- Pattern refinement y Context revision desde outcomes siguen pendientes
  (dependen de este loop como base).

## Estado del producto
El Learning Loop queda operativo: el sistema ahora computa ECE desde outcomes
reales y alimenta la calibración de Confidence. P7 está cerrado estructuralmente.
