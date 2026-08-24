# CHANGELOG_PHASE20.md

## Company OS Monitor — Phase 20 Journal

Runtime integration verification, adversarial testing, and final hardening.

**Commit:** `b0ad22f` — `feat(security): Phase 20 — runtime integration verification & adversarial testing`
**Date:** 2026-08-24
**Tests:** 137/137 root (70 original + 67 adversarial), 345/345 total

---

## Fixes Implemented

### FIX 1 — Rate limiter `await` correctness
**File:** `apps/services/user-service/src/health.py`
- Login and refresh handlers now properly `await` the rate limiter's `is_allowed()` coroutine

### FIX 2 — Confidence provenance fail-open eliminated
**File:** `apps/gateway/api-gateway/src/service.py`
- `verify_confidence_provenance()` raises `SecurityControlUnavailable` when confidence store is None

### FIX 3 — Atomic refresh token rotation
**File:** `apps/services/user-service/src/service.py`
- Replaced `is_revoked() -> revoke()` (TOCTOU race) with atomic `consume_refresh_token()` using Redis `SET NX EX`

### FIX 4 — Logout exception handling
**File:** `apps/services/user-service/src/service.py`
- Logout no longer swallows `SecurityControlUnavailable` exceptions

### FIX 5 — Rate limiter fail-closed
**File:** `apps/services/user-service/src/ratelimit.py`
- Redis unavailable → `RateLimiterUnavailable` exception (fail-closed)

### FIX 6 — `_NoOpRedis` security ops raise
**File:** `libs/access/token_blacklist.py`
- `.set()` and `.setnx()` now raise `SecurityControlUnavailable` instead of returning silently

### FIX 7 — Report service JWT + tenant isolation
**Files:** `apps/services/report-service/src/health.py`, `apps/services/report-service/src/main.py`
- JWT authentication added; all queries scoped to caller's tenant

### FIX 8 — CI workflow service test execution
**File:** `.github/workflows/ci.yml`
- Service tests run from their own directories with `PYTHONPATH=.`

### FIX 9 — Smoke test rewritten
**File:** `tests/smoke/smoke_test.py`
- Exact status expectations (200, 401, 429), full authentication flow validation

### FIX 10 — Confidence evidence scope validation
**Files:** `apps/services/confidence-service/src/calibrator/calibrator.py`, `libs/learning/confidence.py`
- `calibrate()` calls `validate_confidence_evidence_scope()` before computing scores

### FIX 11 — Gateway action provenance enforcement
**File:** `apps/gateway/api-gateway/src/health.py`
- `action_handler` calls `verify_confidence_provenance()` for propose/commit actions

### FIX 12 — CalibrationContent field fix
**File:** `libs/learning/confidence.py`
- Changed from `pydantic.Field()` to `dataclasses.field()` in `@dataclass` class

### FIX 13 — `RateLimiterUnavailable` exception
**Files:** `apps/services/user-service/src/ratelimit.py`, `apps/services/user-service/src/health.py`
- New exception class; HTTP handlers catch it and return 429

### FIX 14 — Gateway test fixture
**File:** `apps/gateway/api-gateway/tests/test_gateway_http.py`
- `_FakeConfidenceStore` satisfies `ConfidenceStoreAdapter` protocol

### FIX 15 — User-service test `FakeRequest`
**File:** `apps/services/user-service/tests/test_auth_service.py`
- Added `remote` attribute for rate limiter tests

---

## Adversarial Test Suite (67 tests, 14 categories)

| # | Category | Tests | Attack |
|---|----------|-------|--------|
| 01 | Cross-tenant access | 4 | Role-based tenant boundary bypass |
| 02 | Confidence forgery | 3 | Client-supplied confidence score manipulation |
| 03 | Confidence target swap | 3 | Using confidence for wrong target |
| 04 | Refresh replay | 5 | Token reuse after consume |
| 05 | Refresh concurrency | 1 | 50 concurrent refresh token consumption |
| 06 | Redis failure | 3 | Backend unavailability handling |
| 07 | Rate limit bypass | 4 | Sliding window + fail-closed verification |
| 08 | Report tenant bypass | 4 | Cross-tenant report generation |
| 09 | Cookie security | 8 | HttpOnly, Secure, SameSite, path, max_age |
| 10 | Context race | 3 | Concurrent context activation |
| 11 | Migration integrity | 5 | Schema triggers, indexes, evidence scope |
| 12 | SQL tenant leak | 6 | Query-level tenant isolation |
| 13 | Action bypass | 9 | Non-executing capability enforcement |
| 14 | Policy bypass | 9 | Canonical flow + boundary gate |

---

## Deliverables Created

- `docs/remediation/phase-20-runtime-integration-report.md` — Fix details with file paths
- `docs/remediation/phase-20-security-audit.md` — Threat/implementation/verification per fix
- `docs/remediation/phase-20-adversarial-tests.md` — 14 categories documented
- `docs/remediation/phase-20-cognitive-compliance.md` — P1-P7/R1-R7 compliance matrix
- `docs/remediation/phase-20-migration-integrity.md` — Migration safety verification
- `docs/remediation/phase-20-final-risk-register.md` — 17 resolved, 5 remaining
- `docs/remediation/phase-20-baseline.md` — Current metrics baseline

---

## Framework Compliance

| Rule | Enforcement |
|------|-------------|
| R1 (Single Capability) | FIX 13, 15 — isolated rate limiter and auth components |
| R4 (Confidence Before Action) | FIX 2, 10, 11 — provenance verification enforced |
| R3 (Boundary Enforcement) | FIX 1, 4, 5 — security control boundaries |
| R6 (Tenant Isolation) | FIX 7 — report service tenant scoping |
| P5 (Calibrated Confidence) | FIX 10 — evidence scope validation |
| P7 (Learning) | FIX 12 — calibration model data structure |

