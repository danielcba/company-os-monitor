# Company OS Monitor - FASE 8, 9 y 10: Modelo Comercial, Roadmap y Backlog (Cognitive-Aligned)

## Principios Rectores

- **ADR-0001**: Company OS es el centro cognitivo. COS-Monitor es su primera implementación de producto.
- **ADR-0002**: El flujo canónico (Perception → Reasoning → Confidence → Action) es el cerebro. Todo lo demás (pricing, roadmap, sales) sirve al producto que implementa ese flujo.
- **R7**: La arquitectura guía el código, nunca lo contrario. El roadmap y backlog deben reflejar la construcción del pipeline cognitivo, no features aisladas.
- **P7**: Learning Through Outcome — métricas de éxito (OKRs) deben medir outcomes cognitivos, no solo métricas de vanidad.

---

# FASE 8: Modelo Comercial (Cognitive Product Positioning)

## Planes Definidos por Capacidad Cognitiva Entregada

| Capacidad Cognitiva | Básico (Cognitive MVP) | Profesional (Full Pipeline) | Enterprise (Cognitive Platform) |
|---------------------|------------------------|------------------------------|----------------------------------|
| **Perception Layer** | Linux + Windows Observation Capture | All agents (Linux, Win, VMware, Network, Backup, AD) | Custom agents + on-prem deployment |
| **Evidence Organization** | Resource + Service Evidence | All Evidence types + custom rules | Custom Evidence rules (Procedural Memory) |
| **Context Activation** | Single mental model (infrastructure health) | Multiple models (security, capacity, compliance) | Custom mental models + coherence tuning |
| **Pattern Detection** | Threshold + basic trends | Statistical patterns (ARIMA, Holt-Winters, Prophet) | ML patterns (XGBoost, LSTM) + custom |
| **Anomaly Detection** | Point anomalies (threshold breach) | Contextual + collective anomalies | Custom anomaly classes + tolerances |
| **Hypothesis Generation** | Rule-based (predefined templates) | LM Studio assisted (Qwen 14B) | DeepSeek R1 32B + custom hypotheses |
| **Insight Restructuring** | None (manual) | LM Studio triggered (frame failure detection) | Continuous restructuring + analogy |
| **Confidence Calibration** | Basic (evidential support only) | Full Calibration Model (S + C + ECE) | Custom α, M, L₀ + historical calibration |
| **Recommendation** | Single recommendation per anomaly | Multiple alternatives with rationale | Custom action space + risk models |
| **Decision** | Manual commit (human authority) | Semi-automated (policy-bound) | Fully automated policies + human override |
| **Memory (Episodic)** | 30 days (audit_log, decisions) | 90 days + calibration history | 365 days + longitudinal learning |
| **Memory (Semantic)** | Standard compliance mappings | Custom compliance frameworks | Custom knowledge bases + mental models |
| **Procedural Memory** | Fixed contracts (security, hardening) | Tunable contracts (thresholds, tolerances) | Full Procedural Memory customization |
| **External Capabilities** | Dashboard + PDF Reports + Email Alerts | API + Webhooks + On-demand Reports | SDK + White-label + Marketplace |

## Precios (Reflejan Cognitive Throughput Delivered)

| Región | Básico | Profesional | Enterprise |
|--------|--------|-------------|------------|
| **Argentina** | ARS $15,000/mes | ARS $45,000/mes | ARS $120,000/mes |
| **Latinoamérica** | USD $29/mes | USD $89/mes | USD $249/mes |
| **Estados Unidos** | USD $49/mes | USD $149/mes | USD $499/mes |

### Justificación Cognitive-First

- **Básico**: Entrega Perception Layer completo (Observation → Evidence → Context) + Action Layer manual. Suficiente para "ver y decidir".
- **Profesional**: Entrega Reasoning Layer completo (Pattern → Anomaly → Hypothesis → Insight → Confidence) + Recommendation automatizada. Diferenciador: "predecir y proponer".
- **Enterprise**: Entrega Learning Loop operativo (Memory + Calibration + Procedural Memory customization) + Platform capabilities. Diferenciador: "aprender y adaptar".

