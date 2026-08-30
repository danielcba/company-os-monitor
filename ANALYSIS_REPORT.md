# HISTORICAL RECORD — Pre-Remediation Analysis (2026-08-23)

> **Note:** This report reflects the state before the 19-phase remediation. Some findings have been addressed. For current status, see `state/project-state.md`.

# Comprehensive Architecture & Security Analysis Report
## Company OS Monitor — All Phases (1 through Latest)

**Generated:** 2026-08-23  
**Analyzer:** opencode agent  
**Scope:** Full platform — Framework alignment, backend services, frontend, database, infrastructure, CI/CD

---

## Executive Summary

The Company OS Monitor platform demonstrates **strong architectural alignment** with the Company OS Cognitive Architecture Framework (P1-P7, R1-R7, ADR-0001, ADR-0002). The canonical cognitive pipeline (Reality → Decision) is faithfully implemented as immutable, append-only services with proper Cognitive Contracts.

**Overall Risk Level: MODERATE** — No critical cognitive architecture violations, but significant operational, security, and scalability gaps exist in the external/non-canonical layer (auth, gateway, reporting, deployment).

---

## Findings by Category

### 🔴 CRITICAL (Immediate Action Required)

| # | Finding | Component | Impact | Evidence |
|---|---------|-----------|--------|----------|
| C1 | **No JWT refresh token revocation** | `user-service`, `api-gateway` | Token theft = permanent access until expiry (7 days); no logout enforcement | `.env.example` lines 165-166: stateless JWT strategy, no Redis token store |
| C2 | **Report service endpoints unauthenticated (standalone)** | `report-service` | Direct access to report generation/reading bypasses Cognitive Boundary (R3) | `report-service/src/health.py`: no auth middleware; runs on port 8098 |
| C3 | **In-memory rate limiting only** | `user-service`, `api-gateway` | DoS vulnerability; no distributed protection | `user-service/src/health.py`: `RateLimiter` in-memory; gateway has no rate limiting |
| C4 | **Hardcoded localhost service health URLs in gateway** | `api-gateway` | Deployment to K8s/cloud will fail health checks | `api-gateway/src/health.py`: `DEFAULT_SERVICE_HEALTH` assumes localhost:port |

### 🟠 HIGH (Fix Before Production)

| # | Finding | Component | Impact | Evidence |
|---|---------|-----------|--------|----------|
| H1 | **Sequential tenant processing in all canonical services** | `pattern`, `anomaly`, `hypothesis`, `insight`, `recommendation`, `decision`, `context`, `confidence` | O(n) latency per cycle; cannot scale to 100+ tenants | All service.py: `for tenant_id in tenant_ids:` loops without `asyncio.gather` |
| H2 | **N+1 query in recommendation service** | `recommendation-service` | DB load explosion with many hypotheses | `service.py`: `get_confidence()` called per hypothesis in loop |
| H3 | **Full dataset reload every cycle** | All canonical services | Memory/DB pressure; redundant reads | Each cycle calls `list_*()` for all tenants |
| H4 | **Duplicate GracefulShutdown implementation** | `confidence-service` vs `libs/shared/graceful_shutdown.py` | Maintenance burden; inconsistent behavior | `confidence-service/src/main.py` defines custom `GracefulShutdown` |
| H5 | **No circuit breakers on DB calls** | All services | Cascade failures under DB load | No retry/timeout/circuit-breaker pattern in store classes |
| H6 | **No distributed tracing / correlation IDs** | All services | Debugging distributed flows impossible | No OpenTelemetry; no request IDs propagated |
| H7 | **Report service writes to local filesystem** | `report-service` | Not cloud-native; data loss on container restart | `REPORT_OUTPUT_DIR=reports` in `.env.example` line 137 |
| H8 | **Procedural memory thresholds hardcoded in env (no hot reload)** | `anomaly`, `collector`, `decision` | Config changes require restart; no audit of changes | `.env.example` lines 62-66, 23-32, 122-123 |

### 🟡 MEDIUM (Technical Debt)

