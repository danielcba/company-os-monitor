# COS-Monitor (Company OS Monitor)

Versión: 1.0
Estado: Oficial

---

## ¿Qué es COS-Monitor?

COS-Monitor es una plataforma SaaS para monitoreo, análisis y diagnóstico automático de infraestructura IT, construida sobre el framework de arquitectura cognitiva Company OS.

Implementa el pipeline cognitivo canónico — **Percepción → Razonamiento → Aprendizaje → Acción** — como un conjunto de servicios independientes, cada uno con exactamente una capacidad cognitiva. Desde las observaciones crudas hasta las decisiones commiteadas, cada artefacto es inmutable y totalmente trazable.

COS-Monitor no es solo un recolector de datos. Construye la cadena cognitiva desde las observaciones crudas hasta recomendaciones calibradas y decisiones commiteadas, preservando un registro inmutable y totalmente trazable en cada paso:

- Qué fue observado (hechos)
- Cómo se organizó en evidencia
- Qué contexto explica mejor la evidencia
- Qué patrones y anomalías detecta la capa de razonamiento
- Qué hipótesis testables se proponen (nunca se concluye)
- Qué confianza ha ganado cada hipótesis
- Qué acción se recomienda, y qué decisión se commitea — con resultados esperados falsificables

---

## ¿Por qué existe?

La mayoría de las plataformas de monitoreo producen alertas. Muy pocas producen *entendimiento*.

Las organizaciones necesitan un sistema que no solo recolecte señales de su infraestructura, sino que razone sobre ellas de forma disciplinada:

- ¿Qué cuenta como un hecho, y cómo se captura sin interpretación?
- ¿Cómo se organiza la evidencia a partir de observaciones crudas?
- ¿Cómo se selecciona la explicación más coherente entre modelos en competencia?
- ¿Cuándo está justificada la confianza, y cómo se calibra?
- ¿Cómo se convierte una recomendación en una decisión commiteada de la que se pueda aprender?

COS-Monitor existe para responder estas preguntas con precisión, de modo que cada agente, cada servicio y cada operador humano en la plataforma razone usando la misma arquitectura cognitiva.

La convicción central:

> La arquitectura guía el código, nunca al revés.

---

## Arquitectura Cognitiva

COS-Monitor implementa el pipeline canónico: **Perception → Reasoning → Confidence → Action**.

| Capa | Capacidad Cognitiva | Concepto | Servicio |
|------|---------------------|----------|----------|
| Perception | Observation Capture | Observation | linux-agent, windows-agent, vmware-agent |
| Perception | Evidence Organization | Evidence | collector-service |
| Perception | Context Activation | Context | context-service |
| Reasoning | Pattern Detection | Pattern | pattern-service |
| Reasoning | Anomaly Detection | Anomaly | anomaly-service |
| Reasoning | Hypothesis Generation | Hypothesis | hypothesis-service |
| Reasoning | Insight Restructuring | Insight | insight-service |
| Reasoning | Hypothesis Evaluation | — | evaluation-service |
| Learning | Confidence Calibration | Confidence | confidence-service |
| Action | Recommendation | Recommendation | recommendation-service |
| Action | Decision | Decision | decision-service |
| Action | Report (documento de salida) | — | report-service |
| Externa (no-canónica) | Decision Authority, Cognitive Boundary | — | user-service, api-gateway |

Disciplina de diseño:

- **Una capacidad por componente**: cada servicio implementa exactamente una capacidad cognitiva; los servicios están separados entre sí y nunca bypassan el flujo canónico.
- **Contrato Cognitivo**: cada componente expone un contrato Input → Transform → Output testeado.
- **Cognitive Boundary**: los componentes del pipeline solo se invocan según el flujo canónico; las capacidades externas nunca producen juicios cognitivos ni ejecutan el pipeline.
- **No hay acción sin confianza**: el Action Layer está gateado por Confidence calibrada (recomendación → decisión), y ambas son fases futuras del Learning loop.
- **Inmutabilidad**: observaciones, evidencia, contextos, patrones, anomalías, hipótesis, confidence scores, recomendaciones, decisiones y reportes son append-only; el contenido nunca se muta, solo los campos de ciclo de vida pueden cambiar.

---

## El Flujo Cognitivo

```
Realidad → Observación → Evidencia → Contexto → Patrón → Anomalía
       → Hipótesis → Confianza → Recomendación → Decisión
       → Reporte → Memoria (consolidación, pattern_refinement, context_revision,
                           insight_transformation read/compute operativas;
                           learning_memory ledger append-only, autorizada)
```

Cada paso consume solo los artefactos de los pasos anteriores (conocimiento), nunca observaciones crudas después de Perception, y nunca produce acción antes de Confidence.

---

## Estructura del Repositorio

```
company-os-monitor/
├── apps/
│   ├── agents/               # Observation Capturers (Perception)
│   │   ├── linux-agent/
│   │   ├── windows-agent/
│   │   └── vmware-agent/
│   ├── services/             # Servicios cognitivos (una capacidad cada uno)
│   │   ├── collector-service/
│   │   ├── context-service/
│   │   ├── pattern-service/
│   │   ├── anomaly-service/
│   │   ├── hypothesis-service/
│   │   ├── insight-service/
│   │   ├── confidence-service/
│   │   ├── recommendation-service/
│   │   ├── decision-service/
│   │   ├── evaluation-service/
│   │   ├── report-service/
│   │   └── user-service/
│   └── gateway/
│       └── api-gateway/
├── libs/
│   ├── cognitive-core/       # Contratos, modelo de calibración, bus, tool LM Studio
│   ├── perception/           # Observation, Evidence, Context (stores + activator)
│   ├── reasoning/            # Pattern, Anomaly, Hypothesis, Insight
│   ├── learning/             # Confidence, Memory
│   ├── action/               # Recommendation, Decision, Report
│   ├── access/               # Security, RBAC, users, errors
│   └── procedural-memory/    # Librerías Pattern, Tolerance, Hypothesis Template,
│                             #   Action Space y Decision Policy
├── infrastructure/
│   ├── docker/               # Docker Compose, SQL de init (schema + seed)
│   └── db-migrations/        # Migraciones idempotentes por sprint
├── docs/                     # Documentos de arquitectura y dominio
├── journal/                  # Registros de progreso y descubrimientos
└── tests/                    # Tests de contrato, integración y calibración
```

