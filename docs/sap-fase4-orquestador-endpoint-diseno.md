# Diseño — Fase 4: Orquestador y Endpoint de Ejecución SAP R/3

**Estado:** Propuesto (draft de diseño — blueprint-before-code, ADR-0002)
**Fecha:** 2026-11-12
**Aplica a:** `company-os-monitor` (el producto)
**Relaciones:** ADR-0001/0002/0003, D-2026-08-07, P1–P7, R1–R7, Fases 1–3 SAP.

---

## 1. Contexto y motivación

Las Fases 1–3 entregaron las **piezas internas** del módulo SAP:
- Fase 1: `AssetFinanceStore` (tarifas monetarias) + DTOs.
- Fase 2: `SapGateway` (RFC/BAPI + mock) con seguridad de producción.
- Fase 3: `SapBridge` (ActionExecutor) que convierte una **Decision commiteada**
  en un envío a SAP, con idempotencia atómica.

**Falta el cableado:** hoy nadie llama a `SapBridge.execute()`. Este documento diseña
la **capa de orquestación** que (a) detecta las Decisions nuevas y listas para SAP,
(b) arma el `SapPostContext` (asset + horas) a partir de la decisión y (c) dispara
el bridge, todo expuesto mediante un **endpoint API** seguro.

Regla de oro: **blueprint antes que código** (ADR-0002). Este documento es ese
blueprint; no se escribe código hasta que se apruebe.

---

## 2. Principios rectores (alineación FULL con el framework)

| Principio | Cómo se respeta |
|---|---|
| **ADR-0002 / E2** | El orquestador y el endpoint son **capacidades externas no-canónicas**. No ocupan slot cognitivo; no entran al Cognitive Lexicon. |
| **R3 (Cognitive Boundary)** | El orquestador **solo lee** Decisions del store canónico (vía `DecisionStore`) y **escribe** hacia SAP. Nunca inyecta datos al pipeline, nunca genera juicios, nunca postea desde Perception/Reasoning. |
| **R4 (No Action Without Confidence)** | Solo procesa Decisions con `status == committed` (ya gateadas por confidence calibrada). El orquestador **no computa confidence**. |
| **R5 (Decision Record / authority)** | El endpoint exige autorización (RBAC + tenant scope). La ejecución se autoriza vía `authorize_action`/`require_authorized` del gateway (lo mismo que cualquier acción). |
| **P1 (append-only)** | El orquestador no muta tablas cognitivas; usa `sap_posting_log` (Fase 3) para trazabilidad. |
| **P7 / trazabilidad** | Cada envío queda trazable: decision_id → posting_key → outcome → reference. |

---

## 3. Arquitectura del orquestador

```
                    ┌──────────────────────────────────────────────┐
                    │           Gateway (api-gateway)              │
                    │   autenticación JWT + RBAC (R5)              │
                    └───────────────┬──────────────────────────────┘
                                    │  endpoint
                                    ▼
                ┌──────────────────────────────────────────────┐
                │        SapOrchestrator (nuevo, externo)      │
                │  - decide qué Decisions están listas para SAP │
                │  - arma el SapPostContext (asset + horas)     │
                │  - llama a SapBridge.execute()                │
                │  - controla error/éxito                      │
                └───────┬─────────────────────┬────────────────┘
                        │                     │
                        ▼                     ▼
            ┌───────────────────┐   ┌───────────────────┐
            │   DecisionStore   │   │   SapBridge (F3)  │──► SapGateway (F2) ─► SAP
            │ (lectura canónica)│   └───────────────────┘
            └───────────────────┘
```

**Componentes nuevos (diseño):**

### 3.1 `SapOrchestrator` (`libs/integrations/sap/sap_orchestrator.py`)
- **Entrada:** tenant, lista de `Decision` ids (o bien un barrido de Decisions `committed`), y un **mapeo de contexto** provisto por el llamador.
- **Responsabilidades:**
  1. **Leer** cada Decision del `DecisionStore` (solo lectura, P1).
  2. **Validar** que `status == committed` (R4) y que el tenant coincida.
  3. **Resolver el `SapPostContext`**: el orquestador necesita saber `asset_id` y `hours_down`. Como la `Decision` no porta estos campos canónicamente, el orquestador recibe un **mapeo explícito** (`decision_id -> SapPostContext`) del servicio de dominio que conoce el contexto de la caída. **No inventa datos.**
  4. **Llamar** a `SapBridge.execute()` por cada decisión apta.
  5. **Recolectar** resultados y devolver un resumen (`{ok, posting_key, outcome}` por decisión).
