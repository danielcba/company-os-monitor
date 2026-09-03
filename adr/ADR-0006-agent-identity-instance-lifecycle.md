# Architecture Decision Record 0006

Title: Agent Identity & Instance Lifecycle

Status: ACCEPTED
Approved: 2026-09-03
Approved-by: Human Review

Date: 2026-09-02

---

## Context

The current architecture has no formal agent identity model. Agents run with hardcoded `TENANT_ID` and `SOURCE_ID` environment variables. There is no:
- Installation registration or tracking
- Instance lifecycle management (start, stop, restart, crash detection)
- Heartbeat mechanism
- Credential binding to installation
- At-most-one-active-instance enforcement

The H4 Critical Gate (CR-4) requires an explicit agent instance lifecycle with:
- `installation_id` (persistent identity of agent on a host)
- `credential_id` (authentication credential, rotatable)
- `agent_instance_id` (ephemeral identity of a running process)
- Explicit instance registration endpoint
- Ownership: installation → instance
- At-most-one-active-instance invariant
- Restart/reinstall/upgrade/re-enroll semantics

## Decision

### 1. Identity Hierarchy

```
Tenant
  └── Server (host) — existing `servers` table
        └── Installation (agent_installations) — persistent agent identity on a host
              ├── Credential (agent_credentials) — rotatable auth credential (ADR-0005)
              └── Instance (agent_instances) — ephemeral running process
```

### 2. Installation Lifecycle

**Table**: `agent_installations`

```sql
CREATE TABLE agent_installations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    server_id       UUID NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    host_fingerprint CHAR(64) NOT NULL,  -- SHA-256 of host identity (see ADR-0007)
    agent_type      VARCHAR(50) NOT NULL, -- linux_agent, windows_agent, vmware_agent
    agent_version   VARCHAR(50) NOT NULL,
    capabilities_json JSONB NOT NULL DEFAULT '{}', -- declarative quality_class mapping
    status          VARCHAR(20) NOT NULL DEFAULT 'PROVISIONED'
        CHECK (status IN ('PROVISIONED', 'ACTIVE', 'DISABLED', 'REVOKED')),
    registered_at   TIMESTAMPTZ,
    last_seen_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    UNIQUE (tenant_id, server_id, agent_type)
);
```

**States**:
- `PROVISIONED`: Record created (by admin or auto-on-first-register), no credential issued
- `ACTIVE`: Credential issued, installation can register instances
- `DISABLED`: Installation paused; existing instances can heartbeat but no new registrations
- `REVOKED`: Installation permanently removed; all credentials revoked, instances stopped

**Transitions**:
- `PROVISIONED` → `ACTIVE`: Admin issues first credential (or auto on first successful register)
- `ACTIVE` → `DISABLED`: Admin action (maintenance, investigation)
- `DISABLED` → `ACTIVE`: Admin action
- `ACTIVE`/`DISABLED` → `REVOKED`: Admin action (decommission, compromise)
- `REVOKED` is terminal

### 3. Instance Lifecycle

**Table**: `agent_instances`

```sql
CREATE TABLE agent_instances (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    installation_id     UUID NOT NULL REFERENCES agent_installations(id) ON DELETE CASCADE,
    credential_id       UUID NOT NULL REFERENCES agent_credentials(id) ON DELETE CASCADE,
    host_fingerprint    CHAR(64) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING', 'STOPPED')),
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_heartbeat_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    stopped_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    
    -- At most one RUNNING instance per installation
    UNIQUE (installation_id) WHERE status = 'RUNNING'
);
```

**States**:
- `RUNNING`: Instance actively sending heartbeats/telemetry
- `STOPPED`: Instance gracefully stopped or timed out

**Transitions**:
- (none) → `RUNNING`: Explicit registration via `POST /api/v1/agents/instance/register`
- `RUNNING` → `STOPPED`: 
  - Graceful: Agent calls `DELETE /api/v1/agents/instance/{instance_id}` (canonical stop endpoint)
  - Timeout: Heartbeat missing > `heartbeat_timeout_seconds` (default 120s) → background reconciler marks `STOPPED`
  - Crash: Process dies without stop call → timeout detection
- `STOPPED` → (new `RUNNING`): New registration creates NEW instance row (different `agent_instance_id`)

### 4. Explicit Instance Registration

**Endpoint**: `POST /api/v1/agents/instance/register` (machine auth, scope `agent:register`)

**Request**:
```json
{
  "installation_id": "uuid",
  "host_fingerprint": "sha256-hex",
  "agent_version": "1.2.3",
  "metadata": { "pid": 1234, "start_time": "2026-09-02T10:00:00Z" }
}
```