---

## Quick Start

```bash
# 1. Copiar el entorno
cp .env.example .env

# 2. Levantar la infraestructura (postgres 5433, redis 6379) + seed del tenant sandbox
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 3. Verificar la base de datos
docker compose -f infrastructure/docker/docker-compose.yml exec postgres pg_isready -U cosmonitor

# 4. Correr el linux-agent (desarrollo)
cd apps/agents/linux-agent
pip install --break-system-packages -e ".[dev]"
python -m src.main

# 5. Verificar las observaciones en Redis
docker compose -f infrastructure/docker/docker-compose.yml exec redis redis-cli XRANGE observations COUNT 5
```

El tenant sandbox (`TENANT_ID` default) debe existir en `tenants` (seed: `02-seed.sql`). Los agentes Windows/VMware requieren un host WinRM/vCenter real.

---

## Hoja de Ruta

### Fase 1 — Fundación (Completada)

- [x] Estructura del repositorio, pipeline cognitivo, DB schema
- [x] Contratos cognitive-core y observation bus

### Fase 2 — Perception Layer (Completada)

- [x] Recolección multi-agente (Linux, Windows/WMI, VMware) con persistencia en Postgres
- [x] Evidence Organizer con evidencia inmutable y append-only
- [x] Context Activator con competencia de coherencia explicativa

### Fase 3 — Reasoning Layer (Completada)

- [x] Pattern Detector
- [x] Anomaly Detector
- [x] Hypothesis Generator (templates + IA local opcional como herramienta externa)

### Fase 4 — Learning + Action Layer (Completada — Gate Cognitivo Q1)

- [x] Confidence Calibrator (S + C + ECE + score final)
- [x] Recommendation Formulator (gateado por confianza)
- [x] Decision Committer (resultados esperados falsificables)

### Fase 5 — Salida + Seguridad

- [x] Report Generator (ejecutivo, técnico, JSON)
- [x] Multi-tenant + Auth + RBAC + API Gateway (Cognitive Boundary)
- [x] Insight Restructuring (Insight)
- [x] Calibración histórica y Memory / Learning loop
- [x] Procedural Memory v1 (pattern_library, tolerance_library, hypothesis_templates, action_space, decision_policy, insight_rules)

---

## Implementación

### Fundación (Sprint 1)

Estructura inicial de la plataforma: `apps/`, `libs/`, `infrastructure/`, `tests/`, y los contratos cognitive-core con el observation bus canónico. DB schema para las tablas cognitivas (`observations`, `evidence`, `contexts`, `patterns`, `anomalies`, `hypotheses`, `confidence_scores`, `recommendations`, `decisions`, `reports`) más el seed de `tenants`.

### Sprint 2 — Recolección Multi-Agent + Persistencia en Postgres

- `windows-agent` — Observation Capturer (WMI sobre WinRM): CPU, memoria, discos, servicios detenidos (Auto), evento log de Error/Critical
- `vmware-agent` — Observation Capturer (vSphere API/pyVmomi): datastores, VM power states, snapshots, ESXi host health
- `collector-service` — entrada del Evidence Organizer: consume `observations` desde Redis Streams y las persiste (INSERT append-only) en Postgres; ack solo tras INSERT
- Inmutabilidad: trigger de BD bloquea UPDATE/DELETE en `observations`
- Idempotencia: la re-entrega de mensajes no duplica filas (dedup por observation id)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/collector-service:." python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor -c "SELECT fact_type, count(*) FROM observations GROUP BY fact_type;"
```

### Sprint 3 — Evidence Organizer (Perception · Organize)

- `libs/perception/evidence.py` — `EvidenceStore` append-only para la tabla `evidence`: INSERT + dedup idempotente (ON CONFLICT por id determinístico), `verify_connection`, `close`
- Inmutabilidad: trigger de BD bloquea UPDATE/DELETE en `evidence`
- `apps/services/collector-service/src/organizer/` — reglas de organización por dominio (funciones puras sobre Observaciones inmutables):
  - `resource_exhaustion_evidence` (cpu>90% + mem>85% + disk>85%, misma fuente, 5 min)
  - `service_degradation_evidence` (servicio Stopped/Auto + evento Error, 15 min)
  - `auth_anomaly_evidence` (lockout AD + cambio de membresía privilegiada, 1 h)
  - `backup_failure_evidence` (job Failed + repo_free<10%, 1 h)
  - `vmware_capacity_evidence` (datastore_free<15% + snapshot>7d, 30 min)
  - `network_anomaly_evidence` (interface_errors>umbral + port_state_change, 15 min)
  - `description` objetiva/factual, `quality_class` Q1-Q4 y `weight` w_i asignados EN LA CREACIÓN (Q1→0.875, Q2→0.625, Q3→0.375, Q4→0.125, midpoints exactos de las bandas); sin retrofitting
- Orquestación en el collector: tras persistir cada lote de observaciones, el organizador corre sobre el buffer por ventana/tenant y escribe `evidence` (dedup idempotente). Métricas de organizaciones en `/metrics` (`total_evidence`, `total_evidence_duplicates`, `total_evidence_errors`, `evidence_by_type`)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/collector-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor -c "SELECT organization_type, quality_class, weight FROM evidence;"
curl -s http://localhost:8090/metrics
```