| # | Finding | Component | Impact |
|---|---------|-----------|--------|
| M1 | **Collector service lacks `service.py`** | `collector-service` | Inconsistent architecture; logic in `consumer.py` |
| M2 | **Inconsistent cycle env var naming** | `pattern-service` (`DETECTION_CYCLE_SECONDS` vs `*_CYCLE_SECONDS`) | Confusion; maintenance risk |
| M3 | **API Gateway `service.py` is a god object (466 lines)** | `api-gateway` | Hard to maintain; violates SRP |
| M4 | **FacetsCache in-memory only (not distributed)** | `libs/shared/facets_cache.py` | Stale facets in multi-instance deployments |
| M5 | **No request timeouts on httpx client (gateway → services)** | `api-gateway` | Hanging requests under load |
| M6 | **Health checks only verify error count, not DB latency** | All services | False healthy under slow DB |
| M7 | **Collector in-memory pending buffer unbounded risk** | `collector-service/consumer.py` | OOM if organizer errors persist |
| M8 | **Insight service non-competitive frame counter unused** | `insight-service` | Dead code / incomplete feature |
| M9 | **Frontend: No CSP headers, no security.txt** | `apps/web` | XSS risk; no vulnerability reporting |
| M10 | **Frontend: Tokens in localStorage (XSS accessible)** | `apps/web/src/api/client.ts` | Token theft via XSS |
| M11 | **Spanish strings in rationale functions** | `libs/reasoning/anomaly.py` | Inconsistent with English framework |
| M12 | **Product lacks `state/project-state.md` (E4 violation)** | Product repo | Cannot recover product state independently |

### 🟢 LOW (Improvements)

| # | Finding | Component | Impact |
|---|---------|-----------|--------|
| L1 | **No OpenAPI/Swagger spec generation** | All services | Manual API contract maintenance |
| L2 | **No chaos engineering tests** | All | Unknown failure modes |
| L3 | **Docker Compose lacks service definitions** | Infrastructure | No single-command full stack |
| L4 | **No service mesh / mTLS between services** | Infrastructure | Plaintext internal traffic |
| L5 | **Frontend: No automated a11y testing** | `apps/web` | Accessibility regressions |
| L6 | **Frontend: No visual regression testing** | `apps/web` | UI drift |
| L7 | **Agents only linux-agent implemented** | `apps/agents/` | Windows/VMware agents missing |
| L8 | **Mental model coherence evaluation is declarative placeholder** | `context.py`, `calibration_model.py` | True Thagard-style coherence not implemented |
| L9 | **Hypothesis generation: abductive inference not formalized** | `hypothesis_templates.py` + `lm_studio` | Framework notes as future work |
| L10 | **Insight restructuring not automated** | `insight_rules.py` | Frame-switching mechanism missing |

---

## Security Vulnerabilities Detail

### Authentication & Authorization

| Vulnerability | Severity | Location | Remediation |
|--------------|----------|----------|-------------|
| Stateless JWT without revocation | CRITICAL | `user-service/src/auth/security.py` | Add Redis token blacklist; implement logout endpoint that revokes |
| No refresh token rotation | HIGH | `user-service/src/auth/security.py` | Rotate refresh tokens; detect reuse |
| In-memory rate limiter | CRITICAL | `user-service/src/health.py` | Use Redis-backed sliding window |
| No password complexity policy | MEDIUM | `user-service/src/service.py` | Enforce minimum entropy |
| No account lockout on failed attempts | MEDIUM | `user-service/src/service.py` | Track failed logins; exponential backoff |
| CORS from env without validation | MEDIUM | `user-service/src/health.py`, `api-gateway/src/health.py` | Validate origins against allowlist |
| No security headers (HSTS, CSP, X-Frame-Options) | MEDIUM | `api-gateway`, `report-service` | Add middleware |
| Report service unauthenticated | CRITICAL | `report-service/src/health.py` | Add JWT validation middleware |
| Default passwords in `.env.example` | HIGH | `.env.example` lines 142-143, 150-151 | Remove defaults; require secrets manager |

### Data Protection

