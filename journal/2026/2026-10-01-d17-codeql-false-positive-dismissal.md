# 2026-10-01 — D17: CodeQL false positive disposition & alert closure

Unit: `D17 — CODEQL FALSE POSITIVE DISPOSITION & ALERT CLOSURE` (prompt
`/home/dcordoba/Documents/tmp/D2_17.md`).

Authorization matrix: `AUTHORIZE_D17=YES`, `AUTHORIZE_CODEQL_ALERT_DISMISSAL=YES`
(exclusivamente alert #1 `py/path-injection`), `AUTHORIZE_SECURITY_AUDIT=YES`,
`AUTHORIZE_SECURITY_VERIFICATION=YES`, `AUTHORIZE_JOURNAL_UPDATE=YES`;
todo lo demás `NO` (commit, push, tag, GitHub Release, journal commit, future
release, release preparation, version/CHANGELOG/README/LICENSE changes,
dependency remediation, Dependabot review/merge, security tooling, Sprint 13;
tampoco modificación de código, tests, workflows CodeQL, default setup, threat
model, query suite, SARIF, branch protection, secret scanning, push protection
ni Action pinning).

## Dynamic baseline before (after `git fetch --prune --tags`)

- BRANCH `main`; HEAD = origin/main = ls-remote =
  `db1819697352a0c09dc63ff4901f0063be57fc8b`; divergences `0 0` / `0 0`; ALIGN=YES
- Anchors: `v0.1.0` → `3de73fe…` (tag object `d3504eb1…`), `v0.1.1` →
  `db18196…` (tag object `50fc5852…`), local and remote refs verified
- Framework: `381f56cfa48d092f85846e160d2e1fe6878f9f6f`, 9 pre-existing dirty

## Working tree baseline

- `M docs/release-policy.md` (D13, uncommitted — preserved), `M start.sh`,
  `M stop.sh` (pre-existing — preserved), staged = 0, 25 untracked journals
  (D16 included), `.env` untouched. D17 modified 0 tracked files (this journal
  is the only new file).

## Alert identity (FASE 2 revalidation)

- `GET code-scanning/alerts?state=open` → exactly **1** open alert before the
  dismiss: number `1`, rule `py/path-injection`, severity `error`, security
  severity `high`, state `open`, tool `CodeQL 2.27.1`, instance commit
  `db18196…`, location `apps/services/report-service/src/service.py:228-228`,
  message "This path depends on a user-provided value.", created/updated
  `2026-10-01T21:21:55Z`/`21:21:56Z`, `dismissed_reason=null` — same finding
  as D16, same identifier, not replaced, not already dismissed/resolved/fixed.

## D16 classification & revalidation (FASE 3)

- D16: `FALSE POSITIVE` (executable data-flow evidence). Reconfirmed here
  without repeating the whole audit:
  - SOURCE: `?type=` (health.py:91), `?tenant_id=` (health.py:98), JWT claim
    (health.py:65)
  - GUARDS: `uuid.UUID()` fail-closed at health.py:101 (ValueError → 500, no
    write); `RENDERABLE_TYPES` allowlist at health.py:92 (400) and
    service.py:119 (ValueError → 500); cross-tenant authorization
    (health.py:66-71 → 403); `date.isoformat()` = `YYYY-MM-DD`; `uuid5` hex
    rid; literal extension `pdf`/`json`; `output_dir` from env
    (`REPORT_OUTPUT_DIR`), not request-controlled
  - SINK: `service.py:228` `path.write_bytes(payload)` (only reachable via
    `generate()`)
- Executable re-run: traversal inputs `../../etc/passwd`, `..`, `/etc/passwd`,
  `a/b`, empty → all rejected fail-closed before the sink;
  `str(uuid.UUID)` canonical has no `/` and no `..`; composed path is always
  `output_dir/<uuid>/<type>_YYYY-MM-DD_YYYY-MM-DD_<hex8>.<ext>`.
- Code unchanged since D16: `service.py`/`health.py`/tests absent from
  `git diff` and staged diff. CLASSIFICATION SUSTAINED → proceed to dismiss.

## Dismiss action (FASE 4)

- Official operation: `PATCH /repos/{owner}/{repo}/code-scanning/alerts/1`
  with `state=dismissed`, `dismissed_reason=false positive` and a technical
  justification (≤280 chars, no secrets/tokens/credentials/.env values/infra
  details): "FP: flow blocked before path.write_bytes by fail-closed
  uuid.UUID parsing + RENDERABLE_TYPES allowlist + authz checks; path parts
  are canonical UUID/date/UUID5/literals; traversal inputs rejected at
  entry."
- Exactly one API attempt sequence: first request rejected with HTTP 422
  (`comment` not a permitted key → correct field is `dismissed_comment`), a
  second rejected for exceeding the 280-char limit, third accepted. No other
  alert touched; `dismissed_reason` used is exactly `false positive`.

## Remote verification (FASE 5)

- Re-query after the PATCH (independent of the PATCH response): alert `1` →
  `state=dismissed`, `dismissed_reason=false positive`,
  `dismissed_by=danielcba`, `updated=2026-10-01T22:55:30Z`; rule
  `py/path-injection`, `service.py:228-228`, commit `db18196…` unchanged.
- `state=open` count → **0**; `state=all` → only alert 1 (dismissed);
  `py/path-injection` alerts total → 1 (no equivalent/second alert appeared).

## CodeQL configuration integrity (FASE 6)

- `default-setup`: `state=configured`, `query_suite=default`,
  `languages=[actions, javascript, javascript-typescript, python, typescript]`,
  `threat_model=remote`, `schedule=weekly`, `updated_at`
  `2026-10-01T21:22:18Z` (unchanged since D15 — the dismiss did not touch
  configuration)
- Workflows: only `.github/workflows/ci.yml` (untouched); permissions block
  intact; 5/5 `uses:` SHA-pinned; analyses still 3. CHANGES INTRODUCED: NONE
  (alert disposition only).

## Local validation (FASE 7)

- Working tree after the dismiss: identical to baseline — `M
  docs/release-policy.md`, `M start.sh`, `M stop.sh` only; staged = 0;
  `service.py` changed = 0; tests changed = 0; functional diff unchanged.
  CI run on `db18196…` still `completed success`.

## Framework integrity (FASE 8)

- SHA `381f56cfa48d092f85846e160d2e1fe6878f9f6f` unchanged; 9 pre-existing
  dirty entries; framework journal diff = 0; 0 writes attributable to D17.

## Authorization matrix

- YES: D17, CODEQL_ALERT_DISMISSAL (alert #1 only), SECURITY_AUDIT,
  SECURITY_VERIFICATION, JOURNAL_UPDATE
- NO: COMMIT, PUSH, TAG, GITHUB_RELEASE, JOURNAL_COMMIT, FUTURE_RELEASE,
  RELEASE_PREPARATION, VERSION_CHANGE, CHANGELOG_CHANGE, README_CHANGE,
  LICENSE_CHANGE, DEPENDENCY_REMEDIATION, DEPENDABOT_REVIEW/MERGE,
  SECURITY_TOOLING, SPRINT_13

## Release boundary

- `v0.1.0`/`v0.1.1` tags and both releases intact; no `v0.1.2` preparation;
  CHANGELOG/README/`release-policy.md` untouched (D13 modification preserved);
  no commit/push/tag/GitHub Release.

## Commercial content / secrets

- Introduced by D17: 0 (word-boundary scan of this journal → 0 hits;
  0 secret-pattern hits).

## Final status

`D17: CLOSED — FALSE POSITIVE FORMALLY DISMISSED` — alert #1 remotely
verified `state=dismissed`, `dismissed_reason=false positive`; 0 code
changes, 0 configuration changes, 0 Framework writes, no commit/push/release;
this journal STAGED=NO / COMMITTED=NO; no hard stop.