La ventana/umbrales por dominio son configurables via env (`RESOURCE_EXHAUSTION_WINDOW_MINUTES`, `NETWORK_ANOMALY_ERROR_THRESHOLD`, etc., ver `.env.example`). Los agentes pueden publicar observaciones sintéticas al bus para disparar las reglas durante desarrollo.

### Sprint 4 — Context Activator (Perception · Explain)

- `libs/perception/context.py` — catálogo declarativo de **modelos mentales** (`MentalModel`, dataclass frozen, NO razonamiento) mapeando a los `organization_type` de Sprint 3 para los purposes `infrastructure_health`, `security_posture` y `capacity_management`:
  - `resource_pressure` → `resource_exhaustion_evidence`
  - `service_failure` → `service_degradation_evidence`
  - `auth_compromise` → `auth_anomaly_evidence`
  - `capacity_risk` → `backup_failure_evidence` + `vmware_capacity_evidence`
  - `connectivity_degradation` → `network_anomaly_evidence`
- Mismo módulo: `Context` (pydantic `frozen`), `context_id()` determinístico (uuid5 tenant+purpose+evidence_ids) y `ContextStore` (INSERT append-only con `ON CONFLICT (id) DO NOTHING`, dedup idempotente). El contenido (evidence_ids, mental_model_id, purpose, coherence_score, competing_models) es inmutable; `is_active` es campo de ciclo de vida: activar un contexto nuevo desactiva el previo del mismo tenant+purpose
- `apps/services/context-service/` — **Context Activator** (exactamente la capacidad Explain, separado del collector):
  - `src/activator/coherence.py` — competencia de coherencia explicativa (funciones puras): por tenant+purpose, cada modelo candidato explica la fracción de peso de evidencia que cubre su firma; gana el de mayor `coherence_score` (empates → desempate determinístico por model_id). Sin interpretación ni causalidad
  - `src/activator/engine.py` — `ActivatorEngine` (puro): batch de Evidence → `ContextCreate` con ganador + `competing_models` (todos los candidatos con sus scores)
  - `src/service.py` — orquestación: lee evidence de Postgres por tenant, corre la competencia por cada purpose, escribe el Active Context (dedup; desactiva el previo). Métricas: `total_contexts`, `total_context_duplicates`, `total_errors`, `contexts_by_mental_model`, `contexts_by_purpose`
  - `src/health.py` — `/health` y `/metrics`
- Schema: tabla `contexts` usada tal cual; trigger `context_content_immutable_trigger` bloquea UPDATE de columnas de contenido y DELETE (permite el flip de `is_active`)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/context-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT tenant_id, mental_model_id, purpose, coherence_score, competing_models, is_active FROM contexts;"
curl -s http://localhost:8091/metrics
```

### Sprint 5 — Pattern Detector (Reasoning · Generalize)

- `libs/procedural_memory/pattern_library.py` — **Pattern Library** (memoria procedimental, definiciones DECLARATIVAS, no razonamiento): `PatternDefinition` (dataclass frozen) con `pattern_id` versionado (`_v1`/`_v2`), `pattern_type` (MVP solo `temporal`; `correlation`/`sequential`/`threshold` reservados), `scope_mental_models`, `scope_purposes` (vacío = todos), `min_occurrences`, `strength_threshold`, `frequency_label` y `description_template` FACTUAL. El catálogo cubre los 5 mental models de Sprint 4. Revisar un patrón = publicar una NUEVA versión (`_v2`), nunca mutar la publicada
- `libs/reasoning/pattern.py` — modelo `Pattern` (pydantic `frozen`) con `pattern_id()` determinístico (uuid5 tenant + context_id + library_pattern_id; la versión del library queda trazable en el id, y `detected_at` queda FUERA del id para la idempotencia) y `PatternStore` (INSERT append-only, `ON CONFLICT (id) DO NOTHING`, `list_patterns`, `list_tenant_ids`)
- `libs/perception/context.py` — nuevos READS en `ContextStore`: `list_contexts(tenant_id)` devuelve TODAS las activaciones ordenadas por `activated_at` (el stream continuo de Context, no solo `is_active = true`) y `list_tenant_ids()`
- `apps/services/pattern-service/` — **Pattern Detector** (exactamente la capacidad Generalize, separado del collector y del context-service):
  - `src/detector/detector.py` — funciones PURAS (sin I/O): por cada `PatternDefinition`, agrupa las activaciones por scope (mental_model_id, purpose) dentro de la ventana (`DETECTION_WINDOW_DAYS`); `strength_measure = min(occurrences / max(min_occurrences, 1), 1.0)`; emite Candidate Pattern solo si `strength >= strength_threshold`; `frequency` derivada del intervalo mediano entre activaciones (hourly/daily/weekly/event-driven); ancla a la activación más reciente. `description` solo factual
  - `src/service.py` — ciclo por tenant: `ContextStore.list_contexts` → detector → `PatternStore` (dedup idempotente). NUNCA escribe en `contexts`/`evidence`/`observations`, nunca lee el observation bus
  - `src/health.py` — `/health` y `/metrics` (`total_patterns`, `total_pattern_duplicates`, `total_candidates_below_threshold`, `total_errors`, `patterns_by_type`, `patterns_by_mental_model`)
- Schema: tabla `patterns` usada tal cual; trigger `pattern_content_immutable_trigger` (bloquea UPDATE de contenido y DELETE; permite el flip de `is_active`)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/pattern-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT tenant_id, pattern_type, strength_measure, frequency, description FROM patterns;"
curl -s http://localhost:8092/metrics
```

### Sprint 6 — Anomaly Detector (Reasoning · Detect Deviation)

