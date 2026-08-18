# COS-Monitor (Company OS Monitor)

Version: 1.0
Status: Official

---

## What is COS-Monitor?

COS-Monitor is a SaaS platform for monitoring, analysis, and automated diagnosis of IT infrastructure, built on the Company OS cognitive architecture framework.

It implements the canonical cognitive pipeline — **Perception → Reasoning → Learning → Action** — as a set of independent services, each implementing exactly one cognitive capability. From raw observations to committed decisions, every artifact is immutable and fully traceable.

COS-Monitor is not just a data collector. It builds the cognitive chain from raw observations to calibrated recommendations and committed decisions, preserving an immutable, fully traceable record at every step:

- What was observed (facts)
- How it was organized into evidence
- Which context best explains the evidence
- Which patterns and anomalies the reasoning layer detects
- Which testable hypotheses are proposed (never concluded)
- Which confidence each hypothesis has earned
- Which action is recommended, and which decision is committed — with falsifiable expected outcomes

---

## Why does it exist?

Most monitoring platforms produce alerts. Very few produce *understanding*.

Organizations need a system that not only collects signals from their infrastructure but reasons about them in a disciplined way:

- What counts as a fact, and how is it captured without interpretation?
- How is evidence organized from raw observations?
- How is the most coherent explanation selected among competing models?
- When is confidence justified, and how is it calibrated?
- How is a recommendation turned into a committed decision that can be learned from?

COS-Monitor exists to answer these questions with precision, so that every agent, every service, and every human operator in the platform reasons using the same cognitive architecture.

The central conviction:

> The architecture guides the code, never the opposite.

---

## Cognitive Architecture

COS-Monitor implements the canonical pipeline: **Perception → Reasoning → Confidence → Action**.

| Layer | Cognitive Capability | Concept | Service |
|------|---------------------|----------|----------|
| Perception | Observation Capture | Observation | linux-agent, windows-agent, vmware-agent |
| Perception | Evidence Organization | Evidence | collector-service |
| Perception | Context Activation | Context | context-service |
| Reasoning | Pattern Detection | Pattern | pattern-service |
| Reasoning | Anomaly Detection | Anomaly | anomaly-service |
| Reasoning | Hypothesis Generation | Hypothesis | hypothesis-service |
| Reasoning | Insight Restructuring | Insight | (planned) |
| Learning | Confidence Calibration | Confidence | confidence-service |
| Action | Recommendation | Recommendation | recommendation-service |
| Action | Decision | Decision | decision-service |
| Action | Report (output document) | — | report-service |
| External (non-canonical) | Decision Authority, Cognitive Boundary | — | user-service, api-gateway |

Design discipline:

- **One capability per component**: each service implements exactly one cognitive capability; services are separated from each other and never bypass the canonical flow.
- **Cognitive Contract**: each component exposes a tested Input → Transform → Output contract.
- **Cognitive Boundary**: components of the pipeline are only invoked according to the canonical flow; external capabilities never produce cognitive judgments and never execute the pipeline.
- **No action without confidence**: the Action Layer is gated by calibrated Confidence (recommendation → decision), and both are future phases of the Learning loop.
- **Immutability**: observations, evidence, context, patterns, anomalies, hypotheses, confidence scores, recommendations, decisions, and reports are append-only; content is never mutated, only lifecycle fields may change.

---

## The Cognitive Flow

```
Reality → Observation → Evidence → Context → Pattern → Anomaly
       → Hypothesis → Confidence → Recommendation → Decision
       → Report → Memory (planned)
```

Each step consumes only the artifacts of the previous steps (knowledge), never raw observations after Perception, and never produces action before Confidence.

---

## Repository Structure

```
company-os-monitor/
├── apps/
│   ├── agents/               # Observation Capturers (Perception)
│   │   ├── linux-agent/
│   │   ├── windows-agent/
│   │   └── vmware-agent/
│   ├── services/             # Cognitive Services (one capability each)
│   │   ├── collector-service/
│   │   ├── context-service/
│   │   ├── pattern-service/
│   │   ├── anomaly-service/
│   │   ├── hypothesis-service/
│   │   ├── confidence-service/
│   │   ├── recommendation-service/
│   │   ├── decision-service/
│   │   ├── report-service/
│   │   └── user-service/
│   └── gateway/
│       └── api-gateway/
├── libs/
│   ├── cognitive-core/       # Contracts, calibration model, bus, LM Studio tool
│   ├── perception/           # Observation, Evidence, Context (stores + activator)
│   ├── reasoning/            # Pattern, Anomaly, Hypothesis, Insight
│   ├── learning/             # Confidence, Memory
│   ├── action/               # Recommendation, Decision, Report
│   ├── access/               # Security, RBAC, users, errors
│   └── procedural-memory/    # Pattern, Tolerance, Hypothesis Template,
│                             #   Action Space, Decision Policy libraries
├── infrastructure/
│   ├── docker/               # Docker Compose, init SQL (schema + seed)
│   └── db-migrations/        # Idempotent migrations per sprint
├── docs/                     # Architecture and domain documents
├── journal/                  # Progress and discovery records
├── specs/                    # Component specifications
└── tests/                    # Contract, integration, calibration tests
```

---

## Quick Start

