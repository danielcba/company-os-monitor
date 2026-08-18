# Company OS Monitor - FASE 6 y 7: Action Layer — Recommendation, Decision, Procedural Memory (Security)

## Principios Rectores

- **P6 — Deliberate Action**: Recommendation precede Decision; Decision precede Action. Recommendation es advisory y reversible. Decision es committed y accountable.
- **R5**: Every Decision recorded with rationale and expected outcomes (falsifiable).
- **R6**: Explanations are first-class outputs at every layer.
- **R3**: Cognitive boundary enforced architecturally — Perception/Reasoning never execute actions directly.
- **ADR-0002**: Report generation, alerting, dashboard son capacidades externas no-canónicas. Deben originar juicios desde el flujo cognitivo canónico (Recommendation → Decision).

---

# FASE 6: Action Layer — Recommendation & Decision (Report Generation = Formatted Output)

## Arquitectura Cognitiva de la Action Layer

```
CONFIDENCE CALIBRATION (Learning, cross-cutting)
        │
        ▼
┌───────────────────────┐
│  RECOMMENDATION       │  Concept: Recommendation | Family: Action | Capability: Propose
│  (Recommendation Svc) │
│  Input: Active Context + Leading Hypothesis/Insight + Confidence + Action Space
│  Transform: Derive course of action best serving purpose under constraints
│  Output: Recommendation + rationale + expected consequences + confidence + alternatives
└───────────┬───────────┘
            │
            ▼ (Human/System Authority)
┌───────────────────────┐
│  DECISION             │  Concept: Decision | Family: Action | Capability: Commit
│  (Decision Service)   │
│  Input: Recommendation(s) + Confidence + Purpose + Constraints + Risk Tolerance + Authority
│  Transform: Select + commit course of action
│  Output: Decision + recorded rationale + expected outcomes (falsifiable) + confidence + authority
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  EXECUTION & FORMATTING│  Capabilities Externas No-Canónicas (ADR-0002)
│  (Report Generator,   │  - Report Service: Format Recommendation/Decision → PDF/HTML/JSON
│   Alert Dispatcher,   │  - Alert Dispatcher: Decision → Notification (email, webhook, PagerDuty)
│   Dashboard API)      │  - Dashboard API: Active Context + Recommendations + Decisions → UI
└───────────────────────┘
```

## Recommendation Service — Concept: Recommendation | Capacidad: Propose

### Cognitive Contract
- **Input**: Active Context + Leading Hypothesis/Insight + Confidence Score + Action Space (definido explícitamente)
- **Transformation**: Derivar curso de acción que mejor sirva el propósito bajo constraints del contexto actual
- **Output**: 
  - Recommendation (qué hacer)
  - Rationale (por qué — trazable a Evidence/Hypothesis/Insight)
  - Expected Consequences (qué se espera — observable, verificable)
  - Confidence (score calibrado + justification)
  - Alternatives Considered (otras opciones evaluadas con rationale)

### Recommendation Schema (Persistent — decisions table)

```json
{
  "recommendation_id": "uuid",
  "tenant_id": "uuid",
  "hypothesis_id": "uuid",
  "insight_id": "uuid (optional)",
  "confidence_id": "uuid",
  "action_description": "Expand backup volume before day 10, or move backup target to new storage array",
  "rationale": "Disk growth trend (Pattern: disk_growth_weekly_v1, strength 0.87) predicts 95% capacity in 14 days. Hypothesis H1 (new logging) confirmed with confidence 0.82. Expected outcome: backup failure if unaddressed.",
  "expected_consequences": [
    "Backup capacity remains above 20% for next 6 months",
    "No backup failures due to capacity in next 90 days"
  ],
  "alternatives_considered": [
    {"action": "Compress older backups", "rationale": "Lower immediate cost", "rejected_reason": "Higher risk - compression may not keep pace with growth", "confidence": 0.45},
    {"action": "Reduce retention window", "rationale": "Frees space immediately", "rejected_reason": "Compliance violation risk", "confidence": 0.30}
  ],
  "confidence_score": 0.82,
  "confidence_justification": "Strong evidential support (Q1 metrics), high coherence (H1 explains all anomalies), good historical calibration (ECE=0.08)",
  "status": "proposed",
  "proposed_at": "2026-08-11T10:30:00Z"
}
```

