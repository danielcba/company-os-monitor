# Frontend Architecture — COS-Monitor Web (`apps/web`)

> **Date:** 2026-08-20 · **Phase:** Fase 1 (Foundation) + Fase 2 (Dashboard) + Fase 3 (Observations) + Fase 4 (Evidence) + Fase 5 (Contexts) + Fase 6 (Patterns) + Fase 7 (Anomalies) + Fase 8 (Hypotheses) + Fase 9 (Confidence) + Fase 10 (Recommendations) · **Status:** implemented

The COS-Monitor web app is an **external product capability** (ADR-0002): it
represents cognitive concepts, it never redefines them, and it never executes
cognitive logic in the browser. Everything shown originates from the Company OS
pipeline and is served exclusively through the API Gateway (R3). No direct
access to PostgreSQL or Redis. When a relation or datum is missing in the
backend, the UI shows an honest `Not available`/`No trace available` state —
data is never fabricated.

## Stack

| Layer | Choice | Reason |
|---|---|---|
| Framework | React + TypeScript | SPA; each view maps 1:1 to one cognitive capability it represents |
| Build | Vite | Lazy routes / code-splitting per section |
| Styling | Tailwind CSS v4 + CSS-variable tokens | centralized design tokens, light/dark |
| Data | TanStack Query | loading/error/refetch/polling, no state reducers |
| Routing | React Router | protected routes, breadcrumbs, tenant scope |
| Tests | Vitest + React Testing Library | unit/component/integration |
| Icons | lucide-react | minimal, non-decorative |

Location: `apps/web/` inside the product repo.

## Design tokens (brand)

- Neutral deep palette + **one accent** (Confidence/Decision), rigor/calm/structure.
- Light and dark modes via CSS variables in `src/styles/globals.css`
  (`--background`, `--foreground`, `--accent`, `--muted`, `--border`, `--sidebar`, …).
- Explicit `dark` class on `<html>`; theme persisted in localStorage.

## Information architecture

Sections map to real cognitive capabilities. Sections whose read endpoints do
not exist yet are rendered as **planned** (disabled nav, honest `EmptyState`).

- Dashboard (live: cognitive pipeline health via `GET /api/v1/services/health`)
- Cognition: Observations (live) · Evidence (live) · Contexts (live) · Patterns (live) · Anomalies (live) · Hypotheses (live) ·
  Confidence (planned until READ endpoints land)
- Action: Decisions · Recommendations (planned)
- Investigation: Cognitive Trace + Timeline (planned)
- Reports (planned) · Administration: Users (planned)
- Insight / Outcome / Memory: not yet in active nav

## Routes

| Route | Access | Status |
|---|---|---|
| `/login` | public | live |
| `/dashboard` | protected (JWT) | live (pipeline counters + services health) |
| `/cognition/observations` | protected (JWT) | live (paginated raw facts) |
| `/cognition/evidence` | protected (JWT) | live (organized facts + observation desglose) |
| `/cognition/contexts` | protected (JWT) | live (active model + competing models + evidence desglose) |
| `/cognition/patterns` | protected (JWT) | live (detected regularity + source context desglose) |
| `/cognition/anomalies` | protected (JWT) | live (quantified deviation + source context desglose) |
| `/cognition/hypotheses` | protected (JWT) | live (tentative explanation + source anomalies desglose) |
| `/cognition/*`, `/action/*`, `/reports`, `/administration/users` | protected | planned |
| `/` | redirect → `/dashboard` | live |

Protected routes render an `UnauthorizedState`/redirect to `/login` when there
is no valid session; `ForbiddenState` for HTTP 403.

## API client (`src/api/`)

- `client.ts`: fetch wrapper over the API Gateway + user-service for auth.
  - attaches `Authorization: Bearer <access>`
  - on 401 → automatic refresh via `/auth/refresh` → retry once → else sign-out
  - 403 surfaces as `ApiError(status=403)` → `ForbiddenState`
