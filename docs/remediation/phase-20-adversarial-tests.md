# Phase 20 -- Adversarial Tests

**Date:** 2026-08-24
**Scope:** 14 attack categories, 67 test cases
**Status:** 67/67 pass

---

## 1. Overview

The adversarial test suite validates security controls against realistic attack scenarios. Each category targets a specific threat vector and exercises the defense mechanisms implemented across Phases 0-20.

| Category | File | Tests | Status |
|----------|------|-------|--------|
| 01 - Cross-tenant | `tests/security/adversarial/test_01_cross_tenant.py` | 5 | Pass |
| 02 - Confidence forgery | `tests/security/adversarial/test_02_confidence_forgery.py` | 5 | Pass |
| 03 - Target swap | `tests/security/adversarial/test_03_confidence_target_swap.py` | 4 | Pass |
| 04 - Refresh replay | `tests/security/adversarial/test_04_refresh_replay.py` | 4 | Pass |
| 05 - Concurrent refresh | `tests/security/adversarial/test_05_refresh_concurrent.py` | 4 | Pass |
| 06 - Redis failure | `tests/security/adversarial/test_06_redis_failure.py` | 5 | Pass |
| 07 - Rate limit bypass | `tests/security/adversarial/test_07_rate_limit_bypass.py` | 5 | Pass |
| 08 - Report tenant bypass | `tests/security/adversarial/test_08_report_tenant_bypass.py` | 4 | Pass |
| 09 - Cookie security | `tests/security/adversarial/test_09_cookie_security.py` | 5 | Pass |
| 10 - Context race | `tests/security/adversarial/test_10_context_race.py` | 5 | Pass |
| 11 - Migration integrity | `tests/security/adversarial/test_11_migration_integrity.py` | 5 | Pass |
| 12 - SQL tenant leak | `tests/security/adversarial/test_12_sql_tenant_leak.py` | 5 | Pass |
| 13 - Action bypass | `tests/security/adversarial/test_13_action_bypass.py` | 6 | Pass |
| 14 - Policy bypass | `tests/security/adversarial/test_14_policy_bypass.py` | 5 | Pass |

---

## 2. Category Details

### Category 01 -- Cross-Tenant Attack

**File:** `tests/security/adversarial/test_01_cross_tenant.py`
**Threat:** Tenant A attempts to access tenant B's data through the gateway or stores.

**Test cases:**
1. `test_cross_tenant_decisions_blocked` -- Tenant A cannot list tenant B's decisions via `GatewayService`
2. `test_cross_tenant_confidence_blocked` -- Tenant A cannot read tenant B's confidence scores
3. `test_cross_tenant_store_query_blocked` -- Store queries without tenant scope return empty results
4. `test_superadmin_cross_tenant_allowed` -- Cross-tenant access is permitted only for superadmin role
5. `test_tenant_scope_rejects_mismatch` -- `AuthorizationContext` rejects tenant_id mismatch

**Defense:** R6 tenant isolation via `AuthorizationContext`, `TenantScopeError` on mismatch.

---

### Category 02 -- Confidence Forgery

**File:** `tests/security/adversarial/test_02_confidence_forgery.py`
**Threat:** Attacker supplies a forged `confidence_score` to bypass calibration and execute actions.

**Test cases:**
1. `test_forged_confidence_score_rejected` -- Gateway rejects client-supplied `confidence_score`
2. `test_confidence_provenance_required` -- Actions require confidence from the stored calibration
3. `test_missing_confidence_store_raises` -- `SecurityControlUnavailable` when confidence store is None
4. `test_calibration_justification_required` -- Confidence without justification is rejected
5. `test_evidence_scope_validated` -- Evidence outside hypothesis scope is rejected

**Defense:** R4 confidence gate, R5 provenance, `verify_confidence_provenance()`, `validate_confidence_evidence_scope()`.

---

### Category 03 -- Confidence Target Swap

