# SPRINT 7 — HYPOTHESIS GENERATOR (Reasoning: capacidad Predict)

> Persistido desde sesión 2026-08-16. Sesión EVALUADA al inicio.

## Contexto de la sesión previa

- Sprints 1-5 (COMPLETOS): Perception completa (Observation → Evidence → Context) + Pattern Detector. 128 tests (linux 4, windows 6, vmware 6, collector 39, context 30, pattern 43).
- Sprint 6 (COMPLETO esperado al iniciar): Anomaly Detector. `anomaly-service`, `libs/reasoning/anomaly.py`, `libs/procedural_memory/tolerance_library.py`, tabla `anomalies` con trigger de contenido, `ANOMALY_HEALTH_PORT=8093`.
- Infra corriendo: postgres TimescaleDB 127.0.0.1:5433 (db/user/pass = cosmonitor), redis 127.0.0.1:6379. Schema en `infrastructure/docker/init-sql/01-schema.sql` — YA incluye la tabla `hypotheses` (VACÍA): id, tenant_id FK, anomaly_ids UUID[] NOT NULL, pattern_ids UUID[] DEFAULT '{}', description TEXT, predicted_consequences JSONB NOT NULL, falsification_criterion TEXT NOT NULL, coherence_score NUMERIC(3,2), status VARCHAR(20) DEFAULT 'candidate' (candidate/confirmed/falsified), generated_at; índice `idx_hypotheses_tenant_status`. Seed del tenant sandbox en 02-seed.sql.
- Marco cognitivo (SOLO LECTURA, no tocar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`. Producto: `/home/dcordoba/Documents/Default Project/company-os-monitor/`.
- Documentación fuente del Sprint: concepto `Hypothesis` del marco: `/home/dcordoba/Documents/Default Project/company/company-os-main/docs/cognitive-lexicon/core-concepts/hypothesis.md` (Familia Reasoning, Capacidad Predict). Reglas conceptuales: **"A Hypothesis is a testable explanation of an observed or anomalous situation, proposed to account for available Evidence, Patterns, or Anomalies."** Y del design implications: **"Company OS must maintain multiple competing hypotheses simultaneously. Premature convergence on a single explanation is a cognitive failure."** Y **"The architecture must follow the principle of explanatory coherence: accept the hypothesis that maximizes coherence, reject those that contradict it."** Diseño de producto: `docs/03-predictivo-ia-local.md` (FASE 4: Hypothesis Service + templates por dominio + LM Studio), roadmap `docs/05-negocio-roadmap-backlog.md` (item #7 Hypothesis Generation, item #19 LM Studio).

### Correcciones de auditoría ya aplicadas (NO reintroducir)

- Citaciones canónicas: usar `P1`-`P7`, design rules `R1`-`R7` de `cognitive-architecture.md`, conceptos del marco y ADR-0001/0002. NO inventar números de regla ni reciclar "R8/R9/R10". Trazabilidad/objetividad/provenance se describen factual, sin número de regla. NO citar paths/specs que no existan en el checkout.
- Puertos/env: collector `HEALTH_PORT` (8090), context `ACTIVATOR_HEALTH_PORT` (8091), pattern `PATTERN_HEALTH_PORT` (8092), anomaly `ANOMALY_HEALTH_PORT` (8093). El hypothesis-service usará `HYPOTHESIS_HEALTH_PORT` (default 8094). NUNCA reutilizar nombres de env.
- `libs/cognitive_core/calibration_model.py` sigue PLANNED (NO cablear hasta Sprint 8). El `cognitive_tool.py` (ABC para herramientas externas, LM Studio) ES el contrato para integrar LM Studio en este sprint — ver Entregables.
- **ADR-0002**: LM Studio es capacidad externa NO-canónica. Todo output debe pasar por parsing estructurado (Pydantic) + el flujo canónico. NO bypassa: las hipótesis siempre se representan con `predicted_consequences` y `falsification_criterion`. Sin LM Studio disponible → fallback a templates internos (nunca se queda sin salida).

## Objetivo

Implementar el **Hypothesis Generator** (Contract cognitivo: Concept=Hypothesis, Familia=Reasoning, Capacidad=Predict). Input: Active Context + Patterns + Anomalies + Mental Model library. Transform: generar explicaciones testables que den cuenta de la situación y sean consistentes con el modelo mental más coherente. Output: una o más Hypothesis candidatas, cada una con `predicted_consequences` (observables, falsificables) y `falsification_criterion` (outcome concreto que demostraría que es falsa). NO avanzar a Confidence (Sprint 8), Recommendation (Sprint 9) ni Decision (Sprint 10).

Regla conceptual que gobierna el sprint: **"A hypothesis is a commitment to an explanation, held tentatively until evidence decides."** El sistema mantiene múltiples hipótesis competidoras simultáneamente (convergencia prematura = fallo cognitivo) y NO las confirma ni las descarta (status candidate; el descarte/confirmación llega con el evidence futuro y Confidence — fuera de alcance).

## Entorno y comandos (OBLIGATORIO respetar)

- Instalación: `pip install --break-system-packages -e ".[dev]"` (Python 3.14 es externally-managed; `.venv` NO funciona; NO inicializar git).
- NO usar `cd` para ejecutar; usar workdir = raíz del repo. PYTHONPATH por-app:
  `PYTHONPATH="<ruta_app>:<repo_root>" python3 -m pytest <ruta_app/tests> -q`
  con `REPO="/home/dcordoba/Documents/Default Project/company-os-monitor"`.
- Correr TESTS EXISTENTES al final y dejarlos verdes (128 + los de Sprint 6).
- Ruff: reducir violaciones nuevas a cero salvo BLE001. line-length 100.
- Tests de integración con Postgres real: limpiar con `SET session_replication_role = replica` (superuser) y borrar explícitamente las filas hijas.

## Proceso obligatorio (policy del marco)

- **Journaling (E6 / Directive 002)**: entry por sesión en `journal/YYYY/YYYY-MM-DD.md` con el formato del marco (`# Journal — YYYY-MM-DD (Sprint 7 — ...)` + secciones `## Theme`, `## Today's Progress`, `## Discoveries`, `## Decisions`, `## Reflection`, `## Quote of the Day`). Listar archivos cambiados.

## Entregables

1. **Modelo + persistencia de Hypothesis** (`libs/reasoning/hypothesis.py`, nuevo):
   - `HypothesisCreate` / `Hypothesis` (pydantic `frozen`, P1): campos espejo de la tabla `hypotheses` (id, tenant_id, anomaly_ids, pattern_ids, description, predicted_consequences, falsification_criterion, coherence_score, status, generated_at). `build_hypothesis(create)`.
   - `hypothesis_id(tenant_id, anomaly_ids, pattern_ids, description)` determinístico (uuid5, namespace propio) SIN `generated_at` → dedup idempotente. OJO: dos hipótesis distintas sobre la misma anomalía deben tener ids distintos (incluir el texto de la descripción en el hash).
   - `HypothesisStore`: INSERT append-only, `verify_connection`, `close`, reads `list_hypotheses(tenant_id)`, `list_tenant_ids()`. Análogo a `PatternStore`.
   - Agregar a `AnomalyStore` (`libs/reasoning/anomaly.py`) el read que el generador necesita: `list_anomalies(tenant_id) -> list[Anomaly]` (solo lectura, P1) — verificar que existe de Sprint 6 y no romper API.

2. **Templates Library** (`libs/procedural_memory/hypothesis_templates.py`, nuevo; procedural memory — plantillas declarativas por dominio, NO razonamiento):
   - `HypothesisTemplate` (dataclass frozen): `template_id` (versionado, ej. `auth_burst_compromise_v1`), `scope_anomaly_class` (MVP: `point`), `scope_mental_models`, `scope_purposes`, `description_template` (texto con placeholders de hechos), `consequence_templates` (list[str] — predicciones observables), `falsification_templates` (list[str] — criterios falsificables).
   - Catálogo inicial en línea con los dominios de `docs/03-predictivo-ia-local.md` (Disk Saturation, Backup Failure, Auth Burst) y los mental models de Sprint 4. Ej: anomalía point en `resource_pressure` → hipótesis H1/H2/H3 (logging verbosity, retention, auto-growth) cada una con consecuencias y criterios de falsificación.
   - Las plantillas generan hipótesis EXPLICATIVAS con predicción (Non-example del marco: "The backup failed because the disk is full" sin testing es asunción, no hipótesis; "The server will fail" es predicción sin explicación).

3. **Generator** (`apps/services/hypothesis-service/src/generator/`; funciones PURAS, sin I/O, testables):
   - `generate(anomaly, contexts, patterns, library) -> list[HypothesisCreate]`: para cada anomalía point, produce las hipótesis candidatas de los templates cuyo scope aplica, instanciando los placeholders con hechos medidos (sin juicios). Cada hipótesis lleva `predicted_consequences` y `falsification_criterion` no vacíos.
   - **Mantenimiento de hipótesis competidoras**: el generator SIEMPRE emite ≥2 hipótesis por anomalía (cuando haya templates aplicables); nunca convergencia prematura a una sola.
   - `coherence_score` en el MVP: asignar desde el template (estimación declarativa documentada) o placeholder declarado; la calibración real (S+C+ECE) es Sprint 8. NO inventar coherencia no respaldada: documentar el esquema en el docstring.
   - Status inicial: `candidate`. NO confirmar ni falsificar (fuera de alcance: requiere evidencia futura + Confidence).
   - Idempotencia: mismos inputs → mismas Hypothesis (dedup).

4. **Orquestación en `hypothesis-service`** (`apps/services/hypothesis-service/` — el directorio existe VACÍO; crear completo siguiendo anatomía de pattern-service):
   - Misma estructura: `src/main.py`, `src/service.py`, `src/health.py`, `src/generator/`, `tests/`, `pyproject.toml`, `Dockerfile`.
   - R1: `hypothesis-service` implementa EXACTAMENTE una capacidad (Predict). No detecta anomalías ni patrones.
   - Ciclo: por tenant, `AnomalyStore.list_anomalies` (+ contexts/patterns) → generator → `HypothesisStore` persistir (dedup idempotente). NUNCA escribe en `contexts`/`patterns`/`anomalies`/`evidence`/`observations` (P1). NUNCA lee el observation bus (constraint Reasoning).
   - Métricas en `/metrics` (sin números de regla): `total_hypotheses`, `total_hypothesis_duplicates`, `total_anomalies_no_templates`, `total_errors`, `hypotheses_by_status`, `hypotheses_by_mental_model`.
   - Puerto: `HYPOTHESIS_HEALTH_PORT` (default 8094). NO produce recomendaciones/decisiones ni alertas (R3; R4).

5. **Integración LM Studio (capacidad externa, ADR-0002 — OPCIONAL pero prevista)**:
   - `libs/cognitive_core/cognitive_tool.py` es el ABC (`invoke`, `validate_output`, `available`). Implementar `LMStudioHypothesisTool` como herramienta EXTERNA para agregar diversidad: su `validate_output` debe exigir que toda hipótesis tenga `falsification_criterion` no vacío.
   - Contrato: output estructurado (JSON) → Pydantic validation → integrado con las hipótesis de templates. Si `available()` es falso (LM Studio no corriendo) → fallback solo templates (NUNCA se rompe el flujo canónico).
   - No cablear Confidence en este sprint (Sprint 8). LM Studio es herramienta, no fuente de verdad.

6. **Schema**: tabla `hypotheses` YA existe — usarla tal cual; NO regenerar. Evaluar y JUSTIFICAR trigger de inmutabilidad de contenido (precedente pattern/anomaly): recomendado `prevent_hypothesis_content_update` (contenido inmutable P1, DELETE bloqueado; `status` como único flippable — candidate/confirmed/falsified es ciclo de vida). Si se adopta, migración idempotente `infrastructure/db-migrations/sprint7-hypothesis-content-trigger.sql` + aplicar a la BD existente. Documentar en journal.

7. **Tests** (unit + integración PG):
   - Una prueba por template: anomalía point en el scope → genera las hipótesis del template con placeholders instanciados; `predicted_consequences` y `falsification_criterion` no vacíos.
   - Múltiples competidoras: para una anomalía → ≥2 hipótesis distintas (assert sobre count y sobre ids distintos).
   - Anti-conclusión: las hipótesis son candidatas (status candidate), sin causalidad afirmada como hecho (assert: sin "es la causa"/"está confirmado"); descripciones con lenguaje hipotético.
   - Dedup: re-ejecución sobre los mismos inputs no duplica filas.
   - Trazabilidad: `hypothesis.anomaly_ids` referencian anomalías reales; cadena hypothesis → anomaly → pattern → context → evidence → observations se lee hacia atrás.
   - Integración PG: INSERT hypothesis, read-back, `status='candidate'`.
   - LM Studio: test de `validate_output` (rechaza hipótesis sin falsification_criterion) y de fallback cuando no está disponible (mock).
   - Regresión: TODAS las suites previas verdes (128 + Sprint 6 + nuevas).

8. **Docs/env**: README (sección Sprint 7 + cómo correr), `.env.example` (agregar `HYPOTHESIS_HEALTH_PORT=8094`, `HYPOTHESIS_CYCLE_SECONDS`, `LM_STUDIO_URL` — ya existe, verificar — y flags de templates). Journal al cierre. NO modificar prompts previos ni journal previo.

## Cumplimiento cognitivo a validar al cerrar

- R1: `hypothesis-service` implementa EXACTAMENTE una capacidad (Predict).
- R2: Contract (Input: Active Context + Patterns/Anomalies + Mental Model library → Transform: generar explicaciones testables → Output: Hypothesis(es) + predicted consequences + falsification criteria) testeado.
- Concepto Hypothesis: compromiso tentativo con una explicación; hipótesis MÚLTIPLES y competidoras (premature convergence = cognitive failure); explicación + predicción (Non-example: predicción sin explicación no es hipótesis).
- Falsificación: `falsification_criterion` es obligatorio en TODA hipótesis (assert testeado), en términos observables concretos.
- Reasoning Layer constraint: actúa sobre conocimiento (anomalías, patterns, contexts), nunca sobre el mundo; no produce efectos sobre artefactos previos (P1).
- P1: `hypotheses` append-only (+ trigger si se decide); re-ejecución no duplica; trazabilidad verificada.
- ADR-0002: LM Studio es herramienta externa, validate_output garantiza contratos; fallback sin LM Studio; nada bypassa el flujo canónico.
- R3: frontera — sin recomendaciones/decisiones/alertas. R4: nada influye acción sin Confidence (Sprint 8).
- No avanzar a Confidence (Sprint 8), Recommendation (Sprint 9), Decision (Sprint 10) ni Insight (Sprint 13).

## Criterios de aceptación verificables

- pytest verde: 128 + Sprint 6 + nuevos del hypothesis-service / hypothesis model / templates.
- Corriendo `hypothesis-service` contra la PG real (con anomalies sembradas sintéticas): para cada anomalía point, ≥2 hipótesis candidatas con `predicted_consequences` y `falsification_criterion`; anomalías sin template → métrica `total_anomalies_no_templates`, sin filas.
- `status='candidate'` en todas las filas nuevas; ninguna hipótesis confirmada/falsificada.
- Re-corrida sin duplicados (dedup probado).
- `contexts`, `patterns`, `anomalies`, `evidence`, `observations` sin cambios tras el ciclo (P1 verificada).
- Métricas en `:8094/metrics` (hypothesis-service con `HYPOTHESIS_HEALTH_PORT=8094`).
