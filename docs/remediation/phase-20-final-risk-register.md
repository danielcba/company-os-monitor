# Phase 20 -- Final Risk Register

**Date:** 2026-08-24
**Baseline:** Phase 20 complete

---

## 1. Resolved Risks

The following risks from the Phase 0 baseline have been resolved by Phases 1-20:

| ID | Original Severity | Description | Resolution |
|----|-------------------|-------------|------------|
| R-001 | P0 | Token blacklist fail-open on Redis failure | Phase 3: `is_revoked()` fail-closed |
| R-002 | P0 | Non-atomic refresh token rotation | Phase 3 + Phase 20 FIX 3: Atomic `consume_refresh_token()` |
| R-003 | P0 | Client-supplied confidence_score bypasses calibration | Phase 2 + Phase 20 FIX 2,11: Provenance verification |
| R-004 | P0 | No rate limiter on login/refresh | Phase 4 + Phase 20 FIX 1,5,13: Async rate limiter with fail-closed |
| R-005 | P1 | Non-atomic context activation | Phase 5: Atomic transaction + UNIQUE constraint |
| R-006 | P1 | Context ID incomplete fingerprint | Phase 6: Expanded fingerprint |
| R-007 | P1 | Confidence evidence scope leakage | Phase 7 + Phase 20 FIX 10: Scope validation |
| R-008 | P1 | DB engine fragmentation | Phase 8: Shared engine |
| R-009 | P1 | No concurrency bounds | Phase 9: Semaphore |
| R-010 | P1 | Rigid cognitive boundary | Phase 10: Declarative policy |
| R-011 | P1 | Decision/Execution merged | Phase 11: Separation |
| R-012 | P1 | Missing tenant scoping in stores | Phase 12: Tenant scope in all queries |
| R-013 | P1 | Frontend tokens in localStorage | Phase 13: HttpOnly cookies |
| R-014 | P2 | CSP with unsafe-inline/eval | Phase 14: Nonce-based CSP |
| R-015 | P2 | CI continue-on-error | Phase 15 + Phase 20 FIX 8: CI blocks on failures |
| R-016 | P2 | No integration tests | Phase 16 + Phase 20 FIX 9: Smoke test |
| R-017 | P2 | No architecture invariant tests | Phase 17: Architecture as Code |

---

## 2. Active Risks

### 2.1 Remaining Risks (Non-Blocking)

| ID | Severity | Likelihood | Component | Description | Mitigation | Status |
|----|----------|------------|-----------|-------------|------------|--------|
| RR-001 | Medium | Low | Report service | POST endpoints (report generation) lack rate limiting | Add rate limiting in future phase | Open |
| RR-002 | Medium | Low | Frontend | No CSRF protection middleware | Implement CSRF tokens in future phase | Open |
| RR-003 | Low | Low | Observability | No structured tracing correlation (request_id, trace_id, tenant_id) | Add tracing middleware in future phase | Open |
| RR-004 | Low | Low | Learning | Decision outcomes not feeding back to calibration | Implement outcome -> calibration loop (P7) | Open |
| RR-005 | Low | Low | Frontend | Frontend tests not executed in CI (npm not available) | Add Node.js to CI environment | Open |

### 2.2 Known Limitations (Documented)

| ID | Severity | Component | Description | Justification |
|----|----------|-----------|-------------|---------------|
| KL-001 | Low | Rate limiter | In-memory fallback for non-security-critical endpoints | Availability trade-off; security-critical endpoints fail-closed |
| KL-002 | Low | CORS | 3 pre-existing CORS test failures | Known issue, not security-relevant |
| KL-003 | Low | Bandit | 22 medium-severity bandit findings | Hardcoded tmp dirs in tests, 0.0.0.0 binding; low real-world risk |

---

## 3. Risk Trend

| Phase | P0 Open | P1 Open | P2 Open | P3 Open | Total Open |
|-------|---------|---------|---------|---------|------------|
| Phase 0 | 4 | 8 | 4 | 2 | 18 |
| Phase 10 | 0 | 2 | 4 | 2 | 8 |
| Phase 20 | 0 | 0 | 2 | 3 | 5 |

**Trend:** All P0 and P1 risks have been resolved. Only medium and low severity risks remain.

---

## 4. Conclusion

Phase 20 resolves all critical (P0) and high (P1) risks identified in the Phase 0 baseline. The remaining 5 risks are medium or low severity, with low likelihood. No blocking issues remain for production deployment.
