# COS-Monitor (Company OS Monitor)

Plataforma SaaS para monitoreo, análisis y diagnóstico automático de infraestructura IT usando arquitectura cognitiva Company OS.

## Arquitectura Cognitiva

Implementa el pipeline canónico: **Perception → Reasoning → Confidence → Action**

| Capa | Capacidad Cognitiva | Concepto | Servicio |
|------|---------------------|----------|----------|
| Perception | Observation Capture | Observation | linux-agent, windows-agent, ... |
| Perception | Evidence Organization | Evidence | collector-service |
| Perception | Context Activation | Context | context-service |
| Reasoning | Pattern Detection | Pattern | pattern-service |
| Reasoning | Anomaly Detection | Anomaly | anomaly-service |
| Reasoning | Hypothesis Generation | Hypothesis | hypothesis-service |
| Reasoning | Insight Restructuring | Insight | insight-service |
| Learning | Confidence Calibration | Confidence | confidence-service |
| Action | Recommendation | Recommendation | recommendation-service |
| Action | Decision | Decision | decision-service |

## Estructura del Proyecto

```
cos-monitor/
├── apps/
│   ├── agents/           # Observation Capturers (Perception)
│   └── services/         # Cognitive Services
├── libs/
│   ├── cognitive-core/   # Contracts, calibration, bus
│   ├── perception/       # Observation, Evidence, Context
│   ├── reasoning/        # Pattern, Anomaly, Hypothesis, Insight
│   ├── learning/         # Confidence, Memory
│   ├── action/           # Recommendation, Decision
│   └── procedural-memory/ # Security, policies
├── infrastructure/
│   └── docker/           # Docker Compose, init SQL
└── tests/                # Contract, integration, calibration tests
```

## Quick Start

```bash
# 1. Copy environment
cp .env.example .env

# 2. Start infrastructure
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 3. Verify database
docker compose -f infrastructure/docker/docker-compose.yml exec postgres pg_isready -U cosmonitor

# 4. Run linux-agent (development)
cd apps/agents/linux-agent
pip install --break-system-packages -e ".[dev]"
python -m src.main

# 5. Check observations in Redis
docker compose -f infrastructure/docker/docker-compose.yml exec redis redis-cli XRANGE observations COUNT 5
```

## Sprint 2: Multi-Agent Collection + Postgres Persistence

- `windows-agent` - Observation Capturer (WMI over WinRM): CPU, memoria, discos,
  servicios detenidos (Auto), evento log de Error/Critical
- `vmware-agent` - Observation Capturer (vSphere API/pyVmomi): datastores,
  VM power states, snapshots, ESXi host health
- `collector-service` - Evidence Organizer: consume `observations` desde Redis
  Streams y las persiste (INSERT append-only) en Postgres; ack solo tras INSERT
- Inmutabilidad (P1): trigger de BD bloquea UPDATE/DELETE en `observations`
- Idempotencia: re-entrega de mensajes no duplica filas (dedup por observation id)

### Correr Sprint 2

```bash
# 1. Infra (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. Persistir observaciones del bus en Postgres
PYTHONPATH="apps/services/collector-service:." python3 -m src.main
# PYTHONPATH adicional para el proyecto:
# PYTHONPATH="apps/services/collector-service:/home/dcordoba/Documents/Default Project/company-os-monitor"

# 3. Verificar
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor -c "SELECT fact_type, count(*) FROM observations GROUP BY fact_type;"
```

Los agentes Windows/VMware requieren un host WinRM/vCenter real. El tenant usado por
los agentes (`TENANT_ID` default) debe existir en `tenants` (seed: `02-seed.sql`).

## Sprint 3: Evidence Organizer (Perception - Organize)

- `libs/perception/evidence.py` - `EvidenceStore` append-only para la tabla
  `evidence`: INSERT + dedup idempotente (ON CONFLICT por id determinístico),
  `verify_connection`, `close` (análogo a `ObservationStore`)
- Inmutabilidad (P1): trigger de BD bloquea UPDATE/DELETE en `evidence`
  (`prevent_evidence_update`)
- `apps/services/collector-service/src/organizer/` - reglas de organización por
  dominio (funciones puras sobre Observaciones inmutables):
  - `resource_exhaustion_evidence` (cpu>90% + mem>85% + disk>85%, misma fuente, 5 min)
  - `service_degradation_evidence` (servicio Stopped/Auto + evento Error, 15 min)
  - `auth_anomaly_evidence` (lockout AD + cambio de membresía privilegiada, 1 h)
  - `backup_failure_evidence` (job Failed + repo_free<10%, 1 h)
  - `vmware_capacity_evidence` (datastore_free<15% + snapshot>7d, 30 min)
  - `network_anomaly_evidence` (interface_errors>umbral + port_state_change, 15 min)
  - `description` objetiva/factual, `quality_class` Q1-Q4 y `weight` w_i asignados
    EN LA CREACIÓN (Q1→0.875, Q2→0.625, Q3→0.375, Q4→0.125, midpoints exactos de las bandas). Sin retrofitting.
- Orquestación en el collector: tras persistir cada lote de observaciones, el
  organizador corre sobre el buffer por ventana/tenant y escribe `evidence`
  (dedup idempotente). Métricas de organizaciones expuestas en `/metrics`
  (`total_evidence`, `total_evidence_duplicates`, `total_evidence_errors`,
  `evidence_by_type`).

### Correr Sprint 3

```bash
# 1. Infra (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. Aplicar el trigger de inmutabilidad de evidence (si el schema es anterior al Sprint 3)
#    (en instalaciones nuevas corre con 01-schema.sql automáticamente)

# 3. Correr el Evidence Organizer (consume observaciones -> persiste observations -> organiza evidence)
PYTHONPATH="apps/services/collector-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main

# 4. Verificar evidence generada
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT organization_type, quality_class, weight FROM evidence;"

# 5. Métricas del organizador
curl -s http://localhost:8090/metrics
```

Los agentes pueden publicar observaciones sintéticas al bus para disparar las
reglas durante desarrollo (p. ej. cpu>90%, mem>85%, disk>85% en la misma fuente).
La ventana/umbrales por dominio son configurables via env (`RESOURCE_EXHAUSTION_WINDOW_MINUTES`,
`NETWORK_ANOMALY_ERROR_THRESHOLD`, etc., ver `.env.example`).

## Sprint 4: Context Activator (Perception - Explain)

- `libs/perception/context.py` - catálogo declarativo de **modelos mentales**
  (`MentalModel`, dataclass frozen, NO razonamiento) mapeando a los
  `organization_type` de Sprint 3 para los purposes
  `infrastructure_health`, `security_posture` y `capacity_management`:
  - `resource_pressure` → `resource_exhaustion_evidence`
  - `service_failure` → `service_degradation_evidence`
  - `auth_compromise` → `auth_anomaly_evidence`
  - `capacity_risk` → `backup_failure_evidence` + `vmware_capacity_evidence`
  - `connectivity_degradation` → `network_anomaly_evidence`
