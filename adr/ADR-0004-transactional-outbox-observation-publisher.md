# Architecture Decision Record 0004

Title: Transactional Outbox + Observation Publisher for Telemetry Ingestion

Status: ACCEPTED
Approved: 2026-09-03
Approved-by: Human Review

Date: 2026-09-02

---

## Context

The current architecture has agents (Linux, Windows, VMware) publishing Observations directly to Redis Streams via `ObservationBus.publish()`. This bypasses PostgreSQL transactionality and creates several critical issues identified in the H4 Critical Architectural Gate:

- **No atomicity**: Telemetry ingestion and Observation persistence are not atomic. If the gateway crashes after writing to Redis but before the Collector persists to PostgreSQL, data is lost or duplicated.
- **No tenant isolation at ingestion**: The current `ObservationBus` does not enforce tenant boundaries at publish time.
- **No idempotency guarantee**: Duplicate publications create duplicate Observations because the Collector deduplicates only at read time (`observation_exists`), not at the source.
- **Cognitive Boundary violation risk**: Direct Redis publishing couples the agent (external capability) to the Observation Bus without an explicit transformation layer that assigns `quality_class` based on declarative agent metadata.

The H4 Critical Gate (CR-1) requires a Transactional Outbox pattern where:
- PostgreSQL is the transactional boundary for telemetry ingestion
- An outbox table stores Observations atomically with the telemetry batch
- A decoupled publisher reads the outbox and pushes to Redis Streams
- At-least-once delivery from outbox → Redis with idempotent downstream consumption
- Deterministic Observation ID closes the duplication loop

## Decision

### 1. Transactional Outbox Table

Create `observation_outbox` table in PostgreSQL:

```sql
CREATE TABLE observation_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    installation_id UUID NOT NULL,
    batch_id        UUID NOT NULL,
    credential_id   UUID NOT NULL,      -- credential that authenticated this batch
    payload_hash    CHAR(64) NOT NULL,  -- SHA-256 of canonical payload
    observation     JSONB NOT NULL,     -- full Observation payload (matches observations table)
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'published', 'failed', 'dead_letter')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error      TEXT,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX uq_observation_outbox_idempotent
    ON observation_outbox (tenant_id, installation_id, batch_id, payload_hash);

CREATE INDEX idx_observation_outbox_publish
    ON observation_outbox (status, next_attempt_at)
    WHERE status IN ('pending', 'failed');

-- Content immutability: only lifecycle fields may change after INSERT
CREATE OR REPLACE FUNCTION prevent_outbox_content_update()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.installation_id IS DISTINCT FROM OLD.installation_id
       OR NEW.batch_id IS DISTINCT FROM OLD.batch_id
       OR NEW.credential_id IS DISTINCT FROM OLD.credential_id
       OR NEW.payload_hash IS DISTINCT FROM OLD.payload_hash
       OR NEW.observation IS DISTINCT FROM OLD.observation
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Outbox content is immutable. Only lifecycle fields (status, attempts, next_attempt_at, last_error, published_at) may change.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER outbox_content_immutable_trigger
    BEFORE UPDATE ON observation_outbox
    FOR EACH ROW EXECUTE FUNCTION prevent_outbox_content_update();
```

### 2. Ingestion Endpoint

The Gateway exposes `POST /api/v1/telemetry/ingest` (machine-auth protected) that:
- Validates machine credentials (see ADR-0005): verifies `credential_id` (sub), `installation_id`, `instance_id`, `tenant_id`, scopes
- Resolves `server_id` from the persisted `agent_installations` record: `installation_id` → `agent_installations.server_id` → `servers.id`. This `server_id` becomes the Observation `source_id`. The ingestion endpoint **MUST NOT** use `installation_id` as `source_id`, **MUST NOT** trust client-supplied `server_id`/`source_id`, and **MUST NOT** duplicate `server_id` in the machine token unless architecturally required (it is not for MVP).
- Validates tenant-scoped relationship: the `agent_installations.tenant_id` must match the token's `tenant_id`.
- Extracts `credential_id` from token `sub` claim and includes it in `metric_batches` and `observation_outbox` rows for provenance.
- Computes `payload_hash = SHA-256(canonical_json(payload))` per ADR-0007 canonicalization.
- Inserts into `metric_batches`, `metric_samples`, and `observation_outbox` atomically in a single transaction.
- Returns `202 Accepted` with `batch_id`, `observation_ids` (deterministic UUIDs), and `ingested_at`.

### 3. Deterministic Observation ID

Observation ID is computed as:
```
observation_id = UUIDv5(NAMESPACE_OBSERVATION, f"{tenant_id}:{installation_id}:{batch_id}:{sequence_number}:{fact_type}")
```

Where `tenant_id` is from the machine token, `installation_id` from the token (validated against `agent_installations`), `batch_id` from the request, `sequence_number` is the 1-based sample index within the batch, and `fact_type` is from the sample.

This ensures the same telemetry batch always produces the same Observation IDs, enabling idempotency across retries and duplicate publications.

