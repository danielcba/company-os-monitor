# SPRINT 11 — REPORT GENERATOR (Capacidad Externa No-Canónica — ADR-0002)

> Persistido desde sesión 2026-08-16. Sesión EVALUADA al inicio.

## Contexto de la sesión previa

- Sprints 1-5 (COMPLETOS): Perception completa + Pattern Detector. 128 tests.
- Sprint 6 (COMPLETO esperado): Anomaly Detector. `ANOMALY_HEALTH_PORT=8093`.
- Sprint 7 (COMPLETO esperado): Hypothesis Generator. `HYPOTHESIS_HEALTH_PORT=8094`.
- Sprint 8 (COMPLETO esperado): Confidence Calibration. `CONFIDENCE_HEALTH_PORT=8095`.
- Sprint 9 (COMPLETO esperado): Recommendation. `RECOMMENDATION_HEALTH_PORT=8096`.
- Sprint 10 (COMPLETO esperado): Decision. `libs/action/decision.py`, `libs/procedural_memory/decision_policy.py`, `DECISION_HEALTH_PORT=8097`. Gate cognitivo Q1 alcanzado (primera Decision commitida con outcomes falsificables).
- Infra corriendo: postgres TimescaleDB 127.0.0.1:5433 (db/user/pass = cosmonitor), redis 127.0.0.1:6379. Schema en `infrastructure/docker/init-sql/01-schema.sql` — YA incluye la tabla `reports` (VACÍA): id, tenant_id FK, report_type VARCHAR(50) (executive/technical/compliance), title VARCHAR(500), summary TEXT, content JSONB, ai_generated BOOLEAN DEFAULT TRUE, model_used VARCHAR(100), period_start DATE, period_end DATE, generated_at, file_path VARCHAR(500); índice `idx_reports_tenant_type`.
- Marco cognitivo (SOLO LECTURA, no tocar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`. Producto: `/home/dcordoba/Documents/Default Project/company-os-monitor/`.
- Documentación fuente del Sprint: **ADR-0002** (el flujo canónico es el cerebro; las capacidades externas son no-canónicas y originan sus juicios desde el flujo canónico, NUNCA lo bypassan). Diseño de producto: `docs/04-informes-seguridad.md` (FASE 6: Report Generator — "El Report Service NO genera recomendaciones ni decisiones. Solo formatea Recommendations y Decisions ya cometidas"; templates Executive/Technical/Compliance; tabla `reports`), `docs/01-fundacion-arquitectura.md` (FASE 6: Report Generator como capacidad externa), roadmap `docs/05-negocio-roadmap-backlog.md` (item #11 Report Generator format — "Formatea Decision, no bypass").

### Correcciones de auditoría ya aplicadas (NO reintroducir)

- Citaciones canónicas: usar `P1`-`P7`, design rules `R1`-`R7`, conceptos del marco y ADR-0001/0002. NO inventar números de regla ni reciclar "R8/R9/R10". Trazabilidad/objetividad/provenance factual, sin número de regla. NO citar paths/specs inexistentes.
- Puertos/env: collector `HEALTH_PORT` (8090), context `ACTIVATOR_HEALTH_PORT` (8091), pattern `PATTERN_HEALTH_PORT` (8092), anomaly `ANOMALY_HEALTH_PORT` (8093), hypothesis `HYPOTHESIS_HEALTH_PORT` (8094), confidence `CONFIDENCE_HEALTH_PORT` (8095), recommendation `RECOMMENDATION_HEALTH_PORT` (8096), decision `DECISION_HEALTH_PORT` (8097). El report-service usará `REPORT_HEALTH_PORT` (default 8098). NUNCA reutilizar nombres de env.
- **ADR-0002 es EL gobernante de este sprint**: report-service es NO-canónico. READ-only sobre el flujo canónico (Decision/Recommendation/Context/Confidence). NUNCA escribe en tablas cognitivas (solo en `reports`, su propia tabla de salida). NO produce recomendaciones/decisiones.
- La columna `ai_generated`/`model_used` de `reports` es para LM Studio (futuro, Sprint 18); en el MVP quedará `ai_generated=false`, `model_used=NULL` o documentado — el reporte se genera con templates locales.

## Objetivo

Implementar el **Report Generator** (capacidad externa no-canónica, ADR-0002). Input: Decision(s) + Recommendation(s) + Active Context + Confidence Scores + Tenant Context. Transform: renderizar en el formato solicitado (PDF ejecutivo, PDF técnico, JSON, HTML dashboard). Output: documento formateado (archivo/stream/API response) + fila en tabla `reports`. NO genera juicios: formatea lo que el flujo canónico YA decidió.

Regla conceptual que gobierna el sprint (ADR-0002): **"El flujo canónico (Perception → Reasoning → Confidence → Action) es el cerebro. Todo lo demás es no-canónico y debe originar sus juicios desde el flujo cognitivo central."** El reporte es un FORMATO, no una fuente de verdad. Los datos que muestra (Decision.commitment, expected_outcomes, confidence, traza) vienen EXCLUSIVAMENTE de las tablas del pipeline.

## Entorno y comandos (OBLIGATORIO respetar)

- Instalación: `pip install --break-system-packages -e ".[dev]"` (Python 3.14 es externally-managed; `.venv` NO funciona; NO inicializar git).
- NO usar `cd` para ejecutar; usar workdir = raíz del repo. PYTHONPATH por-app:
  `PYTHONPATH="<ruta_app>:<repo_root>" python3 -m pytest <ruta_app/tests> -q`
  con `REPO="/home/dcordoba/Documents/Default Project/company-os-monitor"`.
- Correr TESTS EXISTENTES al final y dejarlos verdes (128 + Sprints 6-10).
- Ruff: reducir violaciones nuevas a cero salvo BLE001. line-length 100.
- Tests de integración con Postgres real: limpiar con `SET session_replication_role = replica` (superuser) y borrar explícitamente las filas hijas.
- `weasyprint` (generación PDF) ya está en `pyproject.toml` raíz — verificar instalación; si no está disponible en la app, declararla en el `pyproject.toml` del report-service.

## Proceso obligatorio (policy del marco)

- **Journaling (E6 / Directive 002)**: entry por sesión en `journal/YYYY/YYYY-MM-DD.md` con el formato del marco (`# Journal — YYYY-MM-DD (Sprint 11 — ...)` + secciones `## Theme`, `## Today's Progress`, `## Discoveries`, `## Decisions`, `## Reflection`, `## Quote of the Day`). Listar archivos cambiados.

## Entregables

1. **Modelo + persistencia de Report** (`libs/action/report.py`, nuevo; o `libs/learning/` si se prefiere — JUSTIFICAR la familia):
   - `ReportCreate` / `Report` (pydantic `frozen`): campos espejo de la tabla `reports` (id, tenant_id, report_type, title, summary, content JSONB, ai_generated, model_used, period_start, period_end, generated_at, file_path). `build_report(create)`.
   - `report_id(tenant_id, report_type, period_start, period_end)` determinístico (uuid5, namespace propio) → dedup idempotente (re-generar el mismo reporte del mismo período no duplica).
   - `ReportStore`: INSERT, `verify_connection`, `close`, reads `list_reports(tenant_id, report_type)`. NOTA: `reports` es la tabla de salida del servicio (no-canónica) — su trigger de inmutabilidad es decisión de diseño (ver Schema).

2. **Renderers** (`apps/services/report-service/src/renderers/`; funciones PURAS, sin I/O, testables):
   - `render_executive(decision, context, confidence, tenant) -> dict` — resumen ejecutivo 1 página: Top N decisiones críticas con riesgo/confianza/costo/ROI, futuros riesgos (hypotheses con confidence > umbral), decisiones pendientes de autoridad. Campos según `docs/04` (Executive Summary template).
   - `render_technical(decision, ...) -> dict` — traza cognitiva completa: SECTION 1 Cognitive Trace, SECTION 2 Evidence Chain, SECTION 3 Reasoning Chain (pattern/anomaly/hypotheses con status), SECTION 4 Confidence Calibration (S/C/ECE/C_final/α), SECTION 5 Recommendation & Alternatives, SECTION 6 Decision & Expected Outcomes, SECTION 7 Learning Loop (post-execution, puede ir vacío).
   - `render_json(...) -> dict` — los mismos datos en estructura JSON pura (para API/dashboard).
   - Formatters: `to_pdf(html)` (weasyprint), `to_json(obj)`, `to_html(obj)`. El HTML se construye con jinja2 (plantillas locales en `src/templates/`).
   - Los renderers reciben los datos YA leídos de las tablas cognitivas; NO acceden a la BD (single responsibility: el orquestador lee, el renderer formatea).

3. **Orquestación en `report-service`** (`apps/services/report-service/` — el directorio existe VACÍO; crear completo):
   - Estructura: `src/main.py`, `src/service.py`, `src/health.py`, `src/renderers/`, `src/templates/`, `tests/`, `pyproject.toml`, `Dockerfile`.
   - R1 (externo): report-service NO implementa una capacidad cognitiva (es no-canónico, ADR-0002). Su único "contract" es: READ del flujo → format → salida.
   - Ciclo (on-demand o por schedule `REPORT_CYCLE_SECONDS`): por tenant, lee `DecisionStore.list_decisions` + `RecommendationStore.list_recommendations` + `ContextStore.list_contexts` + `ConfidenceStore.list_confidence` (TODOS solo lectura, P1) → renderer según report_type → persistir fila en `reports` + escribir archivo (file_path).
   - NUNCA escribe en `decisions`/`recommendations`/`contexts`/`confidence_scores`/`evidence`/`observations` (P1). NUNCA lee el observation bus.
   - Métricas en `/metrics` (sin números de regla): `total_reports`, `total_report_duplicates`, `total_errors`, `reports_by_type`, `render_duration_seconds`.
   - Puerto: `REPORT_HEALTH_PORT` (default 8098). Endpoints: `POST /api/v1/reports/generate?type=executive|technical|json` y `GET /api/v1/reports` (listado de `reports`).

4. **Schema**: tabla `reports` YA existe — usarla tal cual; NO regenerar. Evaluar trigger de inmutabilidad (los reportes son salidas, no entrada cognitiva: ¿deben ser append-only e inmutables? JUSTIFICAR. Precedente de P1 se aplica a la cadena canónica; para salidas no-canónicas se puede optar por append-only sin trigger o con trigger según auditoría/compliance). Si se adopta, migración idempotente `infrastructure/db-migrations/sprint11-report-content-trigger.sql` + aplicar a la BD. Documentar en journal.

5. **Tests** (unit + integración PG):
   - Por renderer: entrada (decision+context+confidence+tenant) conocida → salida con los campos esperados del template (Executive: top decisiones; Technical: secciones 1-7; JSON: estructura pura). Renderer con input vacío → salida vacía/0 decisiones sin error.
   - ADR-0002 (anti-bypass): el reporte de una decisión contiene EXACTAMENTE los datos de las tablas (assert: el contenido del reporte coincide con el commitment/expected_outcomes/confidence persistidos; no inventa juicios). Test que el report-service NUNCA escribe en tablas cognitivas (assert de efectos: solo INSERT en reports).
   - Dedup: re-generar el mismo reporte del mismo período no duplica filas.
   - Formatters: to_pdf genera bytes no vacíos; to_json válido; to_html contiene los datos.
   - Integración PG: INSERT report, read-back, `report_type`/`content`/`file_path` persistidos.
   - Regresión: TODAS las suites previas verdes (128 + Sprints 6-10 + nuevas).

6. **Docs/env**: README (sección Sprint 11 + cómo correr + nota ADR-0002), `.env.example` (agregar `REPORT_HEALTH_PORT=8098`, `REPORT_CYCLE_SECONDS`, `REPORT_OUTPUT_DIR` con default). Journal al cierre. NO modificar prompts previos ni journal previo.

## Cumplimiento cognitivo a validar al cerrar

- ADR-0002: report-service es NO-canónico — solo formatea, nunca genera juicios; READ-only sobre el flujo; NUNCA bypassa.
- ADR-0002 boundary: Report Generator tiene acceso READ a Decision/Recommendation/Context/Confidence; no escribe en ellas (P1).
- R6: las explicaciones son salidas de primera clase — el Technical Report expone la traza cognitiva completa (rationale, confidence, alternatives, expected outcomes).
- P6: el reporte muestra Recommendations y Decisions ya existentes; no crea ni recomienda.
- P1: las tablas cognitivas no cambian tras el ciclo del report-service (verificado por test).
- Gate: reportes Executive/Technical/JSON generados sobre decisiones reales del flujo canónico.
- No avanzar a Auth/RBAC (Sprint 12), Insight (Sprint 13) ni LM Studio (Sprint 18).

## Criterios de aceptación verificables

- pytest verde: 128 + Sprints 6-10 + nuevos del report-service / renderers.
- Corriendo `report-service` contra la PG real (con decisiones commitidas): `POST /api/v1/reports/generate?type=executive` y `type=technical` y `type=json` devuelven documentos con los datos de las decisiones reales; filas en `reports` con `content` y `file_path`.
- Reporte con decisiones vacías → documento sin errores con "0 decisiones".
- Re-generación del mismo período sin duplicados (dedup probado).
- `decisions`, `recommendations`, `confidence_scores`, `contexts`, `evidence`, `observations` sin cambios tras el ciclo (P1 verificada).
- Métricas en `:8098/metrics` (report-service con `REPORT_HEALTH_PORT=8098`).