| Vulnerability | Severity | Location | Remediation |
|--------------|----------|----------|-------------|
| Passwords in `.env.example` (WinRM, vCenter) | HIGH | `.env.example` lines 140-151 | Use secrets manager; remove from example |
| JWT secret default in `.env.example` | CRITICAL | `.env.example` line 163 | Generate unique per deployment; use RS256 in prod |
| No encryption at rest for PostgreSQL | MEDIUM | Infrastructure | Enable TimescaleDB transparent encryption |
| No TLS between services | MEDIUM | Infrastructure | Deploy service mesh (Istio/Linkerd) or mTLS |
| Audit log includes IP/user-agent (PII) | LOW | `audit_log` table | Pseudonymize or document retention |

### Frontend Security

| Vulnerability | Severity | Location | Remediation |
|--------------|----------|----------|-------------|
| Tokens in localStorage | HIGH | `apps/web/src/api/client.ts` lines 8-17 | Use httpOnly cookies; implement silent refresh |
| No Content Security Policy | MEDIUM | `apps/web/index.html` | Add CSP meta tag or server header |
| No X-Frame-Options | MEDIUM | Gateway/Reverse proxy | Add `X-Frame-Options: DENY` |
| No Referrer-Policy | LOW | Gateway | Add `Referrer-Policy: strict-origin-when-cross-origin` |

---

## Architecture Errors & Alignment Issues

### Cognitive Architecture (Framework P1-P7, R1-R7)

**✅ CORRECTLY IMPLEMENTED:**
- P1: Immutability enforced via DB triggers on all canonical tables
- P2: Context activation via coherence competition with competing models recorded
- P3: Stable concepts in `libs/*`; transformations in `build_*()` functions
- P4: Pattern (regularity) separated from Hypothesis (explanation); Anomaly = deviation
- P5: Full Calibration Model (S + C + ECE) with deterministic content-addressed IDs
- P6: Recommendation ≠ Decision; advisory vs committed; boundary enforces
- R1: 1:1 mapping of libs/services to cognitive capabilities
- R2: Every model has `*Create`, `build_*()`, frozen output
- R3: Gateway `boundary.py` enforces `CANONICAL_FLOW`, validates confidence for actions
- R4: `boundary.py` `CONFIDENCE_REQUIRED_ACTIONS = {"propose", "commit"}`
- R5: Decision records `expected_outcomes` (falsifiable), `authority_id`, `rationale`
- R6: Every layer produces explanation (`description`, `justification`, `rationale`)
- R7: Framework read-only; product references canonical docs

**⚠️ GAPS (Acknowledged by Framework as Future Work):**
- P7 (Learning): Memory layer not operational; no automated outcome comparison → calibration improvement
- Mental model coherence: Declarative placeholder only (`context.py` templates, `calibration_model.py` simplified)
- Abductive inference: Templates + LM Studio only; mechanisms not formalized
- Insight frame-switching: Rules exist but not automatically triggered

### Database Architecture

**✅ STRENGTHS:**
- TimescaleDB hypertables for `observations` (daily chunks) and `audit_log` (monthly)
- Comprehensive immutability triggers on all canonical tables
- Tenant-scoped indexes on all major tables
- Deterministic IDs for idempotent dedup (Evidence, Context, Pattern, Confidence)
- Proper FK cascades (tenant delete → cascade)

**⚠️ CONCERNS:**
- `observations` PK is `(id, captured_at)` — composite PK may impact join performance
- `anomalies.pattern_id` is `ON DELETE SET NULL` but `anomaly` requires `pattern_id` (NOT NULL in model) — potential FK violation
- No partitioning strategy for `confidence_scores` (high write volume expected)
- `alert_rules` and `servers` mutable by design — correct but document why

---

## Scalability & Performance Bottlenecks

### Service-Level

