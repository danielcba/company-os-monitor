# Cómo la Plataforma Cumple el Contrato Cognitivo en Todas sus Fases

## 1. ¿Qué es y qué hace?

COS-Monitor es una plataforma SaaS que implementa el **pipeline cognitivo canónico** Company OS: **Perception → Reasoning → Confidence → Action**. Cada componente implementa exactamente una capacidad cognitiva (R1) con un Cognitive Contract definido (R2). El framework guía el código, nunca al revés (R7).

**Funciones principales:**
- **Perception Layer**: Captura observaciones inmutables de servidores Linux/Windows/VMware/red mediante agents especializados
- **Evidence Organization**: Organiza observaciones en evidencia coherente con quality classes Q1-Q4
- **Context Activation**: Selecciona el modelo mental más coherente mediante competencia explicativa
- **Reasoning Layer**: Detecta patrones, anomalías, genera hipótesis testables y reestructura insights
- **Confidence Calibration**: Computa confianza calibrada usando S (evidencial) + C (coherencia) + ECE (error de calibración esperada)
- **Action Layer**: Formula recomendaciones asesorables y comite decisiones con resultados esperados falsificables
- **Report Generation**: Formatea documentos de salida basados en lo que el flujo cognitivo commiteó

## 2. Cómo lo hace (Implementation)

### Arquitectura por Capas

| Capa | Capacidad | Contract Input → Transform → Output |
|------|-----------|-------------------------------------|
| Perception | Observation Capture | Reality → Capture immutable fact → Observation |
| Perception | Evidence Organization | Observations → Organize coherent body → Evidence (Q1-Q4) |
| Perception | Context Activation | Evidence + Models + Purpose → Coherence competition → Active Context |
| Reasoning | Pattern Detection | Active Context → Detect regularities → Pattern + strength |
| Reasoning | Anomaly Detection | Context + Pattern + Tolerance → Measure deviation → Anomaly + score |
| Reasoning | Hypothesis Generation | Context + Patterns + Anomalies → Testable explanations → Hypothesis + predictions + falsification |
| Learning | Confidence Calibration | Judgment + Evidence + Coherence + History → Calibration Model → Confidence + justification + ECE |
| Action | Recommendation | Context + Hypothesis/Insight + Confidence + Action Space → Propose action → Recommendation + rationale + alternatives |
| Action | Decision | Recommendation + Confidence + Authority → Commit → Decision + rationale + expected outcomes (falsifiable) |

### Principios Clave (P1-P7, R1-R7)

- **P1 (Primacy of Observation)**: Observations are immutable, never interpreted. Agents capture facts without meaning extraction.
- **P2 (Context Competition)**: Context activated by explanatory coherence competition, never generated directly.
- **P5 (Computed Confidence)**: Confidence computed, not intuited. Uses S + C · (1 - ECE) formula.
- **P6 (Recommendation ≠ Decision)**: Recommendations are advisory and reversible. Decisions require explicit authority.
- **R1 (Exactly One Capability)**: Cada servicio implementa exactamente una capacidad cognitiva.
- **R2 (Cognitive Contract)**: Cada componente expone Input → Transform → Output testeado.
- **R3 (Cognitive Boundary)**: Pipeline solo se invoca según flujo canónico; capacidades externas nunca bypassan.
- **R4 (No Action Without Confidence)**: Action layer gateado por confidence calibrada.

### Almacenamiento y Trazabilidad

- **Base de datos PostgreSQL**: Almacena todos los artefactos cognitivos (observations, evidence, contexts, patterns, anomalies, hypotheses, insights, confidence_scores, recommendations, decisions, reports)
- **Append-only inmutability**: Cada tabla tiene triggers que bloquean UPDATE/DELETE en columnas de contenido. Solo campos de ciclo de vida pueden flipparse (is_active, status).
- **UUID determinísticos**: IDs generados con uuid5 usando namespaces propios, garantizando idempotencia.
- **Cadenas de trazabilidad**: Cada artefacto referencia sus inputs (ej: decision → recommendation → confidence → hypothesis → anomaly → pattern → context → evidence → observations).

