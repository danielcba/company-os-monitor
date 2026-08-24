# Current Risk Register

**Date:** 2026-08-23
**Baseline:** Phase 0

---

## P0 — Critical (must fix before any release)

| ID | Component | Description | Framework Rule | Evidence |
|----|-----------|-------------|---------------|----------|
| R-001 | Token blacklist | `is_revoked` returns `False` on Redis failure (fail-open) | Security: fail-closed for auth operations | `libs/access/token_blacklist.py:98` |
| R-002 | Refresh token rotation | Non-atomic check-then-revoke pattern allows race condition | Security: atomic token rotation | User-service login flow |
| R-003 | Confidence gate | Client can send arbitrary `confidence_score` to bypass calibration | R4: confidence must be verified against stored calibrated value | `apps/gateway/api-gateway/src/boundary.py:72-73` |
| R-004 | Rate limiting | No rate limiter on login/refresh/action endpoints | Security: brute-force protection | No ratelimit implementation found |

## P1 — High (must fix before production)

| ID | Component | Description | Framework Rule | Evidence |
|----|-----------|-------------|---------------|----------|
| R-005 | Context activation | Non-atomic INSERT + DEACTIVATE (two commits) can leave 0 active or 2 active | P2: one active context per purpose | `libs/perception/context.py:258-270` |
| R-006 | Context ID | Hashes only `tenant:purpose:evidence_ids`; different mental models can collide | R2/P3: deterministic ID must cover all semantic content | `libs/perception/context.py:115-124` |
| R-007 | Confidence evidence scope | Calibrator may use all-tenant evidence instead of hypothesis-scoped evidence | P4/P5: confidence scoped to judgment | `libs/reasoning/calibrator.py` |
| R-008 | DB engine fragmentation | Each store creates private `create_async_engine` (12+ engines) | Architecture: shared pool | Every `*Store.__init__` |
| R-009 | Concurrency | No bounds on parallel tenant processing | Scalability: resource exhaustion | Service main loops |
| R-010 | Cognitive boundary | Rigid CANONICAL_FLOW dict (direct successor only) contradicts Framework | R3: boundary allows legitimate cycles | `apps/gateway/api-gateway/src/boundary.py:17-27` |
| R-011 | Decision/Execution | Decision contemplates execution authority in boundary | P6: Decision ≠ Action Executor | `boundary.py` ACTIONS set |
| R-012 | Tenant scoping | Some store queries may lack explicit `tenant_id` filter | Security: multi-tenant isolation | Various stores |
| R-013 | Frontend tokens | Stored in localStorage (accessible to XSS) | Security: token theft prevention | Frontend auth code |

## P2 — Medium (should fix before production)

| ID | Component | Description | Framework Rule | Evidence |
|----|-----------|-------------|---------------|----------|
| R-014 | CSP headers | `unsafe-inline` and `unsafe-eval` in default CSP | Security: XSS mitigation | `libs/shared/security_headers.py:24-32` |
| R-015 | CI/CD | `mypy` and `bandit` use `continue-on-error: true` — CI is green with failures | CI: critical checks must block | `.github/workflows/ci.yml:40,60` |
| R-016 | Docker/integration | No integration test environment exists | CI: smoke tests needed | No integration tests |
| R-017 | Architecture tests | No executable invariant tests for framework rules | R7: architecture must be testable | None exist |

## P3 — Low (improve when possible)

| ID | Component | Description | Framework Rule | Evidence |
|----|-----------|-------------|---------------|----------|
| R-018 | Observability | No structured tracing correlation (request_id, trace_id, tenant_id) | Observability: distributed tracing | No tracing middleware |
| R-019 | Learning | Decision outcomes not feeding back to calibration | P7: learning through outcome | No feedback loop |
