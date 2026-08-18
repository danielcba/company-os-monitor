# Company OS Monitor - FASE 1 y 2: Fundación y Arquitectura Cognitiva

## Visión General

# COS-Monitor (Company OS Monitor)

Plataforma SaaS para monitoreo, análisis y diagnóstico automático de infraestructura IT para DataCenters usando IA local (LM Studio) y componentes Open Source. **Todas las funcionalidades, datos, pantallas y decisiones deben estar estrictamente condicionadas por el framework de arquitectura cognitiva Company OS** (https://github.com/danielcba/company-os/, path local: `/home/dcordoba/Documents/Default Project/company/company-os-main/`). Este repositorio es de solo lectura; el framework guía el código, nunca lo contrario (R7).

**Principio rector (ADR-0001)**: Company OS es el centro cognitivo de la organización. COS-Monitor es su primera implementación de producto (ADR-0002). El flujo canónico (Reality → Decision) es el cerebro del producto; toda capacidad externa (agentes, API, dashboard, alertas, reportes, auth, LLM) es no-canónica y debe originar sus juicios desde el flujo cognitivo central.

---

# FASE 1: MVP Cognitivo Mínimo

## Funcionalidades Mínimas (Mapeadas a Conceptos Cognitivos)

| # | Funcionalidad | Concepto Cognitivo Principal | Familia | Contrato Cognitivo Requerido |
|---|--------------|------------------------------|---------|------------------------------|
| 1 | Recolección métricas Linux (CPU, RAM, Disco) | **Observation** | Perception | Input: realidad (servidor) → Transform: captura inmutable → Output: Observation |
| 2 | Recolección métricas Windows vía WMI (CPU, RAM, Disco, Eventos críticos) | **Observation** | Perception | Input: realidad (Windows) → Transform: captura inmutable → Output: Observation |
| 3 | Dashboard web básico con estado actual | **Context** (Active Context) | Perception | Input: Evidence → Transform: interpretación por modelo mental coherente → Output: Active Context |
| 4 | Sistema de alertas | **Anomaly → Hypothesis → Recommendation** | Reasoning → Action | Input: Active Context + Pattern → Transform: detección desviación → Output: Anomaly con Recommendation calibrada |
| 5 | Generación de informe PDF ejecutivo básico | **Insight → Recommendation → Decision** | Reasoning → Action | Input: Hypothesis/Insight + Confidence → Transform: propuesta acción con alternativas → Output: Recommendation/Decision |
| 6 | Autenticación multi-tenant (un administrador por cliente) | **Decision** (authority binding) | Action | Input: Recommendation + Confidence → Transform: compromiso con authority → Output: Decision con outcomes esperados |

## Arquitectura MVP Cognitiva

La arquitectura NO es "microservicios tradicionales". Es una **pipeline cognitivo** que implementa el flujo canónico:

```
Reality (Servidores Linux/Windows)
    ↓
PERCEPTION LAYER
    ├─ Observation Capture (Agentes Linux/Windows)
    ├─ Evidence Organization (Collector Service)
    └─ Context Activation (Context Service - selecciona modelo mental más coherente)
    ↓
REASONING LAYER
    ├─ Pattern Detection (Pattern Service - regularidades en Context)
    ├─ Anomaly Detection (Anomaly Service - desviaciones vs Pattern)
    ├─ Hypothesis Generation (Hypothesis Service - explicaciones testables)
    └─ Insight Restructuring (Insight Service - reorganización conocimiento)
    ↓
CONFIDENCE (Learning, cross-cutting)
    └─ Calibrated Confidence (Confidence Service - evidencia + coherencia + calibración histórica)
    ↓
ACTION LAYER
    ├─ Recommendation (Recommendation Service - curso acción + rationale + alternativas + confidence)
    └─ Decision (Decision Service - compromiso + outcomes falsificables + authority)
    ↓
MEMORY (planned)
    └─ Consolidation (Decision outcomes → calibración Confidence futura)
```

### Capas Cognitivas y sus Responsabilidades (según Cognitive Architecture)

| Capa | Responsabilidad | Constraint Arquitectónico |
|------|-----------------|---------------------------|
| **Perception** | Captura Observations inmutables, organiza Evidence, activa Active Context por coherencia explicativa | **P1**: Percepción no interpreta. Solo captura, organiza, selecciona interpretación más coherente |
| **Reasoning** | Detecta Patterns, identifica Anomalies, genera/evalúa Hypotheses, reestructura en Insights | **Constraint**: Razonamiento actúa sobre conocimiento, nunca directo sobre el mundo |
| **Confidence/Metacognition** | Computa Confidence calibrada para cada juicio, monitorea calidad razonamiento, detecta impasse | **P5**: Confidence se computa, no se intuye. Cross-cutting, no oracle separado |
| **Action** | Produce Recommendations (advisory, reversible) con rationale/alternativas/confidence; commite Decisions (accountable) con traceability/expected outcomes | **P6**: Recommendation ≠ Decision. Perception/Reasoning nunca ejecutan acción sin autorización explícita |
| **Memory (planned)** | Consolida Observations, Decisions, Outcomes; soporta Confidence con calibración histórica | **P7**: Learning through outcome. Comparación expected vs actual → learning |

### Stack Tecnológico (Subordinado a Arquitectura Cognitiva)

- **Backend**: Python/FastAPI — cada servicio implementa **exactly one cognitive capability** (R1) con **Cognitive Contract definido** (R2)
- **Frontend**: HTML + HTMX + Tailwind CSS — renderiza Active Context, Recommendations, Decisions (nunca ejecuta acción directa)
- **Base de datos**: PostgreSQL + TimescaleDB — almacena Observations (inmutables), Evidence, Context, Patterns, Anomalies, Hypotheses, Insights, Confidence scores, Recommendations, Decisions
- **Cache**: Redis — Working Memory (contexto activo, métricas tiempo real últimos 5 min)
- **Contenedorización**: Docker + Docker Compose
- **Recolección**: Agentes Python SSH + WMI remoto — son **Observation Capturers** (Perception family)
- **Comunicación**: REST/HTTP + eventos asíncronos — transporte entre capas cognitivas
- **API Gateway**: Nginx/Traefik/Kong — boundary enforcement (R3)

### Dependencias (Mapeadas a Capacidades Cognitivas)

| Capacidad | Dependencias |
|-----------|--------------|
| Observation Capture | `psutil`, `pywinrm`, `cryptography`, `httpx` |
| Evidence Organization | `sqlalchemy`, `asyncpg`, `pandas` |
| Context Activation | `jinja2`, model abstraction |
| Pattern Detection | `scikit-learn`, `statsmodels`, `prophet` |
| Anomaly Detection | `numpy`, `scikit-learn` |
| Hypothesis Generation | `openai` (LM Studio compatible), mental model library |
| Insight Restructuring | `openai` (LM Studio), analogy engine |
| Confidence Calibration | Calibration Model (evidential support + coherence + historical ECE) |
| Recommendation | Action space definition, Confidence |
| Decision | Authority binding, outcome tracking |

## Riesgos (Enmarcados en Principios Cognitivos)

1. **P1 violation risk**: WMI remoto requiere configuración — si el agente interpreta en lugar de solo capturar, viola Primacy of Observation
2. **P5 violation risk**: LM Studio en CPU (3-5 tok/s) — si Confidence no se calibra correctamente, juicios influyen acción sin calibración
3. **P2 violation risk**: PyMEs sin infraestructura estandarizada — Context activation puede fallar sin mental models adecuados
4. **R3 violation risk**: Agentes remotos requieren apertura puertos — boundary cognitivo debe enforzarse en API Gateway
5. **ADR-0002 compliance**: Ninguna capacidad externa (alertas, reportes) puede bypassar el flujo cognitivo canónico

---

# FASE 2: Arquitectura Cognitiva Completa

## Diagrama Lógico del Pipeline Cognitivo

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            REALITY LAYER                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │ Linux Server │  │ Windows      │  │ VMware Host  │  │ Network      │   │
│  │              │  │ Server       │  │              │  │ Devices      │   │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
└─────────┼─────────────────┼─────────────────┼─────────────────┼─────────────┘
          │                 │                 │                 │
          ▼                 ▼                 ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          PERCEPTION LAYER                                   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  OBSERVATION CAPTURE (Agentes)                                      │   │
│  │  - Linux Agent (psutil/SSH)          →  Observation (immutable)    │   │
│  │  - Windows Agent (WMI/WinRM)         →  Observation (immutable)    │   │
│  │  - VMware Agent (pyVmomi)            →  Observation (immutable)    │   │
│  │  - Network Agent (nmap/SNMP)         →  Observation (immutable)    │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                            │
│                               ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  EVIDENCE ORGANIZATION (Collector Service)                          │   │
│  │  Input: Observations → Transform: organize related observations     │   │
│  │  Output: Evidence (Q1-Q4 Quality Class, weighted)                  │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                            │
│                               ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CONTEXT ACTIVATION (Context Service)                               │   │
│  │  Input: Evidence + Mental Models + Purpose                          │   │
│  │  Transform: explanatory coherence competition                       │   │
│  │  Output: Active Context (foundation for reasoning)                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          REASONING LAYER                                    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PATTERN DETECTION (Pattern Service)                                │   │
│  │  Input: Active Context → Transform: detect recurrent structures     │   │
│  │  Output: Pattern(s) + strength measure (support/frequency/p-value) │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                            │
│                               ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  ANOMALY DETECTION (Anomaly Service)                                │   │
│  │  Input: Active Context + Expected Pattern(s) + Tolerance            │   │
│  │  Transform: compare context vs pattern, measure deviation           │   │
│  │  Output: Anomaly + deviation score + violated pattern(s)            │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                            │
│                               ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  HYPOTHESIS GENERATION (Hypothesis Service)                         │   │
│  │  Input: Active Context + Patterns + Anomalies + Mental Models       │   │
│  │  Transform: generate testable explanations with falsification criteria│   │
│  │  Output: Hypothesis(es) + predicted consequences + falsification   │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                            │
│                               ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  INSIGHT RESTRUCTURING (Insight Service)                            │   │
│  │  Input: Active Context + Active Hypotheses + Knowledge              │   │
│  │  Transform: restructure relationships between knowledge elements    │   │
│  │  Output: Insight (novel understanding) + updated mental model      │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CONFIDENCE & METACOGNITION (Learning, cross-cutting)    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  CONFIDENCE CALIBRATION (Confidence Service)                        │   │
│  │  Input: Hypothesis/Recommendation/Decision + Evidence + Coherence   │   │
│  │  Transform: Calibration Model (S + C) · (1 - ECE)                   │   │
│  │  Output: Confidence score + justification + calibration error est. │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  METACOGNITIVE MONITORING                                           │   │
│  │  - Monitors reasoning quality                                       │   │
│  │  - Detects impasse and calibration failure                          │   │
│  │  - Triggers restructuring when frame fails                          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          ACTION LAYER                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  RECOMMENDATION (Recommendation Service)                            │   │
│  │  Input: Active Context + Leading Hypothesis/Insight + Confidence   │   │
│  │  Transform: derive action course best serving purpose               │   │
│  │  Output: Recommendation + rationale + expected consequences +      │   │
│  │           confidence + alternatives considered                      │   │
│  └────────────────────────────┬────────────────────────────────────────┘   │
│                               │                                            │
│                               ▼                                            │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  DECISION (Decision Service)                                        │   │
│  │  Input: Recommendation(s) + Confidence + Purpose + Constraints     │   │
│  │  Transform: select + commit course of action                        │   │
│  │  Output: Decision + recorded rationale + expected outcomes (falsifiable)│   │
│  │           + confidence score + commitment authority                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          MEMORY LAYER (planned)                             │
│                                                                             │
│  ┌──────────────────────────┐  ┌──────────────────┐  ┌──────────────────┐  │
│  │ Working Memory (Redis)   │  │ Episodic Memory  │  │ Semantic Memory  │  │
│  │ Active Context,          │  │ Session logs,    │  │ Knowledge base,  │  │
│  │ real-time metrics        │  │ decision trails  │  │ patterns, laws   │  │
│  └──────────────────────────┘  └──────────────────┘  └──────────────────┘  │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  PROCEDURAL MEMORY (Cognitive Contracts, Policies)                  │   │
│  │  - How to capture observations                                      │   │
│  │  - How to organize evidence                                         │   │
│  │  - How to activate context                                          │   │
│  │  - How to detect patterns/anomalies                                 │   │
│  │  - How to generate/evaluate hypotheses                              │   │
│  │  - How to calibrate confidence                                      │   │
│  │  - How to form recommendations/decisions                            │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Capacidades Cognitivas (Reemplazan "Microservicios")

Cada capacidad implementa **exactly one cognitive concept** (R1) con **Cognitive Contract** (R2):

| # | Capacidad Cognitiva | Concepto | Familia | Cognitive Contract (Input → Transform → Output) |
|---|---------------------|----------|---------|------------------------------------------------|
| 1 | **Observation Capturer** (Agentes) | Observation | Perception | Reality → Capture immutable fact → Observation |
| 2 | **Evidence Organizer** (Collector) | Evidence | Perception | Observations → Organize coherent body → Evidence (Q1-Q4) |
| 3 | **Context Activator** (Context Service) | Context | Perception | Evidence + Models + Purpose → Coherence competition → Active Context |
| 4 | **Pattern Detector** (Pattern Service) | Pattern | Reasoning | Active Context → Detect regularities → Pattern + strength |
| 5 | **Anomaly Detector** (Anomaly Service) | Anomaly | Reasoning | Context + Pattern + Tolerance → Measure deviation → Anomaly + score |
| 6 | **Hypothesis Generator** (Hypothesis Service) | Hypothesis | Reasoning | Context + Patterns + Anomalies → Generate testable explanations → Hypothesis + predictions + falsification |
| 7 | **Insight Restructurer** (Insight Service) | Insight | Reasoning | Context + Hypotheses + Knowledge → Restructure relationships → Insight + updated model |
| 8 | **Confidence Calibrator** (Confidence Service) | Confidence | Learning | Judgment + Evidence + Coherence + History → Calibration Model → Confidence + justification + ECE |
| 9 | **Recommendation Formulator** (Rec Service) | Recommendation | Action | Context + Hypothesis/Insight + Confidence + Action Space → Propose action → Recommendation + rationale + alternatives |
| 10 | **Decision Committer** (Decision Service) | Decision | Action | Recommendation + Confidence + Authority → Commit → Decision + rationale + expected outcomes (falsifiable) |

## Esquema de Base de Datos (Cognitive-First)

Todas las tablas almacenan **conceptos cognitivos**, no solo "datos técnicos". Cada registro es una instancia de un concepto con su Cognitive Contract cumplido.

### Tabla: observations (Perception - Capture)
- id UUID PK
- tenant_id UUID FK → tenants
- source_id UUID (server/agent identifier)
- source_type VARCHAR(50) (linux_agent/windows_agent/vmware_agent/network_agent)
- fact_type VARCHAR(100) (cpu_utilization, memory_usage, disk_usage, event_log, service_state, etc.)
- fact_value JSONB (valor crudo sin interpretación)
- unit VARCHAR(20)
- captured_at TIMESTAMPTZ NOT NULL (immutable timestamp)
- quality_class VARCHAR(2) (Q1-Q4, assigned at creation per Evidence spec)
- raw_payload JSONB (complete immutable capture)
- **Constraints**: INSERT only, no UPDATE/DELETE (immutability per P1)

### Tabla: evidence (Perception - Organize)
- id UUID PK
- tenant_id UUID FK → tenants
- observation_ids UUID[] (FK → observations, organized set)
- organization_type VARCHAR(50) (resource_exhaustion, auth_anomaly, backup_failure_pattern, etc.)
- description TEXT (coherent organization statement, NO interpretation)
- quality_class VARCHAR(2) (Q1-Q4, derived from constituent observations)
- weight NUMERIC(3,2) (wᵢ ∈ [0,1] per Quality Class for Confidence calibration)
- organized_at TIMESTAMPTZ NOT NULL
- **Constraints**: Evidence never interprets, predicts, or recommends (per Evidence design implications)

### Tabla: contexts (Perception - Explain)
- id UUID PK
- tenant_id UUID FK → tenants
- evidence_ids UUID[] (FK → evidence)
- mental_model_id VARCHAR(100) (identifier of active mental model)
- purpose VARCHAR(200) (current reasoning purpose)
- coherence_score NUMERIC(3,2) (explanatory coherence measure)
- competing_models JSONB (other models evaluated with their coherence scores)
- activated_at TIMESTAMPTZ NOT NULL
- is_active BOOLEAN DEFAULT TRUE
- **Constraints**: Context selected by coherence competition (P2), never generated directly

### Tabla: patterns (Reasoning - Generalize)
- id UUID PK
- tenant_id UUID FK → tenants
- context_id UUID FK → contexts
- pattern_type VARCHAR(100) (temporal, correlation, sequential, threshold)
- description TEXT (recurring structure description)
- strength_measure NUMERIC(5,4) (support/frequency/p-value)
- frequency VARCHAR(50) (weekly, daily, hourly, event-driven)
- detected_at TIMESTAMPTZ NOT NULL
- is_active BOOLEAN DEFAULT TRUE
- **Constraints**: Pattern describes regularity, never explains cause (Law/Hypothesis does)

### Tabla: anomalies (Reasoning - Detect Deviation)
- id UUID PK
- tenant_id UUID FK → tenants
- context_id UUID FK → contexts
- pattern_id UUID NOT NULL FK → patterns (expected pattern violated; NOT NULL: an anomaly only exists relative to an expected pattern)
- deviation_score NUMERIC(8,4) (quantified deviation magnitude; widened from NUMERIC(5,4): ratios can exceed 9.9999)
- tolerance_threshold NUMERIC(8,4) (explicit, auditable, purpose-dependent)
- anomaly_class VARCHAR(50) (point, contextual, collective)
- detected_at TIMESTAMPTZ NOT NULL
- **Constraints**: Anomaly exists only relative to expected pattern (per Anomaly definition)

### Tabla: hypotheses (Reasoning - Predict)
- id UUID PK
- tenant_id UUID FK → tenants
- anomaly_ids UUID[] (FK → anomalies triggering hypothesis)
- pattern_ids UUID[] (FK → patterns supporting hypothesis)
- description TEXT (testable explanation)
- predicted_consequences JSONB (falsifiable predictions in observable terms)
- falsification_criterion TEXT (concrete observable outcome that would falsify)
- coherence_score NUMERIC(3,2) (explanatory coherence)
- status VARCHAR(20) (candidate/confirmed/falsified)
- generated_at TIMESTAMPTZ NOT NULL
- **Constraints**: Multiple competing hypotheses maintained simultaneously (per Hypothesis design implications)

### Tabla: insights (Reasoning - Restructure)
- id UUID PK
- tenant_id UUID FK → tenants
- context_id UUID FK → contexts
- hypothesis_ids UUID[] (FK → hypotheses restructured)
- description TEXT (novel understanding from restructuring)
- prior_understanding TEXT (what the insight replaces)
- mental_model_update JSONB (how the active mental model changes)
- generated_at TIMESTAMPTZ NOT NULL
- **Constraints**: Insight restructures existing knowledge, doesn't add new facts (per Insight definition)

### Tabla: confidence_scores (Learning - Calibrate)
- id UUID PK
- tenant_id UUID FK → tenants
- target_type VARCHAR(50) (hypothesis/recommendation/decision)
- target_id UUID (FK to respective table)
- evidential_support NUMERIC(5,4) (S(H|E) from Calibration Model)
- explanatory_coherence NUMERIC(5,4) (C(H) from coherence computation)
- historical_calibration NUMERIC(5,4) (1 - ECE)
- confidence_score NUMERIC(5,4) (C_final = [α·S + (1-α)·C] · (1-ECE))
- alpha NUMERIC(3,2) (mixing coefficient, fixed a priori, documented)
- calibration_justification TEXT (why this score)
- calibration_error_estimate NUMERIC(5,4)
- computed_at TIMESTAMPTZ NOT NULL
- **Constraints**: Every judgment influencing action MUST carry this (R4, P5)

### Tabla: recommendations (Action - Propose)
- id UUID PK
- tenant_id UUID FK → tenants
- hypothesis_id UUID FK → hypotheses (leading hypothesis)
- insight_id UUID FK → insights (optional, if insight-driven)
- confidence_id UUID FK → confidence_scores
- action_description TEXT (what to do)
- rationale TEXT (why, traceable to evidence/hypothesis)
- expected_consequences JSONB (observable, verifiable outcomes)
- alternatives_considered JSONB (other options evaluated with rationale)
- confidence_score NUMERIC(5,4) (from confidence_id)
- status VARCHAR(20) (proposed/accepted/rejected/superseded)
- proposed_at TIMESTAMPTZ NOT NULL
- **Constraints**: Advisory and reversible (P6). Never executes directly.

### Tabla: decisions (Action - Commit)
- id UUID PK
- tenant_id UUID FK → tenants
- recommendation_id UUID FK → recommendations
- confidence_id UUID FK → confidence_scores
- authority_id UUID (user/system role committing)
- commitment TEXT (definite course of action selected)
- expected_outcomes JSONB (falsifiable predictions in observable terms per Decision spec)
- risk_tolerance VARCHAR(20) (low/medium/high)
- status VARCHAR(20) (committed/executing/completed/rolled_back)
- committed_at TIMESTAMPTZ NOT NULL
- executed_at TIMESTAMPTZ
- actual_outcomes JSONB (for Learning loop comparison)
- **Constraints**: Commitment with authority, timeline, expected outcomes (P6). Recorded with full trace (R5).

### Tabla: tenants (sin cambios, soporte multi-tenant)
- id UUID PK, name, slug, plan, settings, created_at, updated_at

### Tabla: servers (metadata para source_id en observations)
- id UUID PK, tenant_id, hostname, ip_address, os_type, os_version, agent_version, status, last_seen, metadata, created_at

### Tablas de soporte (alert_rules, audit_log, etc.)
- Mantenidas pero referenciadas desde conceptos cognitivos (ej: alert_rule → Anomaly tolerance threshold)

## Estrategia de Crecimiento (Cognitive-Aware)

- **Particionamiento**: observations, evidence, contexts, patterns, anomalies, hypotheses, insights, confidence_scores, recommendations, decisions particionados por mes + tenant_id
- **TimescaleDB**: Para observations (time-series inmutables) con compresión automática y retention policies
- **Read replicas**: Para Context/Active Context queries (dashboard), Recommendation/Decision reads
- **Cacheo (Working Memory)**: Redis para Active Context actual, métricas tiempo real (últimos 5 min), confidence scores recientes
- **Archivo (Episodic Memory)**: Datos > 12 meses → MinIO como JSON/Parquet (session logs, decision trails)
- **Sharding**: Por tenant cuando > 500 tenants (Semantic Memory partitioning)
- **Procedural Memory**: Cognitive Contracts y Policies versionados en Git, deployed via CI/CD