- `libs/reasoning/anomaly.py` — modelo `Anomaly` (pydantic `frozen`) con `anomaly_id()` determinístico (uuid5 tenant + context_id + pattern_id; `detected_at` FUERA del id) y `AnomalyStore` (append-only, dedup idempotente, `list_anomalies`, `list_tenant_ids`)
- `libs/procedural_memory/tolerance_library.py` — **Tolerance Library** (memoria procedimental, umbrales EXPLÍCITOS, auditable, purpose-dependent; NO razonamiento): `ToleranceDefinition` (dataclass frozen, versionada `_v1`/`_v2`) con `pattern_type` (MVP `temporal`), `scope_mental_models`, `scope_purposes`, `anomaly_class` (MVP `point`; contextual/collective reservados), `deviation_spec` (`days_off_schedule`, `count_exceeding_window`) y `threshold`. Un tolerance por cada PatternDefinition de Sprint 5; esquemas de desviación documentados y testeados con valores conocidos
- `libs/perception/context.py` — nuevo READ `list_active_contexts(tenant_id)` (Active Contexts, `is_active = true`)
- `apps/services/anomaly-service/` — **Anomaly Detector** (exactamente la capacidad Detect Deviation, separado de pattern-service):
  - `src/detector/detector.py` — funciones PURAS: para cada Active Context, el patrón esperado es el más reciente de `patterns` para su scope; SIN patrón NO hay desviación (el concepto Anomaly es relativo a patrones, nunca absoluto → métrica `contexts_without_pattern`); `deviation_score` según `deviation_spec`; Candidate Anomaly solo si `deviation_score > tolerance_threshold`. `rationale` FACTUAL (señal, no conclusión)
  - `src/service.py` — ciclo por tenant: `list_active_contexts` + `list_patterns` → detector → `AnomalyStore`. NUNCA escribe en artefactos previos; nunca lee el observation bus. Métricas: `total_anomalies`, `total_anomaly_duplicates`, `total_contexts_without_pattern`, `total_errors`, `anomalies_by_class`, `anomalies_by_mental_model`
  - `src/main.py` — tolerancias configurables por despliegue vía `TOLERANCE_*_THRESHOLD` (defaults canónicos en la library)
- Schema: tabla `anomalies` usada tal cual; trigger `anomaly_content_immutable_trigger` bloquea TODO UPDATE/DELETE (sin flag de ciclo de vida; misma política que `evidence`)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/anomaly-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT tenant_id, context_id, pattern_id, deviation_score, tolerance_threshold, anomaly_class FROM anomalies;"
curl -s http://localhost:8093/metrics
```

### Sprint 7 — Hypothesis Generator (Reasoning · Predict)

- `libs/reasoning/hypothesis.py` — modelo `Hypothesis` (pydantic `frozen`) con `hypothesis_id()` determinístico (uuid5 tenant + anomaly_ids + pattern_ids + descripción; la descripción entra en el hash para que DOS hipótesis competidoras sobre la misma anomalía tengan ids distintos; `generated_at` FUERA del id) y `HypothesisStore` (append-only, dedup idempotente, `list_hypotheses`, `list_tenant_ids`). `status` es campo de ciclo de vida (`candidate`/`confirmed`/`falsified`): el generador SIEMPRE emite `candidate` (confirmar/falsificar requiere evidencia futura + Confidence)
- `libs/procedural_memory/hypothesis_templates.py` — **Hypothesis Template Library** (plantillas declarativas por dominio, NO razonamiento): `HypothesisTemplate` (dataclass frozen, versionada `_v1`) con `scope_anomaly_class` (MVP `point`), `scope_mental_models`, `scope_purposes`, `description_template`, `consequence_templates`, `falsification_templates` y `coherence_estimate` (prior declarativo documentado). Catálogo inicial: 3 hipótesis competidoras por dominio (resource_pressure: logging verbosity / retention / auto-growth; capacity_risk: maintenance schedule / target capacity / antivirus conflict; auth_compromise: compromised account / retry loop / external monitoring). Lenguaje hipotético (podría/candidata) y `falsification_criterion` obligatorio en TODA hipótesis
- `apps/services/hypothesis-service/` — **Hypothesis Generator** (exactamente la capacidad Predict, separado de pattern/anomaly-service):
  - `src/generator/generator.py` — funciones PURAS: para cada anomalía point, el scope se resuelve vía su Active Context (mental_model_id, purpose); se instancian los templates cuyo scope aplica con hechos medidos (`{scope}`, `{deviation_score}`, `{frequency}`, `{anomaly_class}`). SIEMPRE emite ≥2 hipótesis competidoras cuando hay templates aplicables (convergencia prematura a una sola explicación = fallo cognitivo). Anomalía sin template aplicable o sin scope resuelto → sin filas (métrica `total_anomalies_no_templates`)
  - `src/service.py` — ciclo por tenant: `list_anomalies` + `list_contexts` + `list_patterns` → generator → `HypothesisStore`. NUNCA escribe en artefactos previos; nunca lee el observation bus. Métricas: `total_hypotheses`, `total_hypothesis_duplicates`, `total_anomalies_no_templates`, `total_errors`, `hypotheses_by_status`, `hypotheses_by_mental_model`
  - `src/main.py` — `HYPOTHESIS_HEALTH_PORT` (8094), `HYPOTHESIS_CYCLE_SECONDS`
- `libs/cognitive_core/lm_studio_hypothesis_tool.py` — **LMStudioHypothesisTool** (capacidad externa NO-canónica, ADR-0002) implementando el ABC `CognitiveTool`: `invoke` → prompt estructurado → LM Studio → parsing Pydantic → `HypothesisCreate` canónicos; `validate_output` exige `falsification_criterion` no vacío; `available()` sondea el endpoint (`LM_STUDIO_URL`); si no está disponible → fallback solo templates (nunca se rompe el flujo canónico). No cablea Confidence
- Schema: tabla `hypotheses` usada tal cual; trigger `hypothesis_content_immutable_trigger`: contenido inmutable, DELETE bloqueado, `status` como ÚNICO campo flippable

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/hypothesis-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor -c "SELECT status, description, falsification_criterion FROM hypotheses;"
curl -s http://localhost:8094/metrics
```