- `auth.ts`: `login`, `fetchMe`
- `gateway.ts`: `fetchServicesHealth`, `fetchCognitiveSummary`,
  `fetchObservations` (paginated, filterable), `fetchEvidence` (paginated,
  filterable), `fetchEvidenceDetail` (evidence + observation desglose),
  `fetchDecisions`, `fetchReports`
- Types in `src/types/` map to the real pydantic/schema models, hand-written
  (the platform has no OpenAPI).

## Dashboard (Fase 2)

The dashboard is truthful: it renders the real pipeline counters from
`GET /api/v1/tenants/{tenant_id}/cognitive/summary` (viewer+, tenant-scoped)
served by the Gateway's `CognitiveSummaryStore` (pure READ aggregation of the
append-only pipeline state, P1). When Reasoning/Action are empty (0
patterns/anomalies/hypotheses/confidence/recommendations/decisions), the UI
shows honest zeros / `Not available` — data is never fabricated (P1). Status
breakdowns (hypotheses/recommendations/decisions lifecycle) are rendered as
badges or `Not available` when absent.

## Observations (Fase 3)

The Observations view renders the raw, immutable facts of the pipeline
(append-only, P1) exactly as captured — never interpreted. Backed by
`GET /api/v1/tenants/{tenant_id}/observations` (viewer+, tenant-scoped),
served by the Gateway's `ObservationReadStore` (pure READ over the canonical
`observations` table):

- **Pagination** (`limit` 1–200, `offset`), **filters** (`fact_type`,
  `source_type`, `quality_class` Q1–Q4), **sort** (`captured_at` desc/asc).
- Response includes `total` (honest count for the filter) and `facets`
  (distinct fact/source types from the tenant's real data — never invented
  options).
- The UI table shows facts (fact type, fact value, unit, source, captured
  time) with a canonical Q1–Q4 quality-class badge + legend
  (Direct Measurement / Corroborated Inference / Statistical Regularity /
  Anecdotal · Single-Source, per the framework's Evidence concept). A detail
  drawer exposes provenance: raw payload, source id, tenant id. A fixed note
  states the row is a raw fact, not an interpretation. Loading / empty /
  error / forbidden states are explicit; nothing is fabricated (P1).

## Evidence (Fase 4)

The Evidence view renders the coherent organizations of the pipeline's
immutable observations (Perception · Organize, P1) exactly as stored — the
description is objective and the quality class/weight (wᵢ) were assigned at
creation, never retrofitted. Backed by:

- `GET /api/v1/tenants/{tenant_id}/evidence` (viewer+, tenant-scoped),
  served by the Gateway's `EvidenceReadStore` (pure READ over the canonical
  `evidence` table): pagination (`limit` 1–200, `offset`), filters
  (`organization_type`, `quality_class` Q1–Q4), sort (`organized_at`), with
  `total` and `facets` (distinct organization types from the tenant's real
  data — never invented options).
- `GET /api/v1/tenants/{tenant_id}/evidence/{evidence_id}` (viewer+,
  tenant-scoped): one evidence row **with its observation desglose** — the
  organized facts resolved from the canonical `observations` table by
  `observation_ids` (404 when not in this tenant).

The UI table shows organized facts (organization type, Q1–Q4 badge with the
canonical legend, weight wᵢ, number of organized observations, description,
organized time). A detail drawer shows the description, the weight semantics
(assigned at creation from the quality class), and the observation breakdown
as raw facts (fact type, value, unit, captured time, quality badge, raw
payload) — never reinterpreted. Loading / empty / error / forbidden states
are explicit; nothing is fabricated (P1).

## Contexts (Fase 5)

The Contexts view renders the active interpretations of the pipeline
(Perception · Interpret) exactly as stored — a context is never generated
directly (P2), it is selected by explanatory coherence among competing mental
models, and its winner + coherence score were assigned at activation and are
immutable (P1; only the `is_active` lifecycle flag may change). Backed by:

