# Architecture Decision Record 0005

Title: Machine Authentication — Separation from Human Auth

Status: ACCEPTED
Approved: 2026-09-03
Approved-by: Human Review

Date: 2026-09-02

---

## Context

The current authentication system (Sprint 12) implements human authentication via `user-service` with JWT tokens (HS256/RS256). Agents currently use a hardcoded `TENANT_ID` and `SOURCE_ID` environment variables with no authentication when publishing to Redis directly.

The H4 Critical Gate (CR-6) identifies that machine authentication must be **completely separated** from human authentication:
- Different signing key (compromise isolation)
- Different token structure, claims, and scopes
- Separate blacklist/revocation namespace (Redis DB or key prefix)
- Independent rotation and expiration policies
- Fail-closed validation

The current architecture has no machine auth endpoint, no agent registration flow, and no credential lifecycle management.

## Decision

### 1. Separate Signing Key

- **Human JWT**: Signed with `JWT_PRIVATE_KEY` (RS256) or `JWT_SECRET_KEY` (HS256) — configured via existing env vars
- **Machine JWT**: Signed with dedicated `MACHINE_JWT_PRIVATE_KEY` (RS256 preferred) or `MACHINE_JWT_SECRET_KEY` (HS256 for dev only)

**RS256 is mandatory for production**. HS256 is permitted only for local development with explicit documentation. The term "public_key_hash" is incorrect for HS256 (symmetric); HS256 uses a shared secret. RS256 uses a private key for signing, public key for verification.

**Key Rotation (RS256)**:
- Machine JWTs **MUST** include a `kid` (Key ID) header claim identifying the signing key.
- The Gateway maintains a key set: `MACHINE_JWT_PRIVATE_KEY_<kid>` and `MACHINE_JWT_PUBLIC_KEY_<kid>` for each active key.
- On rotation: deploy new key with new `kid`; keep old key(s) active for verification during an overlap window of **24 hours** (covers max refresh token lifetime).
- When verifying a token: look up public key by `kid`. If `kid` unknown → reject token (fail-closed). If `kid` present but key not configured → reject (fail-closed).
- Token issuance always uses the current active signing key (latest `kid`).

### 2. Machine Token Claims

```json
{
  "sub": "credential_id",           // UUID of the agent credential
  "tenant_id": "uuid",              // tenant scope (required)
  "installation_id": "uuid",        // agent installation identity
  "instance_id": "uuid",            // specific running instance
  "scopes": ["telemetry:ingest"],   // minimal scope for MVP
  "iat": 1234567890,
  "exp": 1234567950,                // short-lived: 60 seconds (access)
  "jti": "uuid",                    // unique token ID for blacklist
  "type": "machine_access"
}
```

**Header (RS256)**: `{"alg": "RS256", "kid": "key-id-v1", "typ": "JWT"}` — `kid` identifies the signing key for rotation.

### 3. Scopes (Minimal MVP)

| Scope | Purpose |
|-------|---------|
| `telemetry:ingest` | POST /api/v1/telemetry/ingest |
| `telemetry:heartbeat` | POST /api/v1/agents/instance/heartbeat (future) |
| `agent:register` | POST /api/v1/agents/instance/register (registration token exchange) |

No `admin`, `read`, `write` scopes. Machine tokens are capability-bound, not role-bound.

### 4. Refresh Token & Rotation

- **Access token**: 60 seconds (short to limit blast radius)
- **Refresh token**: 24 hours, stored in Redis with `machine_refresh:{credential_id}` key (TTL = 24h + 1h buffer)
- **Rotation**: On refresh, old access token JTI added to machine blacklist, new access + refresh issued
- **Revocation**: `DELETE /api/v1/agents/credentials/{credential_id}` → adds all active JTIs to blacklist, deletes refresh token
- **Delivery**: Refresh token returned in **response body** (JSON field `refresh_token`). The agent stores it securely (file, secret manager, etc.). No cookie-based delivery for MVP — machine-to-machine agents use response body for simplicity and cross-platform consistency.

### 5. Separate Blacklist Namespace

- **Human blacklist**: `jwt_blacklist:{jti}` (existing, Redis DB 1)
- **Machine blacklist**: `machine_jwt_blacklist:{jti}` (new, Redis DB 2 or key prefix)

Separate Redis DB (2) preferred for operational isolation. If single Redis instance, key prefix `machine_jwt_blacklist:` is acceptable.

### 6. Machine Auth Endpoint

`POST /api/v1/auth/machine/token` — exchanges registration token or refresh token for access + refresh tokens.

