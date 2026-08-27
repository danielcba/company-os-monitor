# Frontend-Backend Contract — COS-Monitor Web

> **Version:** 1.0 · **Status:** Official · **Owner:** COS-Monitor · **Date:** 2026-08-23

## Purpose

This document defines the API contract between the COS-Monitor frontend and the backend services (API Gateway + User Service). All cognitive data flows through the API Gateway (R3); auth endpoints go directly to the User Service.

## Service Endpoints

| Service | URL | Auth | Purpose |
|---|---|---|---|
| API Gateway | `http://localhost:8100/api/v1` | Bearer JWT | All cognitive data |
| User Service | `http://localhost:8099/api/v1` | None (login) / Bearer JWT | Auth, user CRUD |

## Authentication

### POST `/auth/login` (User Service)

**Request:**
```json
{
  "email": "string",
  "password": "string",
  "tenant_id?: string"
}
```

**Response (200):**
```json
{
  "access_token": "string (JWT HS256/RS256)",
  "refresh_token": "string (JWT)",
  "token_type": "bearer",
  "expires_in": 3600
}
```

### POST `/auth/refresh` (User Service)

**Request:**
```json
{
  "refresh_token": "string"
}
```

**Response (200):** Same as login response (new access + refresh tokens).

### GET `/user/me` (User Service)

**Response (200):**
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "email": "string",
  "name": "string | null",
  "role": "viewer | operator | admin | superadmin",
  "is_active": true,
  "created_at": "ISO-8601",
  "updated_at": "ISO-8601"
}
```

## Cognitive Data Endpoints (API Gateway)

All endpoints require `Authorization: Bearer <access_token>` and are scoped by `tenant_id`.

### Health

| Method | Path | Description |
|---|---|---|
| GET | `/services/health` | Pipeline service health status |

### Cognitive Summary

| Method | Path | Description |
|---|---|---|
| GET | `/tenants/{tenant_id}/cognitive/summary` | Totals + status breakdowns |

### Observations (Perception · Capture)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/observations` | `limit`, `offset`, `fact_type`, `source_type`, `quality_class`, `sort` | Paginated observations |

**Response:**
```json
{
  "observations": [{ "id", "tenant_id", "source_id", "source_type", "fact_type", "fact_value": {}, "unit", "captured_at", "quality_class", "raw_payload": {} }],
  "total": "number",
  "limit": "number",
  "offset": "number",
  "facets": { "fact_types": [], "source_types": [], "quality_classes": [] }
}
```

### Evidence (Perception · Organize)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/evidence` | `limit`, `offset`, `organization_type`, `quality_class`, `sort` | Paginated evidence |
| GET | `/tenants/{tenant_id}/evidence/{id}` | — | Evidence detail + observation desglose |

### Contexts (Perception · Interpret)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/contexts` | `limit`, `offset`, `purpose`, `mental_model_id`, `is_active`, `sort` | Paginated contexts |
| GET | `/tenants/{tenant_id}/contexts/{id}` | — | Context detail + evidence desglose |

### Patterns (Reasoning · Generalize)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/patterns` | `limit`, `offset`, `pattern_type`, `is_active`, `sort` | Paginated patterns |
| GET | `/tenants/{tenant_id}/patterns/{id}` | — | Pattern detail + context desglose |

### Anomalies (Reasoning · Detect)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/anomalies` | `limit`, `offset`, `anomaly_class`, `sort` | Paginated anomalies |
| GET | `/tenants/{tenant_id}/anomalies/{id}` | — | Anomaly detail + context desglose |

### Hypotheses (Reasoning · Predict)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/hypotheses` | `limit`, `offset`, `status`, `sort` | Paginated hypotheses |
| GET | `/tenants/{tenant_id}/hypotheses/{id}` | — | Hypothesis detail + anomalies/contexts desglose |

### Insights (Reasoning · Restructure)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/insights` | `limit`, `offset`, `sort` | Paginated insights |
| GET | `/tenants/{tenant_id}/insights/{id}` | — | Insight detail + hypotheses/context desglose |

### Confidence (Learning · Calibrate)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/confidence` | `limit`, `offset`, `target_type`, `sort` | Paginated confidence scores |
| GET | `/tenants/{tenant_id}/confidence/summary` | — | Aggregated confidence stats |
| GET | `/tenants/{tenant_id}/confidence/{id}` | — | Confidence detail + target desglose |