| Service | Bottleneck | Projected Limit | Fix |
|---------|------------|-----------------|-----|
| Collector | Single consumer instance; in-memory buffer | ~10k obs/min | Consumer groups; backpressure; persistent buffer |
| Context | Sequential tenant + purpose iteration | ~50 tenants | `asyncio.gather` per tenant; filter purposes with evidence |
| Pattern | Full context reload per tenant per cycle | ~20 tenants | Incremental detection; materialized views |
| Anomaly | Full pattern/context reload; 5 env thresholds | ~20 tenants | Incremental; hot-reload config |
| Hypothesis | Nested loops (tenant → anomaly → context) | ~10 tenants | Parallelize; batch loads |
| Confidence | Per-tenant evidence/context reload | ~30 tenants | Batch loads; materialized support scores |
| Recommendation | N+1 confidence fetch per hypothesis | ~50 hypotheses | Batch fetch confidences |
| Decision | Loads all recommendations + confidences | ~100 recs/tenant | Paginate; filter by confidence threshold early |
| Gateway | Sequential health checks; no timeout | 12 services | Parallel health checks; configurable timeout |

### Database

| Table | Growth Rate | Risk | Mitigation |
|-------|-------------|------|------------|
| `observations` | High (per agent per minute) | Hypertable chunk management | Tiered storage; compression policies |
| `audit_log` | High (every cognitive event) | Hypertable chunk management | Same as observations |
| `confidence_scores` | Medium (per judgment) | No partitioning | Add partition by `computed_at` |
| `evidence` | Medium | Index bloat | Regular `REINDEX`; partition by tenant? |

---

## Concurrency & Race Conditions

| Risk | Location | Scenario | Likelihood |
|------|----------|----------|------------|
| Duplicate Evidence creation | `libs/perception/evidence.py` `build_evidence()` | Two organizer cycles same window | LOW (deterministic ID) |
| Context activation race | `libs/perception/context.py` `activate_context()` | Two cycles same purpose | LOW (deterministic ID + `is_active` flag) |
| Confidence calibration race | `libs/learning/confidence.py` | Two calibrations same target | LOW (content-addressed ID) |
| Decision double-commit | `libs/action/decision.py` | Two committers same recommendation | MEDIUM (no row-level lock) |
| JWT refresh token reuse | `user-service` | Stolen refresh token used twice | HIGH (stateless, no revocation) |
| Report generation race | `report-service` | Two cycles same period | LOW (deterministic ID) |

---

## Remediation Plan (Prioritized)

### Phase 1: Critical Security (Week 1-2)

| Task | Owner | Effort | Dependencies |
|------|-------|--------|--------------|
| Implement Redis-backed JWT refresh token revocation | Backend | 3 days | Redis cluster |
| Add auth middleware to report-service | Backend | 1 day | Shared `apiFetch` pattern |
| Implement distributed rate limiting (Redis) | Backend | 2 days | Redis cluster |
| Replace hardcoded gateway health URLs with service discovery | Backend | 2 days | Consul/etcd or DNS |
| Remove default secrets from `.env.example` | DevOps | 0.5 days | — |
| Add security headers middleware to gateway | Backend | 1 day | — |

### Phase 2: Scalability & Reliability (Week 3-5)

| Task | Owner | Effort | Dependencies |
|------|-------|--------|--------------|
| Parallelize tenant processing in all canonical services | Backend | 5 days | — |
| Fix N+1 query in recommendation service (batch confidence fetch) | Backend | 2 days | — |
| Implement circuit breakers on DB calls (all services) | Backend | 3 days | — |
| Add distributed tracing (OpenTelemetry) | Backend | 4 days | Jaeger/Tempo |
| Add request timeouts + correlation IDs | Backend | 2 days | — |
| Unify GracefulShutdown implementation | Backend | 1 day | — |
| Add backpressure to collector Redis consumption | Backend | 2 days | — |

### Phase 3: Operational Excellence (Week 6-8)

| Task | Owner | Effort | Dependencies |
|------|-------|--------|--------------|
| Cloud-native report storage (S3/GCS) | Backend | 3 days | S3 bucket |
| Hot-reload for procedural memory thresholds | Backend | 3 days | File watcher / Consul |
| Refactor gateway `service.py` into route modules | Backend | 4 days | — |
| Add DB latency to health checks | Backend | 1 day | — |
| Product `state/project-state.md` for E4 compliance | PM | 1 day | — |
| CI/CD pipeline with security scanning | DevOps | 5 days | GitHub Actions / GitLab CI |
| OpenAPI spec generation from Pydantic | Backend | 3 days | — |

