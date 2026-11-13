# Auditoría — Fase 4 Integración SAP R/3 (COS-Monitor)

**Fecha:** 2026-11-12
**Rol:** ingeniero de software senior / arquitecto / security engineer / reviewer de release
**Alcance:** `libs/integrations/sap/sap_orchestrator.py`, cambios en `apps/gateway/api-gateway/src/{service,health,main}.py`, `tests/integrations/sap/test_sap_orchestrator.py`
**Criterio:** máxima calidad, máxima seguridad, máxima confianza; buenas prácticas de orquestadores/endpoints/conectores SAP; alineación FULL con el framework.

---

## 1. Veredicto general

La Fase 4 está **bien diseñada y alineada al framework** (R3/R4/R5 respetados; orquestador limpio; endpoint autorizado). 56/56 tests verdes; corrida amplia 662 PASSED; ruff/mypy/bandit limpios.

**No está lista para merge:** hay **1 hallazgo HIGH (bug de runtime)** — `token.subject` no existe en `TokenPayload` → `AttributeError` al ejecutar `POST .../sap/postings`. Hay además **1 MED** (ValidationError de Pydantic devuelve 500, debería ser 422) y notas de diseño.

---

## 2. Hallazgos

### HIGH-1 — `token.subject` no existe en `TokenPayload` (bug de runtime)

- **Evidencia:** `service.post_sap_postings()` usa `token.subject`. Pero `TokenPayload` (libs/access/security.py:149) **no tiene** `subject`; tiene `user_id`, `tenant_id`, `email`, `role`, etc. En runtime, `token.subject` lanza `AttributeError`, que el handler captura como 500.
- **Riesgo:** el endpoint `POST .../sap/postings` **falla siempre** con 500 al ejecutarse (no solo en condiciones de borde).
- **Acción:** usar `token.user_id` (la identidad del usuario autenticado) como `authority_id`. Es el campo correcto y disponible.

### MED-1 — ValidationError de Pydantic se devuelve como 500 (debería ser 422)

- **Evidencia:** `service.post_sap_postings()` hace `SapPostRequestBatch.model_validate(body)`. Si el body es inválido (falta `requests`, `hours_down` negativo, UUID malo), Pydantic lanza `ValidationError`, que el handler captura con `except Exception` → 500.
- **Acción:** capturar `pydantic.ValidationError` en el handler y devolver 422 con los detalles. Es el código HTTP correcto para payload inválido.

### MED-2 — El autorizador no valida límite de tamaño del batch

- **Evidencia:** `SapPostRequestBatch` acepta cualquier `requests`. No hay cota superior; un cliente podría mandar miles de requests en un solo POST (abuso/DoS del orquestador).
- **Acción:** agregar límite (ej. max 100 requests por batch) con validación Pydantic.

### LOW-1 — `SapOrchestratorConfig` está sin usar

- **Evidencia:** la dataclass `SapOrchestratorConfig` se define pero nunca se instancia/usa.
- **Acción:** eliminarla o usarla en el `SapOrchestrator.__init__` (configuración).

### LOW-2 — `list_postings` delega todo al `list_for_tenant`

- Correcto. Nota menor: el docstring menciona "dedicated SELECT" que ya existe. OK.

---

## 3. Alineación con el Framework

| Invariante | Estado | Nota |
|---|---|---|
| R3 (Cognitive Boundary) | ✅ | Solo lee Decisions y escribe hacia fuera. |
| R4 (No Action Without Confidence) | ✅ | Solo procesa `committed`. |
| R5 (authority) | ✅ | `require_authorized(action="execute"|"read")` en el service. |
| ADR-0002 | ✅ | Capacidad externa no-canónica. |
| P1 | ✅ | Sin mutación de tablas cognitivas; log append-only. |
| Fail-closed | ✅ | Sin contexto/tarifa → no postea. |

---

## 4. Priorización de remediación

| Orden | Hallazgo | Severidad | Esfuerzo |
|---|---|---|---|
| 1 | HIGH-1 `token.subject` → `token.user_id` | Alta | Trivial |
| 2 | MED-1 ValidationError → 422 | Media | Bajo |
| 3 | MED-2 límite de batch | Media | Bajo |
| 4 | LOW-1 quitar `SapOrchestratorConfig` sin uso | Baja | Trivial |

---

## 5. Conclusión

La Fase 4 es **sólida y alineada**, pero **HIGH-1 es bloqueante**: el endpoint fallaría en runtime. Requiere remediación antes del commit/PR. Tras remediar, re-correr la suite.

---

## 6. Remediación aplicada (2026-11-12) — ✅ CERRADA

| Hallazgo | Remediación | Verificación |
|---|---|---|
| **HIGH-1** `token.subject` | Reemplazado por `token.user_id` (identidad autenticada, campo real de `TokenPayload`) | Suite pasa; código corregido |
| **MED-1** ValidationError→500 | Handler captura `pydantic.ValidationError` y responde **422** con detalles | `except ValidationError` en handler |
| **MED-2** sin límite de batch | `SapPostRequestBatch` limita a `_MAX_BATCH_SIZE=100` requests | field_validator `_bound_size` |
| **LOW-1** `SapOrchestratorConfig` sin uso | Eliminado (clase y export) | ruff limpio |

**Resultados finales tras remediación:**
- Suite SAP+gateway: **56/56 PASSED** (con DB).
- Corrida amplia: **662 PASSED, 0 fallos**.
- ruff ✅ · mypy ✅ (6 archivos) · bandit ✅ (exit 0).

**Estado:** Fase 4 lista para commit/PR. Working tree sin commit (regla NO COMMIT vigente).