**Registration token flow** (initial bootstrap):
1. Admin creates credential via `POST /api/v1/agents/credentials` (human auth, admin scope)
2. Response includes `registration_token` (JWT) with claims:
   ```json
   {
     "sub": "credential_id",
     "tenant_id": "uuid",
     "installation_id": "uuid",
     "jti": "uuid",
     "exp": 1234567890,              // 10 minutes from issuance
     "scopes": ["agent:register"],
     "type": "registration_token"
   }
   ```
   - TTL: 10 minutes (600 seconds)
   - Single-use: blacklisted on first exchange (JTI added to machine blacklist)
   - Replay prevention: second use → 401
   - Host binding: registration token **does not** bind to host fingerprint (impossible before first registration). Protection: registration endpoint (`POST /agents/instance/register`) validates `host_fingerprint` against `agent_installations.host_fingerprint` (ADR-0006). A cloned VM cannot register even with a stolen registration token.
   - Delivery: returned in response body (JSON field `registration_token`). No environment-variable requirement. The admin distributes it securely (e.g., copy-paste, secure file transfer, secret manager).
   - Permissions: scope `agent:register` only; cannot be used for telemetry/heartbeat.
   - Logging/redaction: registration token **MUST BE REDACTED** in all logs (structured logging with secret redaction per ADR-0018 observability). Never log the full token.

3. Agent presents `registration_token` to `POST /api/v1/auth/machine/token` → receives first access + refresh token
4. Registration token is single-use (blacklisted on exchange)

**Refresh flow** (steady state):
1. Agent presents refresh token (in request body, field `refresh_token`) to `POST /api/v1/auth/machine/token`
2. Validates refresh token exists in Redis (`machine_refresh:{credential_id}`), not revoked
3. Issues new access token (60s) + new refresh token (24h), rotates refresh token in Redis
4. Old access token JTI → machine blacklist

### 7. Credential ↔ Installation Relationship

```
agent_installations (1) ←→ (N) agent_credentials
```

- One installation can have multiple credentials (rotation, multiple agents on same host)
- Each credential belongs to exactly one installation
- Credential stores: `credential_id`, `installation_id`, `tenant_id`, `public_key_hash` (for mTLS future), `status`, `created_at`, `revoked_at`
- Only `ACTIVE` credentials can obtain tokens

### 8. Fail-Closed Validation

Gateway machine auth middleware:
1. Verify JWT signature with machine public key (RS256) or secret (HS256 dev)
2. Check `type == "machine_access"` (or `registration_token` for registration endpoint)
3. Check `exp` not expired
4. Check JTI not in machine blacklist (Redis DB 2) — **if Redis unavailable → reject (fail-closed)**
5. Extract `tenant_id`, `installation_id`, `instance_id`, `scopes`, `credential_id` (from `sub`)
6. Validate `installation_id` exists and is `ACTIVE` in `agent_installations`
7. Validate `credential_id` (from `sub`) is `ACTIVE` and belongs to `installation_id`
8. **For telemetry/heartbeat endpoints**: Validate `instance_id` exists, `status == 'RUNNING'`, and `credential_id` matches `agent_instances.credential_id`. A `STOPPED` instance **cannot** send telemetry/heartbeat even if its short-lived JWT has not expired. The middleware must check instance status on every request.
9. Attach `AuthorizationContext` with machine identity to request

**Reconciler/Heartbeat Race**: The reconciler marks instances `STOPPED` when heartbeat times out. There is a window (≤ heartbeat interval, default 30s) where an instance is `STOPPED` in DB but the agent still holds a valid access token. The middleware check in step 8 closes this window: the next telemetry/heartbeat request with a `STOPPED` instance_id is rejected (401). The agent must re-register (new instance_id, new token).

### 9. Token Delivery to Agent

- **Access token**: `Authorization: Bearer <token>` header
- **Refresh token**: returned in response body (JSON field `refresh_token`). Agent stores securely. No cookie-based delivery for MVP.
- **Registration token**: returned in response body (JSON field `registration_token`), single-use, short-lived

## Alternatives Considered

### Shared Human/Machine JWT Signing Key
- Rejected: Compromise of agent credential would allow forging human tokens and vice versa

### Long-Lived Machine Tokens (No Refresh)
- Rejected: No revocation/rotation capability; credential theft = permanent access

### API Keys (Static)
- Rejected: No expiration, no rotation, no revocation granularity, no scope binding

### mTLS Only
- Rejected: Operational complexity for MVP; JWT + registration token achieves same security with simpler deployment. mTLS deferred (ADR-0009: Partition Maintenance — keep MVP minimal)

### Single Redis DB for Both Blacklists
- Acceptable with key prefix (`machine_jwt_blacklist:`). Separate DB (2) preferred but not blocking.

## Architectural Invariants