```bash
# 1. Copy environment
cp .env.example .env

# 2. Start infrastructure (postgres 5433, redis 6379) + seed sandbox tenant
docker compose -f infrastructure/docker/docker-compose.yml up -d

# 3. Verify database
docker compose -f infrastructure/docker/docker-compose.yml exec postgres pg_isready -U cosmonitor

# 4. Run the linux-agent (development)
cd apps/agents/linux-agent
pip install --break-system-packages -e ".[dev]"
python -m src.main

# 5. Check observations in Redis
docker compose -f infrastructure/docker/docker-compose.yml exec redis redis-cli XRANGE observations COUNT 5
```

The sandbox tenant (`TENANT_ID` default) must exist in `tenants` (seed: `02-seed.sql`). Windows/VMware agents require a real WinRM/vCenter host.

---

## Roadmap

### Phase 1 — Foundation (Completed)

- [x] Repository structure, cognitive pipeline, DB schema
- [x] Cognitive-core contracts and observation bus

### Phase 2 — Perception Layer (Completed)

- [x] Multi-agent collection (Linux, Windows/WMI, VMware) with Postgres persistence
- [x] Evidence Organizer with immutable, append-only evidence
- [x] Context Activator with explanatory coherence competition

### Phase 3 — Reasoning Layer (Completed)

- [x] Pattern Detector
- [x] Anomaly Detector
- [x] Hypothesis Generator (templates + optional local AI as external tool)

### Phase 4 — Learning + Action Layer (Completed — Cognitive Gate Q1)

- [x] Confidence Calibrator (S + C + ECE + final score)
- [x] Recommendation Formulator (confidence-gated)
- [x] Decision Committer (falsifiable expected outcomes)

### Phase 5 — Output + Security (In Progress)

- [x] Report Generator (executive, technical, JSON)
- [x] Multi-tenant + Auth + RBAC + API Gateway (Cognitive Boundary)
- [ ] Insight Restructuring (Insight)
- [ ] Historical calibration and Memory / Learning loop
- [ ] Procedural Memory v2 and advanced patterns

---

## Implementation

### Foundation (Sprint 1)

Initial structure of the platform: `apps/`, `libs/`, `infrastructure/`, `tests/`, and the cognitive-core contracts with the canonical observation bus. DB schema for the cognitive tables (`observations`, `evidence`, `contexts`, `patterns`, `anomalies`, `hypotheses`, `confidence_scores`, `recommendations`, `decisions`, `reports`) plus the `tenants` seed.

### Sprint 2 — Multi-Agent Collection + Postgres Persistence

- `windows-agent` — Observation Capturer (WMI over WinRM): CPU, memory, disks, stopped services (Auto), Error/Critical event log
- `vmware-agent` — Observation Capturer (vSphere API/pyVmomi): datastores, VM power states, snapshots, ESXi host health
- `collector-service` — Evidence Organizer entry: consumes `observations` from Redis Streams and persists them (append-only INSERT) in Postgres; acks only after INSERT
- Immutability: a DB trigger blocks UPDATE/DELETE on `observations`
- Idempotency: message redelivery does not duplicate rows (dedup by observation id)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/collector-service:." python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor -c "SELECT fact_type, count(*) FROM observations GROUP BY fact_type;"
```

### Sprint 3 — Evidence Organizer (Perception · Organize)

- `libs/perception/evidence.py` — `EvidenceStore`, append-only for the `evidence` table: INSERT + idempotent dedup (ON CONFLICT by deterministic id), `verify_connection`, `close`
- Immutability: DB trigger blocks UPDATE/DELETE on `evidence`
- `apps/services/collector-service/src/organizer/` — domain organization rules (pure functions over immutable Observations):
  - `resource_exhaustion_evidence` (cpu>90% + mem>85% + disk>85%, same source, 5 min)
  - `service_degradation_evidence` (Stopped/Auto service + Error event, 15 min)
  - `auth_anomaly_evidence` (AD lockout + privileged membership change, 1 h)
  - `backup_failure_evidence` (Failed job + repo_free<10%, 1 h)
  - `vmware_capacity_evidence` (datastore_free<15% + snapshot>7d, 30 min)
  - `network_anomaly_evidence` (interface_errors>threshold + port_state_change, 15 min)
  - Objective/factual `description`, `quality_class` Q1-Q4 and `weight` w_i assigned AT CREATION (Q1→0.875, Q2→0.625, Q3→0.375, Q4→0.125, exact midpoints of the bands); no retrofitting
- Orchestration in the collector: after persisting each batch of observations, the organizer runs over the buffer per window/tenant and writes `evidence` (idempotent dedup). Organization metrics exposed in `/metrics` (`total_evidence`, `total_evidence_duplicates`, `total_evidence_errors`, `evidence_by_type`)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/collector-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor -c "SELECT organization_type, quality_class, weight FROM evidence;"
curl -s http://localhost:8090/metrics
```

Windows/thresholds per domain are configurable via env (`RESOURCE_EXHAUSTION_WINDOW_MINUTES`, `NETWORK_ANOMALY_ERROR_THRESHOLD`, etc., see `.env.example`). Agents can publish synthetic observations to trigger rules during development.

### Sprint 4 — Context Activator (Perception · Explain)

- `libs/perception/context.py` — declarative catalog of **mental models** (`MentalModel`, frozen dataclass, NO reasoning) mapped to the `organization_type`s of Sprint 3 for the purposes `infrastructure_health`, `security_posture`, and `capacity_management`:
  - `resource_pressure` → `resource_exhaustion_evidence`
  - `service_failure` → `service_degradation_evidence`
  - `auth_compromise` → `auth_anomaly_evidence`
  - `capacity_risk` → `backup_failure_evidence` + `vmware_capacity_evidence`
  - `connectivity_degradation` → `network_anomaly_evidence`
