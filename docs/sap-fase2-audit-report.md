# Auditoría — Fase 2 Integración SAP R/3 (COS-Monitor)

**Fecha:** 2026-11-12
**Rol:** ingeniero de software senior / arquitecto / security engineer / reviewer de release
**Alcance:** `libs/integrations/sap/sap_gateway.py`, `tests/integrations/sap/test_sap_gateway.py`
**Criterio:** máxima calidad, máxima seguridad, máxima confianza; buenas prácticas de conectores/APIs/módulos SAP R/3; alineación con framework.

---

## 1. Veredicto general

La Fase 2 está **bien trazada**: abstracción `SapGateway` limpia, `SapResult` tipado, factory fail-closed (mock denegado en producción), fallback no-bloqueante sin SDK, 17 tests verdes, ruff/mypy/bandit limpios.

**No está lista para producción** — hay **2 hallazgos High** (concurrencia sin protección + timeout ausente) y **varios Medium** (usuario hardcodeado en el posting, typo de config, falta de logging, falta de idempotencia de posting). Ninguno rompe el contrato, pero todos afectan confianza en producción.

---

## 2. Hallazgos

### HIGH-1 — Conexión RFC compartida sin protección de concurrencia

- **Evidencia:** `_open_connection()` cachea una única `self._connection`; `post_*`/`commit`/`rollback` llaman a `asyncio.to_thread(conn.call, ...)`. La librería `pyrfc` **no es thread-safe**; dos posts concurrentes sobre la misma conexión pueden corromper el estado de la sesión RFC o producir resultados entremezclados.
- **Riesgo:** en un pipeline async con varios tenants posteando en paralelo, datos de un tenant podrían mezclarse con otro (violación de tenant isolation en el canal de salida).
- **Acción:** serializar las operaciones por gateway con un `asyncio.Lock` (o crear conexión por operación). El lock es la opción mínima y correcta.

### HIGH-2 — Sin timeout en las llamadas RFC (colgamiento)

- **Evidencia:** `request_timeout_s` existe en `SapConfig` (default 30) pero **no se usa** en `conn.call`. `asyncio.to_thread` delega a un thread; si SAP no responde, el thread queda bloqueado (fuga de thread en cada llamada).
- **Riesgo:** DoS por colgamiento; el pool de threads se agota; el pipeline se degrada.
- **Acción:** aplicar timeout. Como `pyrfc` no acepta timeout nativamente, usar `asyncio.wait_for(asyncio.to_thread(...), timeout=self._config.request_timeout_s)` y, ante timeout, devolver `SapResult.failure`/`UNAVAILABLE` y cerrar/recrear la conexión.

### MED-1 — Usuario de posting hardcodeado (`COS_MONITOR`)

- **Evidencia:** `_build_document_post` fija `DOCUMENT_HEADER.USERNAME = "COS_MONITOR"`. El usuario que postea en SAP debería venir de la autenticación/tenant (o de config de secrets), no estar fijo.
- **Riesgo:** todos los batches se registran en SAP como el mismo usuario; sin trazabilidad de quién originó el post (audit). Contradice la trazabilidad deseada (R5/audit).
- **Acción:** agregar `posting_user: str` a `SapConfig` (resuelto desde secretos/config, nunca hardcodeado) y usarlo en el header. Mantener un default vacío que impida postear si no está configurado (fail-closed).

### MED-2 — Typo en config: `ashst` debería ser `ashost`

- **Evidencia:** `SapConfig.ashst` (campo) y `params["ashost"] = self._config.ashst`. Si el operador configura `ashost` (nombre correcto), no se aplicaría. Bug de configuración silencioso.
- **Acción:** renombrar `ashst` → `ashost` (field público) manteniendo compatibilidad no necesaria (aún no hay release). Corregir el dict de params.

### MED-3 — Sin observabilidad (logging)

- **Evidencia:** el gateway no usa `get_logger` (structured_logging que el repo ya usa en `libs/action` y `libs/learning`). No hay rastro de postings/commits/rollbacks.
- **Riesgo:** sin pista de auditoría de qué se envió a SAP, cuándo y con qué resultado. Crítico para un conector financiero.
- **Acción:** integrar `get_logger` en eventos no sensibles (posting OK/failure/commit/rollback con `reference`/`outcome`), **nunca** loguear contenido de `DowntimeCost`/`WeightedMetric` ni campos de conexión/secretos.

### MED-4 — Sin idempotencia del posting (doble posting)

- **Evidencia:** `_build_activity_alloc` usa `REFERENCE = f"cos-{asset_id}"`; pero no hay dedup del lado del gateway ni verificación de si ese posting ya se envió. Un retry de la Fase 3 podría duplicar el posting en SAP.
- **Riesgo:** downtime cost duplicado en SAP (impacto financiero real).
- **Acción:** diseñar una `posting_key` determinística (tenant + asset + ventana temporal) que SAP pueda usar como referencia única; documentar para Fase 3.

