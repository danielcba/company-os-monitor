# Phase 20 -- Security Audit

**Date:** 2026-08-24
**Auditor:** opencode (mimo-v2-5-free)
**Scope:** Security review of all 15 Phase 20 fixes

---

## 1. Audit Summary

Phase 20 addresses 15 integration-level security issues. All fixes were verified against the 67 adversarial test cases (14 attack categories) which passed. The fixes close gaps between unit-level security controls and their real runtime behavior.

| Severity | Fixed | Remaining |
|----------|-------|-----------|
| Critical (P0) | 4 | 0 |
| High (P1) | 5 | 0 |
| Medium (P2) | 6 | 2 |
| **Total** | **15** | **2** |

---

## 2. Fix-by-Fix Security Analysis

### FIX 1 -- Rate limiter `await` correctness

**Threat addressed:** Brute-force attacks on login/refresh bypass rate limiting because the limiter coroutine is never evaluated.

**Implementation:** Both login and refresh handlers now `await limiter.is_allowed(key)`. Returns 429 on denial.

**Verification:** Adversarial test 07 (rate limit bypass) validates correct behavior. Unit tests in `test_rate_limiter.py`.

**Residual risk:** None. Rate limiting is enforced for all security-critical endpoints.

---

### FIX 2 -- Confidence provenance fail-open eliminated

**Threat addressed:** When `confidence_store` is None, an attacker can supply an arbitrary `confidence_score` to bypass calibration and execute uncalibrated actions.

**Implementation:** `verify_confidence_provenance()` now raises `SecurityControlUnavailable` when confidence store is None. Gateway returns 503.

**Verification:** Adversarial tests 02 (confidence forgery), 03 (target swap), 13 (action bypass) validate provenance enforcement.

**Residual risk:** None for the current architecture. Future confidence store backends must implement the `ConfidenceStoreAdapter` protocol correctly.

---

### FIX 3 -- Atomic refresh token rotation

**Threat addressed:** TOCTOU race condition in refresh token rotation. Two concurrent requests could both pass the `is_revoked()` check and both receive new tokens.

**Implementation:** Replaced `is_revoked() -> revoke()` with atomic `consume_refresh_token()` using Redis `SET NX EX`.

**Verification:** Adversarial tests 04 (refresh replay), 05 (concurrent refresh) validate atomicity.

**Residual risk:** None. Atomic consume-once is enforced at the Redis level.

---

### FIX 4 -- Logout exception propagation

**Threat addressed:** `SecurityControlUnavailable` was silently swallowed during logout, allowing a compromised session to persist even when the blacklist backend fails.

**Implementation:** Only expected exceptions are caught; security control failures propagate and return 503.

**Verification:** Adversarial test 06 (Redis failure) validates fail-closed behavior.

**Residual risk:** None. Logout now correctly fails closed.

---

### FIX 5 -- Rate limiter fail-closed on Redis failure

**Threat addressed:** Rate limiter falls back to permissive in-memory mode when Redis is unavailable, allowing brute-force attacks during infrastructure failures.

**Implementation:** `RateLimiterUnavailable` is raised when Redis is down. HTTP handlers catch it and return 429.

**Verification:** Adversarial test 06 (Redis failure) validates fail-closed. FIX 13 adds the exception type.

**Residual risk:** In-memory fallback is still available for non-security-critical endpoints (documented and intentional for availability).

---

### FIX 6 -- `_NoOpRedis` raises `SecurityControlUnavailable`

**Threat addressed:** `_NoOpRedis.set()` and `.setnx()` silently succeed, allowing token blacklist writes to be lost when Redis is not configured.

**Implementation:** Both methods raise `SecurityControlUnavailable`.

**Verification:** Adversarial test 06 (Redis failure) validates the stub raises on write.

**Residual risk:** None. Security operations cannot proceed without a functioning backend.

---

### FIX 7 -- Report service JWT auth + tenant isolation

**Threat addressed:** Report service had no authentication. Any caller could read all reports across all tenants without a valid token.

**Implementation:** JWT validation middleware added. All report queries scoped to caller's tenant_id.

**Verification:** Adversarial test 08 (report tenant bypass) validates tenant isolation.

**Residual risk:** Report generation endpoints (POST) may need rate limiting in a future phase.

---

### FIX 8 -- CI workflow service test isolation

**Threat addressed:** Service tests run from repo root without correct PYTHONPATH, causing import failures to be silently swallowed by CI. Security regressions could pass CI undetected.

**Implementation:** CI now runs each service's tests from its own directory with `PYTHONPATH=.`.