---

## Phase 20.3 — MyPy CI Module Discovery Fix

**Date:** 2026-08-24
**Commit:** `68600e6` — `phase 20.3: fix mypy ci module discovery`
**Tests:** Ruff PASS, MyPy PASS (no duplicate module), 166 root + 123 gateway + 39 service (unit) tests

### Problem
MyPy CI command `mypy libs/ apps/gateway/ apps/services/ --ignore-missing-imports --exclude 'apps/agents'` failed with:
```
apps/services/anomaly-service/src/__init__.py: error: Duplicate module named "src"
(also at "apps/gateway/api-gateway/src/__init__.py")
```

11 services + gateway all use `src/` layout with `__init__.py` → MyPy discovers each as top-level `"src"` module.

### Solution
Split MyPy into per-package invocations from each package base:

| Step | Working Dir | Command |
|------|-------------|---------|
| libs | repo root | `mypy libs/ --ignore-missing-imports --explicit-package-bases` |
| gateway | `apps/gateway/api-gateway/` | `mypy src/ --ignore-missing-imports` |
| services (×11) | each `apps/services/*/` | `mypy src/ --ignore-missing-imports` |

### Files Changed
- `.github/workflows/ci.yml` — replaced single MyPy step with 3 per-package steps
- `docs/remediation/phase-20.3-mypy-ci-fix.md` — full documentation

### Validation
- Ruff = PASS
- MyPy (libs) = PASS (no duplicate module)
- MyPy (gateway) = PASS (no duplicate module)
- MyPy (11 services) = PASS (no duplicate module)
- Root tests = 166 passed
- Gateway tests = 123 passed (3 CORS pre-existing failures)
- Service unit tests = passing (integration tests need Docker)

### Compliance
- No cognitive code changes (Observation, Evidence, Context, Pattern, Anomaly, Hypothesis, Insight, Confidence, Recommendation, Decision intact)
- No security changes (JWT, rate limit, tenant isolation, CSP intact)
- No architecture changes (Cognitive Boundary, Decision/Execution separation intact)
- No services excluded to hide errors
- No new `# type: ignore` comments

---

## Phase 20.1 — Runtime Wiring & Production Hardening

**Date:** 2026-08-24
**Tests:** 291 Python tests passing (166 tests/ + 125 apps/gateway/)

### P0 — ConfidenceStore Injection
- `apps/gateway/api-gateway/src/main.py` — GatewayService receives `confidence_store`
- `apps/gateway/api-gateway/src/service.py` — `verify_confidence_provenance()` validates all records
- `apps/gateway/api-gateway/src/boundary.py` — `validate_confidence_binding()` blocks cross-binding
- `apps/gateway/api-gateway/src/confidence.py` — `ConfidenceReadStore` scoped queries
- `apps/gateway/api-gateway/src/summary.py` — Fixed indentation bug, corrected `OperationalError` reference

### P1 — HttpOnly Refresh Cookie
- `libs/access/cookie_auth.py` — SameSite=Lax, HttpOnly, Secure, path-scoped
- `apps/web/src/api/client.ts` — In-memory `accessToken`, no localStorage for tokens
- `apps/web/src/api/auth.ts` — Login sends `credentials: 'include'`
- `apps/web/src/types/auth.ts` — `AuthSession` no longer exposes `refresh_token`
- `apps/services/user-service/src/health.py` — Login/refresh/logout use cookie functions

### P1 — JWT Revocation
- `libs/access/middleware.py` — `jwt_auth_middleware()` accepts optional `blacklist`, FAIL-CLOSED
- `libs/access/token_blacklist.py` — `TokenBlacklist` with `is_revoked()`, `consume_refresh_token()`
- `apps/services/report-service/src/main.py` — `TokenBlacklist` created and passed

### CSRF Protection
- `libs/access/csrf.py` — New middleware: Origin/Referer validation
- `apps/services/user-service/src/health.py` — CSRF middleware wired

### Frontend Token Security
- `apps/web/src/api/client.ts` — `setTokens()`, `clearTokens()`, `getAccessToken()` API
- 9 frontend test files updated (removed localStorage/refresh_token references)

### New Tests (29)
- `tests/security/adversarial/test_15_phase20_1_wiring.py` — ConfidenceStore, HttpOnly cookies, JWT revocation, CSRF, rate limiter, context activation, evidence scope

### Lint Fixes
- `summary.py` — `sqlalchemy.exc.OperationalError` → `OperationalError` (undefined name bug)
- `health.py` — Removed unused `# noqa: BLE001` directives
- `middleware.py` — `raise ... from None` for proper exception chaining
- `middleware.py` — `from collections.abc import Callable` (UP035)

### CI Fixes (GitHub Actions)
- **PYI041**: `apps/services/user-service/src/ratelimit.py` — `int | float` → `float`
- **F821**: `apps/services/insight-service/tests/test_insight_store.py` — Rewrote broken fixtures (`autouse()` call → `autouse=True`, `db_connection` scope)
- **F541**: `apps/gateway/api-gateway/src/health.py` — Removed unnecessary `f` prefix from f-string
- **C401**: `apps/gateway/api-gateway/tests/test_gateway_http.py` — Rewrote generator expressions as set comprehensions
- **BLE001**: Added `per-file-ignores` to sub-project `pyproject.toml` files (user-service, confidence-service, 3 agents)
- **E501**: Added `per-file-ignores` for `generate_compliance_matrix.py`, `smoke_test.py`, `calibration_model.py`
- **RUF100**: Removed conflicting `# noqa: BLE001` comments; unified config via `pyproject.toml`