- **Fallback no-bloqueante:** si SAP no está disponible, el orquestador lo reporta (vía `SapResult.UNAVAILABLE`) sin romper el resto del pipeline.

### 3.2 Endpoint `POST /api/v1/tenants/{tenant_id}/sap/postings`
- **Propósito:** disparar el procesamiento de las Decisions pendientes de envío a SAP para un tenant.
- **Payload (request):**
  ```json
  {
    "decisions": [
      {"decision_id": "<uuid>", "asset_id": "<uuid>", "hours_down": 2.5}
    ]
  }
  ```
  El cliente (servicio de dominio) provee el contexto explícito. Sin él, el
  orquestador rechaza (fail-closed).
- **Autorización:** requiere acción `execute` (R5) + tenant scope. Se valida con
  `require_authorized(action="execute", requested_tenant_id=tenant_id)` (el
  mismo mecanismo del gateway para ejecución).
- **Respuesta 200:** `{results: [{decision_id, ok, outcome, reference, posting_key}]}`
- **Respuestas de error:** 401 (no autenticado), 403 (sin autorización),
  404 (tenant/decision no encontrados), 422 (payload inválido).
- **Idempotencia:** protegida por `sap_posting_log` (Fase 3): re-enviar la misma
  decisión+asset no duplica el posting.

### 3.3 (Opcional) Endpoint de consulta `GET /api/v1/tenants/{tenant_id}/sap/postings`
- Lista el historial de postings del tenant (auditoría, lectura del log). Requiere acción `read`.

---

## 4. Verificación de invariantes (mapeo)

| Invariante | Dónde se garantiza |
|---|---|
| R3 | El orquestador solo lee `DecisionStore` y escribe log SAP; no toca el pipeline. |
| R4 | Filtra por `status == committed`. |
| R5 | El endpoint usa `require_authorized(action="execute")`. |
| P1 | Sin UPDATE/DELETE en tablas cognitivas; log append-only. |
| Fail-closed | Sin contexto explícito o sin tarifa → no se postea (Fase 3). |

---

## 5. Seguridad del endpoint

| Check | Diseño |
|---|---|
| Autenticación | JWT (mismo middleware que el resto del gateway). |
| Autorización | `require_authorized` (RBAC + tenant scope). Ejecución requiere permiso `execute`. |
| Tenant isolation | Toda lectura/escritura acotada por `tenant_id` del token. |
| Validación de input | Pydantic (schema del payload): UUIDs válidos, `hours_down >= 0`. |
| Rate limiting / DoS | Reutilizar el middleware de rate limiting existente del gateway. |
| No exponer secretos | El endpoint no maneja credenciales (viven en `SapConfig`/secretos). |
| Logging | Solo eventos no sensibles (decision_id, posting_key, outcome) vía `get_logger`. |

---

## 6. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Un llamador manda decisiones no commiteadas | El orquestador valida `status == committed` y rechaza (R4). |
| Contexto de asset/horas incorrecto | El contexto viene explícito del servicio de dominio; el bridge valida rate y fail-closed. |
| Doble envío por retry | Idempotencia atómica de Fase 3 (`claim`/`finalize`). |
| SAP caído | Orquestador reporta `UNAVAILABLE` sin romper el pipeline. |
| Exposición del endpoint | Mismo JWT + RBAC + tenant scope que el resto del gateway. |

---

## 7. Orden de implementación (cuando se apruebe)

1. `SapOrchestrator` (lógica pura + tests unit, sin I/O externo).
2. Endpoint `POST .../sap/postings` en el gateway (con autorización y validación Pydantic).
3. Endpoint `GET .../sap/postings` (auditoría) opcional.
4. Tests de integración E2E con mock gateway (Decision → orquestador → bridge → log).
5. Verificación: ruff/mypy/bandit, suite SAP + corrida amplia.

---

## 8. Fuera de alcance

- Crear/alimentar las `Decision` (eso es del pipeline canónico).
- Inferir `asset_id`/`hours_down` automáticamente (sería inventar datos; el contexto es explícito).
- Postear de forma autónoma sin autorización (siempre vía endpoint autorizado).
- Modificar el framework o el pipeline cognitivo.

---

## 9. Conclusión

La Fase 4 es la **capa de integración** que completa el módulo SAP: un
orquestador que **cablea** las Decision (commiteadas al bridge, expuesto por un
endpoint seguro. Se mantiene alineado a FULL (R3/R4/R5, ADR-0002, P1), con
fail-closed, idempotencia y trazabilidad. Es un blueprint; la implementación
requiere aprobación y no debe empezar antes de este diseño.