The `source_id` embedded in the Observation payload is the `servers.id` resolved from `agent_installations.server_id` (see Ingestion Endpoint). The publisher does not modify `source_id`; it is set at ingestion.

### 4. Observation Publisher

A background worker (`ObservationPublisher`) runs in the Gateway (or as a separate lightweight service):
- Polls `observation_outbox` for `status = 'pending' OR (status = 'failed' AND next_attempt_at <= now())`
- Claims rows via `SELECT ... FOR UPDATE SKIP LOCKED` (bounded concurrency)
- For each row: publishes to Redis Streams via `ObservationBus.publish()`
- On success: `UPDATE ... SET status = 'published', published_at = now()`
- On failure: increments `attempts`, sets `last_error`, schedules `next_attempt_at` with **exponential backoff**:
  - Base delay: 2 seconds
  - Cap: 60 seconds
  - Jitter: ±25% (randomized per attempt to avoid thundering herd)
  - Formula: `next_attempt_at = now() + min(base * 2^(attempts-1), cap) * (1 + random(-0.25, 0.25))`
  - Max attempts: 5
- After max attempts exceeded: `status = 'dead_letter'` (alert + manual intervention)

**Dead-letter semantics**: A `dead_letter` row means the publisher failed to persist `published_at` after 5 attempts. It does **not** imply the Observation was never published to Redis — duplicate Redis publication is possible and accepted. The deterministic Observation ID + Collector idempotency handles duplicates. For MVP, no automated reconciliation is required; `dead_letter` rows are surfaced for operator review. If an operator confirms the Observation reached Redis (via Collector logs), they may manually mark the row `published`. If not, they may trigger a manual re-publish.

### 5. Delivery Semantics

| Stage | Semantic | Mechanism |
|-------|----------|-----------|
| Telemetry → PostgreSQL + outbox | ATOMIC | Single transaction |
| Outbox → Redis Streams | AT-LEAST-ONCE | Publisher retry + `published_at` |
| Redis → Collector | IDEMPOTENT | Deterministic Observation ID + `observation_exists` check |
| Collector → `observations` table | ATOMIC | Single INSERT per Observation |

**Critical**: The architecture does NOT claim "exactly once". It guarantees:
- No Observation is lost (outbox persists until published)
- No logical duplicate Observation is created (deterministic ID + idempotent Collector)
- At-least-once between outbox and Redis is tolerated by downstream idempotency

### 6. Concurrency Control

- Multiple publisher workers: `FOR UPDATE SKIP LOCKED` ensures each row is claimed by exactly one worker
- Row claiming is the locking mechanism; no separate lease table needed
- `published_at` is set only after successful `XADD` to Redis

### 7. Failure Recovery

- **Publisher crashes before `XADD`**: Row remains `pending`, picked up on next poll
- **Publisher crashes after `XADD`, before `published_at`**: Row remains `pending`, publisher retries → duplicate `XADD` → Collector deduplicates via deterministic ID
- **Redis unavailable**: Publisher backs off, rows accumulate in `pending`/`failed`, no data loss
- **Gateway crash during ingestion**: PostgreSQL transaction rolls back, nothing persisted
- **Max retries exceeded (dead_letter)**: Row marked `dead_letter`. This does **not** mean the Observation was never published — duplicate Redis publication may have occurred. Deterministic ID + Collector idempotency handles duplicates. Operator review required: if Observation confirmed in Redis/Collector, manually mark `published`; else trigger manual re-publish.

### 8. Quality Class Assignment

`quality_class` is assigned at ingestion time from **declarative agent capability metadata** stored in `agent_installations.capabilities_json` (see ADR-0006). The ingestion endpoint:
1. Resolves `installation_id` from machine token
2. Reads `capabilities_json` for the installation
3. Maps `fact_type` → `quality_class` via declarative config
4. Embeds `quality_class` in the Observation payload written to outbox

**No synchronous call to cognitive layer** during ingestion. Quality classification is static metadata, not a runtime cognitive query.

## Alternatives Considered

### Direct Redis Publishing (Current)
- Rejected: No atomicity, no tenant isolation at ingress, no durability guarantee

### Kafka as Event Backbone
- Rejected: Over-engineering for MVP; Redis Streams already operational; adds operational complexity

### Synchronous Collector Write
- Rejected: Couples ingestion latency to Collector availability; violates Cognitive Boundary (ingestion should not block on perception)

### Exactly-Once via Distributed Transactions
- Rejected: Not achievable with PostgreSQL + Redis; introduces false confidence; at-least-once + idempotency is the correct model

## Architectural Invariants

1. **Atomic ingestion**: One transaction writes telemetry batch + outbox rows
2. **Deterministic Observation ID**: Same input → same Observation ID always
3. **At-least-once outbox→Redis**: Publisher retries until `published_at` set
4. **Idempotent Collector**: `observation_exists(id, captured_at)` before INSERT
5. **Tenant isolation**: All outbox queries scoped by `tenant_id` from machine token
6. **No cognitive dependency at ingestion**: `quality_class` from declarative metadata only
7. **Outbox is the source of truth**: Redis is a derived stream; reconstruction always possible from outbox

## Security / Multi-tenancy