### Action Space Definition (Procedural Memory)
El espacio de acciones permitidas debe ser **explícito** (Recommendation design implications):

| Domain | Action Space (ejemplos) |
|--------|------------------------|
| **Storage** | expand_volume, add_disk, move_data, compress, purge_old, change_retention, enable_dedup |
| **Compute** | scale_up, scale_out, restart_service, migrate_vm, adjust_limits, tune_kernel |
| **Security** | reset_credentials, revoke_sessions, enable_mfa, block_ip, isolate_host, rotate_keys |
| **Backup** | retry_job, change_schedule, change_target, verify_integrity, test_restore |
| **Network** | block_port, modify_acl, reroute_traffic, enable_ddos_protection |
| **Observability** | increase_log_level, add_metric, create_alert_rule, adjust_threshold |

---

## Decision Service — Concept: Decision | Capacidad: Commit

### Cognitive Contract
- **Input**: Recommendation(s) + Confidence Scores + Purpose + Constraints + Risk Tolerance + Commitment Authority
- **Transformation**: Seleccionar y comprometer curso de acción
- **Output**:
  - Decision (curso de acción definitivo seleccionado)
  - Recorded Rationale (trazabilidad completa: Evidence → Hypothesis → Insight → Confidence → Recommendation → Decision)
  - Expected Outcomes (falsificables, en términos observables — **Decision spec**)
  - Confidence Score asociado
  - Commitment Authority (quién/qué autoriza: user role, automated policy, SLA)

### Decision Schema (Persistent — decisions table)

```json
{
  "decision_id": "uuid",
  "tenant_id": "uuid",
  "recommendation_id": "uuid",
  "confidence_id": "uuid",
  "authority_id": "uuid",  // user_id or policy_id
  "commitment": "Expand backup volume on day 8, increase alert threshold to 90%, document change in runbook",
  "expected_outcomes": [
    {"prediction": "Backup capacity remains above 20% for next 6 months", "verifiable_by": "disk_free_percent metric", "deadline": "2027-02-11"},
    {"prediction": "No backup failures due to capacity in next 90 days", "verifiable_by": "backup_job_status != failed", "deadline": "2026-11-11"}
  ],
  "risk_tolerance": "low",
  "confidence_score": 0.82,
  "status": "committed",
  "committed_at": "2026-08-11T11:00:00Z",
  "executed_at": "2026-08-11T11:15:00Z",
  "actual_outcomes": null  // populated after deadline for Learning loop
}
```

### Falsifiabilidad (Decision Spec — Popper 1934)
- **Expected outcomes MUST be stated in observable, verifiable terms BEFORE execution**
- Si observed outcome = expected outcome → Decision + Confidence confirmed
- Si observed outcome ≠ expected outcome → Context, Hypothesis, o Confidence calibration MUST be revised
- Esta comparación es el **primary input to Confidence calibration y Learning loop**

---

## Report Generator — Capacidad Externa No-Canónica (ADR-0002)

El Report Service **NO genera recomendaciones ni decisiones**. Solo **formatea** Recommendations y Decisions ya cometidas.

### Cognitive Contract (Report Service)
- **Input**: Decision(s) + Recommendation(s) + Active Context + Confidence Scores + Tenant Context
- **Transformation**: Renderizar en formato solicitado (PDF ejecutivo, PDF técnico, JSON, HTML dashboard)
- **Output**: Documento formateado (archivo, stream, API response)

### Report Types (Formatos de Salida)

| Report Type | Audience | Source Content | Format |
|-------------|----------|----------------|--------|
| **Executive Summary** | Directivos (C-level) | Decision.commitment + expected_outcomes (business language) + health_score | PDF 1 página, HTML |
| **Technical Report** | Administradores IT | Full trace: Evidence → Context → Pattern → Anomaly → Hypothesis → Insight → Confidence → Recommendation → Decision + alternatives | PDF 5-10 páginas, JSON |
| **Compliance Report** | Auditores | Decision trail + audit_log + expected vs actual outcomes + calibration history | PDF, JSON |
| **Operational Dashboard** | Operadores (real-time) | Active Context + pending Recommendations + recent Decisions + Confidence scores | HTML/HTMX (live) |

### Executive Summary Template (1 página, non-technical)