**Response**:
```json
{
  "instance_id": "uuid",
  "heartbeat_interval_seconds": 30,
  "heartbeat_timeout_seconds": 120,
  "telemetry_endpoint": "https://gateway/api/v1/telemetry/ingest"
}
```

**Registration Logic**:
1. Validate machine token: `installation_id` matches request, `credential_id` (from `sub`) is `ACTIVE` and belongs to `installation_id`.
2. Verify `host_fingerprint` matches `agent_installations.host_fingerprint` (anti-cloning).
3. Check `UNIQUE (installation_id) WHERE status = 'RUNNING'` — if exists:
   - If existing instance `last_heartbeat_at < now() - timeout`: mark existing `STOPPED`, allow new registration
   - Else: reject with `409 Conflict` (instance already running)
4. Create `agent_instances` row with `status = 'RUNNING'`, `credential_id` from token, `host_fingerprint` from request (copied for audit).
5. Return `instance_id` and heartbeat config

### 5.1 Graceful Stop Endpoint

**Endpoint**: `DELETE /api/v1/agents/instance/{instance_id}` (machine auth, scope `telemetry:heartbeat`)

**Authorization**: Token's `instance_id` must match path parameter. Token's `credential_id` must match `agent_instances.credential_id`. Token's `tenant_id` must match.

**State Transition**: 
- If instance `status == 'RUNNING'` → set `status = 'STOPPED'`, `stopped_at = now()`
- If instance already `STOPPED` → idempotent success (200 OK, no state change)
- If instance not found → 404

**Response**: 200 OK with `{ "instance_id": "uuid", "status": "STOPPED", "stopped_at": "timestamp" }`

---

### 5.2 Heartbeat Protocol

**Endpoint**: `POST /api/v1/agents/instance/heartbeat` (machine auth, scope `telemetry:heartbeat`)

**Request**:
```json
{
  "instance_id": "uuid",
  "status": "RUNNING",
  "metadata": { "cpu": 45, "memory": 60 }
}
```

**Logic**:
1. Validate machine token: `instance_id` matches token's `instance_id`, `credential_id` (from `sub`) matches `agent_instances.credential_id`, `installation_id` matches `agent_instances.installation_id`, `tenant_id` matches. All four IDs must belong to the same tenant.
2. Validate `agent_instances.status == 'RUNNING'`. If `STOPPED` → reject (401).
3. Validate `agent_installations.status == 'ACTIVE'`. If not `ACTIVE` → reject (401).
4. Validate `agent_credentials.status == 'ACTIVE'`. If not `ACTIVE` → reject (401).
5. Update `agent_instances.last_heartbeat_at = now()`
6. Update `agent_installations.last_seen_at = now()`
7. Return current config (may include updated heartbeat interval)

### 6. At-Most-One-Active-Instance Invariant

Enforced by **database constraint**:
```sql
CREATE UNIQUE INDEX uq_agent_instance_active
    ON agent_instances (installation_id)
    WHERE status = 'RUNNING';
```

This is the **single source of truth**. Application logic checks before insert, but the DB constraint is the ultimate guarantee against races.

### 7. Host Fingerprint

**Platform-neutral fingerprint contract** (covers Linux, Windows, VMware):

The host fingerprint is a SHA-256 hash of a canonical JSON object containing stable host identifiers. The exact components vary by platform but the contract is uniform:

```json
{
  "platform": "linux|windows|vmware",
  "machine_id": "string",           // Linux: /etc/machine-id; Windows: HKLM\\SOFTWARE\\Microsoft\\Cryptography\\MachineGuid; VMware: SMBIOS UUID
  "system_uuid": "string",          // Linux: DMI product_uuid; Windows: Win32_ComputerSystemProduct.UUID; VMware: VM UUID
  "mac_addresses": ["sorted", "list", "of", "permanent", "macs"],  // only physical NICs, sorted lexicographically
  "cpu_serials": ["sorted", "list", "of", "cpu", "serials"]       // if available; empty array if not
}
```

**Canonicalization rules**:
- All string values trimmed, lowercase for MAC addresses
- Arrays sorted lexicographically (UTF-8)
- Missing/unavailable components → empty string (for scalars) or empty array (for arrays) — **never omitted**
- JSON serialized with: sorted keys, compact separators `(",", ":")`, UTF-8, no whitespace
- Hash: `SHA-256(canonical_json).hexdigest()` → 64 hex chars

