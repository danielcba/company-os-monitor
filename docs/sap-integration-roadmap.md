# Hoja de Ruta — Integración SAP R/3 (COS-Monitor)

**Estado:** Propuesto (draft, sin implementar)
**Fecha:** 2026-11-12
**Rol:** ingeniero de software senior / arquitecto / security engineer / reviewer de release
**Aplica a:** `company-os-monitor` (el producto)
**Basado en:** D-2026-08-07 (SAP R/3 Integration Is an External, Non-Canonical Capability), ADR-0001/0002/0003, P1–P7, R1–R7.

---

## 0. Resumen ejecutivo

| Área | Estado actual |
|---|---|
| Decisión de arquitectura | ✅ `D-2026-08-07` (SAP = capacidad externa no-canónica) |
| Código de integración SAP | ❌ No existe (ningún `pyrfc`/`BAPI_*`/conector) |
| Modelo de datos financiero | ❌ Tabla `servers` sin `cost_per_hour`/`currency` |
| Cálculo de downtime cost | ❌ No existe |
| Punto de salida del pipeline | ❌ No hay bridge hacia RFC/BAPI |

**Conclusión:** La integración SAP está **decidida en arquitectura** pero **sin implementar**. Lo primero no es código de RFC, sino **el modelo de datos financiero** (el dato que SAP necesita). Luego el conector externo, luego el bridge desde el flujo canónico.

---

## 1. Contexto y principios rectores

### 1.1 La decisión de arquitectura (D-2026-08-07)

La fuente de verdad ya existe en `company-os/decisions/decisions.md`:

- **Transport:** RFC/BAPI vía PyRFC (SAP NW RFC SDK), **dependencia opcional**.
- **Downtime cost:** `cost = hours_down * rate_per_hour` (asset/service rate).
- **Posting:** `BAPI_ACC_ACTIVITY_ALLOC_POST` (activity allocation) y `BAPI_ACC_DOCUMENT_POST`; siempre `BAPI_TRANSACTION_COMMIT` tras éxito y `BAPI_TRANSACTION_ROLLBACK` en error.
- **Weighted metrics:** enviadas con pesos por asset/servicio.
- **Mock mode:** provisto para desarrollo/tests; **nunca habilitado en producción**.

### 1.2 Invariantes que se protegen

| Invariante | Cómo se respeta |
|---|---|
| **E2 / ADR-0002** | SAP es una capacidad **externa, no-canónica**; no ocupa slot cognitivo. No entra al Cognitive Lexicon. |
| **R3 (Cognitive Boundary)** | El conector **consumen** artefactos canónicos (Decision/Recommendation) y los traduce a llamadas SAP. **Nunca bypassa** el pipeline ni emite posts propios desde Perception/Reasoning. |
| **R4 (No Action Without Confidence)** | Solo se postea a SAP lo que proviene de una **Decision commiteada** (con confidence calibrada), nunca de un score crudo. |
| **R7 (Architecture Guides Code)** | El código se adapta al canon; el canon no se modifica para acomodar SAP. |
| **P1 / Append-only** | El conector **lee** el store canónico; no escribe en las tablas cognitivas. |
| **Seguridad** | Credenciales SAP solo vía secretos (patrón `docs/secrets-management.md`), nunca hardcodeadas; el mock es inaccesible en producción. |

---

## 2. Fases (orden de implementación cumplible)

> **Dependencia de hardware:** el despliegue estable de los 13 servicios exige un host con más de 8GB. La Fase 5 (validación contra SAP real) además requiere acceso a un sistema SAP (sandbox/quality). Las Fases 1–3 son 100% implementables y verificables en el host actual con mock.

### Fase 1 — Modelo de datos financiero (prerrequisito) ✅ IMPLEMENTADA (working tree, 2026-11-12)

**Qué:** agregar los campos financieros que SAP necesita, al nivel de activo/servicio.

