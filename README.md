# COS-Monitor (Company OS Monitor)

**COS-Monitor** is a SaaS platform for monitoring, analysis, and automated diagnosis of IT infrastructure, built on the Company OS cognitive architecture framework.

It implements the canonical cognitive pipeline — **Perception → Reasoning → Learning → Action** — as a set of independent services, each implementing exactly one cognitive capability. From raw observations to committed decisions, every artifact is immutable and fully traceable.

This repository is the product: the services, the libraries, the infrastructure, and the engineering discipline that bring Company OS to life as an operating monitor.

---

## README (full versions)

This file is an index. The complete, maintained documentation is here:

- [README_EN.md](README_EN.md) — Full description in **English**
- [README_ES.md](README_ES.md) — Descripción completa en **Español**

---

## Repository Structure

```
company-os-monitor/
├── apps/
│   ├── agents/               # Observation Capturers (Perception)
│   └── services/             # Cognitive Services
├── libs/
│   ├── cognitive-core/       # Contracts, calibration, bus
│   ├── perception/           # Observation, Evidence, Context
│   ├── reasoning/            # Pattern, Anomaly, Hypothesis, Insight
│   ├── learning/             # Confidence, Memory
│   ├── action/               # Recommendation, Decision, Report
│   ├── access/               # Auth / RBAC / tokens
│   └── procedural-memory/    # Pattern, Tolerance, Action Space, Policies
├── infrastructure/
│   ├── docker/               # Docker Compose, init SQL
│   └── db-migrations/        # Idempotent migrations per sprint
├── docs/                     # Architecture and domain documents
├── journal/                  # Progress and discovery records
└── tests/                    # Contract, integration, calibration tests
```

---

## Cognitive Flow

```
Reality → Observation → Evidence → Context → Pattern → Anomaly
       → Hypothesis → Confidence → Recommendation → Decision
       → Report → Memory (consolidation, pattern_refinement, context_revision,
                         insight_transformation read/compute operativas;
                         learning_memory ledger append-only, authorized)
```

---

## Vertical Slice & Verification

COS-Monitor ships a demonstrable, end-to-end cognitive pipeline. The full
chain **Observation → Evidence → Context → Pattern → Anomaly → Hypothesis →
Confidence → Recommendation → Decision → Report** is real, not a disconnected
mock. The automated integration test `tests/integration/test_cognitive_pipeline_e2e.py`
walks this entire chain (including the non-canonical Report) against real
PostgreSQL and asserts full traceability, tenant isolation and the R4 confidence
gate.

To prove it on a fresh environment:

1. **Start infrastructure + services** (PostgreSQL + Redis, schema, migrations,
   and the autonomous pipeline):
   ```bash
   ./start.sh            # boots infra, applies migrations, starts all services + linux-agent
   ```

2. **Run a reproducible synthetic scenario** (no real hosts required — uses the
   same stores/contracts as production):
   ```bash
   python3 scripts/qa_seed.py --watch --max-minutes 15
   ```

3. **Run the in-process end-to-end integration test** that walks every stage
   and asserts traceability, tenant isolation, and the confidence (R4) gate:
   ```bash
   DATABASE_URL=postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor \
     pytest tests/integration/test_cognitive_pipeline_e2e.py -v
   ```
   This test runs as part of the CI `pytest tests/` step.

---

## Cognitive Trace API (Phase 2A)

A read-only provenance view over the canonical cognitive stores. It answers
*"why did Company OS reach this conclusion?"* by reconstructing, from a Report
(root), the full chain of artifacts that justify it:

```
Report → Decision → Recommendation → Confidence → Hypothesis
       → Anomaly → Pattern → Context → Evidence → Observation
```

- **It is a READ MODEL, not a new cognitive stage and not a persisted entity.**
  No `CognitiveTrace` table is created; the trace is assembled on demand from
  the canonical tables (P1/P3).
- **Report → Decision is 1:N** (canonical): a periodic Report aggregates N
  Decisions, enumerated in its `content["decision_traces"]`. There is no
  singular `report.decision_id` FK (ADR-0002).
