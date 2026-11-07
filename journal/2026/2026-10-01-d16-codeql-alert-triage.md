# 2026-10-01 — D16: CodeQL alert triage & remediation

Unit: `D16 — CODEQL ALERT TRIAGE & REMEDIATION` (prompt
`/home/dcordoba/Documents/tmp/D2_16.md`).

Authorization matrix: `AUTHORIZE_D16=YES`, `AUTHORIZE_SECURITY_AUDIT=YES`,
`AUTHORIZE_SECURITY_VERIFICATION=YES`, `AUTHORIZE_CODEQL_TRIAGE=YES`,
`AUTHORIZE_CODEQL_REMEDIATION=YES` (only for a confirmed true positive),
`AUTHORIZE_SECURITY_TESTING=YES`, `AUTHORIZE_JOURNAL_UPDATE=YES`; everything
else `NO` (commit, push, tag, GitHub Release, journal commit, future release,
release preparation, version/CHANGELOG/README/LICENSE changes, dependency
remediation, Dependabot review/merge, security tooling, Sprint 13).

## Dynamic baseline before (after `git fetch --prune --tags`)

- BRANCH `main`; HEAD = origin/main = ls-remote =
  `db1819697352a0c09dc63ff4901f0063be57fc8b`; divergences `0 0` / `0 0`; ALIGN=YES
- Anchors: `v0.1.0` → `3de73fe…` (tag object `d3504eb1…`), `v0.1.1` →
  `db18196…` (tag object `50fc5852…`), both local and remote refs verified

## Working tree baseline

- `M docs/release-policy.md` (D13, uncommitted — preserved untouched),
  `M start.sh`, `M stop.sh` (pre-existing — preserved), staged = 0,
  24 untracked journals (including D15), `.env` untouched. D16 modified 0
  tracked files (this journal is the only new file).

## CodeQL alert identity (FASE 1 revalidation)

- `GET code-scanning/alerts?state=open` → exactly **1** open alert:
  - number `1`, rule `py/path-injection`, severity `error`,
    security severity `high`, state `open`, tool `CodeQL 2.27.1`
  - repo `danielcba/company-os-monitor`, instance ref `refs/heads/main`,
    commit `db18196…`, location
    `apps/services/report-service/src/service.py:228-228`
  - message: "This path depends on a user-provided value."
  - created `2026-10-01T21:21:55Z`, updated `2026-10-01T21:21:56Z`,
    instances = 1
- Analyses: 3 on `refs/heads/main` @ `db18196…` — python results 1,
  javascript-typescript 0, actions 0. Alert unchanged since D15.
- The SARIF archive is not exposed by the REST API for default-setup runs
  (`code-scanning/sarifs/{id}` returns processing status only, no download
  URL), so the triage evidence is the REST alert metadata plus a concrete
  data-flow analysis of the real code (FASE 2).

## Data flow analysis (FASE 2)

- SINK: `service.py:228` `path.write_bytes(payload)`, where `path =
  Path(self.output_dir) / str(tenant_id) / filename` is composed at
  `service.py:220-227`.
- Callers: `_write_artifact` is called only by `generate()`
  (`service.py:163`); `generate()` is called only by the HTTP handler
  (`health.py:100`), the scheduled cycle (`service.py:104`,
  `run_report_cycle`), and tests.
- SOURCE candidates (remote): `?type=` (`health.py:91`), `?tenant_id=`
  (`health.py:98`), JWT tenant claim (`health.py:65`).