- Same module: `Context` (pydantic `frozen`), deterministic `context_id()` (uuid5 tenant+purpose+evidence_ids), and `ContextStore` (append-only INSERT with `ON CONFLICT (id) DO NOTHING`, idempotent dedup). Content (evidence_ids, mental_model_id, purpose, coherence_score, competing_models) is immutable; `is_active` is a lifecycle field: activating a new context deactivates the previous one for the same tenant+purpose
- `apps/services/context-service/` — **Context Activator** (exactly the Explain capability, separate from the collector):
  - `src/activator/coherence.py` — explanatory coherence competition (pure functions): per tenant+purpose, each candidate model explains the fraction of evidence weight covered by its signature; the highest `coherence_score` wins (ties broken deterministically by model_id). No interpretation, no causality
  - `src/activator/engine.py` — `ActivatorEngine` (pure): batch of Evidence → `ContextCreate` with winner + `competing_models` (all candidates with their scores)
  - `src/service.py` — orchestration: reads evidence from Postgres per tenant, runs the competition per purpose, writes the Active Context (dedup; deactivates the previous). Metrics: `total_contexts`, `total_context_duplicates`, `total_errors`, `contexts_by_mental_model`, `contexts_by_purpose`
  - `src/health.py` — `/health` and `/metrics`
- Schema: `contexts` table as-is; trigger `context_content_immutable_trigger` blocks UPDATE of content columns and DELETE (allows the `is_active` flip)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/context-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT tenant_id, mental_model_id, purpose, coherence_score, competing_models, is_active FROM contexts;"
curl -s http://localhost:8091/metrics
```

### Sprint 5 — Pattern Detector (Reasoning · Generalize)

- `libs/procedural_memory/pattern_library.py` — **Pattern Library** (procedural memory, DECLARATIVE definitions, no reasoning): `PatternDefinition` (frozen dataclass) with versioned `pattern_id` (`_v1`/`_v2`), `pattern_type` (MVP only `temporal`; `correlation`/`sequential`/`threshold` reserved), `scope_mental_models`, `scope_purposes` (empty = all), `min_occurrences`, `strength_threshold`, `frequency_label`, and FACTUAL `description_template`. The catalog covers the 5 mental models of Sprint 4. Updating a pattern = publishing a NEW version (`_v2`), never mutating the published one
- `libs/reasoning/pattern.py` — `Pattern` model (pydantic `frozen`) with deterministic `pattern_id()` (uuid5 tenant + context_id + library_pattern_id; the library version stays traceable in the id, and `detected_at` stays OUT of the id for idempotency) and `PatternStore` (append-only INSERT, `ON CONFLICT (id) DO NOTHING`, `list_patterns`, `list_tenant_ids`)
- `libs/perception/context.py` — new READs in `ContextStore`: `list_contexts(tenant_id)` returns ALL activations ordered by `activated_at` (the continuous Context stream, not just `is_active = true`) and `list_tenant_ids()`
- `apps/services/pattern-service/` — **Pattern Detector** (exactly the Generalize capability, separate from collector and context-service):
  - `src/detector/detector.py` — PURE functions (no I/O): per `PatternDefinition`, groups activations by scope (mental_model_id, purpose) within the window (`DETECTION_WINDOW_DAYS`); `strength_measure = min(occurrences / max(min_occurrences, 1), 1.0)`; emits a Candidate Pattern only if `strength >= strength_threshold`; `frequency` derived from the median interval between activations (hourly/daily/weekly/event-driven); anchored to the most recent activation. `description` only factual
  - `src/service.py` — per-tenant cycle: `ContextStore.list_contexts` → detector → `PatternStore` (idempotent dedup). Never writes to `contexts`/`evidence`/`observations`, never reads the observation bus
  - `src/health.py` — `/health` and `/metrics` (`total_patterns`, `total_pattern_duplicates`, `total_candidates_below_threshold`, `total_errors`, `patterns_by_type`, `patterns_by_mental_model`)
- Schema: `patterns` table as-is; trigger `pattern_content_immutable_trigger` (blocks content UPDATE/DELETE; allows `is_active` flip)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/pattern-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT tenant_id, pattern_type, strength_measure, frequency, description FROM patterns;"
curl -s http://localhost:8092/metrics
```

### Sprint 6 — Anomaly Detector (Reasoning · Detect Deviation)