```
┌─────────────────────────────────────────────────────────────────────┐
│  COS-Monitor Executive Summary — Tenant: ACME Corp                 │
│  Period: 2026-08-04 to 2026-08-11  |  Health Score: 72/100 (🟡)   │
├─────────────────────────────────────────────────────────────────────┤
│  TOP 3 CRITICAL DECISIONS THIS WEEK                                │
│  1. [D-2026-08-11-001] Expand ERP backup volume (Day 8)            │
│     Risk: ERP backup failure in 14 days → business stoppage        │
│     Confidence: 82%  |  Cost: $2,400  |  ROI: Prevents $500k/hr downtime │
│  2. [D-2026-08-09-003] Reset 23 dormant AD accounts                │
│     Risk: Orphaned privileged accounts → compliance violation       │
│     Confidence: 91%  |  Cost: $0 (automated)  |  ROI: Audit pass   │
│  3. [D-2026-08-07-002] Migrate VMware workloads off DS-04          │
│     Risk: Datastore 89% full → VM crashes                          │
│     Confidence: 78%  |  Cost: $1,200  |  ROI: Prevents 4hr outage  │
├─────────────────────────────────────────────────────────────────────┤
│  TOP 3 FUTURE RISKS (Hypotheses with Confidence > 60%)             │
│  1. Database growth acceleration (H1: new feature logging) — 68%   │
│  2. Network bandwidth saturation (Pattern: monthly peak growth) — 62%│
│  3. Certificate expiration cluster (12 certs expiring Q4) — 85%    │
├─────────────────────────────────────────────────────────────────────┤
│  DECISIONS REQUIRING YOUR AUTHORITY                                 │
│  • D-2026-08-11-004: Approve $15k storage expansion (deadline: Day 5)│
│  • D-2026-08-11-005: Authorize emergency VM migration window        │
└─────────────────────────────────────────────────────────────────────┘
```

### Technical Report Template (Trazabilidad Cognitiva Completa)

```
SECTION 1: COGNITIVE TRACE (per Decision)
  Decision ID: D-2026-08-11-001
  Authority: it_admin@acme.com (role: admin)
  Confidence: 0.82 (Calibration: S=0.85, C=0.78, ECE=0.08, α=0.5)

SECTION 2: EVIDENCE CHAIN
  Observations (Q1): disk_free_bytes (1024000), disk_total_bytes (1073741824) @ 5-min intervals
  Evidence (Q1): resource_exhaustion_evidence (weight 0.92) — organized from 1,247 observations
  Context: Active Context "storage_controller_saturation" (coherence 0.89 vs alt 0.34)

SECTION 3: REASONING CHAIN
  Pattern: disk_growth_weekly_v1 (strength 0.87, weekly periodicity confirmed)
  Anomaly: growth_rate_change (CUSUM=12.3 > threshold 5) — collective anomaly
  Hypotheses:
    H1: New logging verbosity (CONFIRMED, confidence 0.82, falsified: verbosity unchanged → false)
    H2: Backup retention change (FALSIFIED, confidence 0.15)
    H3: DB auto-growth misconfig (FALSIFIED, confidence 0.08)
  Insight: All symptoms (backup fail, disk pressure, slow response) = single constraint: storage controller saturation

SECTION 4: CONFIDENCE CALIBRATION
  Evidential Support (S): 0.85 — Q1 metrics, 1,247 observations
  Explanatory Coherence (C): 0.78 — H1 explains all anomalies, no contradictions
  Historical Calibration (1-ECE): 0.92 — 114/120 similar predictions correct
  Final: C_final = [0.5×0.85 + 0.5×0.78] × 0.92 = 0.82

SECTION 5: RECOMMENDATION & ALTERNATIVES
  Rec: Expand volume Day 8 / Move to new array
  Alt 1: Compress (rejected: confidence 0.45, risk high)
  Alt 2: Reduce retention (rejected: confidence 0.30, compliance violation)

SECTION 6: DECISION & EXPECTED OUTCOMES (Falsifiable)
  Commitment: Expand volume Day 8, alert threshold 90%, document runbook
  Outcome 1: disk_free_percent > 20% until 2027-02-11 (verifiable: metric)
  Outcome 2: backup_job_status != failed until 2026-11-11 (verifiable: job status)

SECTION 7: LEARNING LOOP (Post-Execution)
  [To be populated after deadline] Actual vs Expected → Brier Score update → ECE recalibration
```

---

# FASE 7: Procedural Memory — Security, Hardening, Audit (Cognitive Boundary Enforcement)

