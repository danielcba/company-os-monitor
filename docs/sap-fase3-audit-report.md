# Auditoría — Fase 3 Integración SAP R/3 (COS-Monitor)

**Fecha:** 2026-11-12
**Rol:** ingeniero de software senior / arquitecto / security engineer / reviewer de release
**Alcance:** `libs/integrations/sap/sap_bridge.py`, `infrastructure/db-migrations/sap-posting-log.sql`, `tests/integrations/sap/test_sap_bridge.py`
**Criterio:** máxima calidad, máxima seguridad, máxima confianza; alineación con framework (P1–P7, R1–R7, ADR-0001/0002/0003).

---

## 1. Veredicto general

La Fase 3 está **bien implementada y alineada al framework** (R3/R4 respetados; `ActionExecutor`; log append-only). 8 tests verdes; ruff/mypy/bandit limpios; suite SAP 46/46.

**Sin embargo, hay 2 hallazgos que requieren remediación antes de considerar la fase cerrada:** un **HIGH** (TOCTOU en idempotencia → riesgo de doble posting) y un **MED** (la key de idempotencia ignora el payload, pudiendo descartar correcciones silenciosamente). El resto son notas de diseño/mejora.

---

## 2. Hallazgos

### HIGH-1 — Race condition (TOCTOU) en la idempotencia

- **Evidencia:** `execute()` hace:
  1. `posting_log_store.exists(key)` (línea ~258)
  2. `gateway.post_downtime_cost(cost)` (postea a SAP)
  3. `posting_log_store.record(...)` (registra, línea ~291)
  Entre el paso 1 y el 3, dos invocaciones concurrentes con la misma `posting_key` pasan ambas el `exists() == False` y ambas postean a SAP (doble posting). El `ON CONFLICT DO NOTHING` del log protege la tabla, pero **no** protege el envío a SAP que ya ocurrió.
- **Riesgo:** doble posting financiero a SAP en condiciones de concurrencia (retry concurrente, múltiples workers). Impacto monetario.
- **Acción:** hacer la idempotencia **atómica**: intentar insertar el registro del log (con `ON CONFLICT DO NOTHING`) **antes** de postear; si el insert no se aplica (key ya existe), **no postear** y devolver dedup. El `record()` ya devuelve `bool` (nuevo insert) — usar ese valor como gate.

### MED-1 — La key de idempotencia ignora el payload (horas)

- **Evidencia:** `sap_posting_key(tenant, decision, asset)` no incluye `hours_down`/ventana. Si la misma decision+asset se reintenta con **horas diferentes** (corrección de un dato erróneo), `exists()` devuelve True y el bridge **descarta silenciosamente** el posting corregido → SAP conserva el valor incorrecto.
- **Riesgo:** datos financieros incorrectos persistentes en SAP sin posibilidad de corrección.
- **Acción:** documentar explícitamente la semántica (1 posting por decision+asset) **y** defenderla: ya sea (a) incluir un hash del payload en la key, o (b) exponer un mecanismo de supersesión/corrección. Para el MVP, al menos documentar y lanzar warning cuando un retry llega con payload distinto.

### MED-2 — Sin verificación de que la Decision esté `committed` en el bridge

- **Evidencia:** el docstring afirma "must already be committed", pero `execute()` no consulta el `DecisionStore` para validar el status. Si un orquestador invoca el bridge sobre una decision no commiteada, postearía igual.
- **Contexto:** en Phase 11, la autorización de ejecución (incluida la verificación de "committed") ocurre **antes** del `ActionExecutor`. El bridge asume esa garantía. Aun así, conviene documentarlo y, idealmente, validar el status en el orquestador.
- **Acción:** documentar el contrato de invocación (quién garantiza "committed"); opcionalmente inyectar una callback de validación.

### LOW-1 — `gateway_kind` sin validación

- `gateway_kind` es un string libre; debería restringirse a `{"rfc","mock"}`.

### LOW-2 — `DowntimeCost` sin `reason`/contexto

- El bridge construye el costo sin `reason`; podría incluir el `decision_id`/`commitment` como contexto trazable en SAP.

### LOW-3 — `close()` cierra stores compartidos

- Si `AssetFinanceStore`/`SapPostingLogStore` se comparten, `SapBridge.close()` los cierra. Documentar propiedad.

---

## 3. Alineación con el Framework

| Invariante | Estado | Nota |
|---|---|---|
| R3 (Cognitive Boundary) | ✅ | Solo lee Decisions y escribe hacia fuera. |
| R4 (No Action Without Confidence) | ✅ | Consume Decisions commiteadas; no computa confidence. |
| P1 (append-only) | ✅ | `sap_posting_log` con trigger de inmutabilidad. |
| ADR-0002 | ✅ | ActionExecutor externo, no-canónico. |
| P7/R5 trazabilidad | ✅ | Log con `posting_key`, `decision_id`, `outcome`, `reference`. |

---

## 4. Priorización de remediación

| Orden | Hallazgo | Severidad | Esfuerzo |
|---|---|---|---|
| 1 | HIGH-1 TOCTOU | Alta | Bajo (cambiar orden a insert-primero) |
| 2 | MED-1 key ignora payload | Media | Medio (documentar + warning) |
| 3 | MED-2 verificación committed | Media | Documentación/contrato |
| 4 | LOW-1 gateway_kind | Baja | Trivial |
| 5 | LOW-2 reason en costo | Baja | Trivial |
| 6 | LOW-3 close compartido | Baja | Documentación |

---

## 5. Conclusión

La Fase 3 es **arquitectónicamente sólida y alineada**, pero **HIGH-1 (TOCTOU)** debe remediarse para garantizar idempotencia real en producción, y **MED-1** debe documentarse para evitar pérdida silenciosa de correcciones. Son cambios acotados. Tras remediar, re-correr la suite.

---

## 6. Remediación aplicada (2026-11-12) — ✅ CERRADA

| Hallazgo | Remediación | Verificación |
|---|---|---|
| **HIGH-1** TOCTOU | Idempotencia **atómica**: `SapPostingLogStore.claim()` (INSERT con `ON CONFLICT DO NOTHING`) reserva la key ANTES de postear; `finalize()` registra el resultado real (UPDATE de lifecycle fields). Trigger refinado para permitir UPDATE solo de outcome/reference/message (mismo precedente que `decisions`). | `test_bridge_dedups_when_key_already_claimed` PASSED (verifica que una key ya reclamada NO vuelve a postear) |
| **MED-1** key ignora payload | Documentado + warning `sap_posting_dedup` en retry; `reason` incluye decision_id en `DowntimeCost` | Código verificado |
| **MED-2** verificación committed | Documentado como contrato del orquestador (Phase 11 valida antes del ActionExecutor) | Docs |
| **LOW-1** gateway_kind | `InvalidGatewayKindError` + `_GATEWAY_KINDS` | `test_bridge_rejects_invalid_gateway_kind` PASSED |
| **LOW-2** reason en costo | `DowntimeCost.reason=f"decision:{decision}"` | Código |
| **LOW-3** close compartido | Documentado (propiedad de stores) | Docs |

**Resultados finales tras remediación:**
- Tests de SAP: **48/48 PASSED** (con DB).
- Corrida amplia: **654 PASSED, 0 fallos**.
- ruff ✅ · mypy ✅ (5 archivos) · bandit ✅ (exit 0).
- Migración `sap-posting-log.sql` idempotente real + test estático ✅.

**Estado:** Fase 3 cerrada. Working tree sin commit (regla NO COMMIT vigente).
