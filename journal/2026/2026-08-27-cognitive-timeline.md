# 2026-08-27 Cognitive Timeline (Investigation)

## What

Implemented the **Cognitive Timeline** — a read/compute Investigation capability
that reconstructs the chronological sequence of cognitive events for a tenant
from the canonical read stores. No new persisted entity (ADR-0002); the timeline
is derived on demand and never fabricated (P1).

## Why

The Company OS framework's Cognitive Architecture defines Investigation as a
monitoring capability: operators need to understand *when* cognitive events
happened across layers, not just *what* happened (Cognitive Trace, Fase 2A/2B).
The Cognitive Timeline provides this temporal reconstruction, covering the full
canonical chain: Observations → Evidence → Contexts → Patterns → Anomalies →
Hypotheses → Insights → Recommendations → Decisions → Reports → Confidence,
plus the Episodic Memory (audit_log).

The frontend architecture (`docs/frontend/architecture.md:44`) marked this as
"Investigation: Cognitive Trace + Timeline (planned)". This delivers the
Timeline half.

## Implementation

### Backend

- **`libs/memory/cognitive_timeline.py`** (new): Core capability —
  `build_cognitive_timeline()` orchestrates 12 reader calls, maps each payload
  to a `TimelineEvent`, sorts by timestamp, and counts per-layer/per-concept.
  12 reader Protocols mirror the gateway read-store contract. Defensive: a
  failing reader does not break the timeline (that concept is omitted).

- **`apps/gateway/api-gateway/src/service.py`**: Added `timeline_store` param +
  `get_cognitive_timeline()` method (auth `read`).

- **`apps/gateway/api-gateway/src/health.py`**: Route
  `GET /api/v1/tenants/{tenant_id}/cognitive-timeline` + handler with optional
  `limit` and `ascending` query params.

- **`apps/gateway/api-gateway/src/main.py`**: Constructs `CognitiveTimelineStore`
  with all 12 gateway read stores (Observation, Evidence, Context, Pattern,
  Anomaly, Hypothesis, Insight, Recommendation, Decision, Report, Confidence,
  Audit). `EvidenceReadStore` + `AnomalyReadStore` added (new imports).

### Frontend

- **`apps/web/src/types/cognitive.ts`**: `CognitiveTimelineEvent` +
  `CognitiveTimelineResponse` interfaces.

- **`apps/web/src/api/gateway.ts`**: `fetchCognitiveTimeline()` client function.

- **`apps/web/src/features/timeline/useCognitiveTimeline.ts`**: React Query hook
  with `limit` and `ascending` params.

- **`apps/web/src/features/timeline/TimelinePage.tsx`**: Page rendering the
  chronological list with layer/concept badges, a summary card (activity by
  layer), ascending toggle, and limit selector. Loading/empty/error/forbidden
  states handled.

- **`apps/web/src/tests/timeline.test.tsx`**: 3 tests — render with data, empty
  state, 403 forbidden.

- **`apps/web/src/routes/index.tsx`**: Route `/investigation/timeline`.

- **`apps/web/src/components/layout/Sidebar.tsx`**: "Investigation" nav group
  with Cognitive Timeline entry.

### Tests

- **`tests/memory/test_cognitive_timeline.py`**: Pure logic — mapping, sorting,
  layer/concept counting, defensive skip of unavailable reader, store wrapper.

- **`apps/gateway/api-gateway/tests/test_cognitive_timeline.py`**: HTTP — auth
  required, tenant-scoped response, cross-tenant 403.

### Documentation

- **`docs/frontend/frontend-backend-contract.md`**: Added Cognitive Timeline
  section (GET endpoint, query params, full response schema).

## Verification

- **Backend**: ruff clean, pytest 248 tests pass (tests/memory +
  gateway/tests).
- **Frontend**: typecheck clean, lint 0 errors (4 pre-existing warnings),
  182 tests pass (including 3 new timeline tests), build OK.
- CI: PR #13 pending (docker-build on merge to main).