### Sprint 8 — Confidence Calibrator (Learning · Calibrate)

- `libs/cognitive_core/calibration_model.py` — **Calibration Model**: implementa el formal del concepto Confidence: `evidential_support` (log-odds L = L0 + Σ wᵢ·eᵢ + sigmoide), `brier_score`, `ece_score` (M bins, default M=10), `final_confidence` (C_final = [α·S + (1−α)·C]·(1−ECE)) y `CalibrationParams` (α=0.5, M=10, L₀=0 fijos a priori). `explanatory_coherence` ahora es REAL (normalización de satisfacción de constraints, Thagard 1989): C(H) = P/(P+N+U) sobre el esquema `{explains, contradicts, coherent_with, incoherent_with}` (fracción de evidencia explicada, penalizada por contradicciones y evidencia no explicada; 0.5 neutral sin scope). Se mantienen `QUALITY_CLASS_RANGES` y `quality_class_to_weight` (bandas canónicas Q1-Q4)
- `libs/learning/confidence.py` — **modelo Confidence** (Learning · Calibrate): `ConfidenceCreate`/`Confidence` (pydantic `frozen`) espejo de la tabla `confidence_scores`; `confidence_id` determinístico (uuid5, namespace propio): hash de tenant + target + INPUTS de calibración (S, C, 1−ECE, α), SIN `computed_at` — mismos inputs → mismo id (dedup idempotente); inputs distintos (nueva evidencia) → NUEVO id → nueva fila (append-only: la calibración histórica se conserva, nunca se sobreescribe). `ConfidenceStore` (INSERT `ON CONFLICT (id) DO NOTHING`, `verify_connection`, `close`, `list_confidence(tenant_id)`, `get_confidence(target_type, target_id)`, `list_tenant_ids`)
- `apps/services/confidence-service/` — **Confidence Calibrator** (exactamente la capacidad Calibrate; no genera hipótesis ni recomendaciones):
  - `src/calibrator/calibrator.py` — funciones PURAS: `calibrate(hypothesis, evidence, coherence_inputs, params, historical) -> ConfidenceCreate` computa S (pesos con signos +1/−1 según `explains`/`contradicts`), C (explanatory_coherence), el factor (1−ECE) desde el historial de outcomes de la clase y C_final. Sin historial → `historical_calibration=1.0`, ECE=0 (primeros datos, documentado). `calibration_justification` SIEMPRE documenta S, C, ECE, α, M, L₀ y cómo se derivó cada uno. `resolve_scope_evidence` sigue la cadena hypothesis → anomaly → context → evidence (read-only). Anti-tuning: mismo input → mismo id y score (determinismo, testeado)
  - `src/service.py` — ciclo por tenant: `list_hypotheses` + `list_anomalies` + `list_contexts` + `list_evidence` → calibrator → `ConfidenceStore`. NUNCA escribe en artefactos previos; nunca lee el observation bus; no produce acciones; su output habilita el Action Layer. Métricas: `total_confidence_scores`, `total_confidence_duplicates`, `total_errors`, `confidence_by_target_type`, `mean_confidence_score`, `mean_calibration_error_estimate`
  - `src/main.py` — `CONFIDENCE_HEALTH_PORT` (8095), `CONFIDENCE_CYCLE_SECONDS`, `CALIBRATION_ALPHA` (0.5), `CALIBRATION_ECE_BINS` (10); L₀ fijo en 0
  - La API/Store ya soporta `target_type='recommendation'`/`'decision'` por el mismo path ConfidenceCreate/ConfidenceStore
- Schema: tabla `confidence_scores` usada tal cual; trigger `confidence_content_immutable_trigger` (contenido inmutable y DELETE bloqueado — sin flag de ciclo de vida: una re-calibración con nuevos inputs es una NUEVA fila, nunca un UPDATE)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/confidence-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT target_type, evidential_support, explanatory_coherence, historical_calibration, confidence_score, alpha FROM confidence_scores;"
curl -s http://localhost:8095/metrics
```

### Sprint 9 — Recommendation Formulator (Action · Propose)

- `libs/action/recommendation.py` — **modelo Recommendation** (Action · Propose): `RecommendationCreate`/`Recommendation` (pydantic `frozen`) espejo de la tabla `recommendations` (tenant_id, hypothesis_id, insight_id=NULL en el MVP, confidence_id, action_description, rationale, expected_consequences, alternatives_considered, confidence_score, status, proposed_at); `recommendation_id` determinístico (uuid5, namespace propio) SIN `proposed_at` — mismos inputs → mismo id; el `confidence_id` se fija en el id, de modo que una nueva calibración de la misma hipótesis produce una NUEVA recomendación (append-only). `RecommendationStore` (INSERT `ON CONFLICT (id) DO NOTHING`, `verify_connection`, `close`, `list_recommendations(tenant_id)`, `list_tenant_ids`). `status` es el ÚNICO campo flippable (proposed → accepted/rejected/superseded, decidido por Decision)
- `libs/procedural_memory/action_space.py` — **Action Space Library** (declarativa): `ActionSpaceEntry` (dataclass frozen, `action_id` versionado `*_v1`), `domain` (storage/compute/security/backup/network/observability), `allowed_actions` (frozenset explícito), `purposes`. Catálogo inicial: storage: expand_volume/add_disk/move_data/compress/purge_old/change_retention/enable_dedup; security: reset_credentials/revoke_sessions/enable_mfa/block_ip/isolate_host/rotate_keys; backup: retry_job/change_schedule/change_target/verify_integrity/test_restore; etc. `filter_action_space` limita el catálogo por dominios habilitados (flag de despliegue). La recomendación SOLO puede elegir acciones dentro del space explícito de su dominio/purpose
- `apps/services/recommendation-service/` — **Recommendation Formulator** (exactamente la capacidad Propose; NO calibra confidence ni commitea decisiones):
  - `src/formulator/formulator.py` — funciones PURAS: `formulate(hypothesis, confidence, context, action_space) -> RecommendationCreate` deriva el curso de acción que mejor sirve el propósito: resuelve el dominio (mapping declarativo mental_model→dominio con fallback por purpose), selecciona el action space explícito del dominio/purpose, elige la acción principal declarada (`LEADING_ACTION_BY_DOMAIN`) y construye `rationale` SIEMPRE trazable (cita contexto/hypothesis/confidence con hechos), `expected_consequences` observables y verificables, `alternatives_considered` (las demás acciones permitidas, cada una con rationale + rejected_reason + confidence del entendimiento compartido) y `confidence_score` = el calibrado de la hipótesis (nunca recalcula). `status='proposed'` (advisory; no ejecuta nada). `resolve_active_context` sigue la cadena hypothesis → anomaly → context. Anti-orden: lenguaje propositivo, nunca "run now". Determinismo → dedup idempotente
  - `src/service.py` — ciclo por tenant: `list_hypotheses` + `get_confidence` (gate: solo hipótesis CON confidence calibrada) + `list_contexts` → formulator → `RecommendationStore`. NUNCA escribe en artefactos previos; nunca lee el observation bus; no ejecuta acciones ni dispara alertas. Métricas: `total_recommendations`, `total_recommendation_duplicates`, `total_hypotheses_without_confidence`, `total_hypotheses_without_context`, `total_hypotheses_without_action_space`, `total_errors`, `recommendations_by_status`, `recommendations_by_domain`
  - `src/main.py` — `RECOMMENDATION_HEALTH_PORT` (8096), `RECOMMENDATION_CYCLE_SECONDS`, `ACTION_SPACE_DOMAINS`
- Schema: tabla `recommendations` usada tal cual; trigger `recommendation_content_immutable_trigger` (contenido inmutable una vez escrito; DELETE bloqueado; `status` el único flippable). Migración idempotente `infrastructure/db-migrations/sprint9-recommendation-content-trigger.sql`

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/recommendation-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
curl -s http://localhost:8096/metrics
```

