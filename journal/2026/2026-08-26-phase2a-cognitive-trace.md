# 2026-08-26 — Fase 2A: Cognitive Trace contract and read API

Fase 1 permanece cerrada e intacta. Esta ejecución inicia Fase 2A: un **read
model / provenance view** que reconstruye, desde un Report (raíz), la cadena
canónica de artefactos cognitivos. NO se implementa la UI completa (futura
Cognitive Trace UI).

## Branch

- `feature/phase2-cognitive-trace-ui` creada desde `main` (HEAD
  `d39015e`, Fase 1 validada, GREEN).

## Decisiones arquitectónicas (R1–R7 / P1–P7)

- El Cognitive Trace **no es una etapa cognitiva nueva** ni una entidad
  persistida: NO se crea tabla `CognitiveTrace`. Es un read model ensamblado
  bajo demanda desde los stores canónicos (P3).
- `canonical stores → bulk reads (tenant-scoped) → Trace DTO → API`. Lecturas
  bulk para evitar N+1; sin Redis/Kafka/Graph DB/cache distribuida.
- **Report → Decision es 1:N** (canónico, ADR-0002): el Reporte enumera sus
  Decisions en `content["decision_traces"]`; no existe `report.decision_id`.
- **Tenant isolation**: toda query se acota por `tenant_id` (identidad del
  token, no del request). Un Reporte de otro tenant resuelve a nada → 404.
- **Determinismo**: orden estable de nodos (por tipo+id) y edges (tupla
  ordenada). Mismos datos → mismo resultado lógico.
- **Provenance rota no se fabrica**: trace `partial` + `warnings` explícitos.

## Entregables

- `apps/gateway/api-gateway/src/cognitive_trace.py` — `CognitiveTraceStore`
  (bulk reads tenant-scoped, ensambla `nodes`/`edges` deterministas).
- `apps/gateway/api-gateway/src/service.py` — `GatewayService.get_cognitive_trace`
  (resolución de tenant vía `_resolve_tenant`, autoridad `read`).
- `apps/gateway/api-gateway/src/health.py` — ruta
  `GET /api/v1/tenants/{tenant_id}/cognitive-trace/report/{report_id}` +
  handler con authz/tenant isolation/logging.
- `apps/gateway/api-gateway/src/main.py` — wiring del store (engine compartido,
  verify_connection, close).
- Frontend (solo contrato): `apps/web/src/types/cognitive.ts`
  (`CognitiveTraceResponse`) y `apps/web/src/api/gateway.ts`
  (`fetchCognitiveTrace`). Sin UI completa.
- Tests:
  - `apps/gateway/api-gateway/tests/test_cognitive_trace.py` — escenario
    controlado (happy path, multi-decision 1:N, determinismo, tenant
    isolation, missing report, broken provenance).
  - `tests/integration/test_cognitive_trace_e2e.py` — contra el pipeline real
    de Fase 1: el trace reconstruye los mismos artefactos del Reporte.

## Contrato de respuesta

```json
{
  "root":    { "type": "report", "id": "...", "tenant_id": "..." },
  "nodes":   [ { "type", "id", "tenant_id", "timestamp", "data" } ],
  "edges":   [ { "from", "to", "relation" } ],
  "completeness": "complete" | "partial",
  "warnings": [ "..." ]
}
```

## Validación

- Gateway tests (5): GREEN.
- Integration trace (real pipeline): GREEN.
- Fase 1 E2E (`test_cognitive_pipeline_e2e.py`, 3 tests): GREEN (sin regresión).
- Ruff (nuevos archivos): GREEN.
- MyPy gateway src: GREEN.

## STOP CONDITION

Fase 2A cubre contrato + read model + API + autorización + tenant isolation +
tests + docs. Se detiene aquí: NO UI completa, NO Demo Mode, NO LLM, NO nuevos
dominios, NO acciones automáticas, NO avance a otra fase.
