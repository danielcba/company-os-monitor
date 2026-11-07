# 2026-10-01 — D12: v0.1.1 post-release closure audit

Unit: `D12 — v0.1.1 POST-RELEASE CLOSURE AUDIT / PRODUCTION STATE VERIFICATION`
(prompt `/home/dcordoba/Documents/tmp/D2_12.md`).

Authorization matrix: `AUTHORIZE_D12_AUDIT=YES`,
`AUTHORIZE_POST_RELEASE_VERIFICATION=YES`, `AUTHORIZE_GITHUB_VERIFICATION=YES`,
`AUTHORIZE_CI_VERIFICATION=YES`, `AUTHORIZE_DEPENDABOT_VERIFICATION=YES`;
everything else `NO` (no commit, no push, no tag, no GitHub Release changes, no
release preparation, no dependency remediation, no Dependabot review/merge, no
LICENSE, no security tooling, no Code Scanning, no journal commit, no Sprint 13,
no Framework writes, no `.env`/`start.sh`/`stop.sh` edits, no `docs/release-policy.md`
edits). This unit is verification-only; it performs no repository mutation except
this journal.

## Dynamic baseline before (after `git fetch --prune --tags`)

- BRANCH: `main`
- HEAD_SHA: `db1819697352a0c09dc63ff4901f0063be57fc8b`
- MAIN_REMOTE_SHA: `db1819697352a0c09dc63ff4901f0063be57fc8b`
- LS_REMOTE_SHA: `db1819697352a0c09dc63ff4901f0063be57fc8b`
- DIVERGENCE HEAD↔remote: `0 0`; remote↔ls-remote: equal
- Matches D11 release commit (comparison only): `db18196…`
- Worktree before audit: `M start.sh`, `M stop.sh` (pre-existing), 20 untracked
  journals (19 from before D11 + D11 journal), staged = 0, `.env` ignored/untouched

## v0.1.1 integrity

- Local tag: exists, annotated (`tag` object), object
  `50fc5852ddf5aa9df762c97614a829ac4010a09d` → target `db18196…`
- Remote tag: `refs/tags/v0.1.1` = `50fc5852…`, peels to `db18196…`
- GitHub Release `Company OS Monitor v0.1.1`: exists, draft=false,
  prerelease=false, published `2026-10-01T16:40:58Z`, target `main`,
  assets = 0, notes = 26 lines (CHANGELOG `[0.1.1]` section), author `danielcba`
- Ordering: `releases/latest` = `v0.1.1`; releases total = 2 (`v0.1.1` first)
- Comparison vs D11 evidence: identical (tag object, target, release state)
  → classification: EXPECTED (no difference found)

## v0.1.0 integrity

- Commit `3de73fe73296e99f356324cf5f2825c47256f181` (peel, local+remote)
- Tag object `d3504eb1b5f12c3fae83b3455e1c6fdce57a78af` (local+remote)
- Release `Company OS Monitor v0.1.0`: present, draft=false, prerelease=false,
  published `2026-09-30T17:41:08Z`, assets = 0
- Unmodified

## Main / release consistency

- `HEAD == origin/main == ls-remote == v0.1.1 target == release commit`
  (`db18196…`); commits after release commit on main = 0; release commit is an
  ancestor of main. No reconciliation performed.

## Release commit integrity

- `db18196…` — subject `release: prepare v0.1.1`, parent
  `d6f4f8d800d50774a6c328112d88f9e2bc75ff98`, author/committer
  `danielcba <daniel.e.cordoba@gmail.com>`, `2026-10-01 13:29:20 -0300`
- 23 files changed, 53 insertions(+), 23 deletions(-); exactly the D10/D11
  release file set (17 `pyproject.toml`, `apps/web/package.json`,
  `apps/web/package-lock.json`, `README_EN.md`, `README_ES.md`,
  `libs/shared/tracing.py`, `CHANGELOG.md`)
- Unrelated files: none (no journals, no `start.sh`, no `stop.sh`, no `.env`,
  no Framework files)

## CI post-release

- Latest relevant run: `36892577152` (`CI`, run_number 241, event `push`),
  head `db18196…`, `completed | success`, created `2026-10-01T16:30:58Z`