### Sprint 10 — Decision Committer (Action · Commit) — Gate Cognitivo Q1

- `libs/action/decision.py` — **modelo Decision** (Action · Commit): `DecisionCreate`/`Decision` (pydantic `frozen`) espejo de la tabla `decisions` (tenant_id, recommendation_id, confidence_id, authority_id, commitment, expected_outcomes, risk_tolerance, status, committed_at, executed_at, actual_outcomes); `decision_id` determinístico (uuid5, namespace propio) SIN `committed_at`. `DecisionStore` (INSERT `ON CONFLICT (id) DO NOTHING`, `verify_connection`, `close`, `list_decisions(tenant_id)`, `list_tenant_ids`, `list_decisions_by_status`). `status`/`executed_at`/`actual_outcomes` son campos de ciclo de vida: el Learning loop (fases futuras) compara expected vs actual y puebla los outcomes; en el MVP la Decision se REGISTRA, nunca se ejecuta
- `libs/procedural_memory/decision_policy.py` — **Decision Policy Library** (declarativa): `DecisionPolicyEntry` (dataclass frozen, `policy_id` versionado `*_v1`, `domain`, `min_confidence_for_commit`=0.75, `min_confidence_irreversible`=0.9, `allowed_risk_tolerance` por dominio, `requires_authority`). Catálogo canónico por dominio; `select_policy(domain)`, `apply_threshold_overrides` (env `DECISION_MIN_CONFIDENCE*` sin mutar el catálogo)
- `apps/services/decision-service/` — **Decision Committer** (exactamente la capacidad Commit; NO forma recomendaciones ni calibra confidence):
  - `src/committer/committer.py` — funciones PURAS: `Authority` (authority_id + risk_tolerance), `policy_authority_id` (autoridad determinística del policy; usuarios reales llegan en Sprint 12), `recommendation_domain` (dominio del action space desde las alternativas), `resolve_risk_tolerance` (score → low/medium/high, acotado por el policy), `commit_eligibility` (COMMITTABLE / BELOW_CONFIDENCE / RISK_NOT_ALLOWED / NO_AUTHORITY / NO_POLICY), `commit(...)` → `DecisionCreate` con `commitment` DEFINITIVO (sin cláusula alternativa ni intención vaga), y `expected_outcomes` falsificables (prediction + verifiable_by + deadline, declarados ANTES de ejecutar). `status='committed'`, `executed_at=None`, `actual_outcomes=None`; no ejecuta nada
  - `src/service.py` — ciclo por tenant: `list_recommendations` (solo `status='proposed'`) + `list_confidence` (gate) + policy del dominio → committer → `DecisionStore`. NUNCA escribe en artefactos previos; nunca lee el observation bus; no ejecuta acciones. Métricas: `total_decisions`, `total_decision_duplicates`, `total_recommendations_below_confidence`, `total_recommendations_skipped`, `total_errors`, `decisions_by_status`, `decisions_by_risk_tolerance`
  - `src/main.py` — `DECISION_HEALTH_PORT` (8097), `DECISION_CYCLE_SECONDS`, `DECISION_MIN_CONFIDENCE` (0.75), `DECISION_MIN_CONFIDENCE_IRREVERSIBLE` (0.9)
