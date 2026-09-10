# H4 ADR Package — Cross-Validation Report (Post-Remediation)

**Date**: 2026-09-02  
**Status**: **GREEN — READY FOR HUMAN APPROVAL**

---

## H4 ADR Package Status

**GREEN — READY FOR HUMAN APPROVAL**

All BLOCKING and HIGH findings from the adversarial review have been remediated. The four ADRs are now deterministic and IMPLEMENTABLE.

---

## ADR Summary Table

| ADR | Decision | Critical Findings Resolved | Remaining Open Issues |
|-----|----------|---------------------------|----------------------|
| ADR-0004 | Transactional Outbox + Observation Publisher | CR-1, CR-3, CR-2 (Cognitive Boundary) | None — all BLOCKING/HIGH resolved |
| ADR-0005 | Machine Authentication Separation | CR-6 | None — key rotation (kid), refresh delivery, registration token, instance STOPPED validation all specified |
| ADR-0006 | Agent Identity & Instance Lifecycle | CR-4 | None — platform-neutral fingerprint, heartbeat credential validation, DELETE stop endpoint, reconciler race all specified |
| ADR-0007 | Telemetry Contract & Integrity | CR-1, CR-3, 9th Mandatory Decision | None — composite FKs enabled, canonical hash exact, credential provenance, source_id resolution all specified |

---

## Mandatory Decisions Coverage (9/9 — ALL IMPLEMENTABLE)

| # | Mandatory Decision | Coverage | ADR | Implementable |
|---|-------------------|----------|-----|---------------|
| 1 | Transactional Outbox | **COVERED** | ADR-0004 | ✅ YES |
| 2 | Machine Auth Separation | **COVERED** | ADR-0005 | ✅ YES |
| 3 | Quality Class Source | **COVERED** | ADR-0004, ADR-0007 | ✅ YES |
| 4 | Explicit Instance Registration | **COVERED** | ADR-0006 | ✅ YES |
| 5 | Registration Token Delivery | **COVERED** | ADR-0005 | ✅ YES |
| 6 | Host Fingerprint | **COVERED** | ADR-0006 | ✅ YES |
| 7 | Composite Tenant FKs | **COVERED** | ADR-0006, ADR-0007 | ✅ YES (UNIQUE(tenant_id, id) added) |
| 8 | Payload Hash | **COVERED** | ADR-0007 | ✅ YES (exact canonical algorithm) |
| 9 | Partition Maintenance | **COVERED** (deferred to MVP) | ADR-0004, ADR-0007 | ✅ YES (manual, explicit) |

---

## Critical Gate Findings Resolution (All RESOLVED)

| Critical Finding | Status | Resolved In |
|-----------------|--------|-------------|
| CR-1: PostgreSQL ↔ Redis (Transactional Outbox) | **RESOLVED** | ADR-0004 |
| CR-2: Cognitive Boundary (Publisher separation) | **RESOLVED** | ADR-0004 |
| CR-3: Collector Contract (deterministic IDs, idempotency) | **RESOLVED** | ADR-0004, ADR-0007 |
| CR-4: Agent Instance Lifecycle | **RESOLVED** | ADR-0006 |
| CR-6: Machine Auth Separation | **RESOLVED** | ADR-0005 |

---

## Remediated BLOCKING/HIGH Findings (All RESOLVED)

| Original Finding | Severity | Resolution |
|-----------------|----------|------------|
| `server_id` → `source_id` resolution missing | BLOCKING | ADR-0004 §2, ADR-0007 §5: explicit resolution path `installation_id` → `agent_installations.server_id` → `servers.id` → `Observation.source_id` |
| Composite FKs require UNIQUE on parent tables | BLOCKING | ADR-0007 §5: `UNIQUE(tenant_id, id)` added to `agent_installations` and `metric_batches` |
| `credential_id` absent from telemetry provenance | HIGH | ADR-0004 §1/§7, ADR-0007 §3/§5/§8: `credential_id` in `metric_batches`, `observation_outbox`; immutable across rotation |
| Backoff formula unspecified | HIGH | ADR-0004 §4: base=2s, cap=60s, jitter=±25%, max=5; exact formula specified |
| `host_fingerprint` Linux-only | HIGH | ADR-0006 §7: platform-neutral contract for Linux/Windows/VMware; boot_id excluded; stable across reboot |
| Machine JWT key rotation (`kid`) missing | HIGH | ADR-0005 §1: `kid` header claim; key set with 24h overlap; unknown kid → reject |
| Refresh token delivery ambiguous (cookie vs body) | HIGH | ADR-0005 §4/§9: response body chosen for MVP; no cookie |
| Instance STOPPED token validation missing | HIGH | ADR-0005 §8, ADR-0006 §5: middleware validates instance status=RUNNING on every telemetry/heartbeat request |
| Registration token incomplete | HIGH | ADR-0005 §6: full contract with claims, TTL, single-use, host binding via fingerprint at registration, delivery via response body, redaction |
| Canonical payload hash ambiguous | HIGH | ADR-0007 §2: exact language-agnostic algorithm; float shortest representation; captured_at exact string; sorted keys; UTF-8 |
| Dead-letter implies "never published" | HIGH | ADR-0004 §4/§7: dead_letter means publisher failed to confirm; duplicate Redis publication accepted; Collector dedup handles |
| Outbox content immutability not enforced at DB | HIGH | ADR-0004 §1: trigger prevents UPDATE on `observation`, `payload_hash`, `credential_id`, `installation_id`, `batch_id` |
| Heartbeat missing credential validation | HIGH | ADR-0006 §5: validates credential_id, installation_id, tenant_id, instance status all match |
| Stop endpoint ambiguous (POST vs DELETE) | MEDIUM | ADR-0006 §5.1: `DELETE /agents/instance/{instance_id}` canonical |
| Reconciler interval hardcoded | LOW | ADR-0006 §9: configurable via `RECONCILER_INTERVAL_SECONDS` |