- Migración SQL: tabla separada `asset_finance` (mantiene `servers` pura, no toca las tablas cognitivas). `infrastructure/db-migrations/sap-finance.sql`, idempotente.
- Contrato de datos de salida (DTO): `DowntimeCost`, `WeightedMetric`, `AssetFinanceRecord`/`AssetFinanceCreate` en `libs/integrations/sap/finance.py`.
- Cálculo: `DowntimeCost.cost()` = horas_down * rate_per_hour (D-2026-08-07); helper `downtime_cost`.
- Persistencia: `AssetFinanceStore` (INSERT-only, id determinístico `asset_finance_id`, tenant-scoped).

**Cumplimiento:** el cálculo `cost = hours_down * rate_per_hour` ya está cubierto. Esta fase es gating y quedó cubierta.

**Verificación:** migration idempotente (pasa `test_migrations_idempotency`), 12 tests unit verdes, ruff/mypy limpios. Tests de integración del store listos (`tests/integrations/sap/test_asset_finance_store.py`), skipean sin DB.

### Fase 2 — Abstracción del conector SAP (capa externa no-canónica) ✅ IMPLEMENTADA (working tree, 2026-11-12)

**Qué:** módulo `libs/integrations/sap/sap_gateway.py`, **fuera** del flujo canónico.

- `SapGateway` (ABC): `post_downtime_cost`, `post_weighted_metrics`, `commit`, `rollback`, `available` (síncrono, no-bloqueante).
- `SapResult` tipado (SUCCESS/FAILURE/UNAVAILABLE) + `SapConfig` (sin credenciales; repr seguro).
- `RfcSapGateway` vía PyRFC (dependencia opcional; si no está, `available()`=False y las llamadas devuelven `UNAVAILABLE`, nunca bloquean). BAPI: `BAPI_ACC_ACTIVITY_ALLOC_POST`, `BAPI_ACC_DOCUMENT_POST`, `BAPI_TRANSACTION_COMMIT/ROLLBACK`. Llamadas síncronas de pyrfc en `asyncio.to_thread`.
- `MockSapGateway` (dev/tests) gateado por factory: **denegado en producción** (`MockInProductionError`).
- `build_sap_gateway(config, environment, mock)` — factory fail-closed.

**Verificación:** 17 tests del gateway pasar (result, config sin secretos, factory fail-closed, mock post/commit/rollback, Rfc sin SDK → UNAVAILABLE, mapeo BAPI puro). ruff/mypy/bandit limpios. Suite SAP completa **36/36 PASSED** (con DB). Corrida amplia **642 PASSED 0 fallos**.

### Fase 3 — Bridge desde el flujo canónico ✅ IMPLEMENTADA (working tree, 2026-11-12)

**Qué:** `libs/integrations/sap/sap_bridge.py` — el punto de salida real, respetando R3/R4.

- `SapBridge` implementa el **`ActionExecutor` Protocol** (Phase 11): la Decision registra el compromiso; el bridge ejecuta la acción externa (post a SAP). Alineación limpia con el framework.
- **R3:** el bridge solo **lee** Decisions commiteadas del store canónico y **escribe** hacia afuera; nunca inyecta al pipeline, nunca postea desde Perception/Reasoning.
- **R4:** reacciona solo ante Decisions `committed` (ya gateadas por confidence calibrada); no computa confidence.
- **Fail-closed:** requiere `SapPostContext` explícito (asset + hours) y el rate de `AssetFinanceStore` (Fase 1); si falta, no postea (no inventa datos).
- **Idempotencia (MED-4):** `sap_posting_log` (append-only, trigger de inmutabilidad, UNIQUE por `posting_key` = tenant+decision+asset) evita doble posting en retries.
- Commit/rollback BAPI solo según resultado del posting; log de auditoría por envío.