## 3. Alcance

### Capacidades Cognitivas Implementadas (10 servicios):

1. **Observation Capturer** (Perception) - Agentes Linux/Windows/VMware/Red
2. **Evidence Organizer** (Perception) - Collector Service con reglas por dominio
3. **Context Activator** (Perception) - Competencia de coherencia explicativa
4. **Pattern Detector** (Reasoning) - Detección de regularidades
5. **Anomaly Detector** (Reasoning) - Detección de desviaciones vs patrones
6. **Hypothesis Generator** (Reasoning) - Hipótesis testables con criterios de falsificación
7. **Confidence Calibrator** (Learning) - Calibración S + C + ECE
8. **Recommendation Formulator** (Action) - Propuesta de acción con rationale trazable
9. **Decision Committer** (Action) - Compromiso con autoridad y outcomes falsificables
10. **Report Generator** (Action - external) - Formateo de documentos de salida

### Calidad de Datos

- **Quality Classes Q1-Q4**: Q1=direct measurement [0.75,1.0], Q2=corroborated [0.50,0.75), Q3=statistical [0.25,0.50), Q4=anecdotal [0.00,0.25)
- **Weights wᵢ**: Asignados en creación, nunca retrofiteados
- **Evidential Support**: S = log-odds L = L0 + Σ wᵢ·eᵢ + sigmoide
- **Explanatory Coherence**: C(H) = P/(P+N+U) sobre {explains, contradicts, coherent_with, incoherent_with}

## 4. ¿Dónde se Aplica?

### Dominios de Aplicación:

- **Data Centers**: Monitoreo de infraestructura física y virtual (servidores Linux/Windows, VMware, almacenamiento)
- **Entornos de TI Enterprise**: ANY infraestructura con necesidad de diagnóstico cognitivo estructurado
- **Múltiples Tenants**: Isolation completa por tenant_id en todos los artefactos
- **Entornos Híbridos**: Agentes para Linux (psutil/SSH), Windows (WMI/WinRM), VMware (pyVmomi), Red (nmap/SNMP)

### Tipos de Infraestructura Soportada:

- Servidores físicos Linux
- Servidores Windows con WMI
- Entornos VMware vSphere
- Dispositivos de red (SNMP, Nmap)
- Sistemas de backup (Veeam REST API)
- Active Directory (LDAP + PowerShell)

## 5. ¿En Qué Entornos es Útil?

### Entornos de Despliegue:

- **SaaS Multi-tenant**: Plataforma como servicio con aislamiento por tenant
- **On-premise**: Despliegue local con Docker Compose
- **Nube híbrida**: Integración con infraestructura existente
- **Entornos de desarrollo/producción**: Mismo schema, configuraciones por entorno

### Requisitos Técnicos:

- **Backend**: Python 3.11+ con FastAPI
- **Base de datos**: PostgreSQL 16 (sin dependencia de TimescaleDB; las observaciones usan columnas TIMESTAMPTZ nativas)
- **Cache**: Redis para Working Memory (contexto activo, últimas 5 minutos)
- **Contenedorización**: Docker + Docker Compose
- **Agentes**: Python SSH para Linux, WinRM para Windows, pyVmomi para VMware

### Puertos del Sistema:

- 8090-8099: Servicios cognitivos (pattern, anomaly, hypothesis, confidence, recommendation, decision)
- 8100: API Gateway (cognitive boundary enforcement)
- 8098: Report Service
- 8099: User Service (Auth/RBAC)

## 6. Secuencia de Funcionamiento