- `GET /api/v1/tenants/{tenant_id}/contexts` (viewer+, tenant-scoped),
  served by the Gateway's `ContextReadStore` (pure READ over the canonical
  `contexts` table): pagination (`limit` 1–200, `offset`), filters
  (`purpose`, `mental_model_id`, `is_active` true|false), sort
  (`activated_at`), with `total` and `facets` (purposes and mental model ids
  from the tenant's real data — never invented options).
- `GET /api/v1/tenants/{tenant_id}/contexts/{context_id}` (viewer+,
  tenant-scoped): one context row **with its evidence desglose** — the
  supporting evidence resolved from the canonical `evidence` table by
  `evidence_ids` (404 when not in this tenant).

The UI table shows each activation (activated time, active badge, purpose,
winner mental model, coherence score, number of organized evidence and
competing models) with filters/order over the real facets. A detail drawer
shows the winner mental model, the `competing_models` list with their
coherence scores (winner highlighted), and the supporting evidence breakdown
with its canonical Q1–Q4 badge and weight — the descriptions of mental models
from the catalog are not re-exposed (the Gateway stays a pure READ; it never
reimplements cognitive content). Loading / empty / error / forbidden states
are explicit; nothing is fabricated (P1).

## Patterns (Fase 6)

The Patterns view renders the detected regularities of the pipeline
(Reasoning · Generalize) exactly as stored — a Pattern describes regular
structure, never its cause (P4: explanations belong to Hypothesis, and no
causal claim is rendered on this view). The support (strength_measure) and
frequency were measured at detection and are immutable (P1; only the
`is_active` lifecycle flag may change). Backed by:

- `GET /api/v1/tenants/{tenant_id}/patterns` (viewer+, tenant-scoped),
  served by the Gateway's `PatternReadStore` (pure READ over the canonical
  `patterns` table): pagination (`limit` 1–200, `offset`), filters
  (`pattern_type`, `is_active` true|false), sort (`detected_at`), with
  `total` and `facets` (pattern types from the tenant's real data — never
  invented options).
- `GET /api/v1/tenants/{tenant_id}/patterns/{pattern_id}` (viewer+,
  tenant-scoped): one pattern row **with its context desglose** — the Active
  Context the regularity was detected over, resolved from the canonical
  `contexts` table by `context_id` (404 when not in this tenant).

The UI table shows each regularity (detected time, active badge, pattern
type, frequency, strength_measure, source context id, description) with
filters/order over the real facets. A detail drawer shows the full
description, the strength measure with its semantics (support/frequency/
p-value measured at detection), and the source context (winner mental model,
purpose, coherence score, competing models count) — regularities are shown as
structure, never as explanation (P4). An empty tenant renders an honest
`No patterns yet` state (the detector only appends regularities with
sufficient measured support). Loading / empty / error / forbidden states are
explicit; nothing is fabricated (P1).

## Anomalies (Fase 7)

The Anomalies view renders the detected deviations of the pipeline (Reasoning ·
Detect Deviation) exactly as stored — an anomaly is a quantified deviation from
an expected Pattern over an Active Context (deviation_score exceeds
tolerance_threshold), never a causal explanation (P4). Score and threshold were
assigned at detection and are immutable (P1); an anomaly has no lifecycle flag.
Backed by:

