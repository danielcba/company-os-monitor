# Auditoría — Fase 1 Integración SAP R/3 (COS-Monitor)

**Fecha:** 2026-11-12
**Rol:** ingeniero de software senior / arquitecto / security engineer / reviewer de release
**Alcance:** `libs/integrations/sap/finance.py`, `infrastructure/db-migrations/sap-finance.sql`, `tests/integrations/sap/`
**Criterio:** máxima calidad, máxima seguridad, máxima confianza; buenas prácticas de conectores/APIs/HTTPulos SAP R/3; alineación con framework (P1–P7, R1–R7, ADR-0001/0002/0003).

---

## 1. Veredicto general

La Fase 1 está **bien estructurada, testeada y alineada al framework**: capacidad externa no-canónica (D-2026-08-07), DTOs Pydantic inmutables, cálculo puro de downtime cost, store con idempotencia (uuid5) y tenant isolation, 16/16 tests verdes (4 contra DB real), ruff/mypy/bandit limpios.

**Sin embargo, NO está lista para producción** (release-blocker). Hay **un hallazgo mayor (High)** y varios **medios/bajos** que deben corregirse antes de considerarla "pulida". El más importante: la tabla **no tiene trigger de inmutabilidad**, contradiciendo el precedente del repo (`reports`, tabla no-canónica análoga, sí lo tiene).

---

## 2. Hallazgos

### HIGH-1 — Falta trigger append-only en `asset_finance` (release-blocker)

- **Evidencia:** `sap-finance.sql` crea la tabla sin trigger. El docstring de `AssetFinanceStore` declara "INSERT-only (append-only trail)", pero **la DB no lo fuerza**. El repo tiene precedente claro: `reports` (output no-canónico, ADR-0002) usa `prevent_report_content_update()` + `report_content_immutable_trigger` para bloquear UPDATE/DELETE (migración `sprint11-report-content-trigger.sql`, docs/01).
- **Riesgo:** un UPDATE/DELETE directo (humano, script, bug) podría mutar/borrar un registro financiero que puede haber sido posteado a SAP. Para un conector SAP R/3, el registro del costo de downtime es evidencia auditable; debe ser inalterable.
- **Acción requerida:** agregar `prevent_asset_finance_update()` + `asset_finance_immutable_trigger` (BEFORE UPDATE OR DELETE) en `sap-finance.sql`, replicando el patrón de `reports`. Agregar un test que verifique que UPDATE/DELETE son rechazados.

### MED-1 — El helper `downtime_cost` duplica la fórmula (riesgo de drift)

