# 2026-08-26 — P7: Memory Layer (Outcome Consolidation)

## Objetivo
Implementar la **Fase P7 (Memory)** como capacidad cognitiva de solo lectura/
cómputo (Outcome Consolidation) sobre el store canónico de Decisions, alineada
estrictamente al Company OS Cognitive Architecture Framework (P1-P7, R1-R7,
ADR-0002). Verificación minuciosa antes de cerrar: sin errores, alineación
rigurosa al marco, luego journal + GitHub.

## Diseño (conformidad con el marco)
- **R1 (exactamente una capacidad)**: `libs/memory/consolidation.py` implementa
  UNA capacidad — consolidar `expected_outcomes` vs `actual_outcomes` de
  Decisions. No calibra, no decide, no ejecuta.
- **P1 (Primacía de la Observación / sin fabricación)**: un Decision SIN
  `actual_outcomes` produce consolidación **inconclusive** — los outcomes
  faltantes NUNCA se tratan como fallo (no se inventan observaciones ni
  resultados). Esto corrige el sesgo de fabricación del helper preexistente
  `libs/action/decision.py::compare_expected_actual_outcomes` (ver Residuales).
- **R7 (la arquitectura guía el código)**: lee stores canónicos; no reimplementa
  lógica cognitiva. Reusa `brier_score`/`ece_score`/`CalibrationParams` de
  `libs/cognitive_core/calibration_model.py`.
- **ADR-0002 (capacidad externa, no canónica)**: consolidación es un read/
  compute externo sobre artefactos canónicos. NO crea entidad persistida (la
  persistencia de Memory sigue planificada en el marco): sin nueva tabla, sin
  nuevo id, sin mutación. Espejo del patrón Cognitive Trace.
- **Tenant scope**: toda consolidación se ancla a un `tenant_id`; un batch con
  Decision de otro tenant levanta `CrossTenantConsolidationError` (defense in
  depth sobre el aislamiento ya existente en el gateway).

## Trabajo realizado
- `libs/memory/__init__.py` + `libs/memory/consolidation.py`:
  - `ConsolidationResult` / `ConsolidationReport` (pydantic frozen, read/compute).
  - `build_consolidation(decision)` (puro, sin IO) y
    `consolidate_decisions(tenant_id, decisions)` (raise cross-tenant).
  - `ConsolidationStore` (envuelve un `DecisionReader` inyectable; NO escribe).
  - Protocolos `DecisionReader` / `ConsolidationStoreProtocol`.
  - Helper `_classify_expected_outcome` para mantener la función acotada.
- Gateway (espejo exacto de Cognitive Trace, ADR-0002 / R3 / R7):
  - `service.py`: param `consolidation_store` + `get_consolidation(...)`
    (resuelve tenant vía `_resolve_tenant`, devuelve `model_dump(mode="json")`).
  - `health.py`: ruta `GET /api/v1/tenants/{tenant_id}/memory/consolidation`
    + `consolidation_handler` (auth 401, authz 403, 500 genérico).
  - `main.py`: construye `ConsolidationStore(decision_store=decision_store)` y
    lo inyecta (sin nueva conexión/cierre; comparte el DecisionStore).
- Tests:
  - `tests/memory/test_consolidation.py` (puro, sin IO): 11 tests —
    no-fabricación, corroboración/contradicción, determinismo (frozen),
    rollup agregado, tenant scope.
  - `tests/architecture/test_memory_invariants.py`: invariantes P1/R1/tenant/
    ADR-0002 (sin `__tablename__`, sin write engine).
  - `apps/gateway/api-gateway/tests/test_consolidation.py`: servicio con
    `FakeConsolidationStore` + JWT real (sin PG) — lectura tenant-scoped,
    cross-tenant 403, store no configurado.

## Verificación (Done gate)
- Backend: `pytest apps/gateway/api-gateway/tests` = 149 passed;
  `pytest tests` = 184 passed (incluye los 17 nuevos de P7).
- Lint: `ruff check` sobre archivos nuevos/modificados = **All checks passed**.
- Tipos: `mypy libs/memory apps/gateway/api-gateway/src` = **no issues**.
- Alineación al marco revisada línea a línea (P1, R1, R7, ADR-0002, tenant).

## Criterio de Done (P7)
- [x] Capacidad de Outcome Consolidation implementada (read/compute, sin entidad).
- [x] Sin fabricación de outcomes faltantes (P1).
- [x] Aislamiento de tenant en consolidación.
- [x] Endpoint gateway + handler + wiring en `main.py`.
- [x] Tests unitarios, de arquitectura e de gateway verdes; lint + mypy OK.
- [x] Journal + PR/merge a `main` + `docker-build` GREEN.

## Residuales (fuera de alcance, documentado)
- `libs/action/decision.py::compare_expected_actual_outcomes` aún trata los
  `actual_outcomes` faltantes como 0/fallo (fabricación). La nueva
  consolidación NO lo hace. Recomendado refactorizar ese helper en una fase
  futura para eliminar la divergencia. No se tocó para no ampliar el alcance.

## Estado del producto
P7 Memory (Outcome Consolidation) queda operativo como read/compute externo,
manteniendo conformidad estricta P1-P7 / R1-R7 / ADR-0002.