### Recommendations (Action · Propose)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/recommendations` | `limit`, `offset`, `status`, `sort` | Paginated recommendations |
| GET | `/tenants/{tenant_id}/recommendations/{id}` | — | Recommendation detail + hypothesis/confidence desglose |

### Decisions (Action · Commit)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/decisions` | `limit`, `offset`, `status`, `sort` | Paginated decisions |
| GET | `/tenants/{tenant_id}/decisions/{id}` | — | Decision detail + recommendation/confidence desglose |

### Audit Log (Episodic Memory)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/audit` | `limit`, `offset`, `user_id`, `cognitive_layer`, `cognitive_concept`, `action`, `date_from`, `date_to`, `sort` | Paginated audit entries |

### Reports (Action · Report)

| Method | Path | Query Params | Description |
|---|---|---|---|
| GET | `/tenants/{tenant_id}/reports` | `limit`, `offset`, `report_type`, `sort` | Paginated reports |
| GET | `/tenants/{tenant_id}/reports/{id}` | — | Report detail with content |

### Cognitive Trace (Read Model · Provenance View)

> External capability (ADR-0002). NOT a new cognitive stage or persisted entity.
> Reconstructed on demand from canonical stores; root is always a Report.

| Method | Path | Description |
|---|---|---|
| GET | `/tenants/{tenant_id}/cognitive-trace/report/{report_id}` | Reconstructed provenance graph (nodes + edges) for a Report |

**Response (`CognitiveTraceResponse`):**

```json
{
  "root": { "type": "report", "id": "uuid", "tenant_id": "uuid" },
  "nodes": [ { "type", "id", "tenant_id", "timestamp", "data" } ],
  "edges": [ { "from", "to", "relation" } ],
  "completeness": "complete" | "partial",
  "warnings": [ "..." ]
}
```

**Notes:** Tenant-scoped — a Report from another tenant resolves to 404. If
referenced provenance is missing, the trace returns `partial` with explicit
`warnings`; broken links are never fabricated. Node types:
`report → decision → recommendation → confidence → hypothesis → anomaly →
pattern → context → evidence → observation`.

### Learning (P7) Read/Compute Capabilities

> External capabilities (ADR-0002). NOT new cognitive stages or persisted
> entities. Each derives a ***learning signal*** from Decision outcomes
> (via Outcome Consolidation, the single source of truth for verdicts — no
> fabrication of failures). The gateway consumes its read stores and never
> imports the reasoning/perception pipeline.

| Method | Path | Description |
|---|---|---|
| GET | `/tenants/{tenant_id}/patterns/refinement` | Pattern Refinement signal (P7+P4): keep / degrade / deactivate |
| GET | `/tenants/{tenant_id}/contexts/revision` | Context Revision signal (P7+P2): keep / review / consider_competitor |
| GET | `/tenants/{tenant_id}/insights/transformations` | Insight Transformation journal (R6): prior → updated mental-model + outcome attribution |

**`PatternRefinementResponse`:**
```json
{
  "tenant_id": "uuid",
  "total_patterns": "number",
  "patterns_with_outcomes": "number",
  "results": [
    {
      "pattern_id": "uuid", "pattern_type": "string", "context_id": "uuid",
      "tenant_id": "uuid", "linked_decisions": "number",
      "corroborated": "number", "contradicted": "number", "inconclusive": "number",
      "contradiction_ratio": "number",
      "current_strength": "number", "recommended_strength": "number",
      "recommended_action": "keep" | "degrade" | "deactivate"
    }
  ]
}
```

**`ContextRevisionResponse`:**
```json
{
  "tenant_id": "uuid",
  "total_contexts": "number",
  "contexts_with_outcomes": "number",
  "results": [
    {
      "context_id": "uuid", "tenant_id": "uuid", "linked_decisions": "number",
      "corroborated": "number", "contradicted": "number", "inconclusive": "number",
      "contradiction_ratio": "number",
      "has_competing_models": "boolean",
      "recommended_revision": "keep" | "review" | "consider_competitor",
      "suggested_competitor": "string | null"
    }
  ]
}
```

**`InsightTransformationResponse`:**
```json
{
  "tenant_id": "uuid",
  "total_insights": "number",
  "results": [
    {
      "insight_id": "uuid", "tenant_id": "uuid", "context_id": "uuid | null",
      "description": "string", "prior_understanding": "string | null",
      "mental_model_update": "object | null",
      "transformation_kind": "revised" | "stable" | "unchanged",
      "linked_recommendations": "number",
      "linked_decisions_with_outcomes": "number",
      "corroborated": "number", "contradicted": "number", "inconclusive": "number"
    }
  ]
}
```