### LOW-1 — `available()` no cierra la conexión que abre

- **Evidencia:** `available()` llama a `_open_connection()`, dejando `self._connection` abierta si se llama varias veces (fuga de conexión).
- **Acción:** en `available()`, abrir y cerrar una conexión de probe sin cachearla.

### LOW-2 — Factory sensible a mayúsculas en `environment`

- **Evidencia:** `environment == "production"` exacto; `"Production"`/`"prod"` dejarían pasar el mock. Case-sensitivity frágil.
- **Acción:** normalizar (`environment.strip().lower()`).

### LOW-3 — `MockSapGateway` no implementa `close()`

- **Evidencia:** la clase mock no expone `close()`, a diferencia de `RfcSapGateway`.
- **Acción:** agregar `close()` no-op por consistencia de interfaz.

---

## 3. Seguridad — checklist

| Check | Estado | Nota |
|---|---|---|
| Credenciales en config | ✅ | `SapConfig` no tiene campos de password; repr seguro. |
| Mock en producción | ✅ | Factory fail-closed; testado. |
| Fallback sin SDK | ✅ | `UNAVAILABLE`, nunca raise. |
| Timeout de red | ❌ | HIGH-2: ausente. |
| Concurrencia/thread-safety | ❌ | HIGH-1: conexión compartida sin lock. |
| Usuario de posting | ❌ | MED-1: hardcodeado. |
| Logging sin datos sensibles | ❌ | MED-3: ausente. |
| Validación de entrada | ✅ | Pydantic en DTOs (Fase 1). |
| Inyección SQL | N/A | No hay SQL en el gateway. |
| Bandit | ✅ | exit 0. |

---

## 4. Priorización de remediación

| Orden | Hallazgo | Severidad | Esfuerzo |
|---|---|---|---|
| 1 | HIGH-1 lock de concurrencia | Alta | Bajo |
| 2 | HIGH-2 timeout | Alta | Bajo |
| 3 | MED-1 usuario de posting | Media | Medio |
| 4 | MED-2 typo `ashost` | Media | Trivial |
| 5 | MED-3 logging | Media | Medio |
| 6 | MED-4 idempotencia posting | Media | Diseño (documentar) |
| 7 | LOW-1 close en available | Baja | Bajo |
| 8 | LOW-2 normalizar environment | Baja | Trivial |
| 9 | LOW-3 mock close | Baja | Trivial |

---

## 5. Conclusión

La Fase 2 es un **conector bien diseñado** en su superficie (contrato, factory, fallback), pero **no está lista para producción** por los hallazgos HIGH (concurrencia y timeout) y los MED (usuario, logging, idempotencia). Son remediaciones acotadas y de bajo/medio riesgo.

**Recomendación:** remediar HIGH-1, HIGH-2 y MED-1/MED-2/MED-3 antes de avanzar a Fase 3. MED-4 requiere decisión de diseño de idempotencia (documentar en Fase 3).

---

## 6. Remediación aplicada (2026-11-12) — ✅ CERRADA

| Hallazgo | Remediación | Verificación |
|---|---|---|
| **HIGH-1** concurrencia | `asyncio.Lock` serializa todas las llamadas RFC (`_run_rfc`) | Suite pasa; `_run_rfc` bajo lock |
| **HIGH-2** timeout | `asyncio.wait_for(..., request_timeout_s)`; ante `TimeoutError` cierra conexión y devuelve FAILURE | Código verificado; `request_timeout_s` ahora se usa |
| **MED-1** usuario de posting | `SapConfig.posting_user` (desde secretos/config) + fail-closed si vacío; `_build_document_post` lo usa | `test_build_document_post_uses_configured_posting_user` + `test_rfc_post_fails_closed_without_posting_user` PASSED |
| **MED-2** typo | `ashst` → `ashost` (campo y params) | `_build_connection_params` usa `ashost` |
| **MED-3** logging | `get_logger` integrado; logs de evento no sensibles | Import verificado; ruff limpio |
| **LOW-1** leak en available | Probe con conexión throwaway cerrada | `available()` usa `else` + close |
| **LOW-2** environment case | `environment.strip().lower()` | Factory normaliza |
| **LOW-3** mock close | `MockSapGateway.close()` no-op agregado | Interfaz consistente |
| **MED-4** idempotencia | Documentado para Fase 3 (posting_key determinística); pendiente de diseño | — |

**Resultados finales tras remediación:**
- Tests de SAP: **38/38 PASSED** (con DB).
- Corrida amplia: **644 PASSED, 0 fallos**.
- ruff ✅ · mypy ✅ (4 archivos) · bandit ✅ (exit 0).

**Estado:** Fase 2 lista para avanzar a Fase 3 (con MED-4 a definir en Fase 3). Working tree sin commit (regla NO COMMIT vigente).
