# Architecture Decision Record 0007

Title: Telemetry Contract & Integrity — Batch Identity, Payload Hash, Deterministic Observation ID

Status: ACCEPTED
Approved: 2026-09-03
Approved-by: Human Review

Date: 2026-09-02

---

## Context

The current telemetry ingestion has no formal contract:
- Agents publish Observations directly to Redis with no batching concept
- No payload integrity verification
- No idempotency key at ingestion layer
- Observation IDs are random UUIDs (not deterministic)
- No tenant-aware relationships between telemetry entities

The H4 Critical Gate requires a formal telemetry contract covering:
- Batch identity (`batch_id`)
- Payload integrity (`payload_hash` via SHA-256)
- Duplicate vs conflict semantics
- Deterministic Observation identity
- Tenant-aware relationships
- Immutable vs mutable data classification

## Decision

### 1. Telemetry Ingestion Contract

**Endpoint**: `POST /api/v1/telemetry/ingest` (machine auth, scope `telemetry:ingest`)

**Request** (fields `installation_id`, `instance_id`, `credential_id` are from machine token, not request body):
```json
{
  "batch_id": "uuid",                    // client-generated, unique per ingestion attempt
  "captured_at": "2026-09-02T10:00:00Z", // batch capture timestamp (server validates ±5min)
  "samples": [
    {
      "sequence": 1,                     // 1-based, monotonic within batch
      "fact_type": "cpu_utilization_percent",
      "fact_value": { "value": 45.2 },
      "unit": "percent",
      "labels": { "core": "0" }          // optional, free-form
    },
    {
      "sequence": 2,
      "fact_type": "memory_usage",
      "fact_value": { "free_bytes": 1073741824, "total_bytes": 8589934592, "used_bytes": 7516192768 },
      "unit": "bytes",
      "labels": {}
    }
  ]
}
```

**Machine token provides** (validated by middleware, not in request body):
- `tenant_id`
- `installation_id`
- `instance_id`
- `credential_id` (from `sub` claim)

**Response (202 Accepted)**:
```json
{
  "batch_id": "uuid",
  "status": "accepted",
  "observation_ids": [
    "uuid",  // deterministic, one per sample
    "uuid"
  ],
  "ingested_at": "2026-09-02T10:00:01Z"
}
```

**Response (409 Conflict)**:
```json
{
  "error": "payload_conflict",
  "message": "batch_id already exists with different payload",
  "existing_batch_id": "uuid",
  "existing_payload_hash": "sha256-hex"
}
```

### 2. Canonical Payload Hashing