## Posición Arquitectónica

La seguridad en Company OS **no es una capa separada**. Es **Procedural Memory** (cómo hacer las cosas correctamente) y **Cognitive Boundary Enforcement** (R3: Perception nunca implica action authority).

| Security Concern | Cognitive Architecture Mapping |
|------------------|--------------------------------|
| **Encryption** | Procedural Memory: "How to capture/store observations securely" |
| **Authentication/Authorization** | Decision Authority binding (Decision.spec: commitment authority) + Cognitive Boundary (R3) |
| **Secrets Management** | Procedural Memory: "How to access external systems (agents, APIs) securely" |
| **Hardening** | Procedural Memory: "How to run cognitive services with minimal attack surface" |
| **Audit Logging** | Episodic Memory: "What happened, when, in what order" (Decision trails, Context activations) |
| **Compliance** | Semantic Memory: Laws, standards as knowledge structures informing Context/Purpose |

---

## Procedural Memory: Security Contracts (Versionados en Git, Deployed via CI/CD)

### 1. Observation Capture Security (Agentes)
```yaml
# procedural_memory/agent_security.yaml
agent_security_contract:
  capture:
    - TLS 1.3 mutual auth for all agent↔collector communication
    - Agent identity via mTLS certificates (rotated 90 days via Vault)
    - Observations signed by agent (Ed25519) → tamper-evident (P1: immutable observations)
  storage:
    - Observations encrypted at rest (AES-256-GCM, per-tenant keys)
    - Quality Class assigned at capture (never retrofitted)
  network:
    - Agents initiate outbound only (no inbound ports) — Cognitive Boundary: Reality → Perception only
    - Egress allowlist: collector endpoints only
```

### 2. Evidence Organization Security (Collector)
```yaml
# procedural_memory/collector_security.yaml
collector_security_contract:
  ingestion:
    - Verify agent signature on every Observation
    - Reject Observations with invalid/expired certificates
    - Rate limit per agent (100 obs/min) — prevent flood
  organization:
    - Evidence organization rules are code (Procedural Memory), not data
    - Rules versioned, reviewed, deployed via CI/CD
  storage:
    - Evidence encrypted at rest (AES-256-GCM)
    - Q1-Q4 Quality Class immutable once assigned
```

### 3. Cognitive Boundary Enforcement (API Gateway — R3)
```yaml
# procedural_memory/cognitive_boundary.yaml
cognitive_boundary_contract:
  perception_to_reasoning:
    - ONLY Evidence → Context flow allowed
    - Raw Observations NEVER exposed to Reasoning/Action layers directly
    - API Gateway enforces: /api/v1/evidence/* → Context Service ONLY
  
  reasoning_to_action:
    - ONLY Recommendation (with Confidence) → Decision flow allowed
    - Hypothesis/Insight/Pattern NEVER directly trigger alerts/actions
    - Confidence score MUST be present (R4) — Gateway validates
  
  action_execution:
    - Decision execution requires explicit authority binding
    - Automated decisions: policy_id with defined scope/limits
    - Human decisions: user_id with role authorization
    - ALL executions logged to Episodic Memory (audit_log)
  
  external_capabilities (ADR-0002):
    - Report Generator: READ-only access to Decision/Recommendation/Context
    - Alert Dispatcher: TRIGGERED only by Decision (not Anomaly/Hypothesis)
    - Dashboard: READ-only Active Context + Recommendations + Decisions
```

### 4. Decision Authority & RBAC (Decision.spec → Procedural Memory)
```yaml
# procedural_memory/decision_authority.yaml
decision_authority:
  roles:
    viewer:
      - READ: Active Context, Recommendations, Decisions, Reports
      - NO: Propose, Commit, Execute
    operator:
      - READ: all viewer +
      - ACKNOWLEDGE: Decision (confirm execution started)
      - NO: Propose, Commit
    admin:
      - READ: all operator +
      - PROPOSE: Recommendation (within tenant scope)
      - COMMIT: Decision (within tenant scope, risk_tolerance: low/medium)
      - AUTHORITY: Automated policies (defined scope)
    superadmin:
      - ALL admin +
      - COMMIT: Decision (cross-tenant, risk_tolerance: high)
      - DEFINE: Automated policies, Action Space, Tolerance Thresholds
  
  automated_policies:
    - Defined by superadmin, versioned in Git
    - Scope: specific anomaly/pattern types, specific action space subset
    - Limits: max $ cost, max risk_tolerance, requires human approval above threshold
    - Every automated Decision logged with policy_id as authority
```