**Verification:** CI pipeline passes with all 345 tests.

**Residual risk:** None for current services. New services must follow the same pattern.

---

### FIX 9 -- Smoke test exact status expectations

**Threat addressed:** Smoke test accepted any HTTP status code, providing no guarantee that security controls were actually enforced.

**Implementation:** Smoke test validates exact status codes: 200 for health, 401 for unauthenticated, 429 for rate-limited.

**Verification:** CI smoke test passes with exact expectations.

**Residual risk:** None. Smoke test is a basic integration check.

---

### FIX 10 -- Confidence calibrator evidence scope validation

**Threat addressed:** Calibrator could use evidence outside the hypothesis scope, inflating confidence scores with irrelevant data.

**Implementation:** `calibrate()` calls `validate_confidence_evidence_scope()` before computing scores. Raises `EvidenceScopeError` on scope violation.

**Verification:** Adversarial tests 02 (confidence forgery), 03 (target swap) validate scope enforcement.

**Residual risk:** None for the current implementation. The scope validation is strict and verifiable.

---

### FIX 11 -- Gateway `action_handler` provenance check

**Threat addressed:** Gateway's `action_handler` for propose/commit did not verify confidence provenance, allowing actions with uncalibrated confidence.

**Implementation:** `verify_confidence_provenance()` is called before executing propose/commit actions.

**Verification:** Adversarial test 13 (action bypass) validates provenance enforcement at the gateway level.

**Residual risk:** None. Actions require verified confidence.

---

### FIX 12 -- `CalibrationContent` dataclass fix

**Threat addressed:** `pydantic.Field()` used in a `@dataclass` causes runtime errors, breaking the calibration model. This could prevent confidence calibration entirely.

**Implementation:** Replaced with `dataclasses.field()`.

**Verification:** Confidence-service unit tests (34/34) pass.

**Residual risk:** None. Data structure is now correct.

---

### FIX 13 -- `RateLimiterUnavailable` exception

**Threat addressed:** No typed exception for rate limiter failures. HTTP handlers could not distinguish rate limiter failures from other errors.

**Implementation:** New `RateLimiterUnavailable` exception. HTTP handlers catch it and return 429.

**Verification:** Adversarial test 06 (Redis failure) validates 429 response.

**Residual risk:** None. Typed exception enables proper error handling.

---

### FIX 14 -- Gateway test `_FakeConfidenceStore`

**Threat addressed:** Gateway tests were not exercising the real provenance verification path, giving false confidence in security controls.

**Implementation:** `_FakeConfidenceStore` satisfies `ConfidenceStoreAdapter` protocol.

**Verification:** Gateway tests (123/123) pass with real provenance verification.

**Residual risk:** None. Tests now exercise the real security path.

---

### FIX 15 -- User-service `FakeRequest` remote attribute

**Threat addressed:** Test double missing `remote` attribute caused `AttributeError` in rate limiter tests, preventing validation of rate limiting behavior.

**Implementation:** `FakeRequest` now includes `remote` with `{"host": "..."}` structure.

**Verification:** User-service tests (51/51) pass.

**Residual risk:** None. Rate limiter tests now pass.

---

## 3. Adversarial Test Results

| Category | Tests | Status |
|----------|-------|--------|
| 01 - Cross-tenant | 5 | Pass |
| 02 - Confidence forgery | 5 | Pass |
| 03 - Confidence target swap | 4 | Pass |
| 04 - Refresh replay | 4 | Pass |
| 05 - Concurrent refresh | 4 | Pass |
| 06 - Redis failure | 5 | Pass |
| 07 - Rate limit bypass | 5 | Pass |
| 08 - Report tenant bypass | 4 | Pass |
| 09 - Cookie security | 5 | Pass |
| 10 - Context race | 5 | Pass |
| 11 - Migration integrity | 5 | Pass |
| 12 - SQL tenant leak | 5 | Pass |
| 13 - Action bypass | 6 | Pass |
| 14 - Policy bypass | 5 | Pass |
| **Total** | **67** | **Pass** |

---

## 4. Remaining Risks

| ID | Severity | Description | Mitigation |
|----|----------|-------------|------------|
| RR-001 | Medium | Report service POST endpoints lack rate limiting | Add rate limiting in future phase |
| RR-002 | Medium | No CSRF protection middleware | Implement CSRF tokens in future phase |

---

## 5. Conclusion

All 15 Phase 20 fixes have been implemented and verified. No critical or high-severity security issues remain. The two medium-severity remaining risks are non-blocking and documented in the risk register.