- `GET /api/v1/tenants/{tenant_id}/anomalies` (viewer+, tenant-scoped),
  served by the Gateway's `AnomalyReadStore` (pure READ over the canonical
  `anomalies` table): pagination (`limit` 1–200, `offset`), filter
  (`anomaly_class`), sort (`detected_at`), with `total` and `facets` (anomaly
  classes from the tenant's real data — never invented options).
- `GET /api/v1/tenants/{tenant_id}/anomalies/{anomaly_id}` (viewer+,
  tenant-scoped): one anomaly row **with its context desglose** — the Active
  Context the deviation was detected over, resolved from the canonical
  `contexts` table by `context_id` (404 when not in this tenant).

The UI table shows each deviation (detected time, anomaly class, deviation
score, tolerance threshold, source context id) with filters/order over the real
facets. A detail drawer shows the quantified deviation vs. its threshold and
the source context (winner mental model, purpose, coherence score) — no causal
claim is rendered (P4; cause belongs to Hypothesis). An empty tenant renders an
honest `No anomalies yet` state (the detector only persists when the deviation
exceeds the threshold over a real pattern). Loading / empty / error / forbidden
states are explicit; nothing is fabricated (P1).

## Hypotheses (Fase 8)

The Hypotheses view renders the tentative explanations of the pipeline
(Reasoning · Predict) exactly as stored — this is the first view where causal
explanations appear (P4). A hypothesis is a commitment to an explanation, held
tentatively until evidence decides: it pairs a description with observable
predicted consequences and a concrete falsification criterion. Content columns
are immutable (P1, enforced by the content trigger); only the `status` lifecycle
field may change (candidate → confirmed/falsified is decided by future evidence
+ Confidence). Backed by:

- `GET /api/v1/tenants/{tenant_id}/hypotheses` (viewer+, tenant-scoped),
  served by the Gateway's `HypothesisReadStore` (pure READ over the canonical
  `hypotheses` table): pagination (`limit` 1–200, `offset`), filter
  (`status` candidate|confirmed|falsified), sort (`generated_at`), with `total`
  and `facets` (statuses from the tenant's real data — never invented options).
- `GET /api/v1/tenants/{tenant_id}/hypotheses/{hypothesis_id}` (viewer+,
  tenant-scoped): one hypothesis **with its desglose** — the anomalies it
  accounts for (resolved from the canonical `anomalies` table by
  `anomaly_ids`), the expected patterns it refers to (from `pattern_ids`) and
  the Active Contexts of those anomalies (from the canonical `contexts` table)
  (404 when not in this tenant).

The UI table shows each tentative explanation (generated time, status badge
Candidate/Confirmed/Falsified, coherence score, number of source anomalies,
description) with filters/order over the real facets. A detail drawer shows the
full explanation, the predicted consequences list, the falsification criterion
and the source anomalies with the deviation score and their context (winner
mental model + purpose) — confirmation or falsification is never asserted here
(it requires future evidence + Confidence). An empty tenant renders an honest
`No hypotheses yet` state (the generator only proposes explanations for
detected anomalies). Loading / empty / error / forbidden states are explicit;
nothing is fabricated (P1).

## Confidence (Fase 9)

The Confidence view renders the calibrated reliability estimates the pipeline
computes for its judgments (Learning · Calibrate). Confidence is computed, not
intuited: each canonical `confidence_scores` row records the final score C_final
with a first-class justification — evidential support S, explanatory coherence
C, the calibration factor (1 − ECE), the mixing coefficient α and the
calibration error estimate ECE (P5). A confidence score is a calibrated
estimate of reliability, not "the probability that the hypothesis is true".
Content columns are fully immutable (P1): the table trigger blocks every
UPDATE/DELETE, so a re-calibration with different inputs is a new row, never an
update. Backed by:

- `GET /api/v1/tenants/{tenant_id}/confidence` (viewer+, tenant-scoped),
  served by the Gateway's `ConfidenceReadStore` (pure READ over the canonical
  `confidence_scores` table): pagination (`limit` 1–200, `offset`), filter
  (`target_type` hypothesis|recommendation|decision), sort (`computed_at`), with
  `total` and `facets` (target_types from the tenant's real data — never
  invented options).