- `libs/reasoning/anomaly.py` — `Anomaly` model (pydantic `frozen`) with deterministic `anomaly_id()` (uuid5 tenant + context_id + pattern_id; `detected_at` outside the id) and `AnomalyStore` (append-only, idempotent dedup, `list_anomalies`, `list_tenant_ids`)
- `libs/procedural_memory/tolerance_library.py` — **Tolerance Library** (procedural memory, EXPLICIT, auditable, purpose-dependent thresholds; no reasoning): `ToleranceDefinition` (frozen dataclass, versioned `_v1`/`_v2`) with `pattern_type` (MVP `temporal`), `scope_mental_models`, `scope_purposes`, `anomaly_class` (MVP `point`; contextual/collective reserved), `deviation_spec` (`days_off_schedule`, `count_exceeding_window`) and `threshold`. One tolerance per PatternDefinition of Sprint 5; deviation schemes documented and tested with known values
- `libs/perception/context.py` — new READ `list_active_contexts(tenant_id)` (Active Contexts, `is_active = true`)
- `apps/services/anomaly-service/` — **Anomaly Detector** (exactly the Detect Deviation capability, separate from pattern-service):
  - `src/detector/detector.py` — PURE functions: for each Active Context, the expected pattern is the most recent of `patterns` for its scope; WITHOUT a pattern there is NO deviation (Anomaly is relative to patterns, never absolute → metric `contexts_without_pattern`); `deviation_score` per `deviation_spec`; Candidate Anomaly only if `deviation_score > tolerance_threshold`. FACTUAL `rationale` (signal, not conclusion)
  - `src/service.py` — per-tenant cycle: `list_active_contexts` + `list_patterns` → detector → `AnomalyStore`. Never writes to previous artifacts; never reads the observation bus. Metrics: `total_anomalies`, `total_anomaly_duplicates`, `total_contexts_without_pattern`, `total_errors`, `anomalies_by_class`, `anomalies_by_mental_model`
  - `src/main.py` — tolerances configurable per deployment via `TOLERANCE_*_THRESHOLD` (canonical defaults in the library)
- Schema: `anomalies` table as-is; trigger `anomaly_content_immutable_trigger` blocks ALL UPDATE/DELETE (no lifecycle flag; same policy as `evidence`)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/anomaly-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT tenant_id, context_id, pattern_id, deviation_score, tolerance_threshold, anomaly_class FROM anomalies;"
curl -s http://localhost:8093/metrics
```

### Sprint 7 — Hypothesis Generator (Reasoning · Predict)

- `libs/reasoning/hypothesis.py` — `Hypothesis` model (pydantic `frozen`) with deterministic `hypothesis_id()` (uuid5 tenant + anomaly_ids + pattern_ids + description; the description enters the hash so TWO competing hypotheses on the same anomaly have distinct ids; `generated_at` outside the id) and `HypothesisStore` (append-only, idempotent dedup, `list_hypotheses`, `list_tenant_ids`). `status` is a lifecycle field (`candidate`/`confirmed`/`falsified`): the generator ALWAYS emits `candidate` (confirmation/falsification requires future evidence + Confidence)
- `libs/procedural_memory/hypothesis_templates.py` — **Hypothesis Template Library** (declarative per-domain templates, no reasoning): `HypothesisTemplate` (frozen dataclass, versioned `_v1`) with `scope_anomaly_class` (MVP `point`), `scope_mental_models`, `scope_purposes`, `description_template`, `consequence_templates`, `falsification_templates`, `coherence_estimate` (declarative documented prior). Initial catalog: 3 competing hypotheses per domain (resource_pressure: logging verbosity / retention / auto-growth; capacity_risk: maintenance schedule / target capacity / antivirus conflict; auth_compromise: compromised account / retry loop / external monitoring). Hypothetical language (could/candidate) and a mandatory `falsification_criterion` in EVERY hypothesis
- `apps/services/hypothesis-service/` — **Hypothesis Generator** (exactly the Predict capability, separate from pattern/anomaly-service):
  - `src/generator/generator.py` — PURE functions: for each point anomaly, scope resolved via its Active Context (mental_model_id, purpose); templates with applicable scope instantiated with measured facts (`{scope}`, `{deviation_score}`, `{frequency}`, `{anomaly_class}`). ALWAYS emits ≥2 competing hypotheses when templates apply (premature convergence to a single explanation = cognitive failure). Anomaly without applicable template or unresolved scope → no rows (metric `total_anomalies_no_templates`)
  - `src/service.py` — per-tenant cycle: `list_anomalies` + `list_contexts` + `list_patterns` → generator → `HypothesisStore`. Never writes to previous artifacts; never reads the observation bus. Metrics: `total_hypotheses`, `total_hypothesis_duplicates`, `total_anomalies_no_templates`, `total_errors`, `hypotheses_by_status`, `hypotheses_by_mental_model`
  - `src/main.py` — `HYPOTHESIS_HEALTH_PORT` (8094), `HYPOTHESIS_CYCLE_SECONDS`
- `libs/cognitive_core/lm_studio_hypothesis_tool.py` — **LMStudioHypothesisTool** (external NON-canonical capability) implementing the `CognitiveTool` ABC: `invoke` → structured prompt → LM Studio → Pydantic parsing → canonical `HypothesisCreate`; `validate_output` requires a non-empty `falsification_criterion`; `available()` probes the endpoint (`LM_STUDIO_URL`); if unavailable → template-only fallback (the canonical flow never breaks). Does not wire Confidence
- Schema: `hypotheses` table as-is; trigger `hypothesis_content_immutable_trigger`: immutable content, DELETE blocked, `status` the ONLY flippable field

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/hypothesis-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor -c "SELECT status, description, falsification_criterion FROM hypotheses;"
curl -s http://localhost:8094/metrics
```

### Sprint 8 — Confidence Calibrator (Learning · Calibrate)