**Behavior**:
- **Stability across reboot**: `machine_id`, `system_uuid`, `mac_addresses`, `cpu_serials` are stable across reboots. `boot_id` (Linux) is **excluded** — it changes on every boot and would break fingerprint stability.
- **VM clone detection**: Cloned VMs share `machine_id`/`system_uuid` but typically get new MAC addresses. The fingerprint will differ if MAC addresses change. If MACs are also cloned (full clone), fingerprint matches → registration rejected (cloned VM detected).
- **Component unavailable**: If a component cannot be read (e.g., no CPU serial on Windows), use empty string/array. The fingerprint is still computed from available components.
- **Minimum viable fingerprint**: At least `machine_id` OR `system_uuid` must be non-empty. If both unavailable → installation fails (agent cannot establish identity).

**When captured**:
- **Installation provisioning**: Fingerprint computed once at installation time (first registration or admin create). Stored in `agent_installations.host_fingerprint`.
- **Instance registration**: Fingerprint re-computed and verified against `agent_installations.host_fingerprint`. Mismatch → reject (409).
- **Heartbeat**: Fingerprint NOT re-verified (redundant; instance already bound to installation).

**Stored in**: `agent_installations.host_fingerprint` and `agent_instances.host_fingerprint` (copied at registration for audit trail).

### 8. Restart / Reinstall / Upgrade / Re-enroll Semantics

| Operation | Installation | Instance | Credential |
|-----------|--------------|----------|------------|
| **Restart** (agent process restart) | Same | NEW `instance_id` (new registration) | Same |
| **Upgrade** (agent binary update) | Same (version updated) | NEW `instance_id` | Same |
| **Reinstall** (agent removed + reinstalled) | NEW `installation_id` | NEW `instance_id` | NEW `credential_id` |
| **Re-enroll** (credential rotation) | Same | Same or NEW | NEW `credential_id` (old revoked) |

**Key principle**: `installation_id` persists across restarts/upgrades. Only full reinstall creates new installation. `agent_instance_id` is ALWAYS new on process start (registration).

### 9. Crash Recovery

- Agent crashes → no stop call → `last_heartbeat_at` stops updating
- Background reconciler (runs every 60s, configurable via `RECONCILER_INTERVAL_SECONDS`):
  - Finds `RUNNING` instances with `last_heartbeat_at < now() - heartbeat_timeout_seconds`
  - Updates them to `STOPPED`, sets `stopped_at = now()`
- Next agent start → new registration → new `agent_instance_id` → new row
- Old `STOPPED` instance row preserved for audit trail

**Reconciler/Heartbeat Race Behavior**: The reconciler runs every 60s (default). Heartbeat interval is 30s (default). Timeout is 120s (default). An instance is only marked `STOPPED` if `last_heartbeat_at < now() - 120s`. Since heartbeats arrive every 30s, a healthy instance's `last_heartbeat_at` is always within ~30s of `now()`. The reconciler will only mark an instance `STOPPED` if it has genuinely missed 4+ consecutive heartbeats. There is no race where a healthy instance is incorrectly marked `STOPPED`. If an agent sends a heartbeat concurrently with the reconciler checking, the heartbeat updates `last_heartbeat_at` and the reconciler's query (using the committed value) will see a recent timestamp and skip the instance.

### 10. Host State (Derived)

`servers.status` is **derived**, not directly set:
- `ONLINE`: At least one `RUNNING` instance on this server, heartbeat recent
- `OFFLINE`: No `RUNNING` instances, but installation(s) exist
- `UNKNOWN`: No installations registered
- `DECOMMISSIONED`: All installations `REVOKED`

Derivation runs in background reconciler or on-demand for UI.

## Alternatives Considered

### Implicit Instance (No Registration)
- Rejected: No ownership, no at-most-one enforcement, no crash detection

### Single Instance Row Updated In-Place
- Rejected: Loses restart history; violates append-only audit trail for instance lifecycle

### Heartbeat-Only (No Explicit Register)
- Rejected: Race condition on startup; cannot distinguish "never started" from "crashed"

### Instance ID = Installation ID
- Rejected: Cannot track multiple restarts; loses provenance chain

## Architectural Invariants

1. **Explicit registration**: Every running instance has a row in `agent_instances` with `status = 'RUNNING'`
2. **At-most-one**: `UNIQUE (installation_id) WHERE status = 'RUNNING'` enforced by DB
3. **Instance identity is ephemeral**: New `agent_instance_id` on every registration
4. **Installation identity is persistent**: Survives restarts, upgrades, credential rotation
5. **Host fingerprint binding**: Prevents cloned VM from registering as existing installation
6. **Credential binding**: Instance token carries `credential_id` linking to installation
7. **Heartbeat timeout = STOPPED**: No manual intervention needed for crash detection
8. **Derived host state**: `servers.status` computed from instance heartbeats

