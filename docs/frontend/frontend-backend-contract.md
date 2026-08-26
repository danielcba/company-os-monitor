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