- `libs/cognitive_core/calibration_model.py` — **Calibration Model**: implements the formal Confidence concept: `evidential_support` (log-odds L = L0 + Σ wᵢ·eᵢ + sigmoid), `brier_score`, `ece_score` (M bins, default M=10), `final_confidence` (C_final = [α·S + (1−α)·C]·(1−ECE)) and `CalibrationParams` (α=0.5, M=10, L₀=0 fixed a priori). `explanatory_coherence` is now REAL (constraint satisfaction normalization, Thagard 1989): C(H) = P/(P+N+U) over the `{explains, contradicts, coherent_with, incoherent_with}` scheme (fraction of explained evidence, penalized by contradictions and unexplained evidence; 0.5 neutral without scope). `QUALITY_CLASS_RANGES` and `quality_class_to_weight` (canonical Q1-Q4 bands) are kept
- `libs/learning/confidence.py` — **Confidence model** (Learning · Calibrate): `ConfidenceCreate`/`Confidence` (pydantic `frozen`) mirroring the `confidence_scores` table; deterministic `confidence_id` (uuid5, own namespace): hash of tenant + target + calibration INPUTS (S, C, 1−ECE, α), WITHOUT `computed_at` — same inputs → same id (idempotent dedup); different inputs (new evidence) → NEW id → NEW row (append-only: historical calibration is preserved, never overwritten). `ConfidenceStore` (INSERT `ON CONFLICT (id) DO NOTHING`, `verify_connection`, `close`, `list_confidence(tenant_id)`, `get_confidence(target_type, target_id)`, `list_tenant_ids`)
- `apps/services/confidence-service/` — **Confidence Calibrator** (exactly the Calibrate capability; does not generate hypotheses or recommendations):
  - `src/calibrator/calibrator.py` — PURE functions: `calibrate(hypothesis, evidence, coherence_inputs, params, historical) -> ConfidenceCreate` computes S (weights with signs +1/−1 per `explains`/`contradicts`), C (explanatory_coherence), the (1−ECE) factor from the class outcome history and C_final. No history → `historical_calibration=1.0`, ECE=0 (first data, documented). `calibration_justification` ALWAYS documents S, C, ECE, α, M, L₀ and how each was derived. `resolve_scope_evidence` follows hypothesis → anomaly → context → evidence (read-only). Anti-tuning: same input → same id and score (determinism, tested)
  - `src/service.py` — per-tenant cycle: `list_hypotheses` + `list_anomalies` + `list_contexts` + `list_evidence` → calibrator → `ConfidenceStore`. Never writes to previous artifacts; never reads the observation bus; produces no actions; its output enables the Action Layer. Metrics: `total_confidence_scores`, `total_confidence_duplicates`, `total_errors`, `confidence_by_target_type`, `mean_confidence_score`, `mean_calibration_error_estimate`
  - `src/main.py` — `CONFIDENCE_HEALTH_PORT` (8095), `CONFIDENCE_CYCLE_SECONDS`, `CALIBRATION_ALPHA` (0.5), `CALIBRATION_ECE_BINS` (10); L₀ fixed at 0
  - API/Store already supports `target_type='recommendation'`/`'decision'` through the same ConfidenceCreate/ConfidenceStore path
- Schema: `confidence_scores` table as-is; trigger `confidence_content_immutable_trigger` (content immutable, DELETE blocked — no lifecycle flag: a re-calibration with new inputs is a NEW row, never an UPDATE)

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/confidence-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
docker compose -f infrastructure/docker/docker-compose.yml exec postgres \
  psql -U cosmonitor -d cosmonitor \
  -c "SELECT target_type, evidential_support, explanatory_coherence, historical_calibration, confidence_score, alpha FROM confidence_scores;"
curl -s http://localhost:8095/metrics
```

### Sprint 9 — Recommendation Formulator (Action · Propose)

- `libs/action/recommendation.py` — **Recommendation model** (Action · Propose): `RecommendationCreate`/`Recommendation` (pydantic `frozen`) mirroring the `recommendations` table (tenant_id, hypothesis_id, insight_id=NULL in the MVP, confidence_id, action_description, rationale, expected_consequences, alternatives_considered, confidence_score, status, proposed_at); deterministic `recommendation_id` (uuid5, own namespace) WITHOUT `proposed_at` — same inputs → same id; `confidence_id` is fixed in the id, so a new calibration of the same hypothesis produces a NEW recommendation (append-only). `RecommendationStore` (INSERT `ON CONFLICT (id) DO NOTHING`, `verify_connection`, `close`, `list_recommendations(tenant_id)`, `list_tenant_ids`). `status` is the ONLY flippable field (proposed → accepted/rejected/superseded, decided by Decision)
- `libs/procedural_memory/action_space.py` — **Action Space Library** (declarative): `ActionSpaceEntry` (frozen dataclass, versioned `action_id` `*_v1`), `domain` (storage/compute/security/backup/network/observability), `allowed_actions` (explicit frozenset), `purposes`. Initial catalog: storage: expand_volume/add_disk/move_data/compress/purge_old/change_retention/enable_dedup; security: reset_credentials/revoke_sessions/enable_mfa/block_ip/isolate_host/rotate_keys; backup: retry_job/change_schedule/change_target/verify_integrity/test_restore; etc. `filter_action_space` limits the catalog by enabled domains (deployment flag). A recommendation can ONLY choose actions inside the explicit space of its domain/purpose
- `apps/services/recommendation-service/` — **Recommendation Formulator** (exactly the Propose capability; does not calibrate confidence or commit decisions):
  - `src/formulator/formulator.py` — PURE functions: `formulate(hypothesis, confidence, context, action_space) -> RecommendationCreate` derives the course of action that best serves the purpose: resolves the domain (declarative mental_model→domain mapping with purpose fallback), selects the explicit action space of the domain/purpose, picks the declared leading action (`LEADING_ACTION_BY_DOMAIN`) and builds `rationale` ALWAYS traceable (cites context/hypothesis/confidence with facts), `expected_consequences` observable and verifiable, `alternatives_considered` (the other allowed actions, each with rationale + rejected_reason + shared confidence) and `confidence_score` = the calibrated score of the hypothesis (never recalculated). `status='proposed'` (advisory; nothing is executed). `resolve_active_context` follows hypothesis → anomaly → context. Anti-order: propositive language, never "run now". Determinism → idempotent dedup
  - `src/service.py` — per-tenant cycle: `list_hypotheses` + `get_confidence` (gate: only hypotheses WITH calibrated confidence) + `list_contexts` → formulator → `RecommendationStore`. Never writes to previous artifacts; never reads the observation bus; does not execute actions or fire alerts. Metrics: `total_recommendations`, `total_recommendation_duplicates`, `total_hypotheses_without_confidence`, `total_hypotheses_without_context`, `total_hypotheses_without_action_space`, `total_errors`, `recommendations_by_status`, `recommendations_by_domain`
  - `src/main.py` — `RECOMMENDATION_HEALTH_PORT` (8096), `RECOMMENDATION_CYCLE_SECONDS`, `ACTION_SPACE_DOMAINS`
- Schema: `recommendations` table as-is; trigger `recommendation_content_immutable_trigger` (content immutable once written; DELETE blocked; `status` the only flippable). Idempotent migration `infrastructure/db-migrations/sprint9-recommendation-content-trigger.sql`

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/recommendation-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
curl -s http://localhost:8096/metrics
```