- `GET /api/v1/tenants/{tenant_id}/confidence/{confidence_id}` (viewer+,
  tenant-scoped): one confidence row **with its target desglose** — for a
  `hypothesis` target it reuses the Hypothesis desglose (anomalies by
  `anomaly_ids` + their Active Contexts, resolved from the canonical tables);
  for `decision`/`recommendation` targets it returns the canonical payload of
  those future-layer concepts (404 when not in this tenant).

The UI table shows each calibration (computed time, target type badge, C_final
with its components S, C and ECE, target id) with filters/order over the real
facets. A detail drawer shows the full formula inputs, the
`calibration_justification` verbatim, and the target judgment under evaluation
— including a P5 note that confidence is a reliability estimate, never a
probability of truth. An empty tenant renders an honest `No confidence yet`
state (the calibrator only emits rows when the pipeline produces judgments).
Loading / empty / error / forbidden states are explicit; nothing is fabricated
(P1).

## Recommendations (Fase 10)

The Recommendations view renders the proposed courses of action the pipeline
formulates (Action · Propose). A recommendation is an offer, never a commitment
(P6): it states what to do, why, what is expected to happen, how confident the
system is and what alternatives were considered — all advisory and reversible,
nothing is executed in this view. Each offer carries the CALIBRATED
confidence_score of its leading Hypothesis (R4: the recommendation never
recalibrates — it carries the score and its reasons, already computed) and is
fully traceable: hypothesis → confidence → evidence. Content columns are
immutable (P1, enforced by the content trigger); only the `status` lifecycle
field may change (proposed → accepted/rejected/superseded, decided by the
Decision layer). Backed by:

- `GET /api/v1/tenants/{tenant_id}/recommendations` (viewer+, tenant-scoped),
  served by the Gateway's `RecommendationReadStore` (pure READ over the
  canonical `recommendations` table): pagination (`limit` 1–200, `offset`),
  filter (`status` proposed|accepted|rejected|superseded), sort
  (`proposed_at`), with `total` and `facets` (statuses from the tenant's real
  data — never invented options).
- `GET /api/v1/tenants/{tenant_id}/recommendations/{recommendation_id}`
  (viewer+, tenant-scoped): one recommendation **with its desglose** — the
  leading Hypothesis (with its anomalies/patterns/contexts, reused from
  `HypothesisReadStore`) and the specific calibrated Confidence row that
  supports the offer (with its own target desglose, reused from
  `ConfidenceReadStore`) (404 when not in this tenant).

The UI table shows each offer (proposed time, status badge
Proposed/Accepted/Rejected/Superseded, action description, calibrated
confidence, number of expected consequences, hypothesis id) with
filters/order over the real facets. A detail drawer shows the full offer —
action, rationale, the observable expected consequences, the alternatives
considered (with why each was not chosen) — plus the calibrated confidence
block (S, C, 1 − ECE with the justification verbatim, P5) and the leading
hypothesis with its source anomalies and context. An empty tenant renders an
honest `No recommendations yet` state (the formulator only proposes actions
over real hypotheses + calibrated confidence). Loading / empty / error /
forbidden states are explicit; nothing is fabricated (P1).

## Component tree

```
apps/web/src/
  app/providers.tsx            Query + Theme + Auth providers
  routes/                      ProtectedRoute + route table (lazy)
  components/ui/               button, input, card, badge, skeleton, state primitives
  components/layout/           AppShell, Sidebar, Header, Breadcrumbs,
                               TenantSwitcher (from JWT claims), UserMenu
  components/infrastructure/   ServiceHealthPanel
  components/cognitive/        (Fases 2–12) Pipeline, TraceView, ConceptBadge,
                               ConfidenceGauge, CompetingModels, Timeline
  features/auth/LoginPage.tsx
  features/dashboard/DashboardPage.tsx
  api/  hooks/  lib/  styles/  types/  tests/
```

## Cognitive compliance

- **Views map 1:1 to capabilities**: each view/component represents exactly
  one cognitive capability (the product is an external capability, ADR-0002 —
  R1/R2 bind the cognitive components, not the product UI).