- **Tenant isolation**: every read is scoped by the authenticated tenant; a
  Report requested by another tenant resolves to nothing (404).
- **Deterministic**: stable node/edge ordering; two identical requests produce
  the same logical result. No N+1 queries (bulk, tenant-scoped reads).
- **Broken provenance is never fabricated**: a trace with a missing referenced
  artifact is returned as `partial` with explicit `warnings`.

Endpoint (gateway, tenant-scoped, `read` authority):

```
GET /api/v1/tenants/{tenant_id}/cognitive-trace/report/{report_id}
```

Response contract (stable, serializable):

```json
{
  "root":    { "type": "report", "id": "...", "tenant_id": "..." },
  "nodes":   [ { "type", "id", "tenant_id", "timestamp", "data" } ],
  "edges":   [ { "from", "to", "relation" } ],
  "completeness": "complete" | "partial",
  "warnings": [ "..." ]
}
```

Frontend contract: `CognitiveTraceResponse` / `fetchCognitiveTrace(tenantId, reportId)`
in `apps/web/src/api/gateway.ts` and `apps/web/src/types/cognitive.ts`
(types only — the full Trace UI is a future phase).

---

## Hypothesis Evaluation Service (Reasoning / Evaluate)

The Evaluation Service closes the Learning Loop: it periodically evaluates each
tenant's **candidate** Hypotheses against **new Evidence** produced by Perception
since the hypothesis was generated, applies the formal Evaluation Policy, and
persists immutable, idempotent `Evaluation` records. It updates the Hypothesis
status (the only allowed lifecycle mutation) only on a reliable evidence basis.

| Property | Value |
| --- | --- |
| Port | `8102` (`EVALUATION_HEALTH_PORT`) — distinct from decision-service `8097` |
| Health | `GET /health` (readiness: reports `unhealthy`/503 if the DB is down) |
| Metrics | `GET /metrics` (cycles, evaluations, confirmed/falsified/insufficient, duplicates, errors, last successful cycle) |
| Runtime | started/stopped by `./start.sh` / `./stop.sh` (in `SERVICE_SPECS`) |

**Cognitive boundary (R3/R7).** The Evaluate capability consumes **Evidence**
(the canonical Perception artifact), never the raw Observation store. Evaluation
is a Reasoning-stage operation and must act on organized knowledge, not on raw
perception data.

**Formal semantics.**
- *Falsified* — the falsification criterion is met by evidence. Confidence is a
  metacognitive calibration and does **not** override contradictory evidence:
  high Confidence never blocks falsification.
- *Confirmed* — enough predictions corroborated AND calibrated Confidence above
  threshold AND no falsification met. Confidence is necessary-but-not-sufficient
  gating, never a substitute for evidence.
- *Insufficient* — otherwise; the Hypothesis stays candidate.

The MVP matcher over Evidence descriptions is explicitly **heuristic**
(`MATCHER_RELIABILITY = "heuristic"`). Because textual matching is not a reliable
evaluator, the service does **not** auto-promote a Hypothesis to a terminal state
on a heuristic signal: it records the evaluation as `insufficient` and preserves
the candidate. The formal rules (confirmed/falsified) are exercised on a reliable
evidence basis (future structured matcher).

**Immutability & idempotence.** Each `Evaluation` is append-only (DB trigger
blocks UPDATE/DELETE). The deterministic `evaluation_id` is content-addressed
from tenant + hypothesis + evidence ids + result (no timestamp), so a re-run with
the same evidence is deduped (`ON CONFLICT DO NOTHING`) while new evidence yields
a new row, preserving the full history.

---

## Framework / Monitor Relationship

Company OS (Framework) is the cognitive authority (read-only for this product).
COS-Monitor is the product (ADR-0002). Where the Framework lists a capability as
*planned* (e.g. Memory), the Monitor's **Learning Memory ledger** and **Learning
Loop** are implemented as **authorized product capabilities** of the Monitor — not
a silent modification of the Framework. The framework is never edited by this
repository.

---

## License

Refer to the repository files. See `LICENSE` when present.
