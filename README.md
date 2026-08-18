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

## License

Refer to the repository files. See `LICENSE` when present.