**Payload to hash**: The entire request body **excluding** `batch_id` (since it's the idempotency key), canonically serialized per the exact wire contract below.

**Canonical JSON Algorithm** (language-agnostic, produces identical SHA-256 across implementations):

1. **Parse** request body as JSON.
2. **Remove** the `batch_id` field entirely (it is the idempotency key, not part of payload).
3. **For each field in the payload object**:
   - **Strings**: Keep as-is. `captured_at` is hashed as the exact ISO 8601 string from the request (e.g., `"2026-09-02T10:00:00Z"`). No re-formatting, no timezone normalization.
   - **Numbers (integers/floats)**: Serialize using the shortest decimal representation that round-trips exactly (equivalent to Python `repr()` or JSON `JSON.stringify()` in JavaScript). Examples: `45.2` → `"45.2"`, `45.0` → `"45"`, `1e6` → `"1000000"`, `0.0001` → `"0.0001"`. No trailing zeros, no scientific notation unless necessary for precision.
   - **Booleans**: `true` / `false` (lowercase).
   - **Null**: `null` (lowercase).
   - **Arrays**: Elements in order (sequences are ordered by `sequence` field which is 1-based monotonic). Empty arrays → `[]`.
   - **Objects**: Keys sorted lexicographically (UTF-8 byte order).
4. **Serialize** the entire payload object with:
   - Keys sorted lexicographically
   - No whitespace: separators `(",", ":")`
   - UTF-8 encoding
   - No trailing newline
5. **Hash**: `SHA-256(canonical_bytes).hexdigest()` → 64 lowercase hex characters.

**Reference Python implementation**:
```python
import json
import hashlib

def canonical_payload(request_body: dict) -> bytes:
    """Deterministic serialization for hashing. Language-agnostic contract."""
    # Remove batch_id (idempotency key)
    payload = {k: v for k, v in request_body.items() if k != "batch_id"}
    
    def serialize_value(v):
        if isinstance(v, float):
            # Shortest round-tripping representation
            # Python's repr() does this correctly for IEEE 754
            return repr(v)
        elif isinstance(v, dict):
            # Recursively serialize with sorted keys
            return "{" + ",".join(f"{json.dumps(k)}:{serialize_value(v)}" for k in sorted(v.keys())) + "}"
        elif isinstance(v, list):
            return "[" + ",".join(serialize_value(item) for item in v) + "]"
        else:
            # str, int, bool, None → json.dumps handles correctly
            return json.dumps(v, separators=(",", ":"), ensure_ascii=False)
    
    # Top-level keys sorted
    parts = [f"{json.dumps(k)}:{serialize_value(v)}" for k in sorted(payload.keys())]
    canonical = "{" + ",".join(parts) + "}"
    return canonical.encode("utf-8")

payload_hash = hashlib.sha256(canonical_payload(request_body)).hexdigest()
```

**What is hashed** (after batch_id removal):
- `installation_id` (string UUID)
- `instance_id` (string UUID)
- `credential_id` (string UUID, from token sub)
- `captured_at` (exact ISO 8601 string from request, e.g., `"2026-09-02T10:00:00Z"`)
- `samples[]` array in order (each element: `sequence` int, `fact_type` string, `fact_value` object, `unit` string, `labels` object)

**What is NOT hashed**:
- `batch_id` (idempotency key)
- HTTP headers, auth tokens, server-added timestamps

### 3. Idempotency Semantics

| Scenario | Behavior | HTTP Status |
|----------|----------|-------------|
| New `batch_id` | Insert batch + outbox rows | 202 Accepted |
| Same `batch_id` + **same payload** (hash matches) | No-op, return existing `observation_ids` | 202 Accepted |
| Same `batch_id` + **different payload** (hash differs) | Reject, no new rows | 409 Conflict |

**Database enforcement**:
```sql
-- Parent tables require UNIQUE(tenant_id, id) for composite FK targets
ALTER TABLE agent_installations ADD CONSTRAINT uq_agent_installations_tenant_id UNIQUE (tenant_id, id);
ALTER TABLE metric_batches ADD CONSTRAINT uq_metric_batches_tenant_id UNIQUE (tenant_id, id);

CREATE TABLE metric_batches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    installation_id UUID NOT NULL,
    instance_id     UUID NOT NULL,
    credential_id   UUID NOT NULL,      -- credential that authenticated this batch
    batch_id        UUID NOT NULL,      -- client-provided idempotency key
    payload_hash    CHAR(64) NOT NULL,  -- SHA-256 of canonical payload
    captured_at     TIMESTAMPTZ NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    sample_count    INTEGER NOT NULL,
    
    UNIQUE (tenant_id, installation_id, batch_id, payload_hash)
);

-- Composite FKs (now compatible with parent table UNIQUE constraints)
ALTER TABLE metric_batches
    ADD CONSTRAINT fk_metric_batches_installation
    FOREIGN KEY (tenant_id, installation_id)
    REFERENCES agent_installations(tenant_id, id)
    ON DELETE CASCADE;

CREATE TABLE metric_samples (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    batch_id        UUID NOT NULL,
    sequence        INTEGER NOT NULL,
    fact_type       VARCHAR(100) NOT NULL,
    fact_value      JSONB NOT NULL,
    unit            VARCHAR(20) NOT NULL,
    labels          JSONB DEFAULT '{}',
    
    UNIQUE (tenant_id, batch_id, sequence)
);

ALTER TABLE metric_samples
    ADD CONSTRAINT fk_metric_samples_batch
    FOREIGN KEY (tenant_id, batch_id)
    REFERENCES metric_batches(tenant_id, id)
    ON DELETE CASCADE;
```

### 4. Deterministic Observation ID

Each sample in a batch becomes one Observation. Observation ID is **deterministic**:

```
observation_id = UUIDv5(
    namespace = UUID("6ba7b810-9dad-11d1-80b4-00c04fd430c8"),  # fixed namespace
    name = f"{tenant_id}:{installation_id}:{batch_id}:{sequence}:{fact_type}"
)
```

**Properties**:
- Same input → same Observation ID (enables idempotent Collector dedup)
- Collision-resistant (UUIDv5 + SHA-1 namespace)
- No central ID allocation needed
- Traceable: can reconstruct `tenant_id`, `installation_id`, `batch_id`, `sequence`, `fact_type` from ID (with namespace)

### 5. Tenant-Aware Relationships

All telemetry entities are explicitly tenant-scoped with composite keys where needed:

| Entity | Tenant Scoping | Key Relationships |
|--------|----------------|-------------------|
| `metric_batches` | `tenant_id` + `installation_id` + `credential_id` | FK to `agent_installations(tenant_id, id)` |
| `metric_samples` | `tenant_id` + `batch_id` | FK to `metric_batches(tenant_id, id)` |
| `observation_outbox` | `tenant_id` + `installation_id` + `credential_id` | FK to `agent_installations(tenant_id, id)` |
| `observations` | `tenant_id` + `source_id` | `source_id` = `servers.id` (tenant-scoped) |

**Composite FKs** (enabled by `UNIQUE(tenant_id, id)` on parent tables):
```sql
-- metric_batches → agent_installations
ALTER TABLE metric_batches
    ADD CONSTRAINT fk_metric_batches_installation
    FOREIGN KEY (tenant_id, installation_id)
    REFERENCES agent_installations(tenant_id, id)
    ON DELETE CASCADE;

-- metric_samples → metric_batches  
ALTER TABLE metric_samples
    ADD CONSTRAINT fk_metric_samples_batch
    FOREIGN KEY (tenant_id, batch_id)
    REFERENCES metric_batches(tenant_id, id)
    ON DELETE CASCADE;

-- observation_outbox → agent_installations
ALTER TABLE observation_outbox
    ADD CONSTRAINT fk_observation_outbox_installation
    FOREIGN KEY (tenant_id, installation_id)
    REFERENCES agent_installations(tenant_id, id)
    ON DELETE CASCADE;
```

**Source_id Resolution** (critical for Observation provenance):
The ingestion endpoint **MUST** resolve `source_id` as follows:
1. From machine token: extract `installation_id`
2. Query `agent_installations` for that `installation_id` (validated tenant match)
3. Read `server_id` from the installation row
4. Use `server_id` as `Observation.source_id` (which equals `servers.id`)
5. The `host_fingerprint` in the installation row provides clone-detection; the `server_id` provides the authoritative host identity for provenance chain: `host_fingerprint` → `servers.id` → `observations.source_id`.

**No client-supplied source_id**: The ingestion endpoint ignores any `source_id` in the request (none expected). The machine token does not carry `server_id` — it is resolved server-side from the installation record. This ensures tenant-scoped integrity and prevents spoofing.

### 6. Immutable vs Mutable Classification

| Table | Mutability | Rationale |
|-------|------------|-----------|
| `metric_batches` | **IMMUTABLE** (append-only) | Audit trail of ingestion; trigger blocks UPDATE/DELETE |
| `metric_samples` | **IMMUTABLE** (append-only) | Raw telemetry never modified; trigger blocks UPDATE/DELETE |
| `observation_outbox` | **MUTABLE (lifecycle only)** | `status`, `attempts`, `next_attempt_at`, `last_error`, `published_at` change; `observation`, `payload_hash`, `credential_id`, `installation_id`, `batch_id` immutable |
| `observations` | **IMMUTABLE** (P1) | Existing trigger blocks UPDATE/DELETE |
| `agent_installations` | **MUTABLE (lifecycle)** | `status`, `last_seen_at`, `agent_version`, `capabilities_json` mutable; identity immutable |
| `agent_instances` | **MUTABLE (lifecycle)** | `status`, `last_heartbeat_at`, `stopped_at` mutable; identity immutable |
| `agent_credentials` | **MUTABLE (lifecycle)** | `status`, `revoked_at` mutable; identity immutable |

**Append-only triggers** on `metric_batches`, `metric_samples`, `observations` (existing), `observation_outbox` (content columns only — see ADR-0004 for trigger definition).

### 7. Quality Class Assignment (Declarative)

`quality_class` is **not** computed by querying the cognitive layer. It is assigned at ingestion from `agent_installations.capabilities_json`:

```json
// agent_installations.capabilities_json example
{
  "quality_mapping": {
    "cpu_utilization_percent": "Q1",
    "memory_usage": "Q1",
    "disk_usage": "Q2",
    "network_throughput": "Q3",
    "process_count": "Q4"
  },
  "default_quality_class": "Q3"
}
```

**Ingestion logic**:
1. Look up `installation_id` → `capabilities_json`
2. For each sample: `quality_class = quality_mapping.get(fact_type, default_quality_class)`
3. Embed in Observation payload written to outbox

**No synchronous cognitive query**. The mapping is static configuration managed by admin.

### 8. Provenance Chain

```
metric_batches (batch_id, payload_hash, credential_id)
    ↓
metric_samples (sequence, fact_type, ...)
    ↓
observation_outbox (deterministic observation_id, quality_class from capabilities_json, credential_id)
    ↓
Redis Streams (ObservationBus)
    ↓
Collector → observations table (idempotent on observation_id + captured_at)
    ↓
Evidence → Context → Pattern → Anomaly → Hypothesis → ...
```

**Traceability**: Every Observation traces back to:
- `batch_id` (client idempotency key)
- `installation_id` (agent identity)
- `instance_id` (specific run)
- `credential_id` (authenticating credential, immutable per batch)
- `payload_hash` (integrity)
- `sequence` (order within batch)

## Alternatives Considered

### Random Observation IDs
- Rejected: Cannot deduplicate at Collector; requires distributed ID coordination

### Payload Hash Including batch_id
- Rejected: Would make re-ingestion with same payload but different batch_id create duplicate Observations

### Server-Generated batch_id
- Rejected: Client needs to know idempotency key for retry; client-generated allows deterministic retry

### Per-Sample Hash Instead of Batch Hash
- Rejected: Batch is the atomic unit of ingestion; per-sample hashes add complexity without benefit

### Quality Class from Cognitive Layer
- Rejected: Violates Cognitive Boundary (ingestion → perception); creates runtime dependency; latency

## Architectural Invariants

1. **Batch is atomic unit**: All samples in a batch succeed or fail together
2. **Payload hash is integrity seal**: Any modification → different hash → 409 Conflict
3. **Deterministic Observation ID**: Same telemetry → same Observation ID → idempotent end-to-end
4. **Tenant scoping at every level**: No cross-tenant references possible
5. **Immutable raw telemetry**: `metric_batches`, `metric_samples` never updated
6. **Quality class from static config**: No cognitive layer dependency at ingestion
7. **Provenance chain unbroken**: batch → sample → observation → evidence → ...

## Security / Multi-tenancy

- Machine token `tenant_id` must match `installation_id`'s tenant
- `UNIQUE (tenant_id, installation_id, batch_id, payload_hash)` prevents cross-tenant collision
- `payload_hash` prevents payload tampering in transit (agent → gateway)
- `captured_at` validated server-side (±5min) to prevent timestamp manipulation
- `sequence` monotonic within batch prevents reordering attacks

## Failure / Recovery Semantics

| Failure | Behavior |
|---------|----------|
| Gateway crash during ingestion TX | Rollback → nothing persisted → client retries same batch_id |
| Duplicate network packet | Same batch_id + hash → 202, no duplicate rows |
| Corrupted payload in transit | Hash mismatch → 400 Bad Request (before DB) |
| Collector crash after persist | Observation in PG, ack sent → no redelivery |
| Collector crash before persist | Message unacked → redelivery → dedup via observation_id |
| Replay attack (old batch) | `captured_at` outside window → 400; or duplicate → 202 idempotent |

## Consequences

### Benefits
- End-to-end idempotency without distributed coordination
- Payload integrity guaranteed by SHA-256
- Deterministic IDs enable exactly-once semantics at Observation level
- Audit trail of every ingestion attempt
- Quality classification without cognitive coupling

### Costs
- Client must generate and track `batch_id`
- Canonical JSON serialization must match exactly (agent ↔ gateway)
- `metric_batches`/`metric_samples` tables add storage
- Admin must maintain `capabilities_json` per installation

### Complexity Introduced
- Canonical serialization for hashing (must be identical in agent and gateway)
- UUIDv5 namespace management
- Composite FKs and UNIQUE indexes
- Idempotency conflict handling (409 vs 202)

## Implementation Constraints

### What H4.0 Must Implement
1. `metric_batches` table + `metric_samples` table + triggers + `UNIQUE(tenant_id, id)` on parent tables
2. `POST /api/v1/telemetry/ingest` endpoint with full contract
3. Canonical payload serialization + SHA-256 hashing (shared library; exact algorithm per §2)
4. Deterministic Observation ID generator (UUIDv5)
5. Idempotency logic: 202 same hash, 409 different hash
6. Quality class resolution from `capabilities_json`
7. Integration with `observation_outbox` (ADR-0004) and machine auth (ADR-0005)
8. Source_id resolution: `installation_id` → `agent_installations.server_id` → `servers.id` → `Observation.source_id`
9. Composite FKs enabled by `UNIQUE(tenant_id, id)` on `agent_installations` and `metric_batches`

### What Must NOT Be Implemented
- Server-generated `batch_id`
- Per-sample hashing
- Cognitive layer query for quality class
- Automatic batch retries (client responsibility)
- Complex batch aggregation (MVP: one batch = one ingest call)

## Test Requirements

Before considering this decision implemented, the following tests must pass:

1. **Idempotent ingest**: Same batch_id + same payload → 202, single metric_batches row
2. **Conflict detection**: Same batch_id + different payload → 409, no new row
3. **Deterministic Observation ID**: Same input → identical observation_ids across requests
4. **Payload hash integrity**: Modify one byte → different hash → 409
5. **Tenant isolation**: Token for tenant A cannot ingest for tenant B installation
6. **Quality class from config**: Ingestion reads capabilities_json, not cognitive layer
7. **Composite FK enforcement**: Orphan batch rejected (installation_id not found)
8. **Immutability triggers**: UPDATE/DELETE on metric_batches/metric_samples blocked
9. **captured_at validation**: > 5min drift → 400
10. **Sequence monotonicity**: Non-monotonic sequence → 400
11. **Canonical hash determinism**: Same logical payload → identical SHA-256 across Python/Go/Rust implementations (test vectors provided)
12. **Float serialization**: `45.0` → `"45"`, `45.2` → `"45.2"`, `1e6` → `"1000000"` — round-tripping representation
13. **captured_at exact string**: Request `"2026-09-02T10:00:00Z"` hashes identically; no re-formatting
14. **credential_id in provenance**: metric_batches and observation_outbox include credential_id from token sub; immutable across rotation
15. **Source_id resolution**: Ingestion resolves installation_id → server_id → source_id; client-supplied source_id ignored
16. **Composite FKs**: metric_batches → agent_installations(tenant_id, id) enforced; metric_samples → metric_batches(tenant_id, id) enforced

## Dependencies

- **ADR-0001**: Company OS is the Brain
- **ADR-0002**: COS-Monitor is the Product
- **ADR-0004**: Transactional Outbox (outbox rows created in same TX as metric_batches)
- **ADR-0005**: Machine Authentication (token validates installation/instance)
- **ADR-0006**: Agent Identity & Instance Lifecycle (installation_id, instance_id, host_fingerprint)

---

*This ADR resolves CR-3 (Collector Contract), CR-1 (PostgreSQL ↔ Redis idempotency), and the 9th Mandatory Decision (Payload Hash) from the H4 Critical Architectural Gate.*