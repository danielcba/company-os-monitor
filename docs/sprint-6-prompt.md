# SPRINT 6 — ANOMALY DETECTOR (Reasoning: capacidad Detect Deviation)

> Persistido desde sesión 2026-08-16. Sesión EVALUADA al inicio.

## Contexto de la sesión previa

- Sprint 1 (COMPLETO): linux-agent (psutil) → Observation Bus (Redis Stream "observations").
- Sprint 2 (COMPLETO): windows-agent, vmware-agent + collector-service (persiste Observations, append-only, dedup, ack tras INSERT).
- Sprint 3 (COMPLETO): Evidence Organizer. 6 reglas puras, QUALITY_WEIGHTS Q1→0.875, Q2→0.625, Q3→0.375, Q4→0.125, tabla `evidence` con trigger.
- Sprint 4 (COMPLETO): Context Activator. 5 MentalModels, 3 purposes, competencia de coherencia (P2), `contexts` con trigger de contenido. 3 contexts reales.
- Sprint 5 (COMPLETO, 128 tests: linux 4, windows 6, vmware 6, collector-service 39, context-service 30, pattern-service 43): Pattern Detector. `libs/procedural_memory/pattern_library.py` (5 PatternDefinition `context_recurrence_*_v1`, MVP `temporal`), `libs/reasoning/pattern.py` (Pattern frozen, `pattern_id()` uuid5 sin detected_at, `PatternStore`), `apps/services/pattern-service/` (detector puro: `strength_measure = min(occurrences / max(min_occurrences,1), 1.0)`, frequency desde intervalo mediano), trigger `pattern_content_immutable_trigger`. El dataset real NO dispara patrones (1 activación por scope → support insuficiente); tests de integración siembran contexts sintéticos.
- Infra corriendo: postgres TimescaleDB 127.0.0.1:5433 (db/user/pass = cosmonitor), redis 127.0.0.1:6379. Schema en `infrastructure/docker/init-sql/01-schema.sql` — YA incluye la tabla `anomalies` (VACÍA): id, tenant_id FK, context_id FK → contexts, pattern_id FK NOT NULL → patterns (SET NULL), deviation_score NUMERIC(8,4), tolerance_threshold NUMERIC(8,4), anomaly_class (point/contextual/collective), detected_at; índice `idx_anomalies_tenant_pattern`. Seed del tenant sandbox en 02-seed.sql.
- Marco cognitivo (SOLO LECTURA, no tocar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`. Producto: `/home/dcordoba/Documents/Default Project/company-os-monitor/`.
- Documentación fuente del Sprint: concepto `Anomaly` del marco: `/home/dcordoba/Documents/Default Project/company/company-os-main/docs/cognitive-lexicon/core-concepts/anomaly.md` (Familia Reasoning, Capacidad Detect Deviation). Regla conceptual: **"An Anomaly is a deviation from an expected Pattern that exceeds a defined tolerance threshold."** Y: "Anomaly detection must be defined relative to patterns, never absolutely." Diseño de producto: `docs/03-predictivo-ia-local.md` (FASE 4: Anomaly Service, clases, tolerancias), tabla `anomalies` en `docs/01-fundacion-arquitectura.md`, roadmap `docs/05-negocio-roadmap-backlog.md` (item #6 Anomaly Detection point).

### Correcciones de auditoría ya aplicadas (NO reintroducir)

- Citaciones canónicas: usar `P1`-`P7`, design rules `R1`-`R7` de `cognitive-architecture.md`, conceptos del marco y ADR-0001/0002. NO inventar números de regla ni reciclar "R8/R9/R10" (colisionaban con las canónicas). Trazabilidad/objetividad/provenance se describen de forma factual, sin número de regla. NO citar paths/specs que no existan en el checkout del marco.
- Puertos/env: cada servicio usa su propio env de puerto (NUNCA reutilizar el mismo nombre): collector `HEALTH_PORT` (8090), context `ACTIVATOR_HEALTH_PORT` (8091), pattern `PATTERN_HEALTH_PORT` (8092). El anomaly-service usará `ANOMALY_HEALTH_PORT` (default 8093).
- `libs/cognitive_core/calibration_model.py` y `cognitive_tool.py` siguen PLANNED (NO cableados). La calibración de Confidence (R4/P5) NO se toca en este sprint. Anomaly NO dispara alertas ni acciones (R3; roadmap: alertas solo cuando Decision service esté operativo).

## Objetivo

Implementar el **Anomaly Detector** (Contract cognitivo: Concept=Anomaly, Familia=Reasoning, Capacidad=Detect Deviation). Input: Active Contexts + Expected Pattern(s) (de `patterns`) + Tolerance thresholds (explícitos). Transform: comparar el Active Context contra el patrón esperado y medir la magnitud de desviación. Output: fila(s) en tabla `anomalies` con `deviation_score` cuantificado, `tolerance_threshold` explícito/auditable y `anomaly_class`. NO avanzar a Hypothesis (Sprint 7), Insight ni Confidence (Sprint 8).

Regla conceptual del marco que debe gobernar el sprint: **"Anomaly detection must be defined relative to patterns, never absolutely. Without an expected pattern, no deviation can be identified."** Una observación "rara" SIN patrón esperado NO es una anomalía — es una Observation. Y los Non-examples del concepto: "A login failure occurred" es una Observation, no una Anomaly; "The network is compromised" es una Hypothesis, no una Anomaly.

## Entorno y comandos (OBLIGATORIO respetar)

- Instalación: `pip install --break-system-packages -e ".[dev]"` (Python 3.14 es externally-managed; `.venv` NO funciona; NO inicializar git).
- NO usar `cd` para ejecutar; usar workdir = raíz del repo. PYTHONPATH por-app (los paquetes `src/` y `tests/` colisionan si se corren juntas):
  `PYTHONPATH="<ruta_app>:<repo_root>" python3 -m pytest <ruta_app/tests> -q`
  con `REPO="/home/dcordoba/Documents/Default Project/company-os-monitor"`.
- Correr TESTS EXISTENTES al final y dejarlos verdes (128 = linux 4 + windows 6 + vmware 6 + collector 39 + context 30 + pattern 43).
- Ruff: reducir violaciones nuevas a cero salvo BLE001 (patrón deliberado `except Exception` del repositorio). line-length 100.
- Tests de integración con Postgres real: limpiar con `SET session_replication_role = replica` (superuser) y borrar explícitamente las filas hijas (trigger de inmutabilidad + FK cascade sobre hypertable bloquean el DELETE directo).

## Proceso obligatorio (policy del marco)

- **Journaling (E6 / Directive 002)**: en cada punto de cambio canónico dejar un entry en `journal/YYYY/YYYY-MM-DD.md` con el formato del marco (`# Journal — YYYY-MM-DD (Sprint 6 — ...)` + secciones `## Theme`, `## Today's Progress`, `## Discoveries`, `## Decisions`, `## Reflection`, `## Quote of the Day`). Listar los archivos que cambiaron.

## Entregables

1. **Modelo + persistencia de Anomaly** (`libs/reasoning/anomaly.py`, nuevo, análogo a `libs/reasoning/pattern.py`):
   - `AnomalyCreate` / `Anomaly` (pydantic `frozen`, P1): campos espejo de la tabla `anomalies` (id, tenant_id, context_id, pattern_id, deviation_score, tolerance_threshold, anomaly_class, detected_at). `build_anomaly(create)`.
   - `anomaly_id(tenant_id, context_id, pattern_id)` determinístico (uuid5, namespace propio) SIN `detected_at` → dedup idempotente (`ON CONFLICT (id) DO NOTHING`).
   - `AnomalyStore`: INSERT append-only, `verify_connection`, `close`, reads `list_anomalies(tenant_id)`, `list_tenant_ids()`. Análogo a `PatternStore`.
   - Agregar a `PatternStore` (`libs/reasoning/pattern.py`) el read que el detector necesita: `list_patterns(tenant_id) -> list[Pattern]` (solo lectura, P1) — ya debe existir de Sprint 5; si existe, verificar firma y no romper la API.
   - Agregar a `ContextStore` (`libs/perception/context.py`) los reads que necesita el detector: `list_active_contexts(tenant_id) -> list[Context]` con `is_active = true` (el Active Context actual por purpose) si no existen; `list_contexts` ya existe (stream completo).

2. **Tolerances Library** (`libs/procedural_memory/tolerance_library.py`, nuevo; procedural memory — umbrales EXPLÍCITOS, auditable, purpose-dependent, declarativos; NO razonamiento):
   - `ToleranceDefinition` (dataclass frozen): `tolerance_id` (versionado), `pattern_type` (MVP: `temporal`), `scope_mental_models`, `scope_purposes`, `anomaly_class` (MVP: `point`; `contextual`/`collective` reservados, NO implementar), `threshold` (valor del tolerance, ej. "deviation > 3σ" o días esperados), `deviation_spec` (cómo se mide la desviación: ej. `days_off_schedule`, `count_exceeding_window`).
   - Catálogo inicial en línea con los 5 PatternDefinitions de Sprint 5: para cada `context_recurrence_*_v1` un tolerance que define qué cuenta como desviación (ej. una activación del scope FUERA del intervalo esperado, o N activaciones dentro de una ventana menor al intervalo mediano esperado).
   - Documentar el esquema de desviación exacto y testearlo con valores conocidos.

3. **Detector** (`apps/services/anomaly-service/src/detector/`; funciones PURAS, sin I/O, testables):
   - `detect(contexts, patterns, tolerances, ...) -> list[CandidateAnomaly]` por tenant: para cada Active Context, comparar contra el patrón esperado del scope (el más reciente en `patterns` para su mental_model/purpose); calcular `deviation_score` según `deviation_spec`; solo emitir Candidate Anomaly si `deviation_score > tolerance_threshold`.
   - `anomaly_class` = `point` en el MVP. `description` NO se persiste (no hay columna) — pero el detector debe producir un rationale factual que quede en métricas/journal.
   - Sin patrón esperado para el scope → NO anomalía (regla conceptual: relative to patterns, never absolutely). Registrar en métricas `total_contexts_without_pattern`.
   - Prohibido causalidad/predicción: la anomalía "señala" la desviación (señal, no conclusión); la explicación es de Hypothesis (Sprint 7).
   - Idempotencia: mismos inputs → mismo `Anomaly` (dedup).

4. **Orquestación en `anomaly-service`** (`apps/services/anomaly-service/` — el directorio existe VACÍO; crear completo siguiendo la anatomía de pattern-service):
   - Misma estructura: `src/main.py`, `src/service.py`, `src/health.py`, `src/detector/`, `tests/`, `pyproject.toml`, `Dockerfile`.
   - R1: `anomaly-service` implementa EXACTAMENTE una capacidad (Detect Deviation). No detecta patrones, no genera hipótesis.
   - Ciclo: por tenant, `ContextStore.list_active_contexts` + `PatternStore.list_patterns` → detector → `AnomalyStore` persistir (dedup idempotente). NUNCA escribe en `contexts`/`patterns`/`evidence`/`observations` (P1). NUNCA lee el observation bus (constraint Reasoning: actúa sobre conocimiento).
   - Métricas en `/metrics` (observabilidad OPERATIVA, sin números de regla): `total_anomalies`, `total_anomaly_duplicates`, `total_contexts_without_pattern`, `total_errors`, `anomalies_by_class`, `anomalies_by_mental_model`.
   - Puerto: `ANOMALY_HEALTH_PORT` (default 8093). NO dispara alertas ni acciones (R3; R4: sin Confidence aún).

5. **Schema**: tabla `anomalies` YA existe en `01-schema.sql` — usarla tal cual; NO regenerar la tabla. Evaluar y JUSTIFICAR la adición de un trigger de inmutabilidad de contenido para `anomalies` (precedente `pattern_content_immutable_trigger`): recomendado `prevent_anomaly_content_update` (contenido inmutable P1, DELETE bloqueado; `is_active` no existe en esta tabla → bloqueo total UPDATE/DELETE, como evidence). Si se adopta, entregar la migración idempotente `infrastructure/db-migrations/sprint6-anomaly-content-trigger.sql` y APLICARLA a la BD existente. Documentar la elección en el journal.

6. **Tests** (unit + integración PG):
   - Una prueba por tolerance: contexto que desvía del patrón esperado (timestamps fuera de intervalo) → detecta anomalía con `deviation_score > threshold`; y Negativo: contexto dentro del patrón esperado → NO anomalía; y contexto SIN patrón esperado → NO anomalía (solo métrica).
   - `deviation_score` con valores conocidos.
   - Anti-conclusión: la anomalía no contiene causalidad (assert sobre el rationale factual, sin "porque"/"fallará").
   - Dedup: re-ejecución sobre los mismos inputs no duplica filas.
   - Trazabilidad: `anomaly.context_id` y `anomaly.pattern_id` referencian filas reales; cadena anomaly → pattern → context → evidence → observations se lee hacia atrás.
   - Integración PG: INSERT anomaly, read-back, `deviation_score`/`tolerance_threshold`/`anomaly_class` persistidos.
   - Regresión: TODAS las suites previas verdes (128 + nuevas).

7. **Docs/env**: actualizar README (sección Sprint 6 + cómo correr el anomaly-service), `.env.example` (agregar `ANOMALY_HEALTH_PORT=8093`, `ANOMALY_CYCLE_SECONDS`, y variables de tolerancias con defaults documentados). Journal de la sesión al cierre. NO modificar `docs/sprint-3-prompt.md`, `docs/sprint-4-prompt.md`, `docs/sprint-5-prompt.md` ni el journal previo.

## Cumplimiento cognitivo a validar al cerrar

- R1: `anomaly-service` implementa EXACTAMENTE una capacidad (Detect Deviation).
- R2: Contract (Input: Active Context + Expected Pattern + Tolerance → Transform: medir desviación → Output: Anomaly + deviation_score + pattern(s) violado(s)) testeado.
- Concepto Anomaly: la anomalía existe SOLO relativa a un patrón esperado (relative to patterns, never absolutely); sin patrón no hay anomalía.
- Non-examples respetados: no se persisten "observaciones raras" como anomalías; no se emite causalidad (eso es Hypothesis, Sprint 7).
- Reasoning Layer constraint: actúa sobre conocimiento (contexts + patterns), nunca sobre el mundo ni observations crudas; no produce efectos sobre `contexts`/`patterns`/`evidence`/`observations` (P1).
- P1: `anomalies` append-only (+ trigger si se decide); re-ejecución no duplica; trazabilidad anomaly → pattern → context → evidence → observations verificada.
- R3: frontera — el anomaly-service no gatilla alertas ni acciones. R4: nada influye acción sin Confidence (aún no hay action layer ni calibración).
- No iniciar Hypothesis (Sprint 7), Insight (Sprint 13) ni clases contextual/collective (reservadas).

## Criterios de aceptación verificables

- pytest verde: 128 previos + nuevos del anomaly-service / anomaly model / tolerance library.
- Corriendo `anomaly-service` contra la PG real (8 observations, 3 evidence, 3 contexts, 0 patterns): sin patterns esperados NO se producen anomalías (documentado; métrica `total_contexts_without_pattern` > 0). Tests de integración siembran patterns + contexts sintéticos que desvían para verificar detección + dedup + trazabilidad.
- `deviation_score` y `tolerance_threshold` numéricos y auditables en filas de `anomalies` cuando se detecta.
- Re-corrida sin duplicados (dedup probado).
- `contexts`, `patterns`, `evidence`, `observations` sin cambios tras el ciclo completo (P1 verificada).
- Métricas disponibles en `:8093/metrics` (anomaly-service con `ANOMALY_HEALTH_PORT=8093`).
