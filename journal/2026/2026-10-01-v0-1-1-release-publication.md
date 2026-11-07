# 2026-10-01 — D11: v0.1.1 release commit, tag and publication

Unit: `D11 — v0.1.1 RELEASE COMMIT / PUBLISH` (prompt
`/home/dcordoba/Documents/tmp/D2_11.md`).

Authorized: `AUTHORIZE_RELEASE_COMMIT=YES`, `AUTHORIZE_RELEASE_PUSH=YES`,
`AUTHORIZE_RELEASE_TAG=YES`, `AUTHORIZE_GITHUB_RELEASE=YES`.
All other authorizations: `NO` (no branch/PR creation, no `git add` outside the
release file set, no commit of journals, no Framework writes, no
`docs/release-policy.md` edits, no secret/commit-history rewriting).

## Baseline (verified, not assumed)

- `HEAD` = `origin/main` = `git ls-remote` = `d6f4f8d800d50774a6c328112d88f9e2bc75ff98`
- divergence `0 0`, branch `main`
- Worktree at entry: 25 tracked modified (23 release files from D10 +
  pre-existing `start.sh`, `stop.sh`), 19 untracked journal files, staged = 0
- Ancla `v0.1.0`: tag object `d3504eb1b5f12c3fae83b3455e1c6fdce57a78af`,
  commit `3de73fe73296e99f356324cf5f2825c47256f181`, GitHub Release
  `Company OS Monitor v0.1.0` present (draft=false, prerelease=false)
- `v0.1.1` absent: local tag, remote tag and GitHub Release all absent
- Branch protection `main` unchanged:
  `required_pull_request_reviews.required_approving_review_count=1`,
  `required_signatures.enabled=true`, `strict=true`,
  contexts `["lint-and-test (3.12, 24)", "docker-build"]`,
  `force_push=false`, `deletions=false`

## File set (exactly 23, verified against expectation)

- 17 `pyproject.toml` → `version = "0.1.1"` (exactly one match each)
- `apps/web/package.json` `version=0.1.1`; `apps/web/package-lock.json` root and
  `packages[""].version=0.1.1` (lockfile diff = 4 lines, versions only —
  no dependency change; `undici 8.11.2`, `jsdom 30.0.1` unchanged)
- `README_EN.md:3` `Version: 0.1.1`; `README_ES.md:3` `Versión: 0.1.1`
  (`README.md` has no version metadata → untouched)
- `libs/shared/tracing.py:55` `APP_VERSION` default `"0.1.1"`
- `CHANGELOG.md`: new `## [0.1.1] - 2026-10-01` section (30 lines) + link
  `[0.1.1]: https://github.com/danielcba/company-os-monitor/releases/tag/v0.1.1`;
  `## [0.1.0] - 2026-09-30` and its link untouched
- Excluded from staging and verified absent from the commit: `start.sh`,
  `stop.sh`, `.env`, all `journal/` files

## Validations (fresh, this baseline)

- `ruff check .` → "All checks passed!"
- `mypy --config-file mypy.ini libs/` → "Success: no issues found in 70 source files"
- `bandit -r apps/ libs/ -ll -c bandit.yaml` → exit 0, "No issues identified."
- `python -m compileall -q apps libs` → exit 0
- `pytest tests/security tests/architecture -q` → 354 passed
- `pytest tests/ -q` → 799 passed (0 skips, 0 xfails, no regressions)
- `docker compose ... config -q` → exit 0
- `npm run build` → build success; `npx vitest run` → 29 files / 182 tests passed
- `npm install --dry-run` → "up to date"; `npm audit` → 0 vulnerabilities

## Release artifact (evidence only — not committed, not attached)

- Fresh build: `docker build -f apps/web/Dockerfile` →
  `sha256:8aed0c9a263b8e4700686212962029eaa3875570ddec1f5a32647d840b6e2378`
  (size 75341208, runtime `nginx/1.27.5`)
- Runtime inspection: `NODE:ABSENT`, `node_modules:ABSENT`,
  `undici_files=0`, `jsdom_files=0` → no runtime exposure

## Release commit, push, tag, release

- Commit: `release: prepare v0.1.1`
  - `RELEASE_COMMIT_SHA = db1819697352a0c09dc63ff4901f0063be57fc8b`
  - parent = `d6f4f8d800d50774a6c328112d88f9e2bc75ff98`
  - author/committer `danielcba <daniel.e.cordoba@gmail.com>`,
    `2026-10-01 13:29:20 -0300`
  - 23 files changed, 53 insertions(+), 23 deletions(-); unrelated files in
    commit: none
- Push: `git push origin main` (no force) → `d6f4f8d..db18196`;
  after fetch: `HEAD` = `origin/main` = `ls-remote` = `db18196…`, divergence `0 0`
- CI on `db18196…`: workflow run `36892577152` (`CI`) → `completed | success`;
  required jobs `lint-and-test (3.12, 24)` → success,
  `docker-build` → success
- Tag: annotated `v0.1.1`, tag object
  `50fc5852ddf5aa9df762c97614a829ac4010a09d` → commit `db18196…`
  (tagger `danielcba`); pushed with `git push origin v0.1.1`;
  remote ref verified: annotated `tag` object on remote, peeling to `db18196…`
- GitHub Release: `Company OS Monitor v0.1.1` (tag `v0.1.1`,
  draft=false, prerelease=false, published `2026-10-01T16:40:58Z`),
  notes = CHANGELOG `[0.1.1]` section (26 lines), assets = 0,
  currently listed first (Latest)
- `v0.1.0` re-verified after publication: tag object `d3504eb1…` unchanged,
  release `Company OS Monitor v0.1.0` draft=false, prerelease=false;
  releases total = 2

## Post-state

- `git status`: `M start.sh`, `M stop.sh` (pre-existing, never staged),
  19 untracked journal files (20 after this entry), staged = 0
- Dependabot: 0 open alerts (0 dismissed); `npm audit` 0
- `docs/release-policy.md`: not modified (its `0.1.0` snapshot lines remain
  intentionally stale per D10/D11 instructions)
- Framework: `381f56cfa48d092f85846e160d2e1fe6878f9f6f`, 9 pre-existing dirty
  entries, 0 writes
- LICENSE: still absent — owner decision pending (see `docs/release-policy.md`)

## Result

`D11: RELEASED` — `v0.1.1` published; `v0.1.0` immutable anchor intact.