---

# FASE 9: Roadmap (Cognitive Pipeline Construction)

Cada sprint construye una **capacidad cognitiva** del pipeline canónico, no features aisladas.

## Sprint 0-4 (Mes 1): Perception Layer MVP — **Cognitive Foundation**

**Objetivo Cognitivo**: Reality → Observation → Evidence → Context operativo para 1 tenant piloto

| Sprint | Capacidad Cognitiva | Entregable | Cognitive Contract Validado |
|--------|---------------------|------------|----------------------------|
| 0 | Infraestructura Cognitiva | Docker, PostgreSQL, TimescaleDB, Redis, CI/CD | Data Layer soporta immutable Observations + Evidence |
| 1 | Observation Capture (Linux) | `linux-agent` (psutil/SSH) → Observation Bus | P1: Immutable capture, Q1 Quality Class |
| 2 | Observation Capture (Windows) | `windows-agent` (WMI/WinRM) → Observation Bus | P1: Immutable capture, Q1 Quality Class |
| 3 | Evidence Organization | `collector-service` → Evidence (resource_exhaustion, service_degradation) | Evidence Spec: Q1-Q4, weights, no interpretation |
| 4 | Context Activation | `context-service` → Active Context (coherence competition: 5 mental models × 3 purposes, ≥2 modelos por purpose) | P2: Coherence competition, Context selected not generated |

**Cognitive Gate**: Active Context renderizado en Dashboard (HTMX) mostrando Evidence organizado, NO métricas crudas. Zero alerts, zero recommendations — solo Perception Layer.

---

## Sprint 5-12 (Q1): Reasoning Layer Foundation — **Cognitive Core**

**Objetivo Cognitivo**: Context → Pattern → Anomaly → Hypothesis → Confidence → Recommendation → Decision para 5 tenants

| Sprint | Capacidad Cognitiva | Entregable | Cognitive Contract Validado |
|--------|---------------------|------------|----------------------------|
| 5 | Pattern Detection | `pattern-service` (disk_growth_weekly, backup_friday_periodic) | Pattern Spec: strength measure, temporal periodic |
| 6 | Anomaly Detection | `anomaly-service` (growth_rate_change, schedule_deviation) | Anomaly Spec: tolerance explicit, deviation score |
| 7 | Hypothesis Generation | `hypothesis-service` (templates + LM Studio Qwen 14B) | Hypothesis Spec: falsification criterion, predicted consequences |
| 8 | Confidence Calibration | `confidence-service` (Calibration Model S+C+ECE, α=0.5) | Confidence Spec: computed not intuited, published params |
| 9 | Recommendation | `recommendation-service` (action space, alternatives, rationale) | Recommendation Spec: advisory, reversible, traceable |
| 10 | Decision | `decision-service` (commitment, expected outcomes falsifiable) | Decision Spec: authority binding, falsifiable outcomes |
| 11 | Report Generator | `report-service` (Executive + Technical templates) | ADR-0002: Formats Decision/Recommendation, no bypass |
| 12 | Multi-tenant + Auth | `user-service` (JWT, RBAC, tenant isolation) | Decision Authority: roles map to commitment authority |

**Cognitive Gate**: Primer Decision commitida con expected outcomes falsificables. Learning loop inicia (comparación actual vs esperado a 30/60/90 días).

---

## Sprint 13-24 (H1): Reasoning Layer Depth + Learning — **Cognitive Maturity**

**Objetivo Cognitivo**: Insight Restructuring + Historical Calibration + Procedural Memory tuning para 25 tenants

