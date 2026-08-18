# SPRINT 5 — PATTERN DETECTOR (Reasoning: capacidad Generalize)

> Persistido desde sesión 2026-08-14. Sesión EVALUADA al inicio.

## Contexto de la sesión previa

- Sprint 1 (COMPLETO): linux-agent (psutil) → Observation Bus (Redis Stream "observations"). `observation_bus.py` con `Observation` (pydantic frozen, P1), `publish`/`consume`/`ack`.
- Sprint 2 (COMPLETO): multi-agente (windows-agent, vmware-agent) + collector-service que consume Redis Streams y persiste Observations en Postgres (append-only, dedup idempotente, ack tras INSERT). E2E verificado.
- Sprint 3 (COMPLETO): Evidence Organizer. `libs/perception/evidence.py`, reglas puras por dominio en `collector-service/src/organizer/`, QUALITY_WEIGHTS Q1→0.875, Q2→0.625, Q3→0.375, Q4→0.125 asignados en la creación, tabla `evidence` con trigger de inmutabilidad. 8 observations y 3 evidence reales en la PG.
- Sprint 4 (COMPLETO, 85/85 tests: linux 4, windows 6, vmware 6, collector-service 39, context-service 30): Context Activator. `libs/perception/context.py` (MentalModel declarativos — 5 modelos, 3 purposes con ≥2 modelos para confrontación P2; `Context` frozen; `context_id()` uuid5 determinístico; `ContextStore` append-only; trigger de contenido en `contexts`; `is_active` como ciclo de vida). 3 contexts reales en PG (capacity_risk ×2, service_failure ×1), re-corrida sin duplicados.
- Infra corriendo: postgres TimescaleDB 127.0.0.1:5433 (db/user/pass = cosmonitor), redis 127.0.0.1:6379. Schema en `infrastructure/docker/init-sql/01-schema.sql` — YA incluye la tabla `patterns` (VACÍA): id, tenant_id FK, context_id FK → contexts, pattern_type (temporal/correlation/sequential/threshold), description, strength_measure NUMERIC(5,4), frequency VARCHAR, detected_at, is_active; índice `idx_patterns_tenant_type(tenant_id, pattern_type, detected_at DESC)`. Seed del tenant sandbox en 02-seed.sql.
- Marco cognitivo (SOLO LECTURA, no tocar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`. Producto: `/home/dcordoba/Documents/Default Project/company-os-monitor/`.
- Documentación fuente del Sprint: concepto `Pattern` del marco: `/home/dcordoba/Documents/Default Project/company/company-os-main/docs/cognitive-lexicon/core-concepts/pattern.md` (Familia Reasoning, Capacidad Generalize), el principio `P4 — Regularity and Law`, el pipeline/constraints en `cognitive-architecture.md` (Reasoning Layer: "reasoning acts on knowledge, never directly on the world"). Diseño de producto: `docs/03-predictivo-ia-local.md` (FASE 4: Pattern Service + Pattern Library), tabla `patterns` en `docs/01-fundacion-arquitectura.md`, roadmap `docs/05-negocio-roadmap-backlog.md` (item #5 Pattern Detection temporal, "primer paso Reasoning: detecta regularidad").

### Correcciones de auditoría ya aplicadas (NO reintroducir)

Sesión de auditoría (2026-08-14) corrigió incongruencias de documentación. Mantener las convenciones:
- Citaciones canónicas: usar `P1`/`P2`/`P3`/`P4`, las design rules `R1`-`R7` de `cognitive-architecture.md`, y los conceptos del marco. NO inventar números de reglas ni reciclar "R8/R9/R10" con significados propios (colisionaban con las canónicas; quedaron reetiquetadas: objetividad→P2, asignación-en-creación→(P1), trazabilidad→descriptiva sin número de regla).
- Puertos/env: el collector usa `HEALTH_PORT` (default 8090); el context-service usa `ACTIVATOR_HEALTH_PORT` (default 8091). El pattern-service usará `PATTERN_HEALTH_PORT` (default 8092). NUNCA reutilizar el mismo nombre de env en dos servicios del `.env.example`.
- `libs/cognitive_core/calibration_model.py` y `cognitive_tool.py` están marcados PLANNED Phase 5+ (NO cableados). La calibración de Confidence (R4) NO se toca en este sprint.

## Objetivo

Iniciar la Reasoning Layer implementando el **Pattern Detector** (Contract cognitivo: Concept=Pattern, Familia=Reasoning, Capacidad=Generalize). Input: Active Contexts ya persistidos en Postgres (el stream de activaciones en `contexts`, append-only) + Pattern Library (patrones conocidos declarativos). Transform: detectar regularidades recurrentes dentro del flujo de contextos y compararlas contra el library. Output: fila(s) en tabla `patterns` (Candidate Pattern(s)) con `description` únicamente factual, `strength_measure` (support/frequency) y `frequency`. NO avanzar a Anomaly, Hypothesis, Insight ni Confidence (sprints siguientes).

Regla conceptual del marco que debe gobernar el sprint: **"Company OS does not invent patterns. It detects regularities that are present in the available context and that satisfy a sufficient degree of support."** El sistema no "inventa" regularidades: mide apoyo suficiente sobre el stream de contextos y lo reporta como patrón. Y el constraint de la Reasoning Layer: **el razonamiento actúa sobre conocimiento, nunca directamente sobre el mundo** — el detector lee contextos (conocimiento), nunca el observation bus ni agentes.

## Entorno y comandos (OBLIGATORIO respetar)

- Instalación: `pip install --break-system-packages -e ".[dev]"` (Python 3.14 es externally-managed; `.venv` NO funciona; NO inicializar git).
- NO usar `cd` para ejecutar; usar workdir = raíz del repo. PYTHONPATH por-app (los paquetes `src/` y `tests/` colisionan si se corren juntas):
  `PYTHONPATH="<ruta_app>:<repo_root>" python3 -m pytest <ruta_app/tests> -q`
  con `REPO="/home/dcordoba/Documents/Default Project/company-os-monitor"`.
  Ejemplo: `PYTHONPATH="apps/services/pattern-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m pytest apps/services/pattern-service/tests -q`
- Correr TESTS EXISTENTES al final y dejarlos verdes (linux-agent 4, windows-agent 6, vmware-agent 6, collector-service 39, context-service 30).
- Ruff: reducir violaciones nuevas a cero salvo BLE001 (patrón deliberado `except Exception` del repositorio). line-length 100.
- auth en tests de integración con Postgres real: para limpiar datos usar `SET session_replication_role = replica` (superuser) y borrar explícitamente las filas hijas (el trigger de inmutabilidad y la FK cascade sobre hypertable bloquean el DELETE directo).

## Proceso obligatorio (policy del marco)

- **Journaling (E6 / Directive 002)**: en cada punto de cambio canónico (cada sesión que crea/modifica/borra archivos) dejar un entry en `journal/YYYY/YYYY-MM-DD.md` siguiendo el formato del marco: `# Journal — YYYY-MM-DD (Sprint 5 — ...)` + secciones `## Theme`, `## Today's Progress`, `## Discoveries`, `## Decisions`, `## Reflection`, `## Quote of the Day`. Listar los archivos que cambiaron.

## Entregables

1. **Pattern Library** (`libs/procedural_memory/pattern_library.py`, nuevo; procedural memory — patrones conocidos, definiciones DECLARATIVAS, NO razonamiento):
   - `PatternDefinition` (dataclass frozen): `pattern_id` (versionado, ej. `context_recurrence_capacity_risk_v1`), `pattern_type` (MVP: `temporal`; dejar reservados `correlation`/`sequential`/`threshold`, NO implementar), `domain`, `scope_mental_models: frozenset[str]`, `scope_purposes: frozenset[str]` (vacío = todos), `min_occurrences: int`, `strength_threshold: float` (0..1), `frequency_label: str` (daily/weekly/hourly/event-driven), `description_template: str` (template FACTUAL con placeholders de los hechos medidos).
   - Catálogo inicial mínimo en línea con los 5 mental models / 3 purposes de Sprint 4 (p.ej. `context_recurrence_capacity_risk_v1`, `context_recurrence_service_failure_v1`, `context_recurrence_resource_pressure_v1`, ...). Cada entrada declara qué scope de contextos cubre y el apoyo mínimo.
   - Revisabilidad (P4): un patrón es una "working regularity"; la revisión es una NUEVA versión del library (`pattern_id` `_v2`), NUNCA mutar una versión publicada ni hacer UPDATE sobre filas de `patterns`.

2. **Modelo + persistencia de Pattern** (`libs/reasoning/pattern.py`, nuevo paquete `reasoning`):
   - `PatternCreate` / `Pattern` (pydantic `frozen`, P1): campos espejo de la tabla `patterns` (id, tenant_id, context_id, pattern_type, description, strength_measure [0,1], frequency, detected_at, is_active). `build_pattern(create)` análogo a `build_context`.
   - `pattern_id(tenant_id, context_id, library_pattern_id)` determinístico (uuid5, namespace propio): la versión del library queda trazable en el id; re-ejecución sobre los mismos hechos produce el mismo id → dedup idempotente (`ON CONFLICT (id) DO NOTHING`). OJO: NO incluir `detected_at` en el id (rompería la idempotencia entre corridas).
   - `PatternStore`: INSERT append-only, `verify_connection`, `close`, y reads para el detector (`list_patterns(tenant_id)`, `list_tenant_ids()`). Análogo a `EvidenceStore`/`ContextStore`.
   - Agregar a `ContextStore` (`libs/perception/context.py`) los reads que el detector necesita: `list_contexts(tenant_id) -> list[Context]` (todas las activaciones ordenadas por `activated_at` — el stream continuo de Context, NO solo el `is_active = true`) y `list_tenant_ids()` (como en EvidenceStore). Estos métodos solo LEEN; nunca modifican contextos (P1).

3. **Detector** (`apps/services/pattern-service/src/detector/`; funciones PURAS, sin I/O, testables):
   - `detect(contexts, library, window_days) -> list[CandidatePattern]` por tenant: para cada `PatternDefinition`, agrupar las activaciones por scope (mental_model_id y purpose), ordenadas por `activated_at`; contar ocurrencias dentro de la ventana de evaluación (`DETECTION_WINDOW_DAYS`); calcular `strength_measure` en [0,1] con un esquema documentado y testeado (p.ej. support = ocurrencias_en_ventana / max(min_occurrences, 1), acotado a 1.0); derivar `frequency_label` del intervalo mediano entre activaciones (p.ej. días → daily/weekly/event-driven). Escribir el esquema exacto en el docstring y testearlo con valores conocidos.
   - Solo si `strength_measure >= strength_threshold` del library → Candidate Pattern con `description` construida del template + hechos medidos (ej.: "El contexto capacity_risk para infrastructure_health se activó N veces en la ventana (intervalo mediano ~7 días). Regularidad detectada."). PROHIBIDO causalidad/predicción — Non-examples del marco: "el backup de viernes falla porque el job de mantenimiento" (explicación) y "la infra va a fallar" (predicción) NO son patterns.
   - El patrón se ancla a UN `context_id` representativo (ej. la activación más reciente del grupo que supera el umbral); la `description` lleva el conteo. Los candidatos bajo el umbral no se persisten pero se registran para métricas.
   - Idempotencia: misma ventana + mismos contextos + misma versión de library → mismo `Pattern` (dedup).

4. **Orquestación en `pattern-service`** (`apps/services/pattern-service/` — el directorio existe VACÍO; crearlo completo siguiendo la anatomía de context-service):
   - Misma estructura: `src/main.py`, `src/service.py`, `src/health.py`, `src/detector/`, `tests/`, `pyproject.toml`, `Dockerfile`.
   - R1: `pattern-service` implementa EXACTAMENTE una capacidad (Generalize). El context-service no detecta patrones y el pattern-service no activa context.
   - Ciclo: por tenant, `ContextStore.list_contexts` → detector → `PatternStore` persistir (dedup idempotente). NUNCA escribe en `contexts`/`evidence`/`observations` (P1). NUNCA lee el observation bus ni agentes (constraint Reasoning: actúa sobre conocimiento).
   - Métricas en `/metrics` (observabilidad OPERATIVA del servicio — NO usar números de regla): `total_patterns`, `total_pattern_duplicates`, `total_candidates_below_threshold`, `total_errors`, `patterns_by_type`, `patterns_by_mental_model`.
   - Puerto: `PATTERN_HEALTH_PORT` (default 8092). No contacta agentes ni produce alertas/acciones (R3: frontera cognitiva; roadmap: alertas solo cuando Decision service esté operativo; R4).

5. **Schema**: tabla `patterns` YA existe en `01-schema.sql` — usarla tal cual; NO regenerear la tabla. Evaluar y JUSTIFICAR la adición de un trigger de inmutabilidad de contenido para `patterns` (precedente `context_content_immutable_trigger`): recomendado `prevent_pattern_update` que bloquee UPDATE/DELETE de contenido, dejando opcional el flip de `is_active` como ciclo de vida. Si se adopta, entregar la migración idempotente `infrastructure/db-migrations/sprint5-pattern-content-trigger.sql` y APLICARLA a la BD existente. Documentar la elección (¿trigger o solo append por convención?) en el journal con justificación.

6. **Tests** (unit + integración PG):
   - Una prueba por `PatternDefinition` con contextos sintéticos (mismo scope, timestamps espaciados): detecta cuando support ≥ umbral; y Negativo cuando el apoyo es insuficiente o el scope no aparece.
   - Scoring `strength_measure` con valores conocidos y derivación del `frequency_label`.
   - Anti-inventar: la `description` de un patrón detectado no contiene lenguaje causal/predictivo (assert sobre presencia de "porque"/"fallará"/etc. o equivalentes).
   - Dedup: re-ejecución del detector sobre los mismos contextos no duplica filas.
   - Trazabilidad: `pattern.context_id` referencia un context real y la cadena pattern → context → evidence → observations se puede leer hacia atrás.
   - Integración PG: INSERT pattern, read-back, `strength_measure`/`frequency` persistidos.
   - Regresión: correr TODAS las suites previas y dejarlas verdes (85 = 4+6+6+39+30).

7. **Docs/env**: actualizar README (sección Sprint 5 + cómo correr el pattern-service), `.env.example` (agregar `PATTERN_HEALTH_PORT=8092`, `DETECTION_WINDOW_DAYS` con default documentado). Journal de la sesión al cierre. NO modificar `docs/sprint-3-prompt.md`, `docs/sprint-4-prompt.md` ni el journal previo.

## Cumplimiento cognitivo a validar al cerrar

- R1: `pattern-service` implementa EXACTAMENTE una capacidad (Generalize). El collector/context-service no detectan patrones.
- R2: Contract (Input: Active Contexts + Pattern Library → Transform: detección de regularidades → Output: Pattern(s) + strength_measure) testeado.
- P4: los patterns revelan regularidad; NO explican causa (eso lo hará Hypothesis, Sprint 7). `description` factual, sin aserciones causales ni predictivas.
- Reasoning Layer constraint: el detector actúa sobre conocimiento (contexts), nunca directamente sobre el mundo; no consume observaciones crudas ni produce efectos sobre `contexts`/`evidence`/`observations` (P1).
- P1: patterns append-only (y trigger de contenido si se decide); re-ejecución no duplica; trazabilidad pattern → context → evidence → observations verificada.
- P3: conceptos estables; `PatternDefinition` declarativas, no razonamiento, no ML.
- R3: frontera — pattern-service no gatilla acciones ni alertas. R4: nada influye acción sin Confidence (aún no hay action layer ni calibración).
- Revisabilidad (P4): un patrón es una regularidad de trabajo; la revisión es nueva versión del library, nunca UPDATE de filas.
- No iniciar Anomaly (Sprint 6), Hypothesis (Sprint 7) ni técnicas avanzadas (correlación/secuencia/ML) — quedan para fases siguientes.

## Criterios de aceptación verificables

- pytest verde: 85 previos + nuevos del pattern-service / pattern library.
- Corriendo `pattern-service` contra la PG real (8 observations, 3 evidence, 3 contexts) intenta la detección. Si el dataset real no dispara ningún patrón válido, usar siembra temporaria en tests de integración con contextos sintéticos (documentar el resultado real en el journal). Si dispara, las filas de `patterns` deben tener `context_id` referenciando contexts reales, `strength_measure`, `frequency` y `description` factual.
- `description` factual verificada por tests (sin lenguaje causal/predictivo).
- Re-corrida sin duplicados (dedup probado).
- `observations`, `evidence` y `contexts` sin cambios tras el ciclo completo (P1 verificada).
- Métricas disponibles en `:8092/metrics` (pattern-service con `PATTERN_HEALTH_PORT=8092`).