- Mismo módulo: `Context` (pydantic `frozen`), `context_id()` determinístico
  (uuid5 tenant+purpose+evidence_ids) y `ContextStore` (INSERT append-only con
  `ON CONFLICT (id) DO NOTHING`, dedup idempotente, `verify_connection`,
  `close`). El contenido (evidence_ids, mental_model_id, purpose,
  coherence_score, competing_models) es inmutable (P1); `is_active` es estado de
  ciclo de vida: activar un contexto nuevo desactiva el previo del mismo
  tenant+purpose.
- `apps/services/context-service/` - **Context Activator** (R1: exactamente la
  capacidad Explain, separado del collector-service):
  - `src/activator/coherence.py` - competencia de coherencia explicativa (P2,
    funciones puras): por tenant+purpose, cada modelo candidato explica la
    fracción de peso de evidencia (`weight` de la evidence) que cubre su firma;
    gana el de mayor `coherence_score` (empates → desempate determinístico por
    model_id, documentado). Sin interpretación ni causalidad (P2).
  - `src/activator/engine.py` - `ActivatorEngine` (puro): batch de Evidence →
    `ContextCreate` con ganador + `competing_models` (todos los candidatos con
    sus scores, no solo el ganador).
  - `src/service.py` - orquestación: lee evidence de Postgres por tenant, corre
    la competencia por cada purpose, escribe el Active Context (dedup;
    desactiva el previo). Métricas: `total_contexts`,
    `total_context_duplicates`, `total_errors`, `contexts_by_mental_model`,
    `contexts_by_purpose`.
  - `src/health.py` - `/health` y `/metrics` (observabilidad operativa del servicio).
- Schema: tabla `contexts` usada tal cual; se agregó el trigger
  `context_content_immutable_trigger` (bloquea UPDATE de columnas de contenido y
  DELETE; permite el flip de `is_active`).

### Correr Sprint 4

```bash
# 1. Infra (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. (solo si el schema es anterior al Sprint 4) aplicar el trigger de contenido:
#    ver infra/db-migrations/sprint4-context-content-trigger.sql ó el bloque de
#    protect_context_content()/context_content_immutable_trigger en 01-schema.sql

# 3. Correr el Context Activator (evidence -> contexts)
PYTHONPATH="apps/services/context-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main

# 4. Verificar los Active Contexts
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT tenant_id, mental_model_id, purpose, coherence_score, competing_models, is_active FROM contexts;"

# 5. Métricas del activador
curl -s http://localhost:8091/metrics
```

Los 5 mental models compiten por purpose; `competing_models` registra la
competencia (candidatos + scores). Re-ejecutar el servicio sobre la misma
evidencia no duplica contexts (id determinístico + `ON CONFLICT DO NOTHING`).

## Sprint 5: Pattern Detector (Reasoning - Generalize)

- `libs/procedural_memory/pattern_library.py` - **Pattern Library** (memoria
  procedimental, definiciones DECLARATIVAS, no razonamiento): `PatternDefinition`
  (dataclass frozen) con `pattern_id` versionado (`_v1`/`_v2`), `pattern_type`
  (MVP solo `temporal`; `correlation`/`sequential`/`threshold` reservados),
  `scope_mental_models`, `scope_purposes` (vacío = todos), `min_occurrences`,
  `strength_threshold`, `frequency_label` y `description_template` FACTUAL. El
  catálogo cubre los 5 mental models de Sprint 4. P4: revisar un patrón =
  publicar una NUEVA versión (`_v2`), nunca mutar la publicada.
- `libs/reasoning/pattern.py` - modelo `Pattern` (pydantic `frozen`, P1) con
  `pattern_id()` determinístico (uuid5 tenant + context_id + library_pattern_id;
  la versión del library queda trazable en el id, y el `detected_at` queda FUERA
  del id para mantener la idempotencia entre corridas) y `PatternStore`
  (INSERT append-only, `ON CONFLICT (id) DO NOTHING`, dedup idempotente,
  `list_patterns`, `list_tenant_ids`).
- `libs/perception/context.py` - nuevos READS en `ContextStore` (solo lectura,
  P1): `list_contexts(tenant_id)` devuelve TODAS las activaciones ordenadas por
  `activated_at` (el stream continuo de Context, no solo `is_active = true`) y
  `list_tenant_ids()`.
- `apps/services/pattern-service/` - **Pattern Detector** (R1: exactamente la
  capacidad Generalize, separado del collector y del context-service):
  - `src/detector/detector.py` - funciones PURAS (sin I/O): por cada
    `PatternDefinition`, agrupa las activaciones por scope
    (mental_model_id, purpose) dentro de la ventana (`DETECTION_WINDOW_DAYS`);
    `strength_measure = min(occurrences / max(min_occurrences, 1), 1.0)`; emite
    Candidate Pattern solo si `strength >= strength_threshold`; `frequency`
    derivada del intervalo mediano entre activaciones (hourly/daily/weekly/
    event-driven); ancla a la activación más reciente. `description` solo
    factual (nunca causal/predictiva, P4).
  - `src/service.py` - ciclo por tenant: `ContextStore.list_contexts` →
    detector → `PatternStore` (dedup idempotente). NUNCA escribe en
    `contexts`/`evidence`/`observations` (P1), nunca lee el observation bus
    (constraint Reasoning: actúa sobre conocimiento).
  - `src/health.py` - `/health` y `/metrics` (`total_patterns`,
    `total_pattern_duplicates`, `total_candidates_below_threshold`,
    `total_errors`, `patterns_by_type`, `patterns_by_mental_model`).
- Schema: tabla `patterns` usada tal cual (ya existía). Se agregó el trigger
  `pattern_content_immutable_trigger` (bloquea UPDATE de columnas de contenido y
  DELETE; permite el flip de `is_active`).

### Correr Sprint 5

```bash
# 1. Infra (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. (solo si el schema es anterior al Sprint 5) aplicar el trigger de contenido:
#    ver infra/db-migrations/sprint5-pattern-content-trigger.sql ó el bloque de
#    prevent_pattern_content_update()/pattern_content_immutable_trigger en
#    01-schema.sql

# 3. Correr el Pattern Detector (contexts -> patterns)
PYTHONPATH="apps/services/pattern-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main

# 4. Verificar los patterns detectados
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT tenant_id, pattern_type, strength_measure, frequency, description FROM patterns;"

# 5. Métricas del detector
curl -s http://localhost:8092/metrics
```

El detector mide apoyo sobre el stream de contexts (conocimiento), nunca sobre
observaciones crudas. Con el dataset real de la sandbox (1 activación por
scope) no se dispara ningún patrón (support insuficiente); los tests de
integración siembran contexts sintéticos con recurrencia semanal para verificar
detección + dedup + trazabilidad pattern → context → evidence → observations.

## Sprint 6: Anomaly Detector (Reasoning - Detect Deviation)

- `libs/reasoning/anomaly.py` - modelo `Anomaly` (pydantic `frozen`, P1) con
  `anomaly_id()` determinístico (uuid5 tenant + context_id + pattern_id;
  `detected_at` queda FUERA del id para mantener la idempotencia entre
  corridas) y `AnomalyStore` (INSERT append-only, `ON CONFLICT (id) DO
  NOTHING`, dedup idempotente, `list_anomalies`, `list_tenant_ids`).