| Sprint | Capacidad Cognitiva | Entregable | Cognitive Contract Validado |
|--------|---------------------|------------|----------------------------|
| 13 | Insight Restructuring | `insight-service` (frame failure triggers, LM Studio DeepSeek R1) | Insight Spec: restructures knowledge, updates mental model |
| 14 | Historical Calibration | ECE monitoring, Brier Score tracking, calibration alerts | Confidence Spec: Confidence ← Memory (Learning loop) |
| 15 | Procedural Memory v2 | Tolerance thresholds tunable, Action Space configurable | Procedural Memory: contracts versioned, deployed via CI/CD |
| 16 | Advanced Patterns | Correlation clusters, event sequences, threshold approach | Pattern Spec: multiple types, library versioned |
| 17 | Advanced Anomalies | Contextual + collective anomalies, CUSUM, rate change | Anomaly Spec: three classes, explicit tolerances |
| 18 | LM Studio Upgrade | Qwen 32B (GPU), structured output validation | External Tool Contract: CognitiveTool.validate_output() |
| 19 | Compliance Semantic Memory | ISO 27001, CIS, NIST as knowledge structures | Semantic Memory: informs Purpose, Tolerances, Action Space |
| 20 | Episodic Memory Query | Audit trail UI, decision trail visualization | Episodic Memory: what happened, when, in order |
| 21 | Cognitive Boundary Hardening | Gateway middleware enforcing R3, automated policy decisions | R3: Perception never implies action authority |
| 22 | On-prem Cognitive Package | Docker sellado con full pipeline + Procedural Memory | ADR-0002: Product = canonical flow + external capabilities |
| 23 | Sales Funnel Cognitive | Landing page explains cognitive value (not feature list) | P7: Learning Through Outcome — measure cognitive value delivery |
| 24 | H1 Retrospective | Calibration review, ECE analysis, cognitive debt audit | P7: Compare expected vs actual cognitive outcomes |

**Cognitive Gate**: ECE < 0.15 for all judgment classes. Insight restructuring triggered automatically. Procedural Memory contracts reviewed quarterly.

---

## Sprint 25-48 (Año 1): Learning Loop + Platform — **Cognitive Platform**

**Objetivo Cognitivo**: Memory consolidation + Custom mental models + Partner ecosystem para 100+ tenants

| Sprint | Capacidad Cognitiva | Entregable | Cognitive Contract Validado |
|--------|---------------------|------------|----------------------------|
| 25-28 | Memory Consolidation | Working→Episodic→Semantic pipeline, retention policies | Memory Stratification: Working/Episodic/Semantic/Procedural |
| 29-32 | Custom Mental Models | Tenant-specific models, coherence tuning, model marketplace | P2: Explanatory coherence with custom models |
| 33-36 | Partner Procedural Memory | MSP white-label contracts, shared Procedural Memory | Procedural Memory: versioned, shared, auditable |
| 37-40 | SDK + Marketplace | External developers add Observation Capturers, Evidence Rules | ADR-0002: Blueprint before code, cognitive contracts required |
| 41-44 | Multi-region Cognitive | Active Context replication, Decision authority federation | Cognitive Boundary: consistent across regions |
| 45-48 | $1M ARR Cognitive | Cognitive value metrics (decisions committed, outcomes matched, ECE trends) | P7: Success measured by learning outcomes, not just revenue |

---

# FASE 10: Backlog Priorizado por Cognitive ROI

Priorización por **impacto en el pipeline cognitivo** (no ROI financiero aislado). Cada item mapea a un Cognitive Contract.

