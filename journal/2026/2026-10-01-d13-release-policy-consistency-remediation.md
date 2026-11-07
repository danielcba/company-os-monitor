# 2026-10-01 — D13: release policy consistency remediation

Unit: `D13 — Release Policy Consistency Remediation` (prompt
`/home/dcordoba/Documents/tmp/D2_13.md`).

Authorization matrix: `AUTHORIZE_D13=YES`,
`AUTHORIZE_RELEASE_POLICY_REMEDIATION=YES`; everything else `NO` (no commit, no
push, no tag, no GitHub Release, no future release, no release preparation,
no LICENSE, no security tooling, no Code Scanning, no dependency remediation,
no Dependabot review/merge, no journal commit, no Sprint 13, no Framework or
Framework journal writes).

## Dynamic baseline before (after `git fetch --prune --tags`)

- BRANCH `main`; HEAD = origin/main = ls-remote =
  `db1819697352a0c09dc63ff4901f0063be57fc8b`; divergences `0 0` / `0 0`
- Worktree before edit: `M start.sh`, `M stop.sh` (pre-existing), 21 untracked
  journals (19 pre-D11 + D11 + D12), staged = 0, `.env` untouched
- Framework: `381f56cfa48d092f85846e160d2e1fe6878f9f6f`, 9 pre-existing dirty
  entries

## Release anchors (read-only verification)

- `v0.1.0` commit `3de73fe73296e99f356324cf5f2825c47256f181`, tag object
  `d3504eb1b5f12c3fae83b3455e1c6fdce57a78af` (local+remote)
- `v0.1.1` tag object `50fc5852ddf5aa9df762c97614a829ac4010a09d` → target
  `db1819697352a0c09dc63ff4901f0063be57fc8b` = current `main`
- GitHub Release `Company OS Monitor v0.1.1` published, draft=false,
  prerelease=false (total releases = 2)
- Product version at HEAD = `0.1.1` (17 `pyproject.toml`, `apps/web/package.json`)

## Initial state of `docs/release-policy.md`

- 87 lines, tracked, last changed in `3de73fe` (release prepare v0.1.0)
- `0.1.0` occurrences: 3 total
  - `:22` — illustrative tag-format example in rule 3 (`for example v0.1.0`)
    → HISTORICAL/ILLUSTRATIVE, preserved
  - `:66` — `**Product version:** 0.1.0 (D2 Option A, first release)` →
    stale current-state claim
  - `:67` — `17 files, all 0.1.0` → stale current-state claim

## Stale references detected vs criterion

- Stale (claims describing the *current* state that are no longer true):
  `docs/release-policy.md:66`, `docs/release-policy.md:67`
- Historical/valid (must be preserved): `:22` format example; the D2 decision
  origin (`:5–6`, journal reference); the fact that `0.1.0` was the first
  release; `CHANGELOG.md` `[0.1.0]` history; both tags and both GitHub Releases
- Criterion: only assertions presented as *current fact* were corrected;
  no blanket `0.1.0` → `0.1.1` replacement was performed
- Files scanned for other current-state `0.1.0` claims: `docs/`, READMEs,
  `.github/` → none elsewhere; journals carry historical decision records
  (append-only, preserved). No out-of-scope file required modification.

## Changes performed

- `docs/release-policy.md` only — 1 hunk, 2 stale lines:
  - `:66` → `**Product version:** \`0.1.1\` (current release \`v0.1.1\`; the D2
    Option A first release was \`0.1.0\`).`
  - `:67` → `Python components: \`version\` in each \`pyproject.toml\`
    (17 files, all \`0.1.1\`).`
- No policy rule, procedure, security requirement, licensing statement,
  automation or claim was added/changed; rules count remains 12;
  `LICENSE STATUS = OWNER DECISION REQUIRED` section untouched.

## Validation after edit

- `git diff -- docs/release-policy.md` = exactly the 2-line factual correction
- `git diff --check` → exit 0
- `git status --short` → `M docs/release-policy.md` + pre-existing
  `M start.sh`, `M stop.sh`; staged = 0
- Untouched (verified empty diff): 17 `pyproject.toml`, `apps/web/package.json`,
  `apps/web/package-lock.json`, `README_EN.md`, `README_ES.md`, `README.md`,
  `CHANGELOG.md`, `libs/shared/tracing.py`
- `LICENSE` not created; `.env` untouched; Framework SHA unchanged with the same
  9 pre-existing dirty entries and 0 diff in `company-os-main/journal`
- Historical journals unmodified (0 tracked journal diffs; untracked count 21)
- Scoped semantic checks (release-policy only): CURRENT PRODUCT VERSION `0.1.1`
  PASS; CURRENT RELEASE `v0.1.1` PASS; HISTORICAL RELEASE `0.1.0` preserved PASS;
  no stale `0.1.0` current-state claims remain PASS;
  `17 files, all 0.1.1` matches HEAD (17 pyproject at HEAD with `0.1.1`,
  package.json `0.1.1`) PASS → `RELEASE POLICY CONSISTENCY: PASS`
  (scope: `docs/release-policy.md` only, not a whole-repo consistency claim)

## Working tree preservation

- Pre-existing preserved: `M start.sh`, `M stop.sh`, `.env`, 21 untracked journals
- D13 changes: `docs/release-policy.md` (1 file) + this journal (new, untracked)
- staged = 0; no commit, no push (`COMMIT = NOT PERFORMED`,
  `PUSH = NOT PERFORMED`)

## Commercial content

- Introduced by D13: 0 (scan of `docs/release-policy.md` diff and this journal →
  0 hits on the standard commercial/marketing term list)

## Out of scope (observations only, not executed)

- LICENSE = OWNER DECISION PENDING; security tooling; Code Scanning;
  publication of Monitor journals; release automation; Sprint 13; future release

## Final status

`D13: CLOSED` — factual documentation aligned with confirmed `v0.1.1` state;
no hard stop triggered.