- `libs/procedural_memory/tolerance_library.py` - **Tolerance Library**
  (memoria procedimental, umbrales EXPLÍCITOS, auditable, purpose-dependent;
  NO razonamiento): `ToleranceDefinition` (dataclass frozen) versionada
  (`_v1`/`_v2`) con `pattern_type` (MVP `temporal`), `scope_mental_models`,
  `scope_purposes`, `anomaly_class` (MVP `point`; contextual/collective
  reservados), `deviation_spec` (`days_off_schedule`,
  `count_exceeding_window`) y `threshold`. Un tolerance por cada
  PatternDefinition de Sprint 5. Esquemas de desviación documentados y
  testeados con valores conocidos.
- `libs/perception/context.py` - nuevo READ en `ContextStore` (solo lectura,
  P1): `list_active_contexts(tenant_id)` devuelve los Active Contexts
  (`is_active = true`, el actual por purpose).
- `apps/services/anomaly-service/` - **Anomaly Detector** (R1: exactamente la
  capacidad Detect Deviation, separado de pattern-service):
  - `src/detector/detector.py` - funciones PURAS (sin I/O): para cada Active
    Context, el patrón esperado es el más reciente de `patterns` para su scope
    (mental_model_id, purpose resuelto vía el context ancla); sin patrón NO
    hay desviación (concepto Anomaly: relative to patterns, never absolute →
    métrica `contexts_without_pattern`); `deviation_score` según
    `deviation_spec`; Candidate Anomaly solo si `deviation_score >
    tolerance_threshold`. `rationale` FACTUAL (señal, no conclusión; la
    explicación es de Hypothesis, Sprint 7).
  - `src/service.py` - ciclo por tenant: `ContextStore.list_active_contexts` +
    `PatternStore.list_patterns` → detector → `AnomalyStore` (dedup
    idempotente). NUNCA escribe en `contexts`/`patterns`/`evidence`/
    `observations` (P1), nunca lee el observation bus (constraint Reasoning:
    actúa sobre conocimiento). Métricas: `total_anomalies`,
    `total_anomaly_duplicates`, `total_contexts_without_pattern`, `total_errors`,
    `anomalies_by_class`, `anomalies_by_mental_model`.
  - `src/health.py` - `/health` y `/metrics` (observabilidad operativa).
  - `src/main.py` - tolerancias configurables por despliegue vía
    `TOLERANCE_*_THRESHOLD` (defaults canónicos en la library).
- Schema: tabla `anomalies` usada tal cual (ya existía). Se agregó el trigger
  `anomaly_content_immutable_trigger` (bloquea TODO UPDATE/DELETE: `anomalies`
  no tiene flag `is_active`, política igual a `evidence`).

### Correr Sprint 6

```bash
# 1. Infra (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. (solo si el schema es anterior al Sprint 6) aplicar el trigger de contenido:
#    ver infra/db-migrations/sprint6-anomaly-content-trigger.sql ó el bloque de
#    prevent_anomaly_content_update()/anomaly_content_immutable_trigger en
#    01-schema.sql

# 3. Correr el Anomaly Detector (contexts + patterns -> anomalies)
PYTHONPATH="apps/services/anomaly-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main

# 4. Verificar las anomalies detectadas
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT tenant_id, context_id, pattern_id, deviation_score, tolerance_threshold, anomaly_class FROM anomalies;"

# 5. Métricas del detector
curl -s http://localhost:8093/metrics
```

El detector compara conocimiento contra conocimiento (Active Contexts vs
patrones esperados), nunca observaciones crudas. Contra el dataset real de la
sandbox (3 contexts activos, 0 patterns) NO se produce ninguna anomalía:
sin patrón esperado no hay desviación (métrica `total_contexts_without_pattern`
> 0). Los tests de integración siembran patterns + contexts sintéticos que
desvían para verificar detección + dedup + trazabilidad
anomaly → pattern → context → evidence → observations.

## Sprint 7: Hypothesis Generator (Reasoning - Predict)

- `libs/reasoning/hypothesis.py` - modelo `Hypothesis` (pydantic `frozen`, P1)
  con `hypothesis_id()` determinístico (uuid5 tenant + anomaly_ids +
  pattern_ids + descripción; la descripción entra en el hash para que DOS
  hipótesis competidoras sobre la misma anomalía tengan ids distintos, y
  `generated_at` queda FUERA del id para la idempotencia entre corridas) y
  `HypothesisStore` (INSERT append-only, `ON CONFLICT (id) DO NOTHING`, dedup
  idempotente, `list_hypotheses`, `list_tenant_ids`). `status` es campo de
  ciclo de vida (`candidate`/`confirmed`/`falsified`): el generador SIEMPRE
  emite `candidate` (nunca confirma ni falsifica; eso requiere evidencia futura
  + Confidence, Sprint 8).
- `libs/procedural_memory/hypothesis_templates.py` - **Hypothesis Template
  Library** (memoria procedimental, plantillas declarativas por dominio, NO
  razonamiento): `HypothesisTemplate` (dataclass frozen) versionada (`_v1`) con
  `scope_anomaly_class` (MVP `point`), `scope_mental_models`,
  `scope_purposes`, `description_template`, `consequence_templates`,
  `falsification_templates` y `coherence_estimate` (prior declarativo
  documentado; la coherencia calibrada S+C+ECE llega con Confidence). Catálogo
  inicial: 3 hipótesis competidoras por dominio de `docs/03`
  (resource_pressure: logging verbosity / retention / auto-growth;
  capacity_risk: maintenance schedule / target capacity / antivirus conflict;
  auth_compromise: compromised account / retry loop / external monitoring).
  Lenguaje hipotético (podría/candidata) y `falsification_criterion`
  obligatorio en TODA hipótesis.
- `apps/services/hypothesis-service/` - **Hypothesis Generator** (R1:
  exactamente la capacidad Predict, separado de pattern/anomaly-service):
  - `src/generator/generator.py` - funciones PURAS (sin I/O): para cada
    anomalía point, el scope se resuelve vía su Active Context
    (mental_model_id, purpose), se instancian los templates cuyo scope aplica
    con hechos medidos (`{scope}`, `{deviation_score}`, `{frequency}` de la
    pattern esperada, `{anomaly_class}`). SIEMPRE emite ≥2 hipótesis
    competidoras cuando hay templates aplicables (convergencia prematura a una
    sola explicación = fallo cognitivo). Anomalía sin template aplicable o sin
    scope resuelto → sin filas (métrica `total_anomalies_no_templates`).
  - `src/service.py` - ciclo por tenant: `AnomalyStore.list_anomalies` +
    `ContextStore.list_contexts` + `PatternStore.list_patterns` → generator →
    `HypothesisStore` (dedup idempotente). NUNCA escribe en `contexts`/
    `patterns`/`anomalies`/`evidence`/`observations` (P1), nunca lee el
    observation bus (constraint Reasoning: actúa sobre conocimiento). Métricas:
    `total_hypotheses`, `total_hypothesis_duplicates`,
    `total_anomalies_no_templates`, `total_errors`, `hypotheses_by_status`,
    `hypotheses_by_mental_model`.
  - `src/health.py` - `/health` y `/metrics` (observabilidad operativa).
  - `src/main.py` - `HYPOTHESIS_HEALTH_PORT` (8094) y
    `HYPOTHESIS_CYCLE_SECONDS`.