| # | Capacidad Cognitiva | Cognitive Layer | Concepto | Prioridad | Complejidad | Dependencias | Horas | Cognitive Value |
|---|---------------------|-----------------|----------|-----------|-------------|--------------|-------|-----------------|
| 1 | Linux Observation Capture | Perception | Observation | Crítica | Baja | Ninguna | 40 | Foundation: sin Observation no hay pipeline |
| 2 | Windows Observation Capture | Perception | Observation | Crítica | Media | #1 | 60 | Completa Perception para entornos híbridos |
| 3 | Evidence Organization | Perception | Evidence | Crítica | Media | #1, #2 | 50 | Transforma Observations → Evidence (Q1-Q4) |
| 4 | Context Activation | Perception | Context | Crítica | Alta | #3 | 80 | Active Context = foundation para todo Reasoning |
| 5 | Pattern Detection (temporal) | Reasoning | Pattern | Crítica | Alta | #4 | 60 | Primer paso Reasoning: detecta regularidad |
| 6 | Anomaly Detection (point) | Reasoning | Anomaly | Crítica | Media | #5 | 40 | Detecta desviación → dispara Hypothesis |
| 7 | Hypothesis Generation (templates) | Reasoning | Hypothesis | Crítica | Alta | #6 | 60 | Explicaciones testables con falsificación |
| 8 | Confidence Calibration (basic) | Learning | Confidence | Crítica | Alta | #7 | 60 | R4: Ningún juicio influye acción sin Confidence |
| 9 | Recommendation | Action | Recommendation | Crítica | Media | #8 | 50 | P6: Advisory, reversible, traceable |
| 10 | Decision | Action | Decision | Crítica | Media | #9 | 50 | P6: Commitment + falsifiable outcomes |
| 11 | Report Generator (format) | External | — | Alta | Media | #10 | 40 | ADR-0002: Formatea Decision, no bypass |
| 12 | Multi-tenant + Auth + RBAC | All | Decision Authority | Alta | Alta | #10 | 80 | Authority binding para Decision |
| 13 | VMware Observation Capture | Perception | Observation | Alta | Alta | #1 | 80 | Completa Perception para virtualización |
| 14 | AD Observation Capture | Perception | Observation | Alta | Media | #2 | 40 | Completa Perception para identidad |
| 15 | Backup Observation Capture | Perception | Observation | Alta | Media | #2 | 40 | Completa Perception para recuperación |
| 16 | Network Observation Capture | Perception | Observation | Media | Alta | #1 | 80 | Completa Perception para red |
| 17 | Advanced Patterns (correlation, sequence) | Reasoning | Pattern | Media | Alta | #5 | 80 | Pattern Library depth |
| 18 | Advanced Anomalies (contextual, collective) | Reasoning | Anomaly | Media | Alta | #6 | 60 | Anomaly classes completas |
| 19 | LM Studio Hypothesis Generation | Reasoning | Hypothesis | Media | Alta | #7, #8 | 60 | Abductive reasoning externo |
| 20 | Insight Restructuring | Reasoning | Insight | Media | Muy Alta | #7, #19 | 80 | P3: Transformative intelligence |
| 21 | Historical Calibration (ECE, Brier) | Learning | Confidence | Media | Alta | #8 | 60 | P5: Calibrated confidence real |
| 22 | Procedural Memory v2 (tunable) | Memory | Procedural | Media | Alta | #12 | 60 | Contracts versionados, deployables |
| 23 | Compliance Semantic Memory | Memory | Semantic | Media | Media | #4 | 40 | Standards as knowledge structures |
| 24 | Episodic Memory Query UI | Memory | Episodic | Media | Media | #10 | 40 | Decision trails, audit visualization |
| 25 | Cognitive Boundary Hardening | All | Boundary | Media | Alta | #12 | 60 | R3 enforcement automatizado |
| 26 | On-prem Cognitive Package | Product | — | Baja | Muy Alta | #1-25 | 120 | Full pipeline deployable |
| 27 | Partner/White-label Procedural Memory | Product | Procedural | Baja | Muy Alta | #22 | 160 | Shared cognitive contracts |
| 28 | SDK + Marketplace | Product | — | Baja | Muy Alta | #25 | 200 | External cognitive capabilities |
| 29 | ISO 27001 Certification | Compliance | Semantic | Baja | Muy Alta | #23 | 300 | Semantic Memory validated externally |
| 30 | SOC 2 Type II | Compliance | Semantic | Baja | Muy Alta | #29 | 500 | Continuous cognitive compliance |

**Total horas estimadas MVP (items 1-12)**: ~610 horas (3-4 meses full-time)  
**Total horas estimadas Año 1 (items 1-25)**: ~1,400 horas  
**Total horas estimadas Plataforma (items 1-30)**: ~2,800 horas  

> **Nota**: El MVP cognitivo requiere más items que el "MVP técnico" anterior porque **cada capa cognitiva debe estar completa** (Perception → Reasoning → Confidence → Action) antes de que el sistema pueda producir Decisions con Confidence calibrada. Un pipeline incompleto viola R4 y P5.

---