### 5. Secrets Management (Procedural Memory: How to Access External Systems)
```yaml
# procedural_memory/secrets.yaml
secrets_contract:
  storage: HashiCorp Vault (production) | .env (development only)
  rotation: Automatic every 90 days (Vault rotation policies)
  access:
    - Agents: Dynamic secrets (lease 1h, renewable) — never static creds
    - Collector: Static token (Vault AppRole, rotated 90 days)
    - LM Studio: No secrets needed (local)
    - External APIs (Veeam, vCenter): Dynamic secrets per integration
  audit: Every secret access logged (Vault audit device → Episodic Memory)
```

### 6. Infrastructure Hardening (Procedural Memory: How to Run Cognitive Services)
```yaml
# procedural_memory/hardening.yaml
hardening_contract:
  containers:
    - Non-root user (UID 1000+)
    - Read-only rootfs
    - Drop ALL capabilities, add only required (NET_BIND_SERVICE for :443)
    - seccomp profile (default deny, allow syscalls)
    - AppArmor profile per service
    - No shell, no package manager in runtime image
  
  database (PostgreSQL/TimescaleDB):
    - SSL only (cert from Vault, rotated 90 days)
    - pg_hba.conf: cert auth for app, reject password
    - Roles: readonly (dashboard), readwrite (collector), admin (migrations only)
    - Row-level security: tenant_id enforcement at DB level
  
  api_gateway (Nginx/Traefik):
    - WAF: ModSecurity OWASP CRS 3.3+
    - Rate limiting: 100 req/min per user, 10 req/min per API key
    - DDoS: connection limits, request body limits
    - mTLS termination for agent traffic
    - Cognitive Boundary rules as middleware (see cognitive_boundary.yaml)
  
  OS (Ubuntu 24.04 LTS):
    - Automatic security updates (unattended-upgrades)
    - fail2ban: SSH, API auth failures
    - auditd: all syscalls for cognitive services
    - CIS Benchmark Level 1 applied
```

---

## Episodic Memory: Audit Logging (Decision Trails + Cognitive Traces)

### Audit Log Schema (Episodic Memory — what happened, when, in order)

```sql
-- audit_log (Episodic Memory)
CREATE TABLE audit_log (
    id UUID PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    user_id UUID,  -- null for automated decisions
    policy_id UUID,  -- for automated decisions
    cognitive_layer VARCHAR(20) NOT NULL,  -- perception/reasoning/confidence/action/memory
    cognitive_concept VARCHAR(30) NOT NULL,  -- observation/evidence/context/pattern/anomaly/hypothesis/insight/confidence/recommendation/decision
    action VARCHAR(50) NOT NULL,  -- captured/organized/activated/detected/generated/restructured/calibrated/proposed/committed/executed
    resource_type VARCHAR(50) NOT NULL,  -- observation/evidence/context/pattern/anomaly/hypothesis/insight/confidence/recommendation/decision
    resource_id UUID NOT NULL,
    details JSONB,  -- {old_values, new_values, confidence_score, rationale, expected_outcomes}
    ip_address INET,
    user_agent TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- Immutability (Episodic Memory constraint)
    CONSTRAINT audit_log_immutable CHECK (false)  -- Enforced by trigger: no UPDATE/DELETE
);

-- Partition by month + tenant for scale
CREATE INDEX idx_audit_tenant_time ON audit_log (tenant_id, timestamp DESC);
CREATE INDEX idx_audit_cognitive_trace ON audit_log (cognitive_layer, cognitive_concept, resource_id);
```

### What Gets Logged (Cognitive Trace Completeness)