### Sprint 10 — Decision Committer (Action · Commit) — Cognitive Gate Q1

- `libs/action/decision.py` — **Decision model** (Action · Commit): `DecisionCreate`/`Decision` (pydantic `frozen`) mirroring the `decisions` table (tenant_id, recommendation_id, confidence_id, authority_id, commitment, expected_outcomes, risk_tolerance, status, committed_at, executed_at, actual_outcomes); deterministic `decision_id` (uuid5, own namespace) WITHOUT `committed_at`. `DecisionStore` (INSERT `ON CONFLICT (id) DO NOTHING`, `verify_connection`, `close`, `list_decisions(tenant_id)`, `list_tenant_ids`, `list_decisions_by_status`). `status`/`executed_at`/`actual_outcomes` are lifecycle fields: the Learning loop (future phases) compares expected vs actual and fills the outcomes; in the MVP the Decision is REGISTERED, never executed
- `libs/procedural_memory/decision_policy.py` — **Decision Policy Library** (declarative): `DecisionPolicyEntry` (frozen dataclass, versioned `policy_id` `*_v1`, `domain`, `min_confidence_for_commit`=0.75, `min_confidence_irreversible`=0.9, `allowed_risk_tolerance` per domain, `requires_authority`). Canonical catalog per domain; `select_policy(domain)`, `apply_threshold_overrides` (env `DECISION_MIN_CONFIDENCE*` without mutating the catalog)
- `apps/services/decision-service/` — **Decision Committer** (exactly the Commit capability; does not form recommendations or calibrate confidence):
  - `src/committer/committer.py` — PURE functions: `Authority` (authority_id + risk_tolerance), `policy_authority_id` (deterministic policy authority; real users arrive in Sprint 12), `recommendation_domain` (domain from the action space of the alternatives), `resolve_risk_tolerance` (score → low/medium/high, bounded by the policy), `commit_eligibility` (COMMITTABLE / BELOW_CONFIDENCE / RISK_NOT_ALLOWED / NO_AUTHORITY / NO_POLICY), `commit(...)` → `DecisionCreate` with a DEFINITIVE `commitment` (no alternative clause, no vague intention), and falsifiable `expected_outcomes` (prediction + verifiable_by + deadline, declared BEFORE executing). `status='committed'`, `executed_at=None`, `actual_outcomes=None`; nothing is executed
  - `src/service.py` — per-tenant cycle: `list_recommendations` (only `status='proposed'`) + `list_confidence` (gate) + policy of the domain → committer → `DecisionStore`. Never writes to previous artifacts; never reads the observation bus; does not execute actions. Metrics: `total_decisions`, `total_decision_duplicates`, `total_recommendations_below_confidence`, `total_recommendations_skipped`, `total_errors`, `decisions_by_status`, `decisions_by_risk_tolerance`
  - `src/main.py` — `DECISION_HEALTH_PORT` (8097), `DECISION_CYCLE_SECONDS`, `DECISION_MIN_CONFIDENCE` (0.75), `DECISION_MIN_CONFIDENCE_IRREVERSIBLE` (0.9)