---

## Architectural Principles Verification (All ✅)

| Principle / Rule | Protected | Verification |
|------------------|-----------|--------------|
| P1 (Observation Primacy / Immutability) | ✅ | All Observation/telemetry tables have append-only triggers; outbox content immutable via trigger |
| R1 (One Cognitive Capability per Component) | ✅ | Publisher, Collector, Gateway are external capabilities (ADR-0002) |
| R3 (Cognitive Boundary) | ✅ | Ingestion → Outbox → Publisher → Bus → Collector → Perception; no shortcuts; quality_class from metadata |
| R4 (Confidence Required for Action) | ✅ | Machine auth validates token; no cognitive action without authority |
| R7 (Architecture Guides Code) | ✅ | ADRs define architecture before implementation |
| Tenant Isolation | ✅ | All tables have tenant_id; composite UNIQUE/FKs; app-layer scoping via machine token |
| H3 Not Modified | ✅ | ADRs reference H3 tables (learning_memory, learning_executions) but don't change them |
| No execution_id in Telemetry | ✅ | Telemetry uses batch_id, installation_id, instance_id, credential_id — not execution_id |
| Provenance = host_id → observations.source_id | ✅ | ADR-0006: host_fingerprint → server_id; ADR-0007: installation_id → server_id → source_id |

---

## Cross-ADR Consistency Checks (All ✅)

### No Contradictory Decisions
- ADR-0004 (Outbox) and ADR-0007 (Telemetry Contract) agree on atomic ingestion TX, credential_id provenance, source_id resolution
- ADR-0005 (Machine Auth) and ADR-0006 (Instance Lifecycle) share credential_id, installation_id, instance_id; heartbeat validates all four
- ADR-0006 and ADR-0007 both use host_fingerprint for clone detection; platform-neutral algorithm defined
- ADR-0004 quality_class from capabilities_json (ADR-0006/0007) — no cognitive query
- ADR-0005 token validation (ADR-0005 §8) enforces instance RUNNING status (ADR-0006)

### All 9 MUST DECIDE Covered & Implementable
1. **Outbox** → ADR-0004 (exact retry, dead-letter, immutability)
2. **Machine auth** → ADR-0005 (kid, response body, registration token, STOPPED validation)
3. **Quality source** → ADR-0004/0007 (declarative capabilities_json, admin-managed)
4. **Instance registration** → ADR-0006 (explicit, fingerprint, credential binding)
5. **Registration token delivery** → ADR-0005 (response body, 10min, single-use, redacted)
6. **Host fingerprint** → ADR-0006 (platform-neutral, stable, boot_id excluded)
7. **Composite tenant FKs** → ADR-0007 (UNIQUE(tenant_id, id) on parents enables FKs)
8. **Payload hash** → ADR-0007 (exact canonical algorithm, language-agnostic)
9. **Partition maintenance** → ADR-0004/0007 (manual for MVP, explicit deferral)

### Cognitive Boundary Explicit
- **Agent** = Observation Capturer / Telemetry Producer (ADR-0006, ADR-0007)
- **Telemetry Ingestion** = External ingestion endpoint (ADR-0004, ADR-0007)
- **Observation Publisher** = Transforms telemetry → Observation (ADR-0004)
- **Collector** = Consumes Observation Bus → Perception/Organization (existing, unchanged)
- **Gateway** = Auth + Boundary enforcement ONLY (ADR-0005, existing)
  - Does NOT execute learning
  - Does NOT write learning_memory
  - Does NOT decide outcomes
  - Does NOT become cognitive component
- **Quality classification** = Declarative metadata (capabilities_json), NOT synchronous cognitive query

### Instance Lifecycle Formal
| Entity | States | Defined In |
|--------|--------|------------|
| Installation | PROVISIONED → ACTIVE → DISABLED → REVOKED | ADR-0006 |
| Instance | RUNNING / STOPPED | ADR-0006 |
| Host (derived) | UNKNOWN / ONLINE / OFFLINE / DECOMMISSIONED | ADR-0006 |

Explicit registration, ownership, restart semantics, at-most-one invariant (DB constraint), heartbeat timeout, crash recovery, reconciler race — all defined.