- Schema: tabla `decisions` usada tal cual; trigger `decision_content_immutable_trigger` (CONTENIDO inmutable una vez escrito; DELETE bloqueado; `status` — committed → executing/completed/rolled_back — y `executed_at`/`actual_outcomes` son los campos de ciclo de vida flippable, poblados solo por el Learning loop). Migración idempotente `infrastructure/db-migrations/sprint10-decision-content-trigger.sql`
- **Gate cognitivo Q1 alcanzado**: primera Decision commitida sobre la sandbox con expected outcomes falsificables (prediction + verifiable_by + deadline) y la cadena de trazabilidad completa decision → recommendation → confidence → hypothesis → anomaly → pattern → context → evidence → observations

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/decision-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
curl -s http://localhost:8097/metrics
```

### Sprint 11 — Report Generator (Action · Report, documento de salida)

- `libs/action/report.py` — **modelo Report** (familia output-document del Action Layer): `ReportCreate`/`Report` (pydantic `frozen`) espejo de la tabla `reports` (tenant_id, report_type, title, summary, content, ai_generated, model_used, period_start, period_end, generated_at, file_path); `report_id` determinístico (uuid5, namespace propio) SIN `generated_at` ni `content` — mismos inputs → mismo id. `ReportStore` (INSERT idempotente, `report_exists`, `list_reports`, `get_report`, `list_tenant_ids`, `get_tenant`, `verify_connection`, `close`). Explícitamente NO-canónico (ADR-0002): SOLO formatea lo que el flujo cognitivo ya commiteó, escribe en su tabla propia `reports`, nunca genera juicios, nunca toca las tablas cognitivas. `ai_generated=False`/`model_used=None` en este MVP (render local por templates; LM Studio en un sprint futuro)
- `apps/services/report-service/` — **Report Generator** (formatea, no razona):
  - `src/renderers/common.py` — `ReportSource` (dataclass con los artefactos leídos: decisions, recommendations, contexts, confidences, hypotheses, anomalies, patterns, evidence, observations, tenant, period, generated_at), `as_jsonable`, `build_decision_traces` (correlaciona decision → recommendation → confidence → hypothesis → anomaly → pattern → context → evidence → observations), `latest_confidence_for(hypothesis)`
  - `src/renderers/executive.py` — `render_executive(source)` PURA: Top Decisions (commitment, risk_tolerance, confidence, expected_outcome_count, acción de la recommendation), `pending_authority` (solo risk_tolerance "high"), `future_risks` (hypotheses con confidence_score > `risk_threshold`, default 0.6). NUNCA inventa costes/ROI: solo lo que el flujo commiteó
  - `src/renderers/technical.py` — `render_technical(source)` PURA: secciones 1-7 (Cognitive Trace, Anomalies, Patterns, Confidence Calibration, Reasoning Chain, Decision & Expected Outcomes, Evidencia/Context)
  - `src/renderers/json_render.py` — `render_json(source)` PURA: estructura exacta de `build_decision_traces` (formato máquina)
  - `src/renderers/formatters.py` — I/O: `to_html` (jinja2), `to_pdf` (weasyprint), `to_json`. Renderers puros vs formatters con I/O
  - `src/service.py` — ciclo por tenant: lee Decisiones/Recomendaciones/Contexts/Confidences/Hypotheses/Anomalies/Patterns/Evidence/Observations → period = rango de `committed_at` (min..max, hoy si vacío) → render → formatter → `ReportStore.save_report` (dedup). Métricas: `total_reports`, `total_report_duplicates`, `total_errors`, `by_type`, `render_duration_seconds`, `last_run_at`
  - `src/health.py` — `/health`, `/metrics`, `POST /api/v1/reports/generate` (tenant opcional, type executive/technical/json), `GET /api/v1/reports`
  - `src/main.py` — `REPORT_HEALTH_PORT` (8098), `REPORT_CYCLE_SECONDS`, `REPORT_OUTPUT_DIR`
- `libs/perception/store.py` — se agregó `ObservationStore.list_observations` (READ) para completar la traza de evidencia en los reportes
- Schema: tabla `reports` usada tal cual; trigger `report_content_immutable_trigger` (contenido inmutable una vez escrito; DELETE bloqueado). Migración idempotente `infrastructure/db-migrations/sprint11-report-content-trigger.sql`

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/report-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
curl -s -X POST "http://localhost:8098/api/v1/reports/generate?type=executive&tenant_id=00000000-0000-0000-0000-000000000001"
curl -s "http://localhost:8098/api/v1/reports?tenant_id=00000000-0000-0000-0000-000000000001"
curl -s http://localhost:8098/metrics
```

### Sprint 12 — Multi-tenant + Auth + RBAC (Decision Authority — Capacidad Externa)

El **user-service** (JWT/roles por tenant) y el **API Gateway** (enforcement del Cognitive Boundary) cierran el bloque **Q1**: pipeline completo + autoridad + boundary. Ambos son capacidades EXTERNAS no-canónicas (**ADR-0002**): autorizan y protegen el acceso al flujo canónico, NUNCA producen juicios cognitivos y NUNCA ejecutan el pipeline. El RBAC se modela como **Decision Authority binding** (la autoridad de compromiso bajo la cual se tomó una Decision), no como "tabla de permisos".

- `libs/access/` — **Access layer** (compartida por user-service y gateway):
  - `security.py` — bcrypt (hash/verify) + JWT (HS256 dev / RS256 prod) con claims de identidad + rol + tenant. Hallazgo: `passlib 1.7.4` es incompatible con `bcrypt>=4.1` (usa `bcrypt.__about__.__version__`, eliminado); se usa el paquete `bcrypt` directamente
  - `rbac.py` — matriz **roles × permisos**: viewer (READ de context/recommendations/decisions/reports; NO propose/commit/execute), operator (+ACK, NO propose/commit), admin (READ + PROPOSE + COMMIT en tenant con risk low/medium + define políticas), superadmin (todo + cross-tenant + high risk + execute). Constantes puras testeadas celda a celda; `commit_risk_allowed` y `tenant_scope` (aislamiento multi-tenant)
  - `users.py` — modelo `User` + `UserStore` (tabla `users`, por tenant; email UNIQUE global; hash bcrypt nunca plaintext; queries siempre scoped por `tenant_id`)
  - `errors.py` — `InvalidTokenError` (401), `AuthorizationError`/`TenantIsolationError` (403), `UserConflictError` (409)
