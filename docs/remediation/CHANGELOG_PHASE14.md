# CHANGELOG_PHASE14.md

## Company OS Monitor — Changelog

All notable changes from the 19-phase remediation are documented here.

---

## [1.0.0] - 2026-08-22

### Added

#### Phase 1 — Multi-Tenant Security (R6)
- `libs/access/tenant_scope.py`: AuthorizationContext abstraction
- Cross-tenant security tests in `test_gateway_service.py`

#### Phase 2 — Confidence Provenance (R5)
- `ConfidenceStoreAdapter` protocol for store-agnostic confidence lookup
- `validate_confidence_binding()` async function for DB verification
- Updated `GatewayService` with `confidence_store` parameter

#### Phase 3 — JWT/Token Security
- `is_revoked()` now fail-closed (raises `SecurityControlUnavailable`)
- `is_revoked_non_critical()` for fail-open (metrics/health)
- `consume_refresh_token()` using Redis `SET NX EX` for atomic consume-once

#### Phase 4 — Rate Limiter (P6)
- Atomic Lua script for sliding window
- Async API (`await limiter.is_allowed(key)`)

#### Phase 5 — Context Activation Atomicity (P2)
- Atomic INSERT+DEACTIVATE in single transaction
- UNIQUE partial index migration

#### Phase 6 — Context Deterministic ID (P2)
- Expanded fingerprint to include `mental_model_id`, `coherence_score`, `competing_models`

#### Phase 7 — Confidence Evidence Scope (P1)
- `evidence_ids` field in Confidence model
- `validate_confidence_evidence_scope()` function
- Migration for evidence_ids column

#### Phase 8 — DB Architecture
- Enhanced `libs/shared/db.py` with full pool configuration
- Added `pool_timeout`, `pool_recycle`, `statement_timeout` parameters

#### Phase 9 — Bounded Concurrency (P1)
- `libs/shared/concurrency.py`: `BoundedTenantProcessor` with semaphore
- Configuration: `MAX_CONCURRENT_TENANTS`, `MAX_BATCH_SIZE`

#### Phase 10 — Cognitive Boundary 2.0 (P1)
- `apps/gateway/api-gateway/src/capability_policy.py`: Declarative capability policies
- Separated: capability transition, boundary protection, confidence gate, authority

#### Phase 11 — Decision/Execution Separation (P1)
- `libs/action/executor.py`: ActionExecutor protocol
- `validate_no_direct_execution()`: Observation/Reasoning never execute
- `validate_execution_authorization()`: Execution requires superadmin

#### Phase 12 — Tenant Scoping de Todos los Stores (P1)
- Added `tenant_id` to `SELECT_LATEST_BY_TARGET` (confidence)
- Added `tenant_id` to `SET_CONTEXT_ACTIVE` (context)
- Added `tenant_id` to `update_outcomes()` (decision)

#### Phase 13 — Security of Frontend (P1)
- `libs/access/cookie_auth.py`: HttpOnly cookie-based token storage
- Design document for migration strategy

#### Phase 14 — CSP/Security Headers
- Per-request nonce generation for script-src
- `X-CSP-Nonce` header for frontend
- Removed `unsafe-inline` and `unsafe-eval` from script-src

#### Phase 15 — CI/CD Hardening
- Removed `continue-on-error: true` from mypy and bandit
- Removed Docker build `continue-on-error: true`

#### Phase 16 — Docker/Deployment Real Validation (P2)
- `tests/smoke/smoke_test.py`: End-to-end smoke test script

#### Phase 17 — Architecture as Code
- `tests/architecture/test_cognitive_invariants.py`: 12 invariant tests
- `tests/gateway/test_capability_policy.py`: 19 policy tests

#### Phase 18 — Observability/Correlation (P2)
- `libs/shared/structured_logging.py`: Structured logging with sanitization
- Sensitive data redaction (passwords, tokens, secrets)

#### Phase 19 — Learning/P7 (P3)
- `docs/learning/learning-pipeline-status.md`: P7 status documentation
- `tests/learning/test_learning_pipeline.py`: Comparison function tests

### Changed

- `apps/gateway/api-gateway/src/service.py`: Refactored to use AuthorizationContext
- `apps/gateway/api-gateway/src/boundary.py`: Added ConfidenceStoreAdapter protocol
- `libs/access/token_blacklist.py`: Rewritten with fail-closed and atomic rotation
- `libs/perception/context.py`: Atomic activation, deterministic ID, tenant scoping
- `libs/shared/db.py`: Enhanced with full pool configuration
- `libs/shared/security_headers.py`: Hardened CSP with nonce
- `libs/learning/confidence.py`: Added evidence_ids, tenant scoping
- `libs/action/decision.py`: Added tenant_id to update_outcomes
- `.github/workflows/ci.yml`: Removed continue-on-error

### Fixed

- Multi-tenant isolation bypass in gateway service
- Confidence score fabrication vulnerability
- JWT revocation fail-open security issue
- Refresh token race condition
- Context activation race condition
- Missing tenant_id in SQL queries
- CSP unsafe-inline/eval vulnerabilities
- CI/CD hiding security failures