### Tenant Isolation
- All new tables: `tenant_id` column + FK to `tenants`
- Composite UNIQUE: `(tenant_id, installation_id, batch_id, payload_hash)` (ADR-0007)
- Composite FK: `(tenant_id, installation_id)` → `agent_installations(tenant_id, id)` (ADR-0007) — enabled by UNIQUE(tenant_id, id)
- Partial UNIQUE: `installation_id` WHERE `status = 'RUNNING'` (ADR-0006) — tenant scoped via installation FK
- Application-layer scoping via machine token `tenant_id`
- Credential → Installation → Instance chain all tenant-scoped

### Idempotency Formal
```
same tenant + installation + batch_id + same payload_hash
    → idempotent duplicate (202, no new row)

same tenant + installation + batch_id + different payload_hash
    → conflict / 409
```
Canonical payload hashing with SHA-256, deterministic UUIDv5 Observation IDs — exact algorithm specified in ADR-0007 §2.

### MVP Minimal
| KEEP (MVP) | DEFER |
|------------|-------|
| PostgreSQL | mTLS |
| Redis Streams (existing) | Disk buffering |
| Gateway (existing) | pg_partman |
| Collector (existing) | TPM |
| Existing agents | Advanced metrics backend |
| Simple background publisher | Unnecessary new microservices |
| Manual retention/partition | — |

---

## Files Created

| File | Purpose |
|------|---------|
| `adr/ADR-0004-transactional-outbox-observation-publisher.md` | Transactional Outbox + Publisher |
| `adr/ADR-0005-machine-authentication.md` | Machine Auth Separation |
| `adr/ADR-0006-agent-identity-instance-lifecycle.md` | Agent Identity & Instance Lifecycle |
| `adr/ADR-0007-telemetry-contract-integrity.md` | Telemetry Contract & Integrity |

---

## Files NOT Modified

- Framework documents (`/home/dcordoba/Documents/Default Project/company/company-os-main/`) — **read-only**
- Existing ADRs (ADR-0001, ADR-0002, ADR-0003) — **not modified**
- Application code — **no code changes**
- Database migrations — **not created**
- Tests — **not implemented**

---

## Decisions Requiring Human Review (Operational, Not Architectural)

The following are operational configuration decisions, not architectural ambiguities:

1. **RS256 Key Management** (ADR-0005): RS256 mandated for production; HS256 dev-only. Confirm production key storage/rotation process.
2. **Redis DB 2 vs Key Prefix** (ADR-0005): Separate Redis DB (2) preferred for isolation; key prefix `machine_jwt_blacklist:` acceptable if single Redis. Operations decision.
3. **Heartbeat Timeout Default** (ADR-0006): 120 seconds proposed; configurable. Confirm with operational requirements.
4. **Partition Maintenance** (ADR-0004, ADR-0007): Explicitly deferred to manual for MVP. Confirm acceptable or require pg_partman in H4.0.
5. **Reconciler Interval** (ADR-0006): 60s default, configurable via `RECONCILER_INTERVAL_SECONDS`. Confirm default.

**All architectural ambiguities have been resolved.** These remaining items are runtime configuration choices.

---

## ADR Approval Readiness

| ADR | Status | BLOCKING | HIGH |
|-----|--------|----------|------|
| ADR-0004 | **GREEN** | 0 | 0 |
| ADR-0005 | **GREEN** | 0 | 0 |
| ADR-0006 | **GREEN** | 0 | 0 |
| ADR-0007 | **GREEN** | 0 | 0 |

### Mandatory Decisions
**9/9 inequívocas: YES** — All explicitly defined, consistent, and implementable.

### H4 Architectural Invariants
- **P1** ✅ (all immutable tables have triggers; outbox content immutable)
- **R1** ✅ (Publisher/Collector/Gateway = external capabilities)
- **R3** ✅ (Ingestion → Outbox → Publisher → Bus → Collector → Perception; no shortcuts)
- **R7** ✅ (ADRs define architecture before implementation)
- **Tenant Isolation** ✅ (composite UNIQUE/FKs + app-layer scoping)
- **Telemetry/Cognitive Boundary** ✅ (quality_class from metadata; no cognitive query)
- **H3 Isolation** ✅ (ADRs reference H3 tables but don't modify)
- **Provenance** ✅ (host_fingerprint → server_id → source_id chain complete)

---

## FINAL RECOMMENDATION

**GREEN — ADRs READY FOR HUMAN APPROVAL**

No BLOCKING or HIGH architectural ambiguities remain. All 9 mandatory decisions are explicitly defined, internally consistent, and implementable by a developer without further architectural decisions.

**Next Step**: Human review and approval of the four ADRs (ADR-0004 through ADR-0007). Upon approval, proceed to **H4.0 implementation** (contracts & schema) per ADR implementation constraints.

**Do NOT advance to H4.0 implementation until human review completes and ADRs are APPROVED.**

---

*Validation complete. All adversarial findings remediated. Architecture coherent with Company OS Framework (P1-P7, R1-R7, ADR-0001, ADR-0002, ADR-0003).*