**Notes:**
- Verdicts come from Outcome Consolidation (`actual_outcomes` missing/ambiguous →
  `inconclusive`, never a fabricated failure, P1).
- Pattern Refinement only *adjusts support* — it never invents or removes
  patterns (P4). `deactivate` lowers `recommended_strength` to 0.
- Context Revision only *suggests* a competing model (`consider_competitor` +
  `suggested_competitor`); it never activates or generates a Context (P2).
- Insight Transformation journals the prior → updated mental-model
  transformation (R6); classification is descriptive, never a causal claim (P4).
- All three are surfaced in the frontend at `/learning` (read/only UI).

### Learning Memory Ledger (P7 Persistence, authorized 2026-08-27)

> New persisted entity (`learning_memory`). Append-only and immutable-by-record
> (P1); idempotent. Canonical entities are NEVER mutated. This is the only P7
> capability that writes; it is triggered by an explicit, authorized POST.

| Method | Path | Description |
|---|---|---|
| GET | `/tenants/{tenant_id}/memory` | List persisted learning records (query: `target_type`, `target_id`) |
| POST | `/tenants/{tenant_id}/memory` | Persist a learning signal (idempotent; requires Decision Authority `commit`) |

**Request (`PersistLearningMemoryRequest`):**
```json
{
  "target_type": "pattern" | "context" | "insight",
  "target_id": "uuid",
  "signal": { "...": "learned adjustment (free object)" },
  "provenance": { "...": "decision_ids / counts / verdicts" }
}
```

**Response (`LearningMemoryRecord`):**
```json
{
  "id": "uuid",
  "tenant_id": "uuid",
  "target_type": "pattern" | "context" | "insight",
  "target_id": "uuid",
  "signal": { "...": "..." },
  "provenance": { "...": "..." },
  "signal_hash": "sha256-hex",
  "created_at": "ISO-8601"
}
```

**`LearningMemoryResponse` (GET list):** `{ "memories": [LearningMemoryRecord], "total": number }`

**Notes:**
- Idempotency: re-POSTing an identical `signal` for the same `target_type`/
  `target_id` is a no-op (UNIQUE `(tenant_id, target_type, target_id, signal_hash)`).
- Authorization: POST requires `commit` authority (admin/superadmin); GET
  requires `read`. 401 = no/invalid token, 403 = insufficient authority,
  400 = invalid `target_type` or non-object `signal`/`provenance`.
- The frontend `/learning` page lists this ledger ("Persisted Memory") and
  offers a per-row "Save to Memory" action on each read/compute signal.

### Tenants (Superadmin)

| Method | Path | Description |
|---|---|---|
| GET | `/user/tenants` | List all tenants |
| GET | `/user/tenants/{id}` | Tenant detail |

## Error Responses

All error responses follow the structure:

```json
{
  "error": "string (human-readable message)"
}
```

| Status | Code | Meaning |
|---|---|---|
| 400 | — | Invalid request parameters |
| 401 | `unauthorized` | Missing or invalid token |
| 403 | `forbidden` | Insufficient role/permissions |
| 404 | — | Resource not found or not in tenant |
| 409 | — | Conflict (e.g., duplicate email) |
| 500 | — | Internal server error |

## Token Management (Frontend)

- **Storage**: `localStorage` keys `cosmonitor.access_token` and `cosmonitor.refresh_token`
- **Refresh**: On 401 response, `apiFetch` calls `POST /auth/refresh` with the refresh token
- **Retry**: Original request retried once after successful refresh
- **Sign-out**: Tokens cleared from localStorage; user redirected to `/login`

## Tenant Isolation

Every cognitive query is scoped by `tenant_id` in the URL path. The API Gateway extracts `tenant_id` from the JWT claims and verifies it matches the URL parameter. Cross-tenant queries require `superadmin` authority with the `cross_tenant` permission.

## Evolution Notes

- Add OpenAPI 3.1 spec generation from Pydantic models.
- Implement GraphQL federation for complex cross-concept queries.
- Add WebSocket subscriptions for real-time cognitive updates.

## References

- `apps/web/src/api/client.ts` (apiFetch implementation)
- `apps/web/src/api/gateway.ts` (cognitive data functions)
- `apps/web/src/api/auth.ts` (auth functions)
- `apps/gateway/api-gateway/src/health.py` (gateway routes)
- `apps/services/user-service/src/service.py` (user service)