**File:** `tests/security/adversarial/test_03_confidence_target_swap.py`
**Threat:** Attacker uses a valid confidence score but applies it to a different target (e.g., use hypothesis A's confidence for hypothesis B).

**Test cases:**
1. `test_target_type_mismatch_rejected` -- Confidence for "hypothesis" cannot be used for "recommendation"
2. `test_target_id_mismatch_rejected` -- Confidence for hypothesis A cannot satisfy hypothesis B
3. `test_tenant_mismatch_rejected` -- Confidence from tenant A cannot satisfy tenant B
4. `test_expired_confidence_rejected` -- Stale confidence beyond TTL is rejected

**Defense:** `verify_confidence_provenance()` checks target_type, target_id, and tenant_id match.

---

### Category 04 -- Refresh Replay

**File:** `tests/security/adversarial/test_04_refresh_replay.py`
**Threat:** Attacker captures a valid refresh token and replays it to obtain multiple new access tokens.

**Test cases:**
1. `test_first_use_succeeds` -- Valid refresh token is accepted on first use
2. `test_replay_rejected` -- Same refresh token is rejected on second use (consumed)
3. `test_consumed_token_cannot_rotate` -- Consumed token cannot be used to generate new tokens
4. `test_blacklist_enforced` -- Consumed token is added to the blacklist

**Defense:** Atomic `consume_refresh_token()` with Redis `SET NX EX`.

---

### Category 05 -- Concurrent Refresh

**File:** `tests/security/adversarial/test_05_refresh_concurrent.py`
**Threat:** Two concurrent requests use the same refresh token simultaneously. Only one should succeed.

**Test cases:**
1. `test_concurrent_refresh_one_succeeds` -- Of N concurrent refreshes with same token, exactly one succeeds
2. `test_concurrent_refresh_others_fail` -- Remaining concurrent requests receive 401
3. `test_atomicity_guaranteed` -- Redis `SET NX` guarantees only one winner
4. `test_token_consumed_after_first` -- Token is marked consumed after the first successful rotation

**Defense:** Atomic `consume_refresh_token()` prevents double-spend.

---

### Category 06 -- Redis Failure

**File:** `tests/security/adversarial/test_06_redis_failure.py`
**Threat:** Redis becomes unavailable. Security controls must fail-closed, not silently pass through.

**Test cases:**
1. `test_token_check_fail_closed` -- `is_revoked()` raises `SecurityControlUnavailable` when Redis is down
2. `test_rate_limiter_fail_closed` -- Rate limiter raises `RateLimiterUnavailable` when Redis is down
3. `test_blacklist_write_fail_closed` -- `_NoOpRedis.set()` raises `SecurityControlUnavailable`
4. `test_logout_propagates_error` -- Logout handler propagates `SecurityControlUnavailable` (503)
5. `test_login_returns_429` -- Login returns 429 when rate limiter is unavailable

**Defense:** Fail-closed pattern for all security-critical operations.

---

### Category 07 -- Rate Limit Bypass

**File:** `tests/security/adversarial/test_07_rate_limit_bypass.py`
**Threat:** Attacker attempts to bypass rate limiting through various techniques.

**Test cases:**
1. `test_login_rate_limited` -- Login returns 429 after exceeding rate limit
2. `test_refresh_rate_limited` -- Refresh returns 429 after exceeding rate limit
3. `test_different_keys_independent` -- Rate limit keys are independent per client
4. `test_sliding_window_enforced` -- Window expiration resets the count
5. `test_redis_backed_atomic` -- Redis-backed limiter uses atomic Lua script

**Defense:** Atomic sliding window rate limiter with `await` correctness.

---

### Category 08 -- Report Tenant Bypass

**File:** `tests/security/adversarial/test_08_report_tenant_bypass.py`
**Threat:** Attacker accesses report data from other tenants through the report service.

**Test cases:**
1. `test_unauthenticated_rejected` -- Report service rejects requests without valid JWT
2. `test_tenant_scoped_results` -- Reports are scoped to the caller's tenant
3. `test_cross_tenant_report_blocked` -- Tenant A cannot read tenant B's reports
4. `test_jwt_validation_enforced` -- Invalid tokens are rejected with 401

**Defense:** JWT authentication + tenant isolation in report service (FIX 7).

---

### Category 09 -- Cookie Security

**File:** `tests/security/adversarial/test_09_cookie_security.py`
**Threat:** Tokens stored in insecure cookies or headers are vulnerable to theft.

**Test cases:**
1. `test_cookie_httponly` -- Auth cookies have HttpOnly flag
2. `test_cookie_secure` -- Auth cookies have Secure flag
3. `test_cookie_samesite` -- Auth cookies have SameSite=Strict
4. `test_no_token_in_url` -- Tokens never appear in URLs or query parameters
5. `test_no_token_in_localstorage` -- Tokens are not stored in localStorage

**Defense:** HttpOnly/Secure/SameSite cookie configuration (Phase 13).

---

### Category 10 -- Context Race

**File:** `tests/security/adversarial/test_10_context_race.py`
**Threat:** Concurrent context activations violate the one-active-context-per-purpose invariant.

**Test cases:**
1. `test_concurrent_activation_one_wins` -- Of N concurrent activations, exactly one succeeds
2. `test_unique_constraint_enforced` -- UNIQUE partial index prevents duplicate active contexts
3. `test_deactivate_before_activate` -- Old context is deactivated before new one is activated
4. `test_atomic_transaction` -- INSERT + DEACTIVATE in single transaction
5. `test_0_active_prevented` -- Invariant: at most one active context per purpose

**Defense:** Atomic transaction + UNIQUE partial index (Phase 5).

---

### Category 11 -- Migration Integrity

**File:** `tests/security/adversarial/test_11_migration_integrity.py`
**Threat:** Database migrations break existing data or drop security constraints.

**Test cases:**
1. `test_immutability_triggers_present` -- All canonical tables have immutability triggers
2. `test_unique_active_index_exists` -- UNIQUE partial index for active contexts exists
3. `test_evidence_scope_column_exists` -- `evidence_scope` column exists on confidence_scores
4. `test_migration_idempotent` -- Migrations can be re-run without error
5. `test_no_data_loss` -- Migrations do not delete existing rows

**Defense:** Architecture as Code invariant tests (Phase 17).

---

### Category 12 -- SQL Tenant Leak

**File:** `tests/security/adversarial/test_12_sql_tenant_leak.py`
**Threat:** SQL queries in stores lack `tenant_id` filter, allowing cross-tenant data leakage.

**Test cases:**
1. `test_decision_store_tenant_scoped` -- DecisionStore queries include `tenant_id` filter
2. `test_confidence_store_tenant_scoped` -- ConfidenceStore queries include `tenant_id` filter
3. `test_context_store_tenant_scoped` -- ContextStore queries include `tenant_id` filter
4. `test_report_store_tenant_scoped` -- ReportStore queries include `tenant_id` filter
5. `test_observation_store_tenant_scoped` -- ObservationStore queries include `tenant_id` filter

**Defense:** Tenant scoping enforced in all store queries (Phase 12).

---

### Category 13 -- Action Bypass

**File:** `tests/security/adversarial/test_13_action_bypass.py`
**Threat:** Attacker attempts to bypass the cognitive boundary to execute actions without proper authorization.

**Test cases:**
1. `test_propose_requires_confidence` -- Propose action requires verified confidence
2. `test_commit_requires_confidence` -- Commit action requires verified confidence
3. `test_execute_requires_authority` -- Execute requires proper Decision Authority role
4. `test_boundary_rejects_invalid_transition` -- Invalid state transitions are rejected
5. `test_confidence_provenance_enforced` -- Actions without provenance are rejected
6. `test_risk_ceiling_enforced` -- COMMIT actions respect risk ceiling

**Defense:** R3 boundary enforcement, R4 confidence gate, RBAC (Phase 1, 11).

---

### Category 14 -- Policy Bypass

**File:** `tests/security/adversarial/test_14_policy_bypass.py`
**Threat:** Attacker attempts to bypass the capability policy (declarative rules for allowed cognitive transitions).

**Test cases:**
1. `test_unauthorized_capability_rejected` -- Role cannot execute capability outside its policy
2. `test_tenant_isolation_enforced` -- Capability policy respects tenant boundaries
3. `test_superadmin_bypass_allowed` -- Superadmin can bypass capability restrictions
4. `test_viewer_cannot_propose` -- Viewer role cannot propose actions
5. `test_policy_boundary_enforced` -- Boundary checks validate against capability policy

**Defense:** Capability policy (Phase 10), RBAC, tenant isolation.

---

## 3. Defense Layers

The adversarial tests exercise four defense layers:

1. **Authentication/Authorization:** JWT validation, RBAC, tenant scope
2. **Cognitive Boundary:** State transition validation, confidence provenance
3. **Data Integrity:** Immutability triggers, atomic operations, tenant scoping
4. **Infrastructure:** Rate limiting, fail-closed Redis, cookie security