- **R3**: all reads through the Gateway; auth endpoints only via user-service.
- **P1/P2/P4/P6**: observations/evidence shown as facts; context shown as
  active model + competing models; patterns as regularity (never causality);
  recommendation ≠ decision.
- **P5**: confidence is shown as `CALIBRATED` / `NOT AVAILABLE` — never a
  fabricated percentage.
- Frontend never creates cognitive concepts, never touches DB/Redis.

## Backend changes this phase (minimal, justified)

Fase 1 — CORS middleware in `apps/gateway/api-gateway/src/health.py` and
`apps/services/user-service/src/health.py` (allow dev origin
`http://localhost:5173`, methods GET/POST/OPTIONS, headers
Authorization/Content-Type). Boundary enforcement (R3) unchanged.
Tests: `apps/gateway/api-gateway/tests/test_cors.py` (5 cases).

Fase 2 — `CognitiveSummaryStore` (`apps/gateway/api-gateway/src/summary.py`) +
`GET /api/v1/tenants/{tenant_id}/cognitive/summary` (viewer+, tenant-scoped):
pure READ aggregation of append-only pipeline counters per concept
(observations/evidence/contexts/patterns/anomalies/hypotheses/confidence/
recommendations/decisions/reports/servers) + lifecycle status breakdowns.
Wired in `service.py`/`health.py`/`main.py`. Tests:
`apps/gateway/api-gateway/tests/test_gateway_http.py` (+4: 401, own tenant,
cross-tenant 403, superadmin cross-tenant 200).

