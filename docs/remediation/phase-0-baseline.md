# Phase 0 — Baseline Report

**Date:** 2026-08-23
**Branch:** `main` (HEAD: `0be8241`)
**Status:** Baseline established — no changes applied yet

---

## 1. Environment

| Component | Value |
|-----------|-------|
| Python | 3.14 (system), 3.11 target |
| SQLAlchemy | 2.0.52 |
| FastAPI | 0.141.1 |
| aiohttp | 3.14.3 |
| PostgreSQL | timescale/timescaledb:latest-pg16 (port 5433) |
| Redis | redis:7-alpine (port 6379) |
| Node | 20 (frontend) |

---

## 2. Test Baseline

### 2.1 Per-Service Tests (no DB available — unit/integration hybrid)

| Service | Passed | Errors | Notes |
|---------|--------|--------|-------|
| anomaly-service | 42 | 6 | DB-dependent integration tests fail |
| collector-service | 33 | 6 | Same pattern |
| confidence-service | 35 | 5 | Same pattern |
| context-service | 27 | 6 | Same pattern |
| decision-service | 47 | 6 | Same pattern |
| hypothesis-service | 16 | 6 | Same pattern |
| insight-service | 0 | 1 | NameError: `autouse` not defined in test_insight_store.py |
| pattern-service | 38 | 5 | Same pattern |
| recommendation-service | 30 | 6 | Same pattern |
| report-service | 24 | 6+1 fail | 1 test FAILED, 6 errors |
| user-service | 0 | collection error | Missing `aiohttp_cors` module |

**Summary:** ~300 unit tests pass. Integration tests fail due to no running DB in the test environment. The insight-service has a broken test file.

### 2.2 Frontend Tests

Not executed (npm not available in this env). 26 test files exist in `apps/web/src/`.

---

## 3. Static Analysis

### 3.1 Ruff

```
Found 150 errors (72 auto-fixable)
```

Most errors are `T201` (print statements) in `scripts/qa_seed.py`. Low severity for a seed script.

### 3.2 MyPy (strict mode)

**Critical type errors:**

| File | Error | Severity |
|------|-------|----------|
| `libs/perception/evidence.py:99` | `sessionmaker` overload mismatch with `AsyncEngine` | High |
| `libs/perception/context.py:233` | Same | High |
| `libs/learning/confidence.py:91` | `uuid5` argument: bytes vs str | Medium |
| `libs/learning/confidence.py:242` | `sessionmaker` overload mismatch | High |
| `libs/learning/confidence.py:288` | Unsupported `+` on `TextClause` | Medium |
| `libs/action/report.py:212` | `sessionmaker` overload mismatch | High |
| `libs/action/recommendation.py:190` | Same | High |
| `libs/action/decision.py:222` | Same | High |
| `libs/action/decision.py:384` | `CalibrationParams` not defined | High |
| `libs/access/users.py:150` | `sessionmaker` overload mismatch | High |
| `libs/cognitive_core/observation_bus.py` | Multiple type errors (bytes/str) | High |
| `libs/access/token_blacklist.py:61` | Redis type mismatch | High |

**Pattern:** All stores create their own `sessionmaker(AsyncEngine, AsyncSession)` directly, which mypy doesn't recognize as valid overloads. This is the root cause of ~10 type errors.

### 3.3 Bandit Security Scan

| Severity | Count |
|----------|-------|
| High | 0 |
| Medium | 22 |
| Low | 1464 |

Medium findings: hardcoded tmp dirs in tests, `0.0.0.0` binding, SQL string formatting in `decision.py:329`.

---

## 4. Architecture Compliance Matrix (Phase 0)

| Rule | Implementation | Status |
|------|---------------|--------|
| **P1 — Immutability** | DB triggers enforce immutability on all canonical tables | ✅ Correct |
| **P2 — Explanatory Coherence** | `context.py` activates by coherence competition; MentalModel catalog exists | ✅ Correct |
| **P3 — Stable Concepts** | Each concept has dedicated model + store | ✅ Correct |
| **P4 — Regularity** | Pattern detector exists; Hypothesis generates explanations | ✅ Correct |
| **P5 — Calibrated Confidence** | Confidence is content-addressed, append-only, includes justification | ✅ Correct |
| **P6 — Deliberate Action** | Recommendation ≠ Decision; RBAC enforces authority | ✅ Correct |
| **P7 — Learning** | Decision outcomes submitted via `submit_decision_outcomes` (modeled, not fully implemented) | ⚠️ Partial |
| **R1 — One capability per component** | Each service implements one cognitive capability | ✅ Correct |
| **R2 — Cognitive Contract** | Input → Transformation → Output documented per concept | ✅ Correct |
| **R3 — Boundary enforcement** | Gateway boundary.py validates transitions; rigid successor list | ⚠️ Partial (too rigid) |
| **R4 — Confidence gate** | `validate_confidence_present` accepts `confidence_score` from client | ❌ Vulnerable |
| **R5 — Decision authority** | RBAC with role binding; `authority_id` required | ✅ Correct |
| **R6 — Explanations first-class** | `calibration_justification` stored; hypothesis rationale documented | ✅ Correct |
| **R7 — Architecture guides code** | Framework is read-only; code implements capabilities | ✅ Correct |

---

## 5. Risk Register

