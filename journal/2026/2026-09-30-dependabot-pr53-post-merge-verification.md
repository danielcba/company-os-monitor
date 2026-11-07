# D5 — Dependabot PR #53 Merge Gate / Post-Remediation Verification

**Date:** 2026-09-30
**Scope:** read-only merge-gate verification of Dependabot PR #53 and
post-remediation checks for the `undici` vulnerability. No merge, no
dependency change, no local commit, no push.
**Authorizations (all `NO`):** `AUTHORIZE_DEPENDENCY_REMEDIATION`,
`AUTHORIZE_DEPENDABOT_MERGE`, `AUTHORIZE_COMMIT`, `AUTHORIZE_PUSH`,
`AUTHORIZE_JOURNAL_COMMIT`, `AUTHORIZE_FUTURE_RELEASE`.

Append-only entry. New file. D4, D3, D2, earlier journals and Framework
journals were not modified. This journal stays untracked (outside any commit).

## Baseline (FASE 0, after `git fetch --prune --tags`)

- `main`; `HEAD` = `origin/main` = `git ls-remote origin refs/heads/main` =
  `3de73fe73296e99f356324cf5f2825c47256f181`; divergence `0	0`.
- `v0.1.0^{}` = `3de73fe73296e99f356324cf5f2825c47256f181`;
  `git cat-file -t v0.1.0` = `tag`; remote tag
  `d3504eb1b5f12c3fae83b3455e1c6fdce57a78af`.
- Staged = 0; `git diff --name-status` = `M start.sh`, `M stop.sh`
  (PRE-EXISTING). No unexplained divergence → no baseline HARD STOP.

## PR #53 state before action (FASE 1)

```
NUMBER            = 53
STATE             = OPEN (mergedAt=null, closedAt=null, isDraft=false)
TITLE             = chore(deps): bump undici from 8.10.0 to 8.11.2 in /apps/web
BASE / HEAD       = main / dependabot/npm_and_yarn/apps/web/undici-8.11.2
HEAD SHA          = 209d8c7a7f6f2bd7ada48192de38ce9bd948dd66
COMMITS           = 1 (209d8c7) — unchanged since D2_03
CHANGED FILES     = 1 (apps/web/package-lock.json)
ADDITIONS/DELETIONS = +63 / -3
MERGEABLE         = MERGEABLE
MERGE STATE       = BLOCKED
REVIEW DECISION   = REVIEW_REQUIRED
CHECKS            = docker-build success; lint-and-test (3.12, 24) success
LATEST CI RUN     = 36752523312 (headSha 209d8c7)
UPDATED           = 2026-09-30T17:35:46Z
```

- Still exactly `undici 8.10.0 → 8.11.2` in
  `apps/web/package-lock.json`. No additional change appeared since D2_03.

## Review gate (FASE 2)

- Branch protection `main`: `required_approving_review_count = 1`,
  `required_signatures = true`, `strict = true`,
  contexts `["lint-and-test (3.12, 24)", "docker-build"]`,
  `dismiss_stale_reviews = false`, `force_push = false`, `deletions = false`
  → unchanged.
- `GET /pulls/53/reviews` = **0 entries** (no APPROVED, no CHANGES_REQUESTED,
  no DISMISSED, no PENDING).
- Issue comments on #53 = **0** (comment ≠ approval anyway).
- `GET /pulls/53/requested_reviewers` → 1 outstanding request: `danielcba`.
- No self-approval, no admin bypass, no branch-protection change performed.

**REVIEW GATE: FAIL → HARD STOP — PR #53: BLOCKED BY REVIEW**

## PR diff integrity (FASE 3)

Diff re-fetched for head `209d8c7`:

- Only file: `apps/web/package-lock.json` (ONLY_LOCKFILE verified).
- All 3 deletions are the `undici` 8.10.0 entry: `"version"`,
  `"resolved"`, `"integrity"`.