1. **Key separation**: Human and machine signing keys are never shared
2. **Namespace separation**: Blacklists, Redis keys, token types are disjoint
3. **Short-lived access**: Machine access tokens ≤ 60 seconds
4. **Explicit scopes**: No wildcards; each endpoint declares required scope
5. **Installation binding**: Token valid only if `installation_id` is `ACTIVE`
6. **Credential binding**: Token valid only if `credential_id` (sub) is `ACTIVE` and matches installation
7. **Fail-closed**: Redis blacklist unavailable → reject token
8. **No role inheritance**: Machine tokens do not map to human roles (viewer/operator/admin)

## Security / Multi-tenancy

- `tenant_id` in token is authoritative; all operations scoped to it
- Cross-tenant machine requests impossible (token carries single `tenant_id`)
- Credential creation requires human admin in same tenant
- Registration token is single-use, short-lived, bound to `credential_id`
- Refresh token rotation limits window of stolen refresh token to ≤ 24h
- Revocation is immediate (blacklist + refresh token deletion)

## Failure / Recovery Semantics

| Failure | Behavior |
|---------|----------|
| Redis (blacklist) down | Fail-closed: reject all machine tokens |
| Redis (refresh tokens) down | Cannot issue new tokens; existing access tokens work until expiry (60s) |
| Signing key rotation | Deploy new key; old key valid for verification until all tokens expire (max 60s + 24h) |
| Credential revoked | Immediate: all JTIs blacklisted, refresh token deleted |
| Agent clock skew | JWT `exp`/`iat` validated with 30s leeway |
| Registration token replay | Blacklisted on first use; second use → 401 |

## Consequences

### Benefits
- Complete isolation between human and machine auth surfaces
- Short-lived tokens limit credential theft impact
- Explicit scopes enforce least privilege
- Rotation and revocation operationalized
- Registration token bootstrap eliminates shared secrets

### Costs
- Additional `agent_credentials` table
- Machine auth endpoint in Gateway (or user-service)
- Separate Redis DB or key prefix management
- Agent must implement token refresh logic (60s access → proactive refresh)

### Complexity Introduced
- Dual JWT validation paths in Gateway
- Registration token exchange flow
- Refresh token rotation with blacklist coordination
- Credential lifecycle management (create, rotate, revoke)

## Implementation Constraints

### What H4.0 Must Implement
1. `agent_credentials` table (with FK to `agent_installations`)
2. Machine JWT signing/verification (RS256 production, HS256 dev)
3. `POST /api/v1/auth/machine/token` endpoint (registration + refresh flows)
4. Machine blacklist in Redis (DB 2 or key prefix)
5. Gateway middleware for machine token validation (fail-closed)
6. Credential management endpoints (admin-only): create, list, revoke
7. Registration token generation (admin action)

### What Must NOT Be Implemented
- mTLS (deferred)
- Certificate-based auth (deferred)
- Long-lived static API keys
- Human role mapping for machine tokens
- Cross-tenant machine access

## Test Requirements

Before considering this decision implemented, the following tests must pass:

1. **Key separation**: Human token signed with machine key → rejected; machine token signed with human key → rejected
2. **RS256 production**: Machine tokens verify with public key; HS256 dev mode documented and gated
3. **Key rotation (kid)**: Token with unknown `kid` → rejected; token with old `kid` within overlap window → accepted; token with old `kid` after overlap window → rejected
4. **Scope enforcement**: Token without `telemetry:ingest` → 403 on ingest endpoint
5. **Short expiry**: Access token > 60s → rejected
6. **Blacklist fail-closed**: Redis down → machine token rejected (human token uses separate blacklist, may have different policy)
7. **Refresh rotation**: Refresh → new access + new refresh; old access JTI blacklisted; old refresh deleted
8. **Revocation**: Credential revoke → immediate 401 on subsequent requests with that credential's tokens
9. **Registration token**: Single-use; exchange → access+refresh; replay → 401; expired (10min) → 401
10. **Installation binding**: Token for disabled installation → 401
11. **Instance STOPPED validation**: Token with valid JWT but instance_id status=STOPPED → 401 on telemetry/heartbeat endpoints
12. **Tenant isolation**: Machine token for tenant A cannot access tenant B resources
13. **Registration token redaction**: Structured logs never contain full registration token (redacted)

## Dependencies

- **ADR-0001**: Company OS is the Brain
- **ADR-0002**: COS-Monitor is the Product (external capability)
- **ADR-0004**: Transactional Outbox (ingestion endpoint requires machine auth)
- **ADR-0006**: Agent Identity & Instance Lifecycle (installation_id, credential_id)
- **ADR-0007**: Telemetry Contract (batch_id, payload_hash in machine token context)

---

*This ADR resolves CR-6 (Machine Auth) from the H4 Critical Architectural Gate.*