# D4 — Post-Release Security / Dependency Triage (read-only)

**Date:** 2026-09-30
**Scope:** read-only security/dependency triage of the published `v0.1.0`
release; no remediation implemented.
**Authorizations (all `NO`):** `AUTHORIZE_DEPENDENCY_CHANGES`,
`AUTHORIZE_DEPENDABOT_MERGE`, `AUTHORIZE_LICENSE_CHANGE`,
`AUTHORIZE_SECURITY_TOOLING`, `AUTHORIZE_JOURNAL_COMMIT`,
`AUTHORIZE_COMMIT`, `AUTHORIZE_PUSH`.

Append-only entry. New file. No D2 journal, no D3 journal, no earlier journal
and no Framework journal was modified. This journal stays untracked (outside
any commit).

## Baseline (FASE 0, after `git fetch --prune --tags`)

- `main`; `HEAD` = `origin/main` = `git ls-remote origin refs/heads/main` =
  `3de73fe73296e99f356324cf5f2825c47256f181`; divergence `0	0`.
- `git rev-parse 'v0.1.0^{}'` = `3de73fe73296e99f356324cf5f2825c47256f181`;
  `git cat-file -t v0.1.0` = `tag`;
  `git ls-remote --tags origin refs/tags/v0.1.0` =
  `d3504eb1b5f12c3fae83b3455e1c6fdce57a78af`.
- `git log --oneline --decorate -n 10`: newest commit is `3de73fe` (HEAD →
  main, tag v0.1.0) → **0 commits after the release**.
- Staged paths = **0**.

## Release / tag integrity

- Release commit unchanged: 8 files, message `release: prepare v0.1.0`,
  parent `df911a8a976a5d83617060a94cd6992701a384cc`.
- Tag not moved, not recreated, not deleted; GitHub Release
  `Company OS Monitor v0.1.0` read-only: `draft=false`, `prerelease=false`,
  `target=main` → unedited.
- CI run `36752227058` (headSha `3de73fe…`) re-verified:
  `completed/success`; `lint-and-test (3.12, 24)` = success,
  `docker-build` = success.

## Working tree preservation (FASE 1)

- ` M start.sh` (mtime `2026-09-28 17:55:07 -0300`),
  ` M stop.sh` (mtime `2026-09-28 17:11:33 -0300`) — pre-existing, untouched.
- `.env` untracked, mtime `2026-09-29 18:21:03 -0300`, unchanged.
- Untracked journals = **10** (the D3 report referenced 9; the count grew by
  one because the D3 journal itself was created untracked): 6 pre-existing
  (`2026-09-28-f3-agent-port-architectural-decision`,
  `2026-09-28-production-readiness-governance-audit`,
  `2026-09-29-d2-governance-production-readiness-audit`,
  `2026-09-29-d2-release-policy-decision-package`,
  `2026-09-29-final-production-readiness-governance-audit`,
  `2026-09-29-release-governance-decision-audit`) + 3 D2 gate journals +
  `2026-09-30-post-release-production-readiness-gate.md`.
- Tracked journals = **69**; `docs/remediation/*` diff = 0 paths.
- No `git clean`, `reset --hard`, `restore`, `checkout --`, `stash`,
  `add .`, `add -A`.

## Dependency graph (verified with npm)

```text
web@0.1.0
├── dependencies: 11 direct runtime packages (react, react-router-dom, …) — undici NOT among them
└── devDependencies: jsdom@^30.0.1, vitest, vite, typescript, oxlint, @testing-library/*, @vitejs/*, @types/*
        jsdom@30.0.1 └── undici@8.10.0     (dev:true, transitive)
        vitest@4.1.11 └── jsdom@30.0.1 (deduped)
```

- `npm ls undici` → `web@0.1.0 └─┬ jsdom@30.0.1 └── undici@8.10.0`.
- `npm ls jsdom` → direct devDependency + deduped under `vitest`.
- `undici` is neither a direct dependency nor a runtime dependency.

## Runtime / development classification (evidence-based)

- **App source imports**: 0 matches for `undici` or `jsdom` in
  `apps/web/src`, `vite.config.ts`, `index.html` → not part of the bundle.