Fase 3 — `ObservationReadStore` (`apps/gateway/api-gateway/src/observations.py`) +
`GET /api/v1/tenants/{tenant_id}/observations` (viewer+, tenant-scoped):
pure paginated READ of the immutable observation rows with filters
(fact_type/source_type/quality_class), sort (captured_at), `total`, and
facets (distinct types from the tenant's real data). Wired in
`service.py`/`health.py`/`main.py`. Tests: `test_gateway_http.py` (+7: 401,
own tenant page, filters forwarded, cross-tenant 403, superadmin 200, invalid
limit 400, invalid quality_class 400).

Fase 4 — `EvidenceReadStore` (`apps/gateway/api-gateway/src/evidence.py`) +
`GET /api/v1/tenants/{tenant_id}/evidence` (paginated, filterable) +
`GET /api/v1/tenants/{tenant_id}/evidence/{evidence_id}` (detail with the
observation desglose resolved from the canonical observations table; 404
unknown). Wired in `service.py`/`health.py`/`main.py`. Tests:
`test_gateway_http.py` (+11: 401, own tenant page with weight/observation_ids,
filters forwarded, cross-tenant 403, superadmin 200, invalid limit 400,
invalid quality_class 400, detail 401/200 with desglose/404/cross-tenant 403).

Fase 5 — `ContextReadStore` (`apps/gateway/api-gateway/src/contexts.py`) +
`GET /api/v1/tenants/{tenant_id}/contexts` (paginated, filterable:
purpose/mental_model_id/is_active) + `GET /api/v1/tenants/{tenant_id}/contexts/{context_id}`
(detail with the evidence desglose resolved from the canonical evidence table
by `evidence_ids`; 404 unknown). `is_active` filters use
`CAST(:is_active AS BOOLEAN)` in SQL (verified against the real DB). Wired in
`service.py`/`health.py`/`main.py`. Tests: `test_gateway_http.py` (+11: 401,
own tenant page with competing_models, filters forwarded, cross-tenant 403,
superadmin 200, invalid limit 400, invalid is_active 400, detail
401/200 with evidence desglose/404/cross-tenant 403).

Fase 6 — `PatternReadStore` (`apps/gateway/api-gateway/src/patterns.py`) +
`GET /api/v1/tenants/{tenant_id}/patterns` (paginated, filterable:
pattern_type/is_active) + `GET /api/v1/tenants/{tenant_id}/patterns/{pattern_id}`
(detail with the context desglose resolved from the canonical contexts table
by `context_id`; 404 unknown). Wired in `service.py`/`health.py`/`main.py`.
Tests: `test_gateway_http.py` (+11: 401, own tenant page with
strength_measure/frequency, filters forwarded, cross-tenant 403, superadmin
200, invalid limit 400, invalid is_active 400, detail
401/200 with context desglose/404/cross-tenant 403).

Fase 7 — `AnomalyReadStore` (`apps/gateway/api-gateway/src/anomalies.py`) +
`GET /api/v1/tenants/{tenant_id}/anomalies` (paginated, filterable:
anomaly_class) + `GET /api/v1/tenants/{tenant_id}/anomalies/{anomaly_id}`
(detail with the context desglose resolved from the canonical contexts table by
`context_id`; 404 unknown). Wired in `service.py`/`health.py`/`main.py`. Tests:
`test_gateway_http.py` (+11: 401, own tenant page with deviation/threshold,
filters forwarded, cross-tenant 403, superadmin 200, invalid limit 400,
invalid sort 400, detail 401/200 with context desglose/404/cross-tenant 403).

Fase 8 — `HypothesisReadStore` (`apps/gateway/api-gateway/src/hypotheses.py`) +
`GET /api/v1/tenants/{tenant_id}/hypotheses` (paginated, filterable: status
candidate|confirmed|falsified) +
`GET /api/v1/tenants/{tenant_id}/hypotheses/{hypothesis_id}` (detail with the
desglose: anomalies by `anomaly_ids`, patterns by `pattern_ids` and the Active
Contexts of those anomalies, all resolved from the canonical tables; 404
unknown). Wired in `service.py`/`health.py`/`main.py`. Tests:
`test_gateway_http.py` (+12: 401, own tenant page with status/coherence/
consequences, filters forwarded, cross-tenant 403, superadmin 200, invalid
limit 400, invalid status 400, invalid sort 400, detail 401/200 with
anomalies/contexts desglose/404/cross-tenant 403).

Fase 9 — `ConfidenceReadStore` (`apps/gateway/api-gateway/src/confidence.py`) +
`GET /api/v1/tenants/{tenant_id}/confidence` (paginated, filterable:
target_type hypothesis|recommendation|decision, sort computed_at) +
`GET /api/v1/tenants/{tenant_id}/confidence/{confidence_id}` (detail with the
target desglose: hypothesis → the Hypothesis desglose (anomalies + Active
Contexts) reused from `HypothesisReadStore`; decision/recommendation → the
canonical payload of the future Action-layer concepts; 404 unknown). Wired in
`service.py`/`health.py`/`main.py`. Tests: `test_gateway_http.py` (+12: 401,
own tenant page with S/C/ECE/C_final/justification, filters forwarded,
cross-tenant 403, superadmin 200, invalid limit 400, invalid target_type 400,
invalid sort 400, detail 401/200 with the hypothesis/desglose/404/cross-tenant
403).

Fase 10 — `RecommendationReadStore` (`apps/gateway/api-gateway/src/recommendations.py`) +
`GET /api/v1/tenants/{tenant_id}/recommendations` (paginated, filterable:
status proposed|accepted|rejected|superseded, sort proposed_at) +
`GET /api/v1/tenants/{tenant_id}/recommendations/{recommendation_id}` (detail
with the desglose: the leading Hypothesis — anomalies + Active Contexts,
reused from `HypothesisReadStore` — and the calibrated Confidence row that
supports the offer, reused from `ConfidenceReadStore`; 404 unknown). Wired in
`service.py`/`health.py`/`main.py`. Tests: `test_gateway_http.py` (+12: 401,
own tenant page with action/rationale/expected_consequences/
alternatives_considered/confidence_score, filters forwarded, cross-tenant 403,
superadmin 200, invalid limit 400, invalid status 400, invalid sort 400,
detail 401/200 with hypothesis+confidence desglose/404/cross-tenant 403).

## Verification

- `npm run lint` (0 errors) · `npm run typecheck` · `npm test` (66 passed)
  · `npm run build`
- Gateway: `pytest apps/gateway/api-gateway/tests/` (141 passed) · `ruff` clean
- Live smoke test against the real platform: login 200,
  `GET .../observations?limit=3` 200 with real data (total 1877, facets from
  real fact/source types, first row `disk_usage` Q1 linux_agent),
  filter `fact_type=cpu_utilization_percent` → 624 real rows,
  `quality_class=Q2` → 0 (honest empty: all real rows are Q1),
  offset pagination at the tail, cross-tenant superadmin 200, no token 401,
  invalid limit/quality_class 400, CORS preflight 204.
- Fase 4 live: `GET .../evidence?limit=5` 200 with real data (total 3,
  facets from real organization types: resource_exhaustion_evidence /
  service_degradation_evidence / backup_failure_evidence, rows Q1 weight
  0.88), detail `GET .../evidence/{id}` 200 with the observation desglose
  (backup_failure_evidence → 3 real observations: backup_job_status /
  repo_free_bytes / repo_capacity_bytes), filter organization_type → 1,
  `quality_class=Q2` → 0 (honest: all real evidence is Q1), cross-tenant
  admin 403, own empty tenant 200, no token 401, invalid quality_class 400,
  unknown evidence 404, CORS preflight 204.
- Fase 5 live: `GET .../contexts?limit=10` 200 with real data (total 3,
  facets from real purposes: security_posture / infrastructure_health /
  capacity_management; mental model ids: service_failure / capacity_risk;
  all rows active, coherence 0.33), detail `GET .../contexts/{id}` 200 with
  the evidence desglose (service_failure/security_posture → 3 real evidence:
  resource_exhaustion_evidence / service_degradation_evidence /
  backup_failure_evidence, Q1 weight 0.88) and competing models
  [service_failure 0.33, auth_compromise 0.0], filter
  `purpose=security_posture` → 1, `is_active=false` → 0 (honest: all real
  contexts are active), cross-tenant admin 403, own empty tenant 200,
no token 401, invalid is_active 400, unknown context 404, CORS preflight
204.
- Fase 6 live: `GET .../patterns?limit=5` 200 with honest empty state (total
  0, empty facets — the detector only appends regularities whose measured
  support meets the library threshold over the tenant's context stream; the
  sandbox tenant has 1–2 activations per mental model, below the minimum),
  filters `is_active=false` and `pattern_type=temporal` → 0, unknown pattern
  404, invalid limit/is_active 400, no token 401, cross-tenant admin 403,
  own empty tenant 200 with empty facets, CORS preflight 204.
- Fase 9 live: `GET .../confidence?limit=5` 200 with honest empty state (total
  0, empty facets — the calibrator only emits rows when the pipeline produces
  judgments, and the sandbox tenant has no hypotheses/anomalies yet),
  filter `target_type=hypothesis` → 0, invalid target_type 400, no token 401,
  unknown confidence 404, CORS preflight 204.
- Fase 10 live: `GET .../recommendations?limit=5` 200 with honest empty state
  (total 0, empty facets — the formulator only proposes actions over real
  hypotheses + calibrated confidence, and the sandbox tenant has none yet),
  filter `status=proposed` → 0, sort `proposed_at_asc` 200, invalid status 400,
  no token 401, unknown recommendation 404, CORS preflight 204. Full platform
  re-booted with `./start.sh --force` after a dev-process kill; all 12
  services healthy (8080–8100) and regression check on
  observations/evidence/contexts/patterns/anomalies/hypotheses/confidence/
  summary all 200.