- `libs/cognitive_core/lm_studio_hypothesis_tool.py` - **LMStudioHypothesisTool**
  (capacidad externa NO-canónica, ADR-0002) implementando el ABC
  `CognitiveTool`: `invoke` → prompt estructurado → LM Studio → parsing
  Pydantic → `HypothesisCreate` canónicos; `validate_output` exige
  `falsification_criterion` no vacío en TODA hipótesis; `available()` sondea el
  endpoint (`LM_STUDIO_URL`); si no está disponible → fallback solo templates
  (nunca se rompe el flujo canónico). No cablea Confidence (Sprint 8).
- Schema: tabla `hypotheses` usada tal cual (ya existía). Se agregó el trigger
  `hypothesis_content_immutable_trigger`: contenido inmutable (P1), DELETE
  bloqueado (audit trail persistente), y `status` como ÚNICO campo flippable
  (candidate → confirmed/falsified es ciclo de vida).

### Correr Sprint 7

```bash
# 1. Infra (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. (solo si el schema es anterior al Sprint 7) aplicar el trigger de contenido:
#    ver infra/db-migrations/sprint7-hypothesis-content-trigger.sql ó el bloque
#    de prevent_hypothesis_content_update()/hypothesis_content_immutable_trigger
#    en 01-schema.sql

# 3. Correr el Hypothesis Generator (anomalies + contexts + patterns -> hypotheses)
PYTHONPATH="apps/services/hypothesis-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main

# 4. Verificar las hypotheses generadas (todas status='candidate')
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT status, description, falsification_criterion FROM hypotheses;"

# 5. Métricas del generator
curl -s http://localhost:8094/metrics
```

El generator propone explicaciones testables (explicación + predicción +
criterio de falsificación), nunca concluye: mantiene múltiples hipótesis
competidoras en `candidate` y no confirma ni descarta ninguna (eso es evidencia
futura + Confidence). Contra el dataset real de la sandbox (sin anomalies
sembradas) no produce filas; los tests de integración siembran anomalies
sintéticas para verificar generación ≥2 competidoras, dedup, trazabilidad
hypothesis → anomaly → pattern → context → evidence → observations y la
inmutabilidad del contenido.

## Sprint 8: Confidence Calibrator (Learning - Calibrate)

- `libs/cognitive_core/calibration_model.py` - **Calibration Model** (ya NO es
  PLANNED en la parte cableada): implementa el formal del concepto Confidence
  (`confidence.md`): `evidential_support` (log-odds L = L0 + Σ wᵢ·eᵢ + sigmoide),
  `brier_score`, `ece_score` (M bins, default M=10), `final_confidence`
  (C_final = [α·S + (1−α)·C]·(1−ECE)) y `CalibrationParams` (α=0.5, M=10, L₀=0
  fijos a priori). `explanatory_coherence` ahora es REAL (normalización de
  satisfacción de constraints, Thagard 1989): C(H) = P/(P+N+U) sobre el esquema
  `{explains, contradicts, coherent_with, incoherent_with}` (fracción de
  evidencia explicada, penalizada por contradicciones y evidencia no explicada;
  0.5 neutral sin scope). Se mantienen `QUALITY_CLASS_RANGES` y
  `quality_class_to_weight` (bandas canónicas Q1-Q4).
- `libs/learning/confidence.py` - **modelo Confidence** (Learning - Calibrate):
  `ConfidenceCreate`/`Confidence` (pydantic `frozen`, P1) espejo de la tabla
  `confidence_scores`; `confidence_id(tenant_id, target_type, target_id,
  CalibrationContent)` determinístico (uuid5, namespace propio `...080`): hash
  de tenant + target + INPUTS de calibración (S, C, 1−ECE, α), SIN `computed_at`
  — mismos inputs → mismo id (dedup idempotente); inputs distintos (nueva
  evidencia) → NUEVO id → nueva fila (append-only: la calibración histórica se
  conserva, nunca se sobreescribe). `ConfidenceStore` (INSERT `ON CONFLICT (id)
  DO NOTHING`, `verify_connection`, `close`, `list_confidence(tenant_id)`,
  `get_confidence(target_type, target_id)` → última fila,
  `list_tenant_ids`).
- `apps/services/confidence-service/` - **Confidence Calibrator** (R1:
  exactamente la capacidad Calibrate; no genera hipótesis ni recomendaciones):
  - `src/calibrator/calibrator.py` - funciones PURAS (sin I/O):
    `calibrate(hypothesis, evidence, coherence_inputs, params, historical)
    -> ConfidenceCreate` computa S (pesos de quality_class_to_weight con signos
    +1/−1 según `explains`/`contradicts`), C (explanatory_coherence), el factor
    (1−ECE) desde el historial de outcomes de la clase y C_final. Sin historial
    → historical_calibration=1.0, ECE=0 (primeros datos, documentado).
    `calibration_justification` SIEMPRE documenta S, C, ECE, α, M, L₀ y cómo se
    derivó cada uno. `resolve_scope_evidence` sigue la cadena hypothesis →
    anomaly → context → evidence (read-only, P1). Anti-tuning: mismo input →
    mismo id y score (determinismo, testeado).
  - `src/service.py` - ciclo por tenant: `HypothesisStore.list_hypotheses` +
    `AnomalyStore.list_anomalies` + `ContextStore.list_contexts` +
    `EvidenceStore.list_evidence` → calibrator → `ConfidenceStore` (dedup
    idempotente). NUNCA escribe en `hypotheses`/`anomalies`/`contexts`/
    `evidence`/`observations` (P1), nunca lee el observation bus. No produce
    acciones (R3); su output habilita el Action Layer (R4). Métricas:
    `total_confidence_scores`, `total_confidence_duplicates`, `total_errors`,
    `confidence_by_target_type`, `mean_confidence_score`,
    `mean_calibration_error_estimate`.
  - `src/health.py` - `/health` y `/metrics` (observabilidad operativa).
  - `src/main.py` - `CONFIDENCE_HEALTH_PORT` (8095), `CONFIDENCE_CYCLE_SECONDS`,
    `CALIBRATION_ALPHA` (0.5), `CALIBRATION_ECE_BINS` (10); L₀ fijo en 0.
  - La API/Store ya soporta `target_type='recommendation'`/`'decision'`
    (Sprints 9/10) por el mismo path ConfidenceCreate/ConfidenceStore.
- Schema: tabla `confidence_scores` usada tal cual (ya existía). Se agregó el
  trigger `confidence_content_immutable_trigger`: contenido inmutable (P1) y
  DELETE bloqueado (audit trail persistente) — la fila no tiene flag de ciclo de
  vida (una re-calibración con nuevos inputs es una NUEVA fila, nunca un UPDATE).

### Correr Sprint 8