| ID | Severity | Component | Current Behavior | Expected Behavior | Framework Rule | Evidence | Fix |
|----|----------|-----------|------------------|-------------------|---------------|----------|-----|
| R-001 | **P0** | Token blacklist | `is_revoked` returns `False` on Redis failure (fail-open) | Security-critical operations must fail-closed | Security | `token_blacklist.py:98` | Phase 3 |
| R-002 | **P0** | Refresh token rotation | Non-atomic check-then-revoke pattern | Atomic consume-once | Security | User-service login flow | Phase 3 |
| R-003 | **P0** | Confidence gate | Client can send `confidence_score=0.99999` and bypass calibration | Must verify against DB-stored confidence | R4 | `boundary.py:72-73` | Phase 2 |
| R-004 | **P0** | Rate limiting | No rate limiter present | Atomic distributed rate limiting | Security | No `ratelimit.py` found | Phase 4 |
| R-005 | **P1** | Context activation | Non-atomic INSERT + DEACTIVATE (two commits) | Single transaction; DB UNIQUE constraint | P2 | `context.py:258-270` | Phase 5 |
| R-006 | **P1** | Context ID | Hashes only `tenant:purpose:evidence_ids` | Must include `mental_model_id`, `coherence_score`, `competing_models` | R2/P3 | `context.py:115-124` | Phase 6 |
| R-007 | **P1** | Confidence evidence scope | Hypothesis confidence may use all-tenant evidence | Must use hypothesis-scoped evidence only | P4/P5 | `calibrator.py` | Phase 7 |
| R-008 | **P1** | DB engines | Each store creates private `create_async_engine` | Shared engine per process | Architecture | Every `*Store.__init__` | Phase 8 |
| R-009 | **P1** | Concurrency | No bounds on parallel tenant processing | Bounded concurrency (semaphore/pool) | Scalability | Service loops | Phase 9 |
| R-010 | **P1** | Cognitive boundary | Rigid CANONICAL_FLOW dict (direct successor only) | Declarative policy allowing cycles/branches | R3/Framework | `boundary.py:17-27` | Phase 10 |
| R-011 | **P1** | Decision/Execution | Decision contemplates execution authority | Separate Decision from Action Executor | P6 | `boundary.py` ACTIONS set | Phase 11 |
| R-012 | **P1** | Tenant scoping | Some queries lack explicit `tenant_id` filter | Every store query must scope by tenant | Security | Various stores | Phase 12 |
| R-013 | **P1** | Frontend tokens | Stored in localStorage (accessible to XSS) | HttpOnly/Secure cookies | Security | Frontend auth code | Phase 13 |
| R-014 | **P2** | CSP | `unsafe-inline` and `unsafe-eval` in default CSP | Stricter CSP | Security | `security_headers.py:24-32` | Phase 14 |
| R-015 | **P2** | CI/CD | `mypy` and `bandit` use `continue-on-error: true` | Critical checks must block CI | CI | `ci.yml:40,60` | Phase 15 |
| R-016 | **P2** | Docker | No integration test environment | Integration smoke tests | CI/Docker | No integration tests | Phase 16 |
| R-017 | **P2** | Architecture tests | No executable invariant tests | `tests/architecture/` with framework rule tests | R7 | None exist | Phase 17 |
| R-018 | **P2** | Observability | No structured tracing correlation | X-Request-ID, trace_id, tenant_id in logs | Observability | No tracing middleware | Phase 18 |
| R-019 | **P3** | Learning | Decision outcomes modeled but not feeding calibration | Outcome → calibration update loop | P7 | No feedback loop | Phase 19 |

---

## 6. Files Requiring Changes (by phase)

### Phase 1 — Multi-Tenant Security
- `apps/gateway/api-gateway/src/health.py`
- `apps/gateway/api-gateway/src/service.py`
- `libs/access/rbac.py`
- New: `libs/access/tenant_scope.py`

### Phase 2 — Confidence Provenance
- `apps/gateway/api-gateway/src/boundary.py`
- `libs/learning/confidence.py`
- `apps/gateway/api-gateway/src/confidence.py`

### Phase 3 — JWT/Token Security
- `libs/access/token_blacklist.py`
- `apps/user-service/src/service.py`
- `apps/gateway/api-gateway/src/service.py`

### Phase 4 — Rate Limiter
- New: `libs/access/ratelimit.py`

### Phase 5 — Context Activation
- `libs/perception/context.py`
- `infrastructure/docker/init-sql/01-schema.sql`

### Phase 6 — Context Deterministic ID
- `libs/perception/context.py`

### Phase 7 — Confidence Evidence Scope
- `libs/reasoning/calibrator.py` or equivalent

### Phase 8 — DB Architecture
- `libs/shared/db.py`
- All `*Store.__init__` classes

### Phase 9 — Bounded Concurrency
- Service main files

### Phase 10 — Cognitive Boundary 2.0
- `apps/gateway/api-gateway/src/boundary.py`
- `apps/gateway/api-gateway/src/constants.py`

### Phase 11 — Decision/Execution Separation
- `apps/gateway/api-gateway/src/boundary.py`

### Phase 12 — Tenant Scoping
- All store files with SQL queries

### Phase 13 — Frontend Security
- `apps/web/src/` auth-related files

### Phase 14 — CSP
- `libs/shared/security_headers.py`

### Phase 15 — CI/CD
- `.github/workflows/ci.yml`

### Phase 17 — Architecture Tests
- New: `tests/architecture/`

---

## 7. Baseline Conclusion

The codebase demonstrates strong cognitive architecture compliance (P1-P7, R1-R7) with well-designed DB triggers and concept separation. The critical gaps are:

1. **Security P0:** Token blacklist fail-open, no confidence provenance verification, no rate limiting
2. **Architecture P1:** Context activation non-atomic, context ID incomplete, DB engine fragmentation
3. **CI P2:** Critical checks hidden behind `continue-on-error`

No blocking regressions found. The ~300 passing unit tests provide a safety net for remediation.