- **Build output**: `apps/web/dist/` contains no `undici`/`jsdom` string.
- **Runtime image**: `apps/web/Dockerfile` is multi-stage — builder runs
  `npm ci` + `npm run build`; runtime stage is `nginx:1.27-alpine` and copies
  only `/app/dist` (`COPY --from=builder /app/dist /usr/share/nginx/html`).
  `node_modules` is never copied → **undici is not present in the production
  runtime image**.
- **Build-time**: builder runs plain `npm ci` (no `--omit=dev`,
  no `NODE_ENV=production`) → development dependencies, including
  `undici`, are installed during image build → install/build-time exposure.
- **CI**: `.github/workflows/ci.yml` step "Frontend setup" runs `npm ci`,
  `npm run lint`, `npm run typecheck`, then `npm run test` → CI/test-time
  exposure.
- **Test runtime**: `vite.config.ts` sets `test.environment: 'jsdom'` →
  jsdom (and therefore undici) executes when the test suite runs.
- **Compose**: `infrastructure/docker/docker-compose.yml` service `frontend`
  uses `build:` context `../../apps/web` (no `image:` pull of third-party
  app image).

## Dependabot alert inventory (current, read-only, 7 open)

| # | Sev | Package | Installed | Patched | Dir/Trans | Scope | Manifest | First observed | GHSA | CVE |
|---|---|---|---|---|---|---|---|---|---|---|
| 5 | high | undici | 8.10.0 | 8.10.2 | transitive | development | apps/web/package-lock.json | 2026-09-30T06:56:43Z | GHSA-w293-vg96-wgc3 | CVE-2026-84961 |
| 2 | high | undici | 8.10.0 | 8.10.2 | transitive | development | apps/web/package-lock.json | 2026-09-30T01:58:57Z | GHSA-vp8m-p9jh-q5pm | CVE-2026-85152 |
| 11 | medium | undici | 8.10.0 | 8.10.2 | transitive | development | apps/web/package-lock.json | 2026-09-30T07:30:26Z | GHSA-pmjh-fq2x-6v4x | CVE-2026-18149 |
| 9 | medium | undici | 8.10.0 | 8.10.2 | transitive | development | apps/web/package-lock.json | 2026-09-30T07:27:41Z | GHSA-2jfj-6hjv-fm6j | CVE-2026-84933 |
| 10 | low | undici | 8.10.0 | 8.10.2 | transitive | development | apps/web/package-lock.json | 2026-09-30T07:28:59Z | GHSA-2gqq-gqf2-x968 | CVE-2026-84947 |
| 6 | low | undici | 8.10.0 | 8.10.2 | transitive | development | apps/web/package-lock.json | 2026-09-30T07:14:15Z | GHSA-r53p-7pc4-xj5r | CVE-2026-18540 |
| 4 | low | undici | 8.10.0 | 8.10.2 | transitive | development | apps/web/package-lock.json | 2026-09-30T06:52:38Z | GHSA-8436-99hf-9mmv | CVE-2026-85008 |

- Totals: **7 open** = 2 high + 2 medium + 3 low; all range `>= 8.0.0, < 8.10.2`
  except alert 2 (`>= 8.10.0, < 8.10.2`); all patched in `8.10.2`.
- All first observed **before** the release commit (`2026-09-30 14:31:53 -0300`
  = `17:31:53Z`) and before this audit → **PRE-EXISTING**; none introduced by
  D2/D3/D4.
- Open Dependabot PRs = **30** (unchanged set of update PRs).

## PR #53 (READ-ONLY TRIAGED)

- `state=OPEN`, `base=main`, `head=dependabot/npm_and_yarn/apps/web/undici-8.11.2`,
  1 commit `209d8c7`, `changedFiles=1`, `additions=63`, `deletions=3`.
- Only file changed: `apps/web/package-lock.json`.
- Core change: `undici` `8.10.0` → `8.11.2` (`version` + `resolved` URL).
- Remaining diff lines: lockfile metadata entries for optional bundled
  sub-dependencies of `@tailwindcss/oxide-wasm32-wasi`
  (`@emnapi/*`, `@napi-rs/wasm-runtime`, `@tybys/wasm-util`, `tslib`,
  `@tailwindcss/oxide-win32-arm64-msvc`), all `inBundle: true` /
  `optional: true` — metadata only, no `package.json` change, no direct
  dependency version change.