```bash
# 1. Infra (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. (solo si el schema es anterior al Sprint 8) aplicar el trigger de contenido:
#    ver infra/db-migrations/sprint8-confidence-content-trigger.sql ó el bloque
#    de prevent_confidence_content_update()/confidence_content_immutable_trigger
#    en 01-schema.sql

# 3. Correr el Confidence Calibrator (hypotheses + evidence -> confidence_scores)
PYTHONPATH="apps/services/confidence-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main

# 4. Verificar las confidence scores calibradas (S, C, 1-ECE, C_final, alpha,
#    justification, calibration_error_estimate por hypothesis)
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT target_type, evidential_support, explanatory_coherence, historical_calibration, confidence_score, alpha FROM confidence_scores;"

# 5. Métricas del calibrator
curl -s http://localhost:8095/metrics
```

El calibrator computa la Confidence de cada hipótesis candidata (S + C + ECE +
C_final) con parámetros fijos publicados, persistiendo filas completas en
`confidence_scores` (append-only, dedup idempotente). Contra el dataset real de
la sandbox sin hypotheses sembradas no produce filas (`total_confidence_scores=0`)
y no reporta errores; los tests de integración siembran una cadena completa para
verificar calibración ≥1 por hipótesis, dedup, trazabilidad confidence →
hypothesis → anomaly → pattern → context → evidence → observations y P1
(artefactos previos intactos tras el ciclo). Esta capacidad NO produce acciones
(R3) ni decide nada: habilita el Action Layer (R4) que llega en Sprints 9/10.

## Sprint 9: Recommendation Formulator (Action - Propose)

- `libs/action/recommendation.py` - **modelo Recommendation** (Action - Propose):
  `RecommendationCreate`/`Recommendation` (pydantic `frozen`, P1) espejo de la
  tabla `recommendations` (tenant_id, hypothesis_id, insight_id=NULL en el MVP,
  confidence_id, action_description, rationale, expected_consequences,
  alternatives_considered, confidence_score, status, proposed_at);
  `recommendation_id(tenant_id, hypothesis_id, confidence_id, action_description)`
  determinístico (uuid5, namespace propio `...081`) SIN `proposed_at` — mismos
  inputs → mismo id (dedup idempotente); el `confidence_id` se fija en el id, de
  modo que una nueva calibración de la misma hipótesis produce una NUEVA
  recomendación (append-only, P1). `RecommendationStore` (INSERT `ON CONFLICT
  (id) DO NOTHING`, `verify_connection`, `close`, `list_recommendations(tenant_id)`,
  `list_tenant_ids`). `status` es el ÚNICO campo flippable
  (proposed → accepted/rejected/superseded, ciclo decidido por Decision, Sprint 10).
- `libs/procedural_memory/action_space.py` - **Action Space Library** (Procedural
  Memory, declarativa): `ActionSpaceEntry` (dataclass frozen, `action_id`
  versionado `*_v1`), `domain` (storage/compute/security/backup/network/
  observability), `allowed_actions` (frozenset explícito), `purposes` (a qué
  propósitos aplica). Catálogo inicial según `docs/04-informes-seguridad.md`
  (FASE 6: p. ej. storage: expand_volume/add_disk/move_data/compress/purge_old/
  change_retention/enable_dedup; security: reset_credentials/revoke_sessions/
  enable_mfa/block_ip/isolate_host/rotate_keys; backup: retry_job/change_schedule/
  change_target/verify_integrity/test_restore; ...). `filter_action_space` limita
  el catálogo por dominios habilitados (flag de despliegue). La recomendación SOLO
  puede elegir acciones dentro del space explícito de su dominio/purpose.
- `apps/services/recommendation-service/` - **Recommendation Formulator** (R1:
  exactamente la capacidad Propose; NO calibra confidence ni commitea decisiones):
  - `src/formulator/formulator.py` - funciones PURAS (sin I/O):
    `formulate(hypothesis, confidence, context, action_space) -> RecommendationCreate`
    deriva el curso de acción que mejor sirve el propósito: resuelve el dominio
    (mapping declarativo mental_model→dominio con fallback por purpose),
    selecciona el action space explícito del dominio/purpose, elige la acción
    principal declarada (`LEADING_ACTION_BY_DOMAIN`) y construye
    `rationale` SIEMPRE trazable (cita contexto/hypothesis/confidence con hechos),
    `expected_consequences` observables y verificables, `alternatives_considered`
    (las demás acciones permitidas, cada una con rationale + rejected_reason +
    confidence del entendimiento compartido) y `confidence_score` = el calibrado
    de la hipótesis (R4; la recomendación NUNCA recalcula). `status='proposed'`
    (advisory, P6: no ejecuta nada). `resolve_active_context` sigue la cadena
    hypothesis → anomaly → context. Anti-orden: lenguaje propositivo, nunca
    "run now". Determinismo → dedup idempotente.
  - `src/service.py` - ciclo por tenant: `HypothesisStore.list_hypotheses` +
    `ConfidenceStore.get_confidence` (gate R4: solo hipótesis CON confidence
    calibrada) + `ContextStore.list_contexts` → formulator → `RecommendationStore`
    (dedup). NUNCA escribe en `hypotheses`/`anomalies`/`contexts`/`evidence`/
    `observations`/`confidence_scores` (P1), nunca lee el observation bus, no
    ejecuta acciones ni dispara alertas (P6). Métricas: `total_recommendations`,
    `total_recommendation_duplicates`, `total_hypotheses_without_confidence`,
    `total_hypotheses_without_context`, `total_hypotheses_without_action_space`,
    `total_errors`, `recommendations_by_status`, `recommendations_by_domain`.
  - `src/health.py` - `/health` y `/metrics` (observabilidad operativa).
  - `src/main.py` - `RECOMMENDATION_HEALTH_PORT` (8096),
    `RECOMMENDATION_CYCLE_SECONDS`, `ACTION_SPACE_DOMAINS` (flag de action space,
    vacío = todos los dominios).
- Schema: tabla `recommendations` usada tal cual (ya existía, vacía). Se agregó el
  trigger `recommendation_content_immutable_trigger` (P1): contenido inmutable una
  vez escrito (tenant/hypothesis/insight/confidence/action/rationale/consequences/
  alternatives/score/proposed_at) y DELETE bloqueado (audit trail persistente);
  `status` es el ÚNICO flippable. Migración idempotente
  `infrastructure/db-migrations/sprint9-recommendation-content-trigger.sql`.

### Correr Sprint 9

```bash
# 1. Infra (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. (solo si el schema es anterior al Sprint 9) aplicar el trigger de contenido:
#    ver infra/db-migrations/sprint9-recommendation-content-trigger.sql ó el bloque
#    de prevent_recommendation_content_update()/recommendation_content_immutable_trigger
#    en 01-schema.sql

# 3. Correr el Recommendation Formulator (hypotheses + confidence -> recommendations)
PYTHONPATH="apps/services/recommendation-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main

# 4. Métricas del formulator
curl -s http://localhost:8096/metrics
```