```
┌─────────────────────────────────────────────────────────────────┐
│                    FLUJO CANÓNICO COGNITIVO                     │
├─────────────────────────────────────────────────────────────────┤
│ 1. Reality (Servidores)                                             │
│    └─► Observations (inmutables por agents)                       │
│                                                                      │
│ 2. Perception Layer                                                 │
│    ├─ Observation Capture (raw facts, sin interpretación)          │
│    ├─ Evidence Organization (Q1-Q4 weights, organización coherente)│
│    └─ Context Activation (competencia explicativa → Active Context)│
│                                                                      │
│ 3. Reasoning Layer                                                │
│    ├─ Pattern Detection (regularidades en Context)                │
│    ├─ Anomaly Detection (desviación vs patrón + tolerance)         │
│    ├─ Hypothesis Generation (explicaciones testables + falsification)│
│    └─ Insight Restructuring (reorganización conocimiento)          │
│                                                                      │
│ 4. Confidence Layer                                               │
│    ├─ Calibration Model (S + C · (1 - ECE))                        │
│    └─ Metacognitive Monitoring (quality detection)                │
│                                                                      │
│ 5. Action Layer                                                   │
│    ├─ Recommendation (propuesta advisory, reversible)              │
│    └─ Decision (commit con authority + expected outcomes falsables)│
│                                                                      │
│ 6. Memory (planificado)                                           │
│    └─ Consolidation outcomes → future confidence calibration        │
│                                                                      │
│ 7. Report Generation (documentación de lo commiteado)               │
│    └─ Formato ejecutivo/tecnico/JSON basado en decisiones           │
└─────────────────────────────────────────────────────────────────┘
```

### Puntos Críticos en la Secuencia:

1. **Nunca saltar Perception → Reasoning sin Evidence → Context**
2. **Nunca acción sin confidence calibrada (R4 gate)**
3. **Cada decisión debe tener outcomes falsificables (R5)**
4. **Recomendaciones son advisory; decisiones requieren authority explícita (R6)**
5. **Observations nunca interpretadas; interpretación surge en Reasoning (P1)**

## 7. Cognitive Compliance Validation

Cada sprint valida:
- [x] **R1**: Exactamente una capacidad cognitiva por componente
- [x] **R2**: Cognitive Contract (Input→Transform→Output) testeado
- [x] **R3**: Cognitive Boundary enforceado
- [x] **R4**: No hay acción sin Confidence
- [x] **R5**: Decisiones con resultados falsificables
- [x] **P1**: Observaciones inmutables, nunca interpretadas
- [x] **P5**: Confidence computada (S+C+ECE), parámetros publicados

### Vertical Slice — prueba de extremo a extremo

`tests/integration/test_cognitive_pipeline_e2e.py` ejercita la cadena cognitiva
completa **en proceso** (sin microservicios) contra PostgreSQL real, usando los
lib/contracts canónicos de cada etapa:

- **Happy path**: Observation (Linux CPU/MEM/DISK Q1) → Evidence
  (`resource_exhaustion_evidence`) → Context (competencia de coherencia
  `resource_pressure`) → Pattern → Anomaly → Hypothesis (≥2 competidoras) →
  Confidence (S+C+ECE ≈ 0.85) → Recommendation → Decision (commit grabado).
- **Trazabilidad**: aserta Decision → Recommendation → Hypothesis → Anomaly →
  Context → Evidence → Observations, todo dentro del mismo `tenant_id`.
- **Tenant isolation**: dos tenants nunca se ven sus artefactos (R1/P1 scope).
- **R4 / sin evidencia**: `calibrate` rechaza evidencia vacía; `commit` devuelve
  `None` cuando `confidence_score < 0.75` (gate de compromiso).

Este test corre en el paso CI `pytest tests/`. El escenario reproducible sin
infraestructura externa es `scripts/qa_seed.py`.

## 8. Trazabilidad y Provenance

- **Cada artefacto referencia sus inputs**: decision → recommendation → confidence → hypothesis → anomaly → pattern → context → evidence → observations
- **Fila append-only**: Solo INSERT, nunca UPDATE/DELETE en columnas de contenido
- **Dedup idempotente**: ON CONFLICT (id) DO NOTHING en todas las escrituras
- **UUID determinísticos**: Mismo input → mismo id (testing, anti-tuning)
- **Cadenas de trazabilidad completas**: Reportes muestran la traza completa decision → recommendation → confidence → hypothesis → anomaly → pattern → context → evidence → observations