- VALIDATION / TRANSFORMATIONS (all executable, fail-closed):
  - `report_type`: allowlist at `health.py:92` (400 when not in
    `RENDERABLE_TYPES`) and again at `service.py:119` (ValueError → 500).
    `RENDERABLE_TYPES` = fixed literals `executive`/`technical`/`json`
    (`service.py:54-58`; `main.py` constructs the service with the default).
  - `tenant_id`: every HTTP path passes `uuid.UUID(effective_tenant)` at
    `health.py:101` before `generate()`; any non-UUID input (traversal,
    absolute path, empty, encoded variants) raises ValueError → 500 at
    `health.py:110` → **no filesystem write**. A non-superadmin requesting a
    foreign raw tenant string gets AccessError → 403 (`health.py:66-71`);
    a superadmin's raw string still hits the same parser.
  - `str(uuid.UUID(...))` is canonical `[0-9a-f-]{36}`: no `/`, no `\`, no
    `..` (demonstrated executably below).
  - Scheduled path: tenant ids come from `SELECT DISTINCT tenant_id` over
    `tenant_id UUID NOT NULL` columns (`infrastructure/docker/init-sql/
    01-schema.sql`) typed as `list[uuid.UUID]` in every store.
  - Period: `_report_period` (`service.py:232-239`) returns `date` objects
    only (from `committed_at TIMESTAMPTZ` → `.date()`, or the server clock)
    → `isoformat()` is always `YYYY-MM-DD`.
  - `rid`: `uuid.uuid5` (`libs/action/report.py:77`) → `str(rid)[:8]` hex.
  - `extension`: literal `pdf`/`json` returned by `_render`
    (`service.py:201-208`).
  - `output_dir`: env `REPORT_OUTPUT_DIR` (`main.py:51`) — deployment
    config, not remote input.
- Executable demonstration (pure computation, no writes): traversal inputs
  `../../etc/passwd`, `..`, `/etc/passwd`, `` and `a/b` are all rejected by
  `uuid.UUID()`; the constructed path is always
  `reports-output/<uuid>/<type>_YYYY-MM-DD_YYYY-MM-DD_<hex8>.<ext>`
  (normpath inside the base directory). An escaping construction requires a
  raw `../` segment, which the entry parser rejects before `generate()`.
- TRUST BOUNDARY: the JWT-authenticated aiohttp handlers in `health.py`
  (report-service listens on `127.0.0.1:8098`, `main.py`).
- SECURITY IMPACT: none — no attacker-controlled path segment reaches the
  sink; malicious inputs are rejected fail-closed (400/403/500) before any
  write. The service's own call graph has no unguarded remote entry.

## Classification (FASE 3)

**FALSE POSITIVE.**

Rationale: the flagged flow is blocked by concrete, executable, fail-closed
code guarantees at the trust boundary — the `uuid.UUID()` parser
(`health.py:101`), the `RENDERABLE_TYPES` allowlist enforced twice
(`health.py:92`, `service.py:119`), the `date`-typed period, the `uuid5` hex
report id and the literal extension — not by an informal convention.
Not `NO LONGER PRESENT` (the alert commit equals current HEAD; `service.py`
is unmodified since the finding). Not `DUPLICATE/SUPERSEDED` (1 open alert,
1 instance, no related alert).

## Remediation (FASE 4/5)

- **NOT PERFORMED** — `AUTHORIZE_CODEQL_REMEDIATION` covers only a fix for a
  confirmed true positive; for a false positive the unit requires documented
  justification instead. No code change, no `# codeql[...]` suppression, no
  cosmetic sanitization, no dismissal, no new tests (the executable guard
  demonstration above verifies the flow without altering the tree).
- FILES MODIFIED: none. OUT-OF-SCOPE CHANGES: NONE.

## Validation (FASE 6)

- report-service component tests (cwd = service dir + `PYTHONPATH` = repo,
  as CI runs them): **34 passed**
- `pytest tests/security tests/architecture -q`: **354 passed**
- `pytest tests/ -q`: **799 passed**
- `ruff check .`: All checks passed
- `mypy --config-file mypy.ini libs/`: Success, 70 source files
- `bandit -r apps/ libs/ -ll -c bandit.yaml`: exit 0 (0 medium, 0 high; low
  findings below threshold, consistent with prior gates)
- `compileall apps libs`: OK
- `vitest run` (apps/web): 29 files / 182 tests passed
- `docker compose config -q`: OK
- NEW SKIPS = 0, NEW XFAILS = 0, REGRESSIONS = 0; worktree after validation
  identical to baseline (staged = 0)

## CodeQL reanalysis & alert state (FASE 7/8)

- REANALYSIS AVAILABLE = **NO** without an unauthorized action: default
  setup re-runs on push/PR/weekly schedule; re-triggering via config PATCH
  would modify CodeQL configuration (explicitly out of D16 scope), and
  push/PR requires `AUTHORIZE_PUSH=YES`.
- Alert state was **not modified** (dismissal requires explicit
  authorization from this unit, which the matrix does not grant; the FP
  justification is documented here instead).
- FINAL ALERT STATE: **open** (unchanged). PUSH REQUIRED for any remote
  re-run/confirmation: YES; PUSH PERFORMED: NO. No claim of
  `CODEQL ALERT CLOSED` is made.

## GitHub security integrity (unchanged, re-verified)

- Secret Scanning enabled (open 0); Push Protection enabled; Dependabot
  security updates enabled (open 0, fixed 11, dismissed 0); branch
  protection `main` identical (reviews=1, sigs=true, strict=true, contexts
  `lint-and-test (3.12, 24)` + `docker-build`, force=false,
  deletions=false); workflow default permissions `read`; 5/5 `uses:` SHA
  pinned; no `pull_request_target`; bandit gate intact in the required CI
  job; CI run `36892577152` still `completed success` on `db18196…`.

## Framework integrity

- SHA `381f56cfa48d092f85846e160d2e1fe6878f9f6f` unchanged; 9 pre-existing
  dirty entries; framework journal diff = 0; 0 writes attributable to D16.

## Release boundary

- `v0.1.0` / `v0.1.1` tags and both releases intact; no `v0.1.2`
  preparation; CHANGELOG/README/LICENSE untouched;
  `docs/release-policy.md` D13 modification preserved intact; no
  commit/push/tag/GitHub Release.

## Commercial content

- Introduced by D16: 0 (word-boundary scan of this journal → 0 hits;
  0 secret-pattern hits).

## Final status

`D16: CLOSED — FALSE POSITIVE VERIFIED` — CodeQL alert #1
(`py/path-injection`, `service.py:228`) triaged with executable data-flow
evidence; remediation not applicable to a false positive; alert left open
pending an explicitly authorized dismissal or a future authorized CodeQL
run; no commit/push/tag/release; 0 tracked files modified (this journal
STAGED=NO / COMMITTED=NO); no hard stop.