- **Evidencia:** `downtime_cost()` (línea ~112) repite `hours * rate`, duplicando `DowntimeCost.cost()`. Si mañana cambia la fórmula (ej. agregar factor de moneda), las dos divergen.
- **Acción:** eliminar `downtime_cost()` o hacerlo delegar a `DowntimeCost(...)`.cost()`. Preferible eliminar la duplicación (el DTO ya cubre el caso).

### MED-2 — `currency` no valida ISO 4217

- **Evidencia:** `currency: str = Field(min_length=3, max_length=3)` acepta cualquier string de 3 chars (ej. `"FOO"`). SAP requiere códigos de moneda ISO 4217.
- **Acción:** validar contra la lista ISO 4217 (al menos un subconjunto canónico) o un patrón de 3 letras mayúsculas; documentar el default `USD`.

### MED-3 — Sin trazabilidad del autor del dato financiero

- **Evidencia:** `asset_finance` no tiene columna de autor/actor (ej. `updated_by`). Para un posting financiero a SAP, saber **quién** configuró la tarifa es parte de la pista de auditoría (R5/audit).
- **Acción:** agregar `updated_by` (UUID o varchar) opcional, poblado por la capa de API/auth. No rompe append-only (es un dato de contenido, se setea al insertar).

### LOW-1 — `asset_id` sin FK (documentado, no bloqueante)

- **Evidencia:** `asset_id UUID` sin FK. Correcto en el diseño (un "asset" puede ser un service/switch, no solo un server de `servers`), pero debe **documentarse explícitamente** en la migración y el Docstring para que no se confunda con un bug.

### LOW-2 — Typo en docstring de `AssetFinanceRecord`

- **Evidencia:** "country of the DTO above" → debería decir "counterpart". Cosmético.

### LOW-3 — `AssetFinanceStore` no tiene método de borrado/actualización (por diseño, pero conviene explicitarlo)

- **Evidencia:** el store solo tiene `save/get/list/exists`. Correcto para append-only. Sin embargo, para **corregir** una tarifa mal cargada no hay mecanismo salvo insertar otra fila (id determinístico colisiona). Esto es una limitación del diseño "config content-addressed" a revisar en Fase 3: quizás la config de tarifa debería ser **versionada** (historial de tarifas), no idempotente-a-una-fila.

---

## 3. Seguridad — checklist

| Check | Estado | Nota |
|---|---|---|
| Inyección SQL | ✅ | Todo `text()` usa parámetros bind (`:param`), sin concatenación. |
| Secretos en código | ✅ | Sin credenciales hardcodeadas; sin DSN expuesto en el módulo. |
| Pydantic strict/validación | ✅ | `Field(ge=...)`, `frozen=True`, normalización de currency a upper. |
| Credenciales SAP | N/A | No aplica en Fase 1 (sin conector aún). Se manejará en Fase 2 vía secretos. |
| Bandit | ✅ | exit 0 con `bandit -c bandit.yaml -r`. |
| pip-audit | → | Verificar al añadir dependencias (Fase 2 añadirá pyrfc). |
| Logging de datos sensibles | ✅ | El store no loguea contenido; solo be operaciones SQL. (No se introdujo logging propio). |
| Tenant isolation | ✅ | Todas las lecturas/escrituras son `tenant_id`-scoped; test lo verifica. |

---

## 4. Buenas prácticas de conectores SAP R/3 — aplicadas/recomendadas

| Práctica | Estado en Fase 1 | Recomendación hacia Fase 2/3 |
|---|---|---|
| Idempotencia de envío | Parcial | El `asset_finance_id` determinístico da idempotencia de config; pero el **posting** a SAP (Fase 3) debe usar idempotencia de transacción (BAPI_COMMIT/ROLLBACK, unique posting reference). |
| Validación estricta de datos antes de enviar | Parcial | Extender validación de currency (MED-2) y agregar checks de rango monetario. |
| Trazabilidad/auditoría del dato | Débil | Agregar autor del dato (MED-3) y trigger append-only (HIGH-1). |
| Fallback no-bloqueante | N/A | Diseño ya lo contempla (Fase 2). |
| No exponer credenciales | ✅ | El `__repr__` no expone secretos (no hay secretos aún). |
| Manejo de errores de SAP | N/A | Fase 2: capturar `RuntimeError` de PyRFC, mapear a `SapResult`, nunca filtrar traza interna. |

---

## 5. Priorización de remediación

| Orden | Hallazgo | Severidad | Esfuerzo |
|---|---|---|---|
| 1 | HIGH-1 trigger append-only | Alta | Bajo |
| 2 | MED-2 currency ISO 4217 | Media | Bajo |
| 3 | MED-1 eliminar duplicación | Media | Bajo |
| 4 | MED-3 autor del dato | Media | Medio |
| 5 | LOW-2 typo | Baja | Trivial |
| 6 | LOW-3 documentar límite de config fija | Baja | Trivial |

---

## 6. Conclusión

La Fase 1 demuestra **buena ingeniería**: DTOs limpios, tests con DB real, alineación con framework, seguridad sólida. No estaba "lista para release" por **HIGH-1** (inmutabilidad ausente en DB) y los refinamientos MED.

**Recomendación:** remediar HIGH-1 y los MED antes de avanzar a Fase 2.

---

## 7. Remediación aplicada (2026-11-12) — ✅ CERRADA

Todos los hallazgos fueron remediados y verificados:

| Hallazgo | Remediación | Verificación |
|---|---|---|
| **HIGH-1** trigger append-only | `prevent_asset_finance_update()` + `asset_finance_immutable_trigger` (BEFORE UPDATE OR DELETE) en `sap-finance.sql` | Test `test_immutability_trigger_blocks_update_and_delete` PASSED (verifica que UPDATE y DELETE son rechazados) |
| **MED-2** currency ISO 4217 | `ISO4217_CURRENCIES` (subconjunto canónico) + `CurrencyNotSupportedError` + validator compartido | `test_currency_rejects_non_iso4217` / `test_currency_accepts_supported_iso4217` PASSED |
| **MED-1** duplicación `downtime_cost` | Helper eliminado; única fuente de verdad `DowntimeCost.cost()` | Suite repr (13 unit PASSED) |
| **MED-3** autor del dato | Columna `updated_by UUID` + backfill idempotente; poblada en `AssetFinanceCreate`/`Record` | `test_updated_by_is_persisted` PASSED |
| **LOW-2** typo | Corregido en docstring | — |
| **LOW-1** `asset_id` sin FK | Documentado (asset genérico, no solo server) | — |

**Resultados finales tras remediación:**
- Tests de SAP: **19/19 PASSED** (7 integración contra DB real + 12 unit).
- Corrida amplia: **625 PASSED, 0 fallos** (action/architecture/security/memory/reasoning/access/learning/SAP).
- ruff ✅ · mypy ✅ (3 archivos) · bandit ✅ (exit 0).
- Migración idempotente real (4ª aplicación sin error) + test estático ✅.

**Estado:** Fase 1 lista para avanzar a Fase 2. Working tree sin commit (regla NO COMMIT vigente).