- The only package version change = `undici 8.10.0 → 8.11.2`.
- Added `version` lines belong to 6 new `inBundle` optional nodes under
  `node_modules/@tailwindcss/oxide-wasm32-wasi/node_modules/`
  (`@emnapi/core` 1.11.1, `@emnapi/runtime` 1.11.1, `@emnapi/wasi-threads`
  1.2.2, `@napi-rs/wasm-runtime` 1.1.4, `@tybys/wasm-util` 0.10.2,
  `tslib` 2.8.1) — metadata of the same lockfile write, no new top-level
  dependency.
- `package.json`: 0 references in the diff. No React, Vite, Vitest, Tailwind
  or TypeScript version line changed. No script, workflow, backend or
  Framework path touched.

No unexplained change → no HARD STOP on diff.

## CI pre-merge (FASE 4)

- Checks resolved on the exact head SHA `209d8c7a7f6f2bd7ada48192de38ce9bd948dd66`:
  `lint-and-test (3.12, 24)` = completed/success (run `36752523312`,
  job `110014446324`); `docker-build` = completed/success
  (run `36752523312`, job `110016475061`).
- Release CI `36752227058` (SHA `3de73fe`) not used as substitute.

**CI PRE-MERGE: PASS**

## Merge decision and execution (FASE 5 / 6)

`AUTHORIZE_DEPENDABOT_MERGE = NO` and `AUTHORIZE_DEPENDENCY_REMEDIATION = NO`
→ **CASO A**.

```
MERGE: NOT PERFORMED
REMEDIATION: NOT PERFORMED
```

No push, no dependency change, no PR closure, no alert dismissal, no second
PR, no other Dependabot PR touched. Independent of authorization, the review
gate above is FAIL, so a merge would also have required a bypass — not
attempted.

## Post-merge baseline / main state (FASE 7 / 8)

- Merge not performed → no new remote SHA.
- Re-verified after all work: `HEAD` = `origin/main` =
  `git ls-remote origin refs/heads/main` = `3de73fe…`; divergence `0	0`.
- `git merge-base --is-ancestor 3de73fe… origin/main` trivially holds (same
  SHA); history still exactly `v0.1.0 → (nothing)`.
- **POST-MERGE MAIN SHA: N/A**; **CI POST-MERGE: N/A**.

## Dependency verification (FASE 9)

Real tree in `apps/web` (unchanged, as no merge occurred):

```
npm ls undici → jsdom@30.0.1 → undici@8.10.0
npm ls jsdom  → jsdom@30.0.1 (devDependency) ; vitest@4.1.11 → jsdom dedup
npm ls vitest → vitest@4.1.11
```

- Lockfile: `node_modules/undici` = **8.10.0**, `dev: true`.
- `apps/web/package.json` version = `0.1.0`. No manual edit, no override.

## Dependabot after action (FASE 10)

```
state=open    → 7 alerts, all package=undici (scope=development)
state=fixed   → 0
state=dismissed → 0
```

Open: #2 high, #4 low, #5 high, #6 low, #9 medium, #10 low, #11 medium —
the same 7 from D4. Secret-scanning open alerts = 0.
No alert was closed or dismissed manually.

- `UNDICI ALERTS BEFORE = 7`; `UNDICI ALERTS AFTER = 7`;
  `UNDICI ALERTS FIXED = 0`; `UNDICI ALERTS DISMISSED = 0`;
  `DEPENDABOT TOTAL OPEN ALERTS AFTER = 7` (all `undici`, no other package).

## Security validation (FASE 11)

| check | result | baseline |
|---|---|---|
| `ruff check .` | pass | pass |
| `mypy --config-file mypy.ini libs/` | pass, 70 files, no issues | 70, no issues |
| `bandit -r apps/ libs/ -ll -c bandit.yaml` | "No issues identified" | 0 issues |
| `python3 -m compileall apps libs` | pass | pass |
| `pytest tests/security tests/architecture` | **354 passed** | 354 |
| `pytest tests/` | **799 passed** | 799 |
| `npx vitest run` | **29 files / 182 tests** | 29 / 182 |
| `npm install --dry-run` (apps/web) | "up to date", lockfile unchanged | n/a |
| `docker compose … config -q` | pass | pass |