- Ingestion endpoint requires valid machine JWT (see ADR-0005)
- Machine token carries `tenant_id`, `installation_id`, `instance_id`, `credential_id`
- All outbox rows implicitly tenant-scoped via `tenant_id` column
- `UNIQUE` index on `(tenant_id, installation_id, batch_id, payload_hash)` prevents cross-tenant collision
- Row-level security not needed; application-layer scoping + composite UNIQUE is sufficient
- `credential_id` in outbox provides provenance link to the credential that authenticated the batch. Across credential rotation, the `credential_id` in the outbox row reflects the credential active at ingestion time (immutable).

## Failure / Recovery Semantics

| Failure Point | Behavior | Recovery |
|---------------|----------|----------|
| Ingestion TX fails | Nothing persisted | Client retries with same `batch_id` |
| Publisher claims row, crashes before XADD | Row remains `pending` | Next poll picks it up |
| Publisher XADD succeeds, crashes before UPDATE | Row `pending`, duplicate in Redis | Retry → duplicate XADD → Collector dedup |
| Redis down | Rows accumulate in `pending`/`failed` | Auto-recovery when Redis returns |
| Collector crashes after persist | Observation in PG, ack sent | No issue; ack prevents redelivery |
| Max retries exceeded | `status = 'dead_letter'` | Alert → manual replay or fix |

## Consequences

### Benefits
- Durable, auditable telemetry ingestion
- No data loss on crashes
- Idempotent end-to-end
- Cognitive Boundary preserved (ingestion → outbox → publisher → bus → Collector)
- Quality classification without cognitive layer dependency

### Costs
- Additional `observation_outbox` table (~same cardinality as observations)
- Background publisher worker required
- Slightly higher ingestion latency (async publish)
- Dead-letter handling operational process

### Complexity Introduced
- Publisher worker with retry/backoff logic
- Deterministic UUIDv5 generation
- Payload canonicalization for hashing
- Idempotency index maintenance

## Implementation Constraints

### What H4.0 Must Implement
1. `observation_outbox` table + indexes + triggers
2. `POST /api/v1/telemetry/ingest` endpoint in Gateway
3. `ObservationPublisher` background worker
4. Deterministic Observation ID generator (UUIDv5)
5. Payload canonicalization + SHA-256 hashing
5. Integration with machine auth (ADR-0005) and agent lifecycle (ADR-0006)

### What Must NOT Be Implemented
- Synchronous Collector write during ingestion
- Quality classification via cognitive layer query
- Kafka or new message infrastructure
- Distributed transactions
- Disk buffering in agents (agents keep current behavior: publish directly to gateway endpoint)

## Test Requirements

Before considering this decision implemented, the following tests must pass:

1. **Atomic ingestion**: Single transaction persists batch + outbox rows; rollback on failure leaves zero rows
2. **Deterministic ID**: Same input payload → identical Observation IDs across multiple ingestions
3. **Idempotent ingestion**: Duplicate `batch_id` + same payload → 202, no new outbox rows (UNIQUE index)
4. **Conflict detection**: Same `batch_id` + different payload → 409 Conflict
5. **Publisher at-least-once**: Crash after XADD, before UPDATE → retry publishes duplicate → Collector deduplicates
6. **Publisher retry/backoff**: Failed publish → exponential backoff (base=2s, cap=60s, jitter=±25%) → max 5 attempts → dead_letter
7. **Tenant isolation**: Machine token for tenant A cannot ingest/read tenant B outbox rows
8. **Quality class from metadata**: Ingestion reads `capabilities_json`, not cognitive layer
9. **Concurrent publishers**: Multiple workers → each row processed exactly once (FOR UPDATE SKIP LOCKED)
10. **Redis outage**: Publisher pauses, no data loss, auto-resume on Redis recovery
11. **Source_id resolution**: Ingestion resolves `installation_id` → `agent_installations.server_id` → `servers.id` and embeds as `source_id` in Observation; client-supplied source_id ignored
12. **Credential provenance**: `credential_id` from token `sub` persisted in `metric_batches` and `observation_outbox`; immutable across rotation
13. **Outbox content immutability**: UPDATE on `observation`, `payload_hash`, `credential_id`, `installation_id`, `batch_id` blocked by trigger; only lifecycle fields mutable
14. **Dead-letter handling**: Row marked dead_letter after 5 failures; operator can manually mark published or trigger re-publish; duplicate Redis publication accepted and deduplicated by Collector

## Dependencies

- **ADR-0001**: Company OS is the Brain (cognitive architecture authority)
- **ADR-0002**: COS-Monitor is the Product (external capabilities pattern)
- **ADR-0003**: Memory & Learning Layer operational (provenance chain)
- **ADR-0005**: Machine Authentication (token format, scopes, validation)
- **ADR-0006**: Agent Identity & Instance Lifecycle (installation_id, capabilities_json)
- **ADR-0007**: Telemetry Contract & Integrity (batch schema, payload_hash, idempotency)

---

*This ADR resolves CR-1 (PostgreSQL ↔ Redis) from the H4 Critical Architectural Gate.*