- `apps/services/user-service/` — **Auth/RBAC service** (externa, ADR-0002): `POST /api/v1/auth/login` (email+password → access+refresh), `POST /api/v1/auth/refresh` (stateless), `POST /api/v1/users` (admin/superadmin, aislamiento por tenant), `GET /api/v1/me`, `GET /api/v1/users` (admin+, tenant scope). Tokens con rol+tenant; el `authority_id` de las Decisiones (Sprint 10) ahora referenciable a `users.id` reales. Métricas `/metrics`: `total_logins`, `total_login_failures`, `total_tokens_issued`, `total_errors`, `users_by_role`. Puerto `USER_HEALTH_PORT=8099`
- `apps/gateway/api-gateway/` — **Cognitive Boundary enforcement**:
  - `src/boundary.py` — reglas puras del boundary: flujo canónico observación→evidencia→contexto→patrón→anomalía→hipótesis→insight→recomendación→decisión (sin atajos; observations nunca expuestas a Reasoning/Action; Pattern/Anomaly/Hypothesis nunca gatillan acciones) + validación de Confidence presente
  - `POST /api/v1/actions/{action}` (commit/propose/ack/execute) — valida rol + boundary + confidence; NUNCA ejecuta (la ejecución es el ciclo canónico de cada servicio). 401 sin token, 403 rol sin autoridad, 400 boundary
  - READ protegidas por rol con aislamiento por tenant: `GET /api/v1/tenants/{tenant_id}/decisions`, `/reports`, `GET /api/v1/services/health` (forward a los /health del pipeline). Puerto `GATEWAY_HEALTH_PORT=8100`
- Schema: tabla `users` (id, tenant_id FK, email UNIQUE, password_hash bcrypt, name, role CHECK viewer/operator/admin/superadmin, is_active, created_at, updated_at) + `idx_users_tenant_email(tenant_id, email)` en `01-schema.sql`; seed del admin sandbox (password dev documentado) en `02-seed.sql`; migración idempotente `infrastructure/db-migrations/sprint12-users-tables.sql`. `users` es dato externo (ADR-0002): MUTABLE por diseño, sin trigger P1. `decisions` sin cambios (`authority_id` queda UUID libre)
- **Estrategia refresh**: JWT stateless (access + refresh firmados, exp propia; sin tabla `refresh_tokens` ni token store en Redis) — documentada

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" \
  -f infrastructure/db-migrations/sprint12-users-tables.sql
JWT_ALGORITHM=HS256 JWT_SECRET_KEY=dev-secret \
PYTHONPATH="apps/services/user-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main   # puerto 8099
curl -s -X POST http://localhost:8099/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@sandbox.local","password":"cosmonitor"}'
curl -s http://localhost:8099/api/v1/me -H "Authorization: Bearer <ACCESS_TOKEN>"
PYTHONPATH="apps/gateway/api-gateway:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main   # puerto 8100
curl -s -X POST http://localhost:8100/api/v1/actions/commit \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"confidence_score":0.85,"risk_tolerance":"low"}'
curl -s http://localhost:8099/metrics && curl -s http://localhost:8100/metrics
```

La autorización NO es un fin en sí: existe para que cada Decision/acción tenga un **authority binding** auditable y verificable. El gateway enforza que los componentes del pipeline solo se llamen según el flujo canónico y que ninguna capacidad externa ejecute acción sin autorización. Ningún juicio cognitivo pasa por auth/RBAC (test estructural ADR-0002: `libs/access` no importa el pipeline). El siguiente bloque es **H1** (Sprint 13+): Insight, calibración histórica, Procedural Memory v2 y patrones avanzados.

---

## Cognitive Compliance

Cada sprint valida:

- [x] **R1**: Exactamente una capacidad cognitiva por componente
- [x] **R2**: Cognitive Contract (Input→Transform→Output) testeado
- [x] **R3**: Cognitive Boundary enforceado
- [x] **R4**: No hay acción sin Confidence
- [x] **R5**: Decisiones con resultados falsificables
- [x] **P1**: Observaciones inmutables, nunca interpretadas
- [x] **P5**: Confidence computada (S+C+ECE), parámetros publicados

La trazabilidad, objetividad y provenance se garantizan de forma factual a lo largo de toda la cadena: cada artefacto referencia sus inputs, cada fila es append-only y deduplicada idempotentemente, y ningún paso de razonamiento añade interpretación que la evidencia no haya ganado.

---

## Política de citación canónica (Cognitive Citation Policy)

Las citas al marco Company OS usan exclusivamente el set canónico:

- **Principios**: P1–P7 (`cognitive-principles.md`)
- **Design rules**: R1–R7 (`cognitive-architecture.md`)
- **Conceptos**: nombres de `cognitive-lexicon/core-concepts/*.md`
- **ADR**: ADR-0001 (Company OS es el cerebro), ADR-0002 (COS-Monitor es el producto)

Regla: **nada fuera de la policy se escribe.** Toda referencia al marco debe mapear a un elemento canónico existente. No se inventan números de regla (R8/R9/R10), no se usa la numeración R1–R10 de `ontology.md` (colisiona con R1–R7), y la trazabilidad/objetividad/provenance se describen sin número de regla. Enforcement para sesiones de agente: `AGENTS.md`.

---

## Documentación

- `docs/01-fundacion-arquitectura.md` — FASE 1-2: Pipeline cognitivo, DB schema
- `docs/02-motor-recoleccion.md` — FASE 3: Perception Layer (agentes, collector)
- `docs/03-predictivo-ia-local.md` — FASE 4-5: Reasoning + Learning + LM Studio
- `docs/04-informes-seguridad.md` — FASE 6-7: Action Layer + Security as Procedural Memory
- `docs/05-negocio-roadmap-backlog.md` — FASE 8-10: Roadmap, backlog, OKRs cognitivos
- `AGENTS.md` — Guía de sesiones de agente y enforcement de la política de citación

---

> La arquitectura debe guiar el código, nunca al revés.