# 2026-08-26 — Fase 2A Hardening (PR #2)

Hardening final del Cognitive Trace antes del merge. Sin Fase 2B, sin UI, sin
nuevas capacidades. Rama `feature/phase2-cognitive-trace-ui` (HEAD base
`9c79340`).

## Prioridad 1 — Broken Provenance

`_validate_provenance()` ahora valida TODA la cadena canónica utilizada por el
read model, no solo Decision→Recommendation/Confidence y
Recommendation→Hypothesis/Confidence. Relaciones agregadas:

- Confidence → Hypothesis (cuando `target_type == "hypothesis"`).
- Hypothesis → Anomaly / Pattern.
- Anomaly → Pattern / Context.
- Pattern → Context.
- Context → Evidence.
- Evidence → Observation.

Regla mantenida: referencia rota ⇒ `warnings != []` ⇒ `completeness = "partial"`;
nunca se fabrican nodos/edges. Imposible `warnings == []` + `complete` con artefacto
faltante.

Test: `test_broken_provenance_each_relation` (parametrizado, 13 casos A–G + extras)
en `apps/gateway/api-gateway/tests/test_cognitive_trace.py`. Como el esquema
aplica FK, el artefacto "faltante" se siembra en un SEGUNDO tenant: la FK se
cumple (el id existe) pero la lectura tenant-scoped del tenant del trace no lo
encuentra ⇒ provenance rota realista (también ejercita tenant isolation).

## Prioridad 2 — E2E / DB unavailable

`tests/integration/test_cognitive_trace_e2e.py`: si PostgreSQL no está
disponible, en CI (`CI=true`) ahora hace `pytest.fail(...)` (señal real de
outage) en lugar de `pytest.skip(...)` que enmascaraba el fallo con GREEN. En
local sigue haciendo skip.

## Prioridad 3 — Typing

`service.py`: `cognitive_trace_store` tipado explícitamente vía
`CognitiveTraceStoreProtocol` (Protocol) — sin import circular, sin refactor
grande. `get_cognitive_trace` usa el contrato estructural.

## Validación

- Gateway Cognitive Trace tests: 18/18 (5 base + 13 parametrizados).
- Gateway suite completa: 146 passed.
- Integration E2E: 4 passed (trace + Phase 1).
- Root tests: 170 passed (sin regresión).
- Phase 1 E2E: 3/3 GREEN.
- ruff (repo), mypy (gateway + libs), bandit: GREEN.
- Frontend lint/typecheck/test: GREEN (4 warnings pre-existentes, 0 errores).
- docker compose build: termina correctamente.

Arquitectura preservada: Report 1:N Decision, `content["decision_traces"]`,
tenant isolation, bulk reads, determinismo, sin tabla CognitiveTrace, sin nueva
etapa cognitiva.