### Phase 4: Cognitive Completeness (Ongoing)

| Task | Owner | Effort | Dependencies |
|------|-------|--------|--------------|
| Operationalize Memory layer (P7) | Research | Large | Framework Phase 3 |
| Formalize mental model coherence evaluation | Research | Large | Framework Phase 2 |
| Implement abductive inference mechanisms | Research | Large | Framework Phase 2 |
| Automate insight frame-switching | Backend | Medium | Insight service |
| Windows/VMware agents | Backend | Medium | Agent framework |

---

## Framework Alignment Verification Summary

| Area | Status | Notes |
|------|--------|-------|
| **Cognitive Principles (P1-P7)** | ✅ 6/7 Full, 1/7 Planned | P7 Memory not operational (acknowledged) |
| **Design Rules (R1-R7)** | ✅ 7/7 Compliant | All enforced in code + DB |
| **Core Concepts (10)** | ✅ 10/10 Aligned | All with proper Cognitive Contracts |
| **ADR-0001 (OS is Brain)** | ✅ Compliant | Canonical flow is product brain |
| **ADR-0002 (Product Scope)** | ✅ Compliant | External capabilities labeled |
| **Engineering Rules (E1-E6)** | 🟡 5/6 | E4: Product lacks `state/project-state.md` |
| **Current Phase** | Framework: Phase 2 | Product ahead: implemented component specs (Phase 3 work) |

---

## Recommended Journal Entry

```markdown
# 2026-08-23 — Architecture & Security Analysis Complete

## Summary
Comprehensive analysis of all phases (1 through latest) completed. Platform shows strong cognitive architecture alignment (P1-P7, R1-R7, ADR-0001/0002) with 10/10 core concepts properly implemented.

## Critical Findings
- **4 Critical**: JWT revocation, report service auth, rate limiting, gateway service discovery
- **8 High**: Sequential processing, N+1 queries, full reloads, duplicate shutdown, no circuit breakers, no tracing, local FS reports, no hot reload
- **12 Medium**: Architecture inconsistencies, god objects, in-memory caches, frontend security gaps
- **10 Low**: Observability, CI/CD, agents, cognitive completeness

## Remediation Plan
4-phase plan created: Critical Security (2 weeks) → Scalability (3 weeks) → Operations (3 weeks) → Cognitive Completeness (ongoing).

## Framework Alignment
Product correctly implements canonical flow. Primary gap: Memory layer (P7) not operational — acknowledged as planned work per ADR-0002 and framework Phase 2 status.

## Next Actions
1. Begin Phase 1 critical security fixes
2. Create `state/project-state.md` for product repo (E4)
3. Schedule architecture review for Phase 2 scalability work
```

---

## GitHub Actions Recommended

```yaml
# .github/workflows/ci.yml (recommended)
name: CI
on: [push, pull_request]
jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Setup Python
        uses: actions/setup-python@v5
        with: { python-version: '3.11' }
      - name: Install deps
        run: pip install -e ".[dev]"
      - name: Ruff lint
        run: ruff check .
      - name: MyPy typecheck
        run: mypy .
      - name: PyTest
        run: pytest --cov=libs --cov=apps
      - name: Frontend lint/typecheck/test
        working-directory: apps/web
        run: |
          npm ci
          npm run lint
          npm run typecheck
          npm run test
      - name: Security scan
        run: |
          pip install bandit safety
          bandit -r apps/ libs/
          safety check
      - name: Docker build test
        run: docker compose -f infrastructure/docker/docker-compose.yml build
```

---

## Conclusion

The Company OS Monitor platform is **architecturally sound** with respect to its cognitive framework. The canonical pipeline correctly implements all principles, rules, and concepts. However, the **external/non-canonical layer** (auth, gateway, reporting, deployment, frontend) has significant security and operational gaps that must be addressed before production deployment.

**Recommended immediate focus:** Critical security fixes (JWT revocation, report auth, rate limiting, service discovery) followed by scalability improvements (parallelization, batching, circuit breakers, tracing).

The product is **ready for the next framework phase (Phase 3 — Engineering)** once critical/high issues are resolved.