- Schema: `decisions` table as-is; trigger `decision_content_immutable_trigger` (CONTENT immutable once written; DELETE blocked; `status` — committed → executing/completed/rolled_back — and `executed_at`/`actual_outcomes` are the flippable lifecycle fields, populated only by the Learning loop). Idempotent migration `infrastructure/db-migrations/sprint10-decision-content-trigger.sql`
- **Cognitive Gate Q1 reached**: first Decision committed on the sandbox with falsifiable expected outcomes (prediction + verifiable_by + deadline) and the complete traceability chain decision → recommendation → confidence → hypothesis → anomaly → pattern → context → evidence → observations

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/decision-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
curl -s http://localhost:8097/metrics
```

### Sprint 11 — Report Generator (Action · Report, output document)

- `libs/action/report.py` — **Report model** (output-document family of the Action Layer): `ReportCreate`/`Report` (pydantic `frozen`) mirroring the `reports` table (tenant_id, report_type, title, summary, content, ai_generated, model_used, period_start, period_end, generated_at, file_path); deterministic `report_id` (uuid5, own namespace) WITHOUT `generated_at` nor `content` — same inputs → same id. `ReportStore` (idempotent INSERT, `report_exists`, `list_reports`, `get_report`, `list_tenant_ids`, `get_tenant`, `verify_connection`, `close`). Explicitly NON-canonical (ADR-0002): ONLY formats what the cognitive flow already committed, writes in its own `reports` table, never generates judgments, never touches cognitive tables. `ai_generated=False`/`model_used=None` in this MVP (local template rendering; LM Studio in a future sprint)
- `apps/services/report-service/` — **Report Generator** (formats, does not reason):
  - `src/renderers/common.py` — `ReportSource` (dataclass with the read artifacts: decisions, recommendations, contexts, confidences, hypotheses, anomalies, patterns, evidence, observations, tenant, period, generated_at), `as_jsonable`, `build_decision_traces` (correlates decision → recommendation → confidence → hypothesis → anomaly → pattern → context → evidence → observations), `latest_confidence_for(hypothesis)`
  - `src/renderers/executive.py` — `render_executive(source)` PURE: Top Decisions (commitment, risk_tolerance, confidence, expected_outcome_count, recommendation action), `pending_authority` (only risk_tolerance "high"), `future_risks` (hypotheses with confidence_score > `risk_threshold`, default 0.6). Never invents costs/ROI: only what the flow committed
  - `src/renderers/technical.py` — `render_technical(source)` PURE: sections 1-7 (Cognitive Trace, Anomalies, Patterns, Confidence Calibration, Reasoning Chain, Decision & Expected Outcomes, Evidence/Context)
  - `src/renderers/json_render.py` — `render_json(source)` PURE: exact `build_decision_traces` structure (machine format)
  - `src/renderers/formatters.py` — I/O: `to_html` (jinja2), `to_pdf` (weasyprint), `to_json`. Pure renderers vs formatters with I/O
  - `src/service.py` — per-tenant cycle: reads Decisions/Recommendations/Contexts/Confidences/Hypotheses/Anomalies/Patterns/Evidence/Observations → period = `committed_at` range (min..max, today if empty) → render → formatter → `ReportStore.save_report` (dedup). Metrics: `total_reports`, `total_report_duplicates`, `total_errors`, `by_type`, `render_duration_seconds`, `last_run_at`
  - `src/health.py` — `/health`, `/metrics`, `POST /api/v1/reports/generate` (optional tenant, type executive/technical/json), `GET /api/v1/reports`
  - `src/main.py` — `REPORT_HEALTH_PORT` (8098), `REPORT_CYCLE_SECONDS`, `REPORT_OUTPUT_DIR`
- `libs/perception/store.py` — added `ObservationStore.list_observations` (READ) to complete the evidence trace in reports
- Schema: `reports` table as-is; trigger `report_content_immutable_trigger` (content immutable once written; DELETE blocked). Idempotent migration `infrastructure/db-migrations/sprint11-report-content-trigger.sql`

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
PYTHONPATH="apps/services/report-service:/home/dcordoba/Documents/Default Project/company-os-monitor" python3 -m src.main
curl -s -X POST "http://localhost:8098/api/v1/reports/generate?type=executive&tenant_id=00000000-0000-0000-0000-000000000001"
curl -s "http://localhost:8098/api/v1/reports?tenant_id=00000000-0000-0000-0000-000000000001"
curl -s http://localhost:8098/metrics
```

### Sprint 12 — Multi-tenant + Auth + RBAC (Decision Authority — External Capability)

The **user-service** (JWT/roles per tenant) and the **API Gateway** (Cognitive Boundary enforcement) close block **Q1**: full pipeline + authority + boundary. Both are external NON-canonical capabilities (ADR-0002): they authorize and protect access to the canonical flow, NEVER produce cognitive judgments and NEVER execute the pipeline. RBAC is modeled as a **Decision Authority binding** (the commitment authority under which a Decision was taken), not as a "permissions table".

- `libs/access/` — **Access layer** (shared by user-service and gateway):
  - `security.py` — bcrypt (hash/verify) + JWT (HS256 dev / RS256 prod) with identity + role + tenant claims. Finding: `passlib 1.7.4` is incompatible with `bcrypt>=4.1` (it uses `bcrypt.__about__.__version__`, removed); the `bcrypt` package is used directly
  - `rbac.py` — **roles × permissions** matrix: viewer (READ of context/recommendations/decisions/reports; NO propose/commit/execute), operator (+ACK, NO propose/commit), admin (READ + PROPOSE + COMMIT in tenant with risk low/medium + defines policies), superadmin (everything + cross-tenant + high risk + execute). Pure constants tested cell by cell; `commit_risk_allowed` and `tenant_scope` (multi-tenant isolation)
  - `users.py` — `User` model + `UserStore` (`users` table, per tenant; global unique email; bcrypt hash never plaintext; queries always scoped by `tenant_id`)
  - `errors.py` — `InvalidTokenError` (401), `AuthorizationError`/`TenantIsolationError` (403), `UserConflictError` (409)