## Security / Multi-tenancy

- All tables have `tenant_id` with FK to `tenants`
- `UNIQUE (tenant_id, server_id, agent_type)` prevents cross-tenant installation collision
- Machine token carries `tenant_id`, `installation_id`, `instance_id`, `credential_id`
- Registration validates all four IDs match and belong to same tenant
- Admin actions (disable, revoke) require human auth (admin/superadmin role)

## Failure / Recovery Semantics

| Scenario | Detection | Recovery |
|----------|-----------|----------|
| Agent graceful stop | `POST /stop` | Instance → `STOPPED`, stopped_at set |
| Agent crash | Heartbeat timeout (120s default) | Reconciler → `STOPPED` |
| Agent restart | New registration | New instance row, old `STOPPED` |
| Cloned VM | Host fingerprint mismatch | Registration rejected (409) |
| Credential stolen | Revoke credential | All tokens invalidated, new credential issued |
| Network partition | Heartbeat timeout | Instance → `STOPPED`; re-register on recovery |

## Consequences

### Benefits
- Full audit trail of agent lifecycle
- At-most-one guarantee at DB level
- Clone detection via host fingerprint
- Clear semantics for restart/upgrade/reinstall
- Operational visibility (which instances running, when last heartbeat)

### Costs
- Two new tables: `agent_installations`, `agent_instances`
- Background reconciler for heartbeat timeout
- Registration endpoint in Gateway
- Agent must implement register/heartbeat/stop logic

### Complexity Introduced
- Installation ↔ Credential ↔ Instance relationship management
- Host fingerprint computation and verification
- Reconciler for timeout detection
- State machine with DB-enforced constraints

## Implementation Constraints

### What H4.0 Must Implement
1. `agent_installations` table + indexes + triggers
2. `agent_instances` table + partial UNIQUE index + triggers
3. `POST /api/v1/agents/instance/register` endpoint
4. `POST /api/v1/agents/instance/heartbeat` endpoint
5. `DELETE /api/v1/agents/instance/{instance_id}` endpoint (canonical stop)
6. Background reconciler (heartbeat timeout → STOPPED; interval configurable)
7. Host fingerprint computation (agent-side + server-side verification; platform-neutral)
8. Admin endpoints: create installation, issue credential, disable/revoke installation

### What Must NOT Be Implemented
- Automatic instance cleanup (STOPPED rows retained for audit)
- Complex host state machine (derived only)
- Agent auto-update (out of scope)
- Multi-instance-per-installation (explicitly forbidden by invariant)

## Test Requirements

Before considering this decision implemented, the following tests must pass:

1. **Registration creates instance**: Valid token + fingerprint → 201 with instance_id
2. **At-most-one enforced**: Second registration while first RUNNING → 409 Conflict
3. **Timeout detection**: Heartbeat stops → 120s → reconciler marks STOPPED
4. **Restart = new instance**: Stop + register → new agent_instance_id, old STOPPED
5. **Fingerprint verification**: Mismatch → 409 Conflict (cloned VM rejected)
6. **Credential binding**: Token credential_id must match installation's active credential
7. **Tenant isolation**: Installation in tenant A cannot register instance in tenant B
8. **Status transitions**: PROVISIONED→ACTIVE→DISABLED→REVOKED valid; REVOKED terminal
9. **Host state derivation**: ONLINE/OFFLINE/UNKNOWN/DECOMMISSIONED matches instance states
10. **Concurrent registration race**: Two simultaneous register requests → one succeeds, one 409 (DB constraint)
11. **Heartbeat validates full binding**: Token with valid instance_id but mismatched credential_id/installation_id/tenant_id → 401
12. **Heartbeat rejects STOPPED instance**: Valid token but instance status=STOPPED → 401
13. **Stop endpoint**: DELETE /agents/instance/{id} transitions RUNNING→STOPPED; idempotent on STOPPED; 404 on not found
14. **Platform-neutral fingerprint**: Linux, Windows, VMware agents produce valid fingerprints; missing components handled gracefully; boot_id excluded
15. **Reconciler race**: Healthy instance with concurrent heartbeat + reconciler check → not marked STOPPED

## Dependencies

- **ADR-0001**: Company OS is the Brain
- **ADR-0002**: COS-Monitor is the Product
- **ADR-0004**: Transactional Outbox (telemetry ingestion uses instance_id)
- **ADR-0005**: Machine Authentication (token carries installation_id, instance_id, credential_id)
- **ADR-0007**: Telemetry Contract (host_fingerprint, batch_id, payload_hash)

---

*This ADR resolves CR-4 (Agent Instance Lifecycle) from the H4 Critical Architectural Gate.*