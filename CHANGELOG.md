# Changelog — Company OS Monitor

All notable changes to the **product** `company-os-monitor` are documented
here. Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/)
and the product follows [Semantic Versioning](https://semver.org/) as defined
in `docs/release-policy.md`.

This file is the release-facing changelog. It is separate from the internal
append-only journals (`journal/`) and from historical remediation reports
(`docs/remediation/`), which do not replace it.

## [0.1.0] - 2026-09-30

First tagged baseline of the complete product (release unit = the whole
`company-os-monitor` platform). Every entry below is traceable to repository
history (commit SHA), documentation, or `journal/`.

### Added

- **Canonical cognitive pipeline** as independent services — one cognitive
  capability per service (R1): collector, context, pattern, anomaly,
  hypothesis, insight, confidence, recommendation, decision, evaluation,
  report, plus the API gateway, user service, and platform agents
  (linux / windows / vmware).
- **Machine identity & authentication** — agent registration, instance
  lifecycle and RS256 machine JWT with kid-based key rotation (`42d0787`,
  `eb6bfd2`, `d011d28`).
- **Telemetry ingest** — canonical serialization, idempotent ingest endpoint
  and observation publisher (`9362d46`, `8aa487c`, `e43bf59`, `dd2bf28`).
- **Cognitive Gate end-to-end** — Decision → Outcome → Execution → Learning
  closed loop (`df8b6fd`), Execution & Outcome contract (`ff0bd0f`), outcome
  status semantics (`453b803`) and outcome-transition observability (`49bd5fb`,
  `19f6512`).
- **Memory & Learning Layer** made operational per ADR-0003
  (`db26fe3`, `e5ac6e7`, `8dc373b`).
- **Cognitive Trace** — read-only provenance view reconstructed on demand from
  canonical stores (Fase 2A, `e3109a9`).
- **Web frontend** (SPA served by an nginx container, `249f475`) with
  multi-tenant UI, authentication, and the Cognitive Trace UI.
- **Repository governance** — CODEOWNERS, hardened Dependabot configuration,
  secret scanning configuration, and least-privilege workflow permissions
  (`099dbbb`, `8ecbdae`).

### Security

- **Loopback-only network perimeter** — Docker published ports restricted to
  `127.0.0.1` (`e32fb88`) and host service bindings restricted to loopback
  (D1, `8560679`); loopback enforcement verified end-to-end.
- **Production CORS handling restored** — exact-origin preflight responses,
  no wildcard (`446dd36`), verified against the CORS matrix.
- **Credential hardening** — D-01 credential remediation (`298d185`, `e3d5a5c`,
  `2c6ed07`), JWT audience verification with fail-closed credentials
  (`d98133f`), and runtime rejection of credential placeholders (`5c7f071`).
- **Nonce-based Content Security Policy** without `unsafe-inline`
  (`5e5f6c4`, D-02 closure `6cf5bfa`).
- **Multi-tenant authorization** (tenant-scoped stores and queries) and
  fail-closed, consume-once JWT handling — see `journal/2026/` remediation
  entries (P1–P19).
- **Rate limiting** via atomic Lua script; **Cognitive Boundary 2.0**
  declarative policy; **Decision/Execution separation** (`ActionExecutor`).

### Fixed

- Agent health port conflict on the host (`6522395`).
- Redis password placed in the wrong position in the env template (`eb686e2`).
- `H4-001` migration made idempotent (`50c5749`).
- Report type contract alignment and secret-scanning scope (`b277096`).
- Removed deprecated refresh-token body fallback (`972e125`).
- CI lint/test stability and test package shadowing (`d7717d0`, `f18deff`,
  `b594b12`, `00acd1b`, `52d8e90`, `a8d97fb`).

### Notes

- **Validation at this baseline:** `pytest tests/` 799 passed,
  `pytest tests/security tests/architecture` 354 passed, frontend test suite
  passing (29 test files), `ruff`/`mypy`/`bandit` clean at project baseline,
  CI run `36649695292` (`lint-and-test (3.12, 24)` + `docker-build`) green on
  `df911a8a976a5d83617060a94cd6992701a384cc`.
- **LICENSE:** not present — license selection is an owner decision
  (see `docs/release-policy.md`).

[0.1.0]: https://github.com/danielcba/company-os-monitor/releases/tag/v0.1.0