NEW SKIPS = 0; NEW XFAILS = 0; REGRESSIONS = 0.

## Production artifact verification (FASE 12)

Fresh build from the current worktree (local image only):
`sha256:cfa4004b054515c4a2a1ec76f3c031bd635a1d9c759f47cb70895bf65b989874`,
75.3 MB, multi-stage `node:24-alpine` builder → `nginx:1.27-alpine` runtime
(`NGINX_VERSION=1.27.5`).

Runtime layer: `command -v node` = NO_NODE;
`/usr/share/nginx/html/node_modules` = NONE; `undici` matches = 0 files;
`jsdom` matches = 0 files; contents = `50x.html`, `index.html`, `assets/`.
Conclusion is artifact-based: runtime exposure **NOT PRESENT**, and the
statement is limited to artifact verification — the vulnerability remains in
the development dependency tree.

## Release v0.1.0 integrity (FASE 13)

- `v0.1.0^{}` = `3de73fe73296e99f356324cf5f2825c47256f181` (local + remote
  tag `d3504eb…` identical).
- GitHub Release `Company OS Monitor v0.1.0`: `draft=false`,
  `target=main`, releases count = 1. Not edited, not marked replaced.
- Tag not moved, not deleted, not recreated; no commits before/after the tag.

## Future release implication (FASE 14, factual only)

`docs/release-policy.md` relevant items: (3) tags are `vMAJOR.MINOR.PATCH`
annotated; (7) published tags immutable, any correction requires a new
version; (8) **post-release fixes require a new version (PATCH at minimum)**;
(9) version bump, CHANGELOG entry and tag form one auditable chain;
(11) journals do not replace the CHANGELOG. Release procedure = preparation
commit (version alignment + CHANGELOG) → CI → annotated tag → push →
GitHub Release.

FACT — no post-release commit exists yet (`main` == release SHA), so item 8
is **not triggered today**. FACT — if/when PR #53 merges, that commit becomes
a post-release fix and policy items 8 + 9 would require a new PATCH version
(next compatible = `v0.1.1`) with its own release unit: version bump across
the 17 `pyproject.toml` files and `apps/web/package.json` (+ lockfile root),
`CHANGELOG.md` entry, annotated tag, GitHub Release.
RECOMMENDATION / PENDING OWNER DECISION — to be executed only in a separate,
explicitly authorized unit.

## Working tree preservation (FASE 16)

`git status --porcelain` = 14 lines before and after (13 baseline entries of
D2_03 + the D2_03 journal itself, all PRE-EXISTING for this unit), plus this
new journal. Nothing staged. No `git clean`/`reset --hard`/`restore`/
`checkout --`/`stash`/`add .` executed. `start.sh`, `stop.sh`, `.env` and all
existing journals untouched (mtimes unchanged).

## Final status

- HARD STOPS: **1** (REVIEW GATE: review requerida ausente →
  PR #53 BLOCKED BY REVIEW).
- BLOCKERS: **2** (0 aprobaciones de 1 requerida; autorizaciones `NO`).
- COMMIT CREATED BY THIS TASK: NO. PUSH PERFORMED: NO.
- Framework `381f56cfa48d092f85846e160d2e1fe6878f9f6f` triple-verified, 0
  writes. `v0.1.0` intact. No secrets, no `.env` values, no commercial
  content. Sprint 13 not started.
- **DEPENDENCY REMEDIATION: BLOCKED.**

## Remaining external actions

1. Review of PR #53 by `danielcba` (required approval) — EXTERNAL.
2. Authorization `AUTHORIZE_DEPENDABOT_MERGE=YES` + `AUTHORIZE_DEPENDENCY_REMEDIATION=YES`.
3. LICENSE (PENDING OWNER DECISION).
4. Code Scanning; Private Vulnerability Reporting.
5. Publish Monitor journals; future release automation; future release
   preparation if/when required by policy; Sprint 13 (NOT STARTED).