El formulator propone el curso de acción que mejor sirve al propósito actual
dentro del action space explícito de su dominio, SOLO para hipótesis con
Confidence calibrada (R4); la recomendación es advisory y reversible (P6), lleva
rationale trazable, expected_consequences observables, alternativas con rationale
y el confidence_score calibrado de la hipótesis (nunca recalcula). Contra el
dataset real de la sandbox sin hypotheses calibradas no produce filas
(`total_recommendations=0`) y no reporta errores; los tests de integración
siembran una cadena completa para verificar recomendaciones con `confidence_id`
NOT NULL, `status='proposed'`, dedup idempotente, trazabilidad recommendation →
hypothesis → confidence → anomaly → pattern → context → evidence → observations,
P1 (artefactos previos intactos tras el ciclo) y el skip de hipótesis sin
confidence (métrica `total_hypotheses_without_confidence`, sin filas).

## Sprint 10: Decision Committer (Action - Commit) — Gate Cognitivo Q1

- `libs/action/decision.py` - **modelo Decision** (Action - Commit):
  `DecisionCreate`/`Decision` (pydantic `frozen`, P1) espejo de la tabla
  `decisions` (tenant_id, recommendation_id, confidence_id, authority_id,
  commitment, expected_outcomes, risk_tolerance, status, committed_at,
  executed_at, actual_outcomes); `decision_id(tenant_id, recommendation_id,
  confidence_id)` determinístico (uuid5, namespace propio `...082`) SIN
  `committed_at` — mismos inputs → mismo id (dedup idempotente). `DecisionStore`
  (INSERT `ON CONFLICT (id) DO NOTHING`, `verify_connection`, `close`,
  `list_decisions(tenant_id)`, `list_tenant_ids`, `list_decisions_by_status`).
  `status`/`executed_at`/`actual_outcomes` son campos de ciclo de vida: el
  Learning loop (fases futuras) compara expected vs actual y puebla los
  outcomes; en el MVP la Decision se REGISTRA, nunca se ejecuta (P6).