## Notas del CTO (Cognitive-First)

### Riesgos Clave Identificados (Cognitive Architecture)

1. **P5 Violation Risk**: LM Studio en CPU (3-5 tok/s) → Confidence calibration degrades si LLM timeout o output incompleto. **Mitigación**: Hypothesis templates internos como fallback, LM Studio solo para diversity.
2. **P2 Violation Risk**: Single mental model en MVP → Context coherence artificial. **Mitigación**: Sprint 4 debe implementar coherence competition (mínimo 2 models: infrastructure_health + security_posture).
3. **R3 Violation Risk**: Alertas por umbral (threshold alerts) en Sprint 0-4 → bypass Reasoning/Confidence. **Eliminado del MVP**: No alerts hasta Decision Service operativo (Sprint 10).
4. **P7 Measurement Risk**: OKRs actuales (clientes, ARR) no miden outcomes cognitivos. **Nuevos OKRs Cognitive**:

### Métricas Clave de Éxito Cognitive (OKRs)

| Quarter | Cognitive OKR | Métrica | Target |
|---------|---------------|---------|--------|
| **Q1** | Perception Layer Complete | Observation capture rate, Evidence quality distribution | 99.9% capture, >90% Q1/Q2 |
| **Q1** | Reasoning Layer Operational | Pattern detection rate, Anomaly precision/recall | >5 patterns/tenant, >80% precision |
| **Q2** | Confidence Calibrated | ECE across all judgment classes | ECE < 0.15 |
| **Q2** | Decision Loop Closed | Decisions committed, outcomes matched at 30/60/90 days | >10 decisions/tenant, >75% match |
| **Q3** | Learning Loop Active | Insight restructuring triggered, Procedural Memory updates | >1 insight/tenant/month, >2 contract updates/qtr |
| **Q4** | Cognitive Platform | Custom mental models deployed, Partner Procedural Memory shared | >3 custom models, >2 partners |

### Estrategia de Salida (Cognitive Asset Value)

- **Año 1-2**: Cognitive MVP → Cognitive Core → Cognitive Maturity. Valor: **pipeline cognitivo operativo con calibración demostrada (ECE < 0.15)**.
- **Año 3**: Cognitive Platform → Custom mental models, Procedural Memory marketplace. Valor: **ecosistema cognitivo extensible**.
- **Año 4-5**: Adquisición por empresa que necesite **arquitectura cognitiva probada** (no solo "IA + monitoring"). Company OS es la arquitectura; COS-Monitor demuestra que funciona en dominios reales.

---

## Cognitive Architecture Compliance Checklist (Por Sprint)

Cada sprint debe validar:

- [ ] **R1**: Cada componente implementa exactly one cognitive capability
- [ ] **R2**: Cada componente tiene Cognitive Contract (Input → Transform → Output) documentado y testado
- [ ] **R3**: Cognitive Boundary enforced (Gateway middleware + tests)
- [ ] **R4**: No conclusion influences action without Confidence (unit tests)
- [ ] **R5**: Every Decision recorded with rationale + expected outcomes (falsifiable)
- [ ] **R6**: Explanations are first-class outputs (API returns rationale, not just results)
- [ ] **R7**: Architecture guides code (Cognitive Contracts drive implementation, not vice versa)
- [ ] **P1**: Observations immutable, never interpreted in Perception
- [ ] **P2**: Context selected by coherence competition, not generated
- [ ] **P3**: Concepts stable, transformations versioned (Procedural Memory)
- [ ] **P4**: Patterns reveal regularity, Hypotheses explain, Insights restructure
- [ ] **P5**: Confidence computed (S+C+ECE), params published, never tuned to match
- [ ] **P6**: Recommendation ≠ Decision, authority explicit
- [ ] **P7**: Expected vs actual outcomes compared, calibration updated
- [ ] **Citación**: toda referencia al marco usa el set canónico (P1–P7, R1–R7, conceptos, ADR-0001/0002); nada fuera de la policy

**Definition of Done Cognitivo**: Todos los checks ✅ + Cognitive Contract tests passing + Calibration metrics logged.
