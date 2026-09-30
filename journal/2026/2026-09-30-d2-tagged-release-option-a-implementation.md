# D2 Option A — Tagged Release: Implementation (preparation, publication pending)

**Date:** 2026-09-30
**Decision:** D2 = **Option A — Tagged Release** (owner decision, given).
**Status:** PREPARATION COMPLETE — publication gates pending
(`AUTHORIZE_COMMIT=NO`, `AUTHORIZE_PUSH=NO` in this operation).

## Baseline

- Repository: `danielcba/company-os-monitor`, branch `main`.
- SHA: `df911a8a976a5d83617060a94cd6992701a384cc`
  (verified `HEAD = origin/main = ls-remote`, 0/0, staged 0 before this task).
- CI of baseline: run `36649695292` (`workflowName=CI`,
  `headSha=df911a8…`, `completed/success`; jobs `lint-and-test (3.12, 24)`
  and `docker-build` PASS).
- Framework `company-os`: `381f56cfa48d092f85846e160d2e1fe6878f9f6f`
  (triple-verified, not written to).

## Decision A and release unit

- **RELEASE VERSION = 0.1.0** — single platform/product version.
- **TAG = v0.1.0** (annotated; to be created only after a release commit is
  published with CI PASS on that exact SHA).
- **RELEASE UNIT = complete product `company-os-monitor`**
  (all services, agents, libraries, web frontend, infrastructure).
- **VERSION POLICY = single platform/product version** (no second versioning
  line).

## Versioning inventory (verified before modifying)

- **17** `pyproject.toml` files with `version = "0.1.0"` — FACT (the
  previously reported "18" was an off-by-one; actual count is 17: root +
  gateway + 3 agents + 12 services). All already correct → **no changes**.
- `apps/web/package.json` had `0.0.0` (placeholder) → **aligned to `0.1.0`**.
- `apps/web/package-lock.json` root entries (`version` at line 3 and
  `packages[""].version`) had `0.0.0` → **aligned to `0.1.0`** (2 lines).
- No other versioned source: no runtime version binding in the frontend, no
  image registry tags (`infrastructure/docker/docker-compose.yml` uses
  `build:` only, no `image:` keys) → **no Docker tag changes**
  (documented decision: no versioned image mechanism exists).
- No third-party versions or dependencies touched.

## CHANGELOG

- New product changelog at **`CHANGELOG.md`** (root), Keep a Changelog style,
  separate from `journal/` and from `docs/remediation/CHANGELOG_PHASE{14,20}.md`
  (those are NOT reused).
- Section `## [0.1.0] - 2026-09-30` — initial section with factual
  Added/Security/Fixed entries, every bullet traced to a verified ancestor
  commit SHA (28 SHAs verified via `git merge-base --is-ancestor`) or to
  documentation/journals. No invented features; 160 commits not copied
  wholesale; no commercial content.

## Release policy

- New `docs/release-policy.md` — the 12 required minimal rules
  (release = complete product, SemVer, `vMAJOR.MINOR.PATCH`, tag on main with
  required CI PASS, GitHub Release = exact tag, no releases over unverified
  commits, published tags immutable, fixes → new version, traceable version
  change, Conventional Commits, journals ≠ CHANGELOG, no complex release
  automation while a controlled manual process suffices) + the explicit manual
  sequence (prepare → push → CI PASS → annotated tag → push tag → GitHub
  Release).

## README / references

- `README_EN.md`: `Version: 1.0` → `Version: 0.1.0` (contradiction with the
  single product version; `Status: Official` untouched).
- `README_ES.md`: `Versión: 1.0` → `Versión: 0.1.0` (same; `Estado:` untouched).
- `README.md` License section: conditional "See `LICENSE` when present."
  replaced with an accurate statement — no LICENSE exists, selection is an
  owner decision, no license is assumed. No false claim introduced.
- No other version/release/CHANGELOG references found (README_EN/ES have no
  License section; no SPDX headers; no license fields in pyprojects).

## LICENSE status

- `LICENSE STATUS = OWNER DECISION REQUIRED` — **EXTERNAL / REQUIRES OWNER
  DECISION**. No LICENSE file exists; none created; no license selected or
  copied. The written release policy does **not** mandate a license file for a
  release, so LICENSE does not gate the v0.1.0 tag under the policy; it remains
  an owner decision required before external distribution that requires one.

## Automation status

- Only `.github/workflows/ci.yml` (lint-and-test + docker-build,
  `permissions: contents: read`, no tag/release/publish triggers). No release
  scripts. → **MANUAL / controlled** per policy. Future automation =
  RECOMMENDATION only (not implemented).

## Files affected by this task

- `apps/web/package.json` (M, 1 line)
- `apps/web/package-lock.json` (M, 2 lines)
- `README.md` (M, License section)
- `README_EN.md` (M, 1 line)
- `README_ES.md` (M, 1 line)
- `docs/release-policy.md` (new)
- `CHANGELOG.md` (new)
- this journal (new, append-only)

Excluded and preserved: `.env`, `start.sh`, `stop.sh`, all historical
journals, `docs/remediation/*`, Framework, Dependabot PR #53, `.github/`.

## Validations (real figures, after changes)

| Gate | Result |
|---|---|
| `git diff --check` | PASS |
| JSON/package metadata | PASS — `0.1.0` synced across `package.json` + both lockfile root entries |
| `npm install --dry-run` (apps/web) | PASS — "up to date", rc=0 |
| YAML (`ci.yml`, unchanged) | PASS |
| `ruff check .` | All checks passed |
| `mypy --config-file mypy.ini libs/` | Success: no issues found in 70 source files |
| `bandit -r apps/ libs/ -ll -c bandit.yaml` | rc=0, No issues identified |
| `python3 -m compileall apps libs` | OK |
| `pytest tests/` | **799 passed** |
| `pytest tests/security tests/architecture` | **354 passed** |
| frontend `vitest run` | **29 files / 182 tests passed** |
| `docker compose config -q` | OK |
| new skips/xfails | 0 (identical to baseline) |

No workflow, config, or test was relaxed; no test disabled.

## External decisions / pending gates

1. **REQUIRES OWNER DECISION:** license choice (LICENSE file absent).
2. **PENDING AUTHORIZATION:** `AUTHORIZE_COMMIT=YES` → single preparation
   commit (parent = `df911a8…`); `AUTHORIZE_PUSH=YES` → push; then CI on the
   new SHA must PASS; only then annotated tag `v0.1.0` + push tag + GitHub
   Release `Company OS Monitor v0.1.0`.
3. Dependabot PR #53: not merged, not touched (EXCLUDED).

## Result

- Option A policy, versioning alignment (0.1.0), CHANGELOG, README
  corrections: **DONE and validated locally**.
- Commit: **NOT CREATED** (no `AUTHORIZE_COMMIT=YES`). Push: **NOT PERFORMED**.
- Tag `v0.1.0` / GitHub Release: **NOT CREATED** (rules 21–22: no tag before
  a final release commit with green CI; no release before verified tag).
- D2 status: **PARTIAL — release policy implemented; publication gates and
  LICENSE owner decision pending.**

No secrets recorded. No commercial content. Framework untouched.