| Cognitive Layer | Concept | Actions Logged |
|-----------------|---------|----------------|
| **Perception** | Observation | captured (agent_id, fact_type, quality_class) |
| | Evidence | organized (evidence_id, observation_ids[], quality_class, weight) |
| | Context | activated (context_id, mental_model_id, coherence_score, competing_models[]) |
| **Reasoning** | Pattern | detected (pattern_id, strength, type) |
| | Anomaly | detected (anomaly_id, pattern_id, deviation_score, tolerance) |
| | Hypothesis | generated (hypothesis_id, anomaly_ids[], predicted_consequences[], falsification) |
| | | confirmed/falsified (hypothesis_id, outcome, confidence_before/after) |
| | Insight | restructured (insight_id, hypothesis_ids[], prior_understanding, new_understanding) |
| **Confidence** | Confidence | calibrated (confidence_id, target_type, target_id, S, C, ECE, C_final, α, M, L₀) |
| **Action** | Recommendation | proposed (rec_id, hypothesis_id, confidence_id, alternatives[]) |
| | Decision | committed (decision_id, rec_id, authority_id, expected_outcomes[], risk_tolerance) |
| | | executed (decision_id, actual_outcomes[], outcome_match: true/false/partial) |
| **Memory** | Calibration | updated (judgment_class, old_ECE, new_ECE, brier_score, trigger) |

### Retention Policy (Episodic Memory)
- **Hot (Redis/Working Memory)**: Last 30 days — real-time dashboard, active investigations
- **Warm (PostgreSQL/Episodic)**: 3 years — compliance, calibration history, decision trails
- **Cold (MinIO/Semantic)**: 7+ years — compressed Parquet, immutable, for longitudinal learning

---

## Semantic Memory: Compliance Standards as Knowledge Structures

Los estándares (ISO 27001, CIS, NIST) son **Semantic Memory** — knowledge structures que informan:
- **Context Activation**: Purpose = "compliance assessment" → activates compliance mental models
- **Tolerance Thresholds**: CIS Control 4.1 → log retention tolerance = 365 days minimum
- **Action Space**: ISO 27001 A.9.2.3 → MFA action required for privileged access decisions
- **Expected Outcomes**: NIST PR.DS-1 → encryption verification as falsifiable decision outcome

### Compliance Mapping (Semantic Memory → Cognitive Contracts)

| Standard | Control | Cognitive Contract Impact |
|----------|---------|---------------------------|
| **ISO 27001 A.9.2.3** | MFA for privileged access | Decision Authority: admin/superadmin decisions require MFA (authority binding) |
| **ISO 27001 A.10** | Cryptography | Procedural Memory: Observation capture/storage encryption contracts |
| **ISO 27001 A.12.4.1** | Event logging protection | Evidence/Observation immutability (P1) + Audit log immutability (Episodic Memory) |
| **CIS Control 1** | Inventory | Observation Capture: asset discovery patterns (network-agent) |
| **CIS Control 4.1** | Log retention > 12 months | Episodic Memory: audit_log retention 3 years minimum |
| **CIS Control 6** | Centralized logs | Evidence Organization: all Observations → Evidence (single source) |
| **CIS Control 13** | Data protection | Procedural Memory: encryption at rest/in transit contracts |
| **CIS Control 16** | Monitoring | Pattern/Anomaly Detection: continuous cognitive monitoring |
| **NIST CSF IDENTIFY** | Asset Management | Context Activation: asset inventory mental model |
| **NIST CSF PROTECT** | Data Security | Procedural Memory: encryption, access control contracts |
| **NIST CSF DETECT** | Anomalies | Anomaly Detection: explicit tolerances, falsifiable |
| **NIST CSF RESPOND** | Incidents | Decision → Execution → Learning loop (expected vs actual) |

---

## Design Implications (Security as Cognitive Architecture)

1. **R3 Enforcement**: Security IS the cognitive boundary implementation. No component bypasses Perception→Reasoning→Confidence→Action.

2. **P1/P5 in Security**: Observations (including security events) are immutable. Confidence calibration applies to security hypotheses (e.g., "this auth burst = compromise" has confidence score).

3. **Decision Authority = Authorization**: RBAC no es "permisos en BD" — es **authority binding en Decision** (Decision.spec: commitment authority). Cada Decision registra quién/qué autorizó.

4. **Audit = Episodic Memory**: Audit log no es "tabla de seguridad" — es **Episodic Memory** del sistema cognitivo. Registra TODOS los pasos cognitivos, no solo login/logout.

5. **Compliance = Semantic Memory**: Estándares son knowledge structures que informan Purpose, Tolerances, Action Space, Expected Outcomes.

6. **Learning from Security Incidents**: Decision outcomes (expected vs actual) → Confidence recalibration → better future security hypotheses.

7. **No "Security Service"**: Seguridad es transversal (Procedural Memory + Boundary + Memory). No microservicio separado.