- `mergeable=MERGEABLE`, `mergeStateStatus=BLOCKED`,
  `reviewDecision=REVIEW_REQUIRED`, `isDraft=false`.
- Checks on the PR head: `docker-build` = pass, `lint-and-test (3.12, 24)` =
  pass (run `36752523312`).
- Remediation coverage: target `8.11.2` ≥ patched `8.10.2` → **all 7 alerts
  on this manifest are addressed by PR #53** (FACT, per alert ranges).
- Not approved, not merged, not closed, not edited by this task.

## Code scanning (FASE 5)

- `code_scanning` repository field = `null`; code-scanning alerts API →
  `404 "no analysis found"`; analyses API → `404 "no analysis found"`.
- `.github/workflows/` contains only `ci.yml` (no CodeQL/SAST workflow).
- → `CODE SCANNING: PRE-EXISTING` (no analysis configured). Not enabled here.

## Private vulnerability reporting (FASE 6)

- `private_vulnerability_reporting` = `null` → not enabled.
- → `PRE-EXISTING` + `RECOMMENDATION`. Not modified here.

## Other security controls (re-verified)

- `secret_scanning=enabled`, `push_protection=enabled`,
  `dependabot_security_updates=enabled`; open secret-scanning alerts = 0.
- Branch protection `main`: `strict=true`,
  contexts `["lint-and-test (3.12, 24)", "docker-build"]`,
  `required_signatures=true`, review count `1`,
  `allow_force_pushes=false`, `allow_deletions=false` → unchanged.

## Security regression check (FASE 10, no dependency changes)

| Check | Result |
|---|---|
| `ruff check .` | All checks passed |
| `mypy --config-file mypy.ini libs/` | Success: no issues in 70 source files |
| `bandit -r apps/ libs/ -ll -c bandit.yaml` | rc=0, "No issues identified" |
| `python3 -m compileall apps libs` | rc=0 |
| `docker compose … --env-file .env config -q` | rc=0 |
| `pytest tests/security tests/architecture` | 354 passed |
| `pytest tests/` | 799 passed |
| `npx vitest run` | 29 files / 182 tests passed |

Identical to the D3 baseline → 0 regressions, 0 new skips/xfails.

## Traceability (FASE 11, unmodified)

`df911a8… → 3de73fe… → CI 36752227058 (success) → annotated tag v0.1.0
(objeto d3504eb…) → remote verified → GitHub Release verified`.
Ancestors of `3de73fe…`: `7ca822d` U6A, `079024e` U6B, `65f528f` U7,
`6522395` F3, `eb686e2` Redis, `446dd36` CORS, `8560679` D1,
`df911a8` D1-test-fix → **8/8 YES**.

## LICENSE decision gate (FASE 7, no implementation)

- No `LICENSE` file, no SPDX, no `license` key in any of the 17
  `pyproject.toml`, no `license` field in `apps/web/package.json`,
  repository `license` = `null`.
- Artifacts a future decision would touch (inventory only, nothing changed):
  new `LICENSE` file; `README.md` License section (lines 195-199);
  `CHANGELOG.md` LICENSE note (line 79-80); `docs/release-policy.md`
  "Licensing" section (lines 74-80); optional `license` metadata in the 17
  `[project]` pyproject tables and in `apps/web/package.json`; GitHub
  repository license detection; a future release entry if distributed.
- Status: **PENDING OWNER DECISION** (no decision taken here).

## Owner decisions / next authorized work units

- A. Owner obligation: **LICENSE** decision.
- B. Separately authorizable technical work:
  `DEPENDENCY / SECURITY VULNERABILITY REMEDIATION` (PR #53 merge and/or
  lockfile update), `CODE SCANNING`, `PRIVATE VULNERABILITY REPORTING`.
- C. Independent work: `PUBLISH MONITOR JOURNALS`,
  `FUTURE RELEASE AUTOMATION`, `SPRINT 13`.
- No unit combined; no mega-commit proposed.

## Final D4 state

- HARD STOP: **0**. BLOCKERS: **0**.
- Dependency changes by this task: **NO**; license changes: **NO**;
  security tooling changes: **NO**; Dependabot merge: **NO**;
  commit: **NO**; push: **NO**.
- Framework: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` triple-verified,
  0 journal modifications, 0 writes.
- No secrets recorded. No commercial content. Sprint 13 not started.