**Verificación:** 8 tests del bridge (ActionExecutor conformance, fail-closed sin contexto/rate, post+commit, rollback en fallo, idempotencia). Suite SAP completa **46/46 PASSED** (con DB). Corrida amplia **652 PASSED 0 fallos**. ruff/mypy/bandit limpios. Migración `sap-posting-log.sql` idempotente real.

### Fase 4 — Configuración, seguridad y calidad

- Secretos SAP (`RFC_CLIENT`, `RFC_USER`, `RFC_PASSWD`, destination) solo vía `.env` → secretos (fail-closed, patrón existente).
- `bandit -c bandit.yaml` (0 High/Medium), `pip-audit` (pyrfc y deps), `mypy`, `ruff`.
- Tests extendidos: contrato, mock, fallback unavailable, tenant isolation.
- Documentación: `docs/secrets-management.md` actualizado + sección de configuración SAP.

### Fase 5 — Validación E2E contra SAP real y rollout

**Requisito:** acceso a un sistema SAP (sandbox/quality) + hardware suficiente.

- Prueba contra RFC destination real (SM59) con datos de prueba.
- Validación en transacciones SAP (`BAPI_ACC_DOCUMENT_POST` → ver POSTING; `COMMIT/ROLLBACK`).
- Documento de demo/pitch (valor monetario por servidor/servicio) — clave para re-inserción laboral.
- Merge a `main` vía PR (rama protegida, procedimiento ya verificado), commits GPG.

---

## 3. Decisiones de diseño clave

| Decisión | Justificación |
|---|---|
| SAP = capacidad externa no-canónica | D-2026-08-07 / ADR-0002. No toca el flujo cognitivo. |
| Modelo financiero primero | Sin `rate_per_hour` no hay `downtime_cost` (la fórmula de la decisión). Prerrequisito. |
| Conector como gateway intercambiable + mock | Decisión de arquitectura; mock garantiza tests sin infra externa y jamás en producción. |
| Bridge en Action/Report layer | Es la única salida canónica; respeta R3/R4. |
| Fallback no-bloqueante | El pipeline nunca depende de SAP; integración aditiva. |

---

## 4. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| Postear a SAP sin datos financieros | Fase 1 gating; sin `rate_per_hour` no se genera post. |
| Violar R3 (bypass del pipeline) | El bridge solo consume Decisions commiteadas; test bloquea posts desde Perception/Reasoning. |
| Mock activado en producción | Gate de entorno fail-closed + test que verifica que `MockSapGateway` no se instancia en prod. |
| Credenciales SAP expuestas | Secretos vía config existente; nunca hardcode; `bandit`/`pip-audit` en CI. |
| Hardward insuficiente | Fases 1–3 verificables en host actual; Fase 5 requiere hardware/SAP real. |
| Dependencia pyrfc no disponible | Dependencia opcional; gateway reporta `unavailable` y el pipeline sigue. |

---

## 5. Fuera de alcance (por ahora)

- Desarrollo ABAP dentro de SAP (ser "un módulo ABAP"). Se integra por canales estándar (RFC/BAPI).
- Postear decisiones no commiteadas o sin confidence canónica.
- Modificar el esquema cognitivo para "acomodar" SAP.
- Escribir directamente en SAP la tabla `servers` / store canónico (solo lectura).

---

## 6. Criterios de "Done" por fase

- **Fase 1:** migration idempotente aplicada, DTOs testeado, `pytest` verde.
- **Fase 2:** `SapGateway` + `RfcSapGateway` + `MockSapGateway`, `mypy`/`ruff`/`bandit` limpios, tests de contrato verdes.
- **Fase 3:** test E2E con mock: Decision → bridge → POST simulado, rollback en error, no-post sin `rate_per_hour`.
- **Fase 4:** secretos fail-closed, audit de seguridad limpio, docs actualizadas.
- **Fase 5:** validación contra SAP real en sandbox, demo/pitch documentada, merge vía PR con GPG.