- `apps/services/user-service/` — **Auth/RBAC service** (external, ADR-0002): `POST /api/v1/auth/login` (email+password → access+refresh), `POST /api/v1/auth/refresh` (stateless), `POST /api/v1/users` (admin/superadmin, tenant isolation), `GET /api/v1/me`, `GET /api/v1/users` (admin+, tenant scope). Tokens carry role+tenant; the Decision `authority_id` (Sprint 10) now references real `users.id`. Metrics `/metrics`: `total_logins`, `total_login_failures`, `total_tokens_issued`, `total_errors`, `users_by_role`. Port `USER_HEALTH_PORT=8099`
- `apps/gateway/api-gateway/` — **Cognitive Boundary enforcement**:
  - `src/boundary.py` — pure boundary rules: canonical flow observation→evidence→context→pattern→anomaly→hypothesis→insight→recommendation→decision (no shortcuts; observations never exposed to Reasoning/Action; Pattern/Anomaly/Hypothesis never trigger actions) + Confidence presence validation
  - `POST /api/v1/actions/{action}` (commit/propose/ack/execute) — validates role + boundary + confidence; NEVER executes (execution is the canonical cycle of each service). 401 without token, 403 role without authority, 400 boundary
  - Role-protected READS with tenant isolation: `GET /api/v1/tenants/{tenant_id}/decisions`, `/reports`, `GET /api/v1/services/health` (forwarding to the pipeline `/health`). Port `GATEWAY_HEALTH_PORT=8100`
- Schema: `users` table (id, tenant_id FK, email UNIQUE, password_hash bcrypt, name, role CHECK viewer/operator/admin/superadmin, is_active, created_at, updated_at) + `idx_users_tenant_email(tenant_id, email)` in `01-schema.sql`; admin sandbox seed (documented dev password) in `02-seed.sql`; idempotent migration `infrastructure/db-migrations/sprint12-users-tables.sql`. `users` is external data (ADR-0002): MUTABLE by design, no P1 trigger. `decisions` unchanged (`authority_id` stays a free UUID)
- **Refresh strategy**: stateless JWT (access + refresh signed, own exp; no `refresh_tokens` table nor token store in Redis) — documented

```bash
docker compose -f infrastructure/docker/docker-compose.yml up -d
psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" \
  -f infrastructure/db-migrations/sprint12-users-tables.sql
JWT_ALGORITHM=HS256 JWT_SECRET_KEY=dev-secret \
PYTHONPATH="apps/services/user-service:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main   # port 8099
curl -s -X POST http://localhost:8099/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@sandbox.local","password":"cosmonitor"}'
curl -s http://localhost:8099/api/v1/me -H "Authorization: Bearer <ACCESS_TOKEN>"
PYTHONPATH="apps/gateway/api-gateway:/home/dcordoba/Documents/Default Project/company-os-monitor" \
  python3 -m src.main   # port 8100
curl -s -X POST http://localhost:8100/api/v1/actions/commit \
  -H "Authorization: Bearer <TOKEN>" -H "Content-Type: application/json" \
  -d '{"confidence_score":0.85,"risk_tolerance":"low"}'
curl -s http://localhost:8099/metrics && curl -s http://localhost:8100/metrics
```

Authorization is not an end in itself: it exists so that every Decision/action has an auditable, verifiable **authority binding**. The gateway enforces that pipeline components are only invoked according to the canonical flow and that no external capability executes an action without authorization. No cognitive judgment passes through auth/RBAC (structural test ADR-0002: `libs/access` does not import the pipeline). The next block is **H1** (Sprint 13+): Insight, historical calibration, Procedural Memory v2, and advanced patterns.

---

## Cognitive Compliance

Every sprint validates:

- [x] **R1**: Exactly one cognitive capability per component
- [x] **R2**: Cognitive Contract (Input→Transform→Output) tested
- [x] **R3**: Cognitive Boundary enforced
- [x] **R4**: No action without Confidence
- [x] **R5**: Decisions with falsifiable outcomes
- [x] **P1**: Observations immutable, never interpreted
- [x] **P5**: Confidence computed (S+C+ECE), params published

Traceability, objectivity, and provenance are guaranteed factually across the whole chain: every artifact references its inputs, every row is append-only and idempotently deduplicated, and no reasoning step adds interpretation that was not earned by evidence.

---

## Cognitive Citation Policy

Citations to the Company OS framework use exclusively the canonical set:

- **Principles**: P1–P7 (`cognitive-principles.md`)
- **Design rules**: R1–R7 (`cognitive-architecture.md`)
- **Concepts**: names from `cognitive-lexicon/core-concepts/*.md`
- **ADR**: ADR-0001 (Company OS is the brain), ADR-0002 (COS-Monitor is the product)

Rule: **nothing outside the policy is written.** Every reference to the framework must map to an existing canonical element. No invented rule numbers (R8/R9/R10), no use of the R1–R10 numbering of `ontology.md` (it collides with R1–R7), and traceability/objectivity/provenance are described without a rule number. Enforcement for agent sessions: `AGENTS.md`.

---

## Documentation

- `docs/01-fundacion-arquitectura.md` — Phases 1-2: Cognitive pipeline, DB schema
- `docs/02-motor-recoleccion.md` — Phase 3: Perception Layer (agents, collector)
- `docs/03-predictivo-ia-local.md` — Phases 4-5: Reasoning + Learning + LM Studio
- `docs/04-informes-seguridad.md` — Phases 6-7: Action Layer + Security as Procedural Memory
- `docs/05-negocio-roadmap-backlog.md` — Phases 8-10: Roadmap, backlog, cognitive OKRs
- `AGENTS.md` — Agent session guide and citation policy enforcement

---

> The architecture should guide the code, never the opposite.