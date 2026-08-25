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
├── specs/                    # Component specifications
└── tests/                    # Contract, integration, calibration tests
```

---

## Cognitive Flow

```
Reality → Observation → Evidence → Context → Pattern → Anomaly
       → Hypothesis → Confidence → Recommendation → Decision
       → Report → Memory (planned)
```

---

## Vertical Slice & Verification

COS-Monitor ships a demonstrable, end-to-end cognitive pipeline. The full
chain **Observation → Evidence → Context → Pattern → Anomaly → Hypothesis →
Confidence → Recommendation → Decision** is real, not a disconnected mock.

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

## License

Refer to the repository files. See `LICENSE` when present.