- `libs/procedural_memory/decision_policy.py` - **Decision Policy Library**
  (Procedural Memory, declarativa): `DecisionPolicyEntry` (dataclass frozen,
  `policy_id` versionado `*_v1`, `domain`, `min_confidence_for_commit`=0.75,
  `min_confidence_irreversible`=0.9 según docs/03 "> 0.75 to commit; > 0.9 for
  irreversible", `allowed_risk_tolerance` por dominio, `requires_authority`).
  Catálogo canónico por dominio; `select_policy(domain)`,
  `apply_threshold_overrides` (env `DECISION_MIN_CONFIDENCE*` sin mutar el
  catálogo).
- `apps/services/decision-service/` - **Decision Committer** (R1: exactamente la
  capacidad Commit; NO forma recomendaciones ni calibra confidence):
  - `src/committer/committer.py` - funciones PURAS (sin I/O): `Authority`
    (authority_id + risk_tolerance), `policy_authority_id` (autoridad
    determinística del policy; Sprint 12 la reemplaza con usuarios reales),
    `recommendation_domain` (dominio del action space desde las alternativas),
    `resolve_risk_tolerance` (score → low/medium/high, acotado por el policy),
    `commit_eligibility` (COMMITTABLE / BELOW_CONFIDENCE / RISK_NOT_ALLOWED /
    NO_AUTHORITY / NO_POLICY), `commit(...)` → `DecisionCreate` con
    `commitment` DEFINITIVO (sin cláusula alternativa ni intención vaga), y
    `expected_outcomes` falsificables (prediction + verifiable_by + deadline,
    declarados ANTES de ejecutar, R5/Popper). P6: `status='committed'`,
    `executed_at=None`, `actual_outcomes=None`; no ejecuta nada.
  - `src/service.py` - ciclo por tenant: `RecommendationStore.list_recommendations`
    (solo `status='proposed'`) + `ConfidenceStore.list_confidence` (gate R4) +
    policy del dominio → committer → `DecisionStore` (dedup). NUNCA escribe en
    artefactos previos (P1), no lee el observation bus, no ejecuta acciones
    (P6). Métricas: `total_decisions`, `total_decision_duplicates`,
    `total_recommendations_below_confidence`, `total_recommendations_skipped`,
    `total_errors`, `decisions_by_status`, `decisions_by_risk_tolerance`.
  - `src/health.py` - `/health` y `/metrics`.
  - `src/main.py` - `DECISION_HEALTH_PORT` (8097), `DECISION_CYCLE_SECONDS`,
    `DECISION_MIN_CONFIDENCE` (0.75), `DECISION_MIN_CONFIDENCE_IRREVERSIBLE`
    (0.9).
- Schema: tabla `decisions` usada tal cual (ya existía, vacía). Se agregó el
  trigger `decision_content_immutable_trigger` (P1): CONTENIDO inmutable una vez
  escrito (id/tenant/recommendation/confidence/authority/commitment/
  expected_outcomes/risk_tolerance/committed_at) y DELETE bloqueado; son
  CICLO DE VIDA flippable `status` (committed → executing/completed/rolled_back)
  y `executed_at`/`actual_outcomes` (poblados solo por el Learning loop).
  Migración idempotente
  `infrastructure/db-migrations/sprint10-decision-content-trigger.sql`.
- **Gate cognitivo Q1 alcanzado**: primera Decision commitida sobre la sandbox
  con expected outcomes falsificables (prediction + verifiable_by + deadline) y
  la cadena de trazabilidad decision → recommendation → confidence →
  hypothesis → anomaly → pattern → context → evidence → observations completa.

### Correr Sprint 10

```bash
# 1. Infra (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. (solo si el schema es anterior al Sprint 10) aplicar el trigger de contenido:
#    ver infra/db-migrations/sprint10-decision-content-trigger.sql ó el bloque
#    de prevent_decision_content_update()/decision_content_immutable_trigger
#    en 01-schema.sql

# 3. Correr el Decision Committer (recommendations + confidence -> decisions)
PYTHONPATH="apps/services/decision-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main

# 4. Métricas del committer
curl -s http://localhost:8097/metrics
```

El committer convierte la Recommendation (oferta advisory, P6) en una Decision
commitida SOLO si su Confidence calibrada supera el umbral del policy del
dominio (R4; ≥0.75 commit, ≥0.9 irreversible) y el risk_tolerance es permitido;
el `commitment` es una sentencia definitiva con owner (autoridad) y timeline,
los `expected_outcomes` son predicciones falsificables en términos observables
(prediction + verifiable_by + deadline) declaradas ANTES de ejecutar (R5), y la
traza completa queda registrada. La re-corrida sobre los mismos inputs no duplica
filas (dedup por id determinístico) y los artefactos previos quedan intactos
(P1: el servicio solo escribe en `decisions`). En la sandbox real sin
recomendaciones propuestas no commitea nada (`total_decisions=0`) y no reporta
errores; los tests de integración siembran la cadena completa para verificar
decisiones `status='committed'`, falsifiabilidad, dedup, trazabilidad, el skip
de recomendaciones con confidence < umbral (métrica
`total_recommendations_below_confidence`, sin filas) y el trigger que bloquea
cambios de contenido pero permite el ciclo de vida
(status/executed_at/actual_outcomes).

## Sprint 11: Report Generator (Action - Report, output document) — FASE 6

- `libs/action/report.py` - **modelo Report** (output-document family del Action
  Layer): `ReportCreate`/`Report` (pydantic `frozen`) espejo de la tabla
  `reports` (tenant_id, report_type, title, summary, content, ai_generated,
  model_used, period_start, period_end, generated_at, file_path);
  `report_id(tenant_id, report_type, period_start, period_end)` determinístico
  (uuid5, namespace propio `...083`) SIN `generated_at` ni `content` — mismos
  inputs → mismo id (dedup idempotente `ON CONFLICT DO NOTHING`).
  `ReportStore` (INSERT idempotente, `report_exists`, `list_reports(tenant_id,
  report_type=None)`, `get_report(id)`, `list_tenant_ids`, `get_tenant`,
  `verify_connection`, `close`). El módulo es explícitamente NO-canónico
  (ADR-0002): SOLO formatea lo que el flujo cognitivo ya commiteó y escribe en
  su tabla propia `reports`; nunca genera juicios ni toca las tablas cognitivas
  (P1). `ai_generated=False`/`model_used=None` en este MVP (render local por
  templates; LM Studio llega en un sprint futuro).
- `apps/services/report-service/` - **Report Generator** (formatea, no razona):
  - `src/renderers/common.py` - `ReportSource` (dataclass con los artefactos
    leídos: decisions, recommendations, contexts, confidences, hypotheses,
    anomalies, patterns, evidence, observations, tenant, period, generated_at),
    `as_jsonable` (serializa pydantic → dict, fechas ISO), `build_decision_traces`
    (correlaciona decision → recommendation → confidence → hypothesis →
    anomaly → pattern → context → evidence → observations),
    `latest_confidence_for(hypothesis)`.
  - `src/renderers/executive.py` - `render_executive(source)` PURA: Top
    Decisions (commitment, risk_tolerance, confidence, expected_outcome_count,
    acción de la recommendation), `pending_authority` (solo risk_tolerance
    "high"), `future_risks` (hypotheses con confidence_score >
    `risk_threshold`, default 0.6). NUNCA inventa costes/ROI: solo lo que el
    flujo commiteó.
  - `src/renderers/technical.py` - `render_technical(source)` PURA: secciones
    1-7 (Cognitive Trace, Anomalies, Patterns, Confidence Calibration,
    Reasoning Chain, Decision & Expected Outcomes, Evidencia/Context).
  - `src/renderers/json_render.py` - `render_json(source)` PURA: estructura
    exacta de `build_decision_traces` (formato máquina).
  - `src/renderers/formatters.py` - I/O: `to_html` (jinja2), `to_pdf`
    (weasyprint), `to_json`. Renderers puros vs formatters con I/O.
  - `src/service.py` - ciclo por tenant: lee Decisiones/Recomendaciones/
    Contexts/Confidences/Hypotheses/Anomalies/Patterns/Evidence/Observations →
    period = rango de `committed_at` (min..max, hoy si vacío) → render →
    formatter → `ReportStore.save_report` (dedup). Métricas: `total_reports`,
    `total_report_duplicates`, `total_errors`, `by_type`,
    `render_duration_seconds`, `last_run_at`.
  - `src/health.py` - `/health`, `/metrics`, `POST /api/v1/reports/generate`
    (tenant opcional, type executive/technical/json), `GET /api/v1/reports`.
  - `src/main.py` - `REPORT_HEALTH_PORT` (8098), `REPORT_CYCLE_SECONDS`,
    `REPORT_OUTPUT_DIR`.
- `libs/perception/store.py` - se agregó `ObservationStore.list_observations`
  (READ) para completar la traza de evidencia en los reportes.
- Schema: tabla `reports` usada tal cual (ya existía, vacía). Se agregó el
  trigger `report_content_immutable_trigger` (cumplimiento de P1 en el output
  NO-canónico): contenido inmutable una vez escrito y DELETE bloqueado.
  Migración idempotente
  `infrastructure/db-migrations/sprint11-report-content-trigger.sql`.
- **FASE 6 iniciada**: el Report Generator formatea Decisiones/Recomendaciones/
  Confidences y la cadena de trazabilidad completa en documentos ejecutivo,
  técnico y JSON, con dedup idempotente por periodo y sin escribir jamás en las
  tablas cognitivas.

### Correr Sprint 11

```bash
# 1. Infra (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. (solo si el schema es anterior al Sprint 11) aplicar el trigger de contenido:
#    ver infra/db-migrations/sprint11-report-content-trigger.sql ó el bloque
#    de prevent_report_content_update()/report_content_immutable_trigger
#    en 01-schema.sql

# 3. Correr el Report Generator (solo lee las tablas cognitivas, escribe `reports`)
PYTHONPATH="apps/services/report-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main

# 4. Generar un reporte ejecutivo para la sandbox
curl -s -X POST "http://localhost:8098/api/v1/reports/generate?type=executive&tenant_id=00000000-0000-0000-0000-000000000001"

# 5. Listar los reportes generados
curl -s "http://localhost:8098/api/v1/reports?tenant_id=00000000-0000-0000-0000-000000000001"

# 6. Métricas del generator
curl -s http://localhost:8098/metrics
```

El Report Generator formatea EXACTAMENTE lo que el flujo cognitivo commiteó
(Decision → Recommendation → Confidence → Hypothesis → Anomaly → Pattern →
Context → Evidence → Observations): un reporte con 0 decisiones produce un
documento limpio "0 decisiones", nunca inventa contenido (ADR-0002). La
re-generación del mismo reporte del mismo periodo no duplica filas (dedup por
id determinístico) y los artefactos previos quedan intactos (P1: el servicio
solo escribe en `reports`). En la sandbox real sin decisiones no genera nada
(`total_reports=0`) y no reporta errores; los tests de integración siembran la
cadena completa para verificar el contenido formateado, la inmutabilidad del
trigger, el dedup y que las tablas cognitivas no se tocan.

## Sprint 12: Multi-tenant + Auth + RBAC (Decision Authority — Capacidad Externa)

El **user-service** (JWT/roles por tenant) y el **API Gateway** (enforcement del
Cognitive Boundary, R3) cierran el bloque **Q1**: pipeline completo + autoridad
+ boundary. Ambos son capacidades EXTERNAS no-canónicas (**ADR-0002**): autorizan
y protegen el acceso al flujo canónico, NUNCA producen juicios cognitivos y NUNCA
ejecutan el pipeline. El RBAC se modela como **Decision Authority binding**
(core-concepts/decision.md: *the commitment authority under which a Decision was
taken*), no como "tabla de permisos" (docs/04).

- `libs/access/` - **Access layer** (compartida por user-service y gateway):
  - `security.py` - bcrypt (hash/verify) + JWT (HS256 dev / RS256 prod) con
    claims de identidad + rol + tenant. **Hallazgo**: `passlib 1.7.4` es
    incompatible con `bcrypt>=4.1` (usa `bcrypt.__about__.__version__`,
    eliminado); se usa el paquete `bcrypt` directamente (sin dep nueva).
  - `rbac.py` - matriz **roles × permisos** (docs/04): viewer (READ de
    context/recommendations/decisions/reports; NO propose/commit/execute),
    operator (+ACK, NO propose/commit), admin (READ + PROPOSE + COMMIT en
    tenant con risk low/medium + define políticas), superadmin (todo +
    cross-tenant + high risk + execute). Constantes puras testeadas celda a
    celda; `commit_risk_allowed` y `tenant_scope` (aislamiento multi-tenant).
  - `users.py` - modelo `User` + `UserStore` (tabla `users`, por tenant;
    email UNIQUE global; hash bcrypt nunca plaintext; queries siempre
    scoped por `tenant_id`).
  - `errors.py` - `InvalidTokenError` (401), `AuthorizationError`/
    `TenantIsolationError` (403), `UserConflictError` (409).
- `apps/services/user-service/` - **Auth/RBAC service** (externa, ADR-0002):
  - `POST /api/v1/auth/login` (email+password → access+refresh), `POST
    /api/v1/auth/refresh` (stateless), `POST /api/v1/users` (admin/superadmin,
    aislamiento por tenant), `GET /api/v1/me`, `GET /api/v1/users` (admin+,
    tenant scope). Tokens con rol+tenant; `authority_id` de las Decisiones
    (Sprint 10) ahora referenciable a `users.id` reales.
  - Métricas `/metrics`: `total_logins`, `total_login_failures`,
    `total_tokens_issued`, `total_errors`, `users_by_role`. Puerto
    `USER_HEALTH_PORT=8099`.
- `apps/gateway/api-gateway/` - **Cognitive Boundary enforcement** (R3):
  - `src/boundary.py` - reglas puras del boundary (docs/04
    `cognitive_boundary.yaml`): flujo canónico observación→evidencia→contexto→
    patrón→anomalía→hipótesis→insight→recomendación→decisión (sin atajos;
    observations nunca expuestas a Reasoning/Action; Pattern/Anomaly/Hypothesis
    nunca gatillan acciones) + validación de Confidence presente (R4).
  - `POST /api/v1/actions/{action}` (commit/propose/ack/execute) - valida rol +
    boundary + confidence; NUNCA ejecuta (la ejecución es el ciclo canónico de
    cada servicio). 401 sin token, 403 rol sin autoridad, 400 boundary.
  - READ protegidas por rol con aislamiento por tenant: `GET
    /api/v1/tenants/{tenant_id}/decisions`, `/reports`, `GET
    /api/v1/services/health` (forward a los /health del pipeline). Puerto
    `GATEWAY_HEALTH_PORT=8100`.
- Schema: tablas `users` (id, tenant_id FK, email UNIQUE, password_hash bcrypt,
  name, role CHECK viewer/operator/admin/superadmin, is_active, created_at,
  updated_at) + `idx_users_tenant_email(tenant_id, email)` en `01-schema.sql`;
  seed del admin sandbox (password dev documentado) en `02-seed.sql`; migración
  idempotente `infrastructure/db-migrations/sprint12-users-tables.sql`. `users`
  es dato externo (ADR-0002): MUTABLE por diseño, sin trigger P1. `decisions`
  sin cambios (authority_id queda UUID libre).
- **Estrategia refresh**: JWT stateless (access + refresh firmados, exp propia;
  sin tabla `refresh_tokens` ni token store en Redis) — documentada.

### Correr Sprint 12

```bash
# 1. Infra + seed (postgres 5433, redis 6379)
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 2. (solo si el schema es anterior al Sprint 12) aplicar la migración:
psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" \
  -f infrastructure/db-migrations/sprint12-users-tables.sql

# 3. Correr el user-service (auth/RBAC)
JWT_ALGORITHM=HS256 JWT_SECRET_KEY=dev-secret \
PYTHONPATH="apps/services/user-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main   # puerto 8099

# 4. Login del admin sandbox (password dev: cosmonitor)
curl -s -X POST http://localhost:8099/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@sandbox.local","password":"cosmonitor"}'

# 5. /me con el token (perfil + rol) y 401 sin token
curl -s http://localhost:8099/api/v1/me -H "Authorization: Bearer <ACCESS_TOKEN>"

# 6. Correr el API Gateway (Cognitive Boundary, R3)
PYTHONPATH="apps/gateway/api-gateway:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main   # puerto 8100

# 7. Viewer commit -> 403; admin commit low con confidence -> 200 (nunca ejecuta)
curl -s -X POST http://localhost:8100/api/v1/actions/commit \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"confidence_score":0.85,"risk_tolerance":"low"}'

# 8. Métricas
curl -s http://localhost:8099/metrics && curl -s http://localhost:8100/metrics
```

La autorización NO es un fin en sí: existe para que cada Decision/acción tenga
un **authority binding** auditable y verificable (R5). El gateway enforza que
los componentes del pipeline solo se llamen según el flujo canónico y que
ninguna capacidad externa ejecute acción sin autorización (R3). Ningún juicio
cognitivo pasa por auth/RBAC (test estructural ADR-0002: `libs/access` no
importa el pipeline). El siguiente bloque es **H1** (Sprint 13+): Insight,
calibración histórica, Procedural Memory v2 y patrones avanzados.

## Cognitive Compliance

Cada sprint valida:
- [x] **R1**: Exactly one cognitive capability per component
- [x] **R2**: Cognitive Contract (Input→Transform→Output) tested
- [x] **R3**: Cognitive Boundary enforced
- [x] **R4**: No action without Confidence
- [x] **R5**: Decisions with falsifiable outcomes
- [x] **P1**: Observations immutable, never interpreted
- [x] **P5**: Confidence computed (S+C+ECE), params published

## Política de citación canónica (Cognitive Citation Policy)

Las citas al marco Company OS usan exclusivamente el set canónico:

- **Principios**: P1–P7 (`cognitive-principles.md`)
- **Design rules**: R1–R7 (`cognitive-architecture.md`)
- **Conceptos**: nombres de `cognitive-lexicon/core-concepts/*.md`
- **ADR**: ADR-0001 (Company OS es el cerebro), ADR-0002 (COS-Monitor es el producto)

Regla: **nada fuera de la policy se escribe.** Toda referencia al marco debe
mapear a un elemento canónico existente. No se inventan números de regla
(R8/R9/R10), no se usa la numeración R1–R10 de `ontology.md` (colisiona con
R1–R7), y la trazabilidad/objetividad/provenance se describen sin número de
regla. Enforcement para sesiones de agente: `AGENTS.md`.

## Documentación

- `docs/01-fundacion-arquitectura.md` - FASE 1-2: Pipeline cognitivo, DB schema
- `docs/02-motor-recoleccion.md` - FASE 3: Perception Layer (agentes, collector)
- `docs/03-predictivo-ia-local.md` - FASE 4-5: Reasoning + Learning + LM Studio
- `docs/04-informes-seguridad.md` - FASE 6-7: Action Layer + Security as Procedural Memory
- `docs/05-negocio-roadmap-backlog.md` - FASE 8-10: Roadmap, backlog, OKRs cognitivos