- Jobs: `lint-and-test (3.12, 24)` = success; `docker-build` = success
- Still the newest CI run on `main` (no newer CI run since D11); no workflow run
  exists for the tag object SHA (tag pushes do not trigger branch workflows)
- No workflows were altered or re-run by this unit

## Dependabot / dependency state

- Open alerts: 0; dismissed: 0; fixed: 11 (all package `undici`)
- New alerts since D11: none
- `npm audit` (apps/web): 0 vulnerabilities; `undici 8.11.2`, `jsdom 30.0.1`
- Read-only; no alert was dismissed, reopened or remediated

## Version consistency (read-only, from `HEAD`)

- 17 `pyproject.toml`: `version = "0.1.1"` (exactly one each)
- `apps/web/package.json` `0.1.1`; `apps/web/package-lock.json` root +
  `packages[""].version` `0.1.1`
- `README_EN.md:3` `Version: 0.1.1`; `README_ES.md:3` `Versión: 0.1.1`
  (`README.md` has no version metadata)
- `libs/shared/tracing.py:55` default `APP_VERSION` `"0.1.1"`
- `CHANGELOG.md`: `## [0.1.1] - 2026-10-01` + link present;
  `## [0.1.0] - 2026-09-30` intact
- Declared version == release tag == GitHub Release tag → CONSISTENT

## Production / build verification (non-destructive)

- `npm install --dry-run` → "up to date"; `npm run build` → success
  (`apps/web/dist` is gitignored, build output not in worktree diff)
- `npm audit` → 0 vulnerabilities
- `docker compose -f infrastructure/docker/docker-compose.yml --env-file .env config -q`
  → exit 0
- `apps/web/package-lock.json` unchanged; no dependency or image change
- Working tree identical before/after these checks (staged = 0)

## Branch protection (`main`, unchanged)

- `required_approving_review_count=1`, `required_signatures.enabled=true`,
  `required_status_checks.strict=true`, contexts
  `["lint-and-test (3.12, 24)", "docker-build"]`, `allow_force_pushes=false`,
  `allow_deletions=false`, `enforce_admins=false`, `required_linear_history=false`,
  `required_conversation_resolution=false`

## Framework integrity

- SHA `381f56cfa48d092f85846e160d2e1fe6878f9f6f` (unchanged)
- Dirty entries: 9, identical to the pre-existing set recorded in D11
  (4 modified, 5 untracked) — all PRE-EXISTING
- Framework journal (`company-os-main/journal`): clean (0 status entries,
  0 diff lines; last touched by an older commit)
- Files with modification time after this unit started: none → 0 writes
  attributable to D12

## Out-of-scope observations (verification only)

- `LICENSE`: still absent → `LICENSE = OWNER DECISION PENDING`
- `docs/release-policy.md:66–67`: still stale (`Product version: 0.1.0`,
  "17 files, all `0.1.0`") vs actual `0.1.1` at HEAD; file last changed in
  `3de73fe` → `OPEN OBSERVATION — OUT OF SCOPE` (not modified)
- Code Scanning: API returns 404 `no analysis found` (no analyses) → observed
  state only (`AUTHORIZE_CODE_SCANNING=NO`)
- Security tooling observed: `secret_scanning=enabled`,
  `secret_scanning_push_protection=enabled`, `dependabot_security_updates=enabled`,
  `secret_scanning_non_provider_patterns=disabled`,
  `secret_scanning_validity_checks=disabled`; secret-scanning alerts open = 0;
  workflows present: `CI`, `Dependabot Updates`, `Dependency Graph` — no change
  (`AUTHORIZE_SECURITY_TOOLING=NO`)

## Working tree preservation

- Pre-existing preserved: `M start.sh`, `M stop.sh` (never staged),
  `.env` untouched, 20 untracked journals preserved
- D12 changes: this journal only (new, untracked)
- staged = 0; no functional file modified by this unit

## Commercial content

- Introduced by D12: 0 (scan over this journal and the release-facing strings →
  0 hits on the standard commercial/marketing term list; 0 secret-pattern hits)

## Final status

`D12: CLOSED` — no hard stop triggered; verification-only, no mutation.
