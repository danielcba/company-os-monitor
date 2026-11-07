# D2 Option A — Release Publication Execution (commit → push → CI → tag → GitHub Release)

**Date:** 2026-09-30
**Authorizations (verbatim):** `AUTHORIZE_COMMIT=YES`, `AUTHORIZE_PUSH=YES`
**Outcome:** publication sequence executed end-to-end and verified.

Append-only entry. Created after the release commit; therefore **not part of**
the release commit and not staged (the release commit contains exactly the 8
authorized paths). No historical journal and no Framework journal modified.

## Baseline (FASE 0, before the commit)

- `git fetch --prune` → no updates.
- `main`; `HEAD` = `origin/main` = `git ls-remote origin refs/heads/main` =
  `df911a8a976a5d83617060a94cd6992701a384cc`; divergence `0	0`.
- `git tag --list` and `git ls-remote --tags origin` empty → `v0.1.0` did not
  exist locally or remotely.
- Staged: exactly 8 paths; `git diff --cached --check` rc=0.

## Pre-commit gate (FASE 2)

| Gate | Result |
|---|---|
| `ruff check .` | All checks passed |
| `mypy --config-file mypy.ini libs/` | Success: no issues in 70 source files |
| `bandit -r apps/ libs/ -ll -c bandit.yaml` | rc=0, "No issues identified" |
| `python3 -m compileall apps libs` | rc=0 |
| `docker compose -f infrastructure/docker/docker-compose.yml --env-file .env config -q` | rc=0 |
| `npm install --dry-run` | rc=0 ("up to date") |
| `pytest tests/` | 799 passed |
| `pytest tests/security tests/architecture` | 354 passed |
| `npx vitest run` | 29 files / 182 tests passed |

Versioning re-confirmed: 17 `pyproject.toml` = `0.1.0`;
`apps/web/package.json` + `package-lock.json` root entries = `0.1.0`;
`APP_VERSION` default = `0.1.0`; README EN/ES = `0.1.0`.
Secret scan on staged diff = 0 hits; commercial content = 0 hits;
`.github/` in staged diff = 0 paths; dependencies updated = 0.

## Framework freeze (FASE 3) and historical integrity (FASE 4)

- Framework `company-os`: `HEAD` = `origin/main` =
  `git ls-remote origin refs/heads/main` =
  `381f56cfa48d092f85846e160d2e1fe6878f9f6f`; Framework journals modified = 0.
- `git merge-base --is-ancestor` vs `df911a8a976a5d83617060a94cd6992701a384cc`
  and vs the release commit: `7ca822d` U6A, `079024e` U6B, `65f528f` U7,
  `65f528f`… `6522395` F3, `eb686e2` Redis, `446dd36` CORS, `8560679` D1,
  `df911a8` D1-test-fix → **8/8 YES** on both.

## Commit (FASE 5)

- Command: `git commit -m "release: prepare v0.1.0"` (the only commit created).
- **RELEASE_COMMIT_SHA = `3de73fe73296e99f356324cf5f2825c47256f181`**
- Parent = `df911a8a976a5d83617060a94cd6992701a384cc` (verified `git rev-parse HEAD^`).
- `git show --stat` = 8 files changed, 321 insertions(+), 6 deletions(-);
  `git diff-tree --name-only` = exactly the 8 authorized paths.
- `git diff HEAD^ HEAD --check` rc=0.
- Excluded and preserved: `start.sh`, `stop.sh`, 6 pre-existing untracked
  journals, `.env`, `docs/remediation/*`, Dependabot PR #53.

## Post-commit local gate (FASE 6)

- `pytest tests/` 799 passed; `pytest tests/security tests/architecture`
  354 passed; `npx vitest run` 29 files / 182 tests passed;
  `ruff` / `mypy` (70 files) / `bandit` clean; compose config rc=0.

## Push (FASE 7) and remote verification (FASE 8)

- `git push origin main` → accepted: `df911a8..3de73fe  main -> main`
  (no `--force`, no `--force-with-lease`).
- Remote banner also reported: "Changes must be made through a pull request"
  and "2 of 2 required status checks are expected" (informational; the push
  was accepted by GitHub without any protection being disabled or bypassed by
  this task).
- After `git fetch --prune`: `HEAD` = `origin/main` =
  `git ls-remote origin refs/heads/main` =
  `3de73fe73296e99f356324cf5f2825c47256f181`; divergence `0	0`.

## Release CI (FASE 9) — exact SHA only

- Run ID: **`36752227058`**, workflow `CI`,
  `headSha = 3de73fe73296e99f356324cf5f2825c47256f181`,
  status `completed`, conclusion **`success`**.
- Jobs (same run, same SHA): `lint-and-test (3.12, 24)` = **success**;
  `docker-build` = **success**.
- Baseline CI (`36649695292` on `df911a8…`) and Dependabot runs were **not**
  used as substitutes.

## Tag (FASE 10–12)

- Pre-check: `git tag --list` and `git ls-remote --tags origin` empty → no
  existing `v0.1.0` (no overwrite).
- Created annotated tag: `git tag -a v0.1.0 3de73fe73296e99f356324cf5f2825c47256f181 -m "Release v0.1.0"`.
- Local: `git cat-file -t v0.1.0` = **`tag`** (annotated, not lightweight);
  tag object = `d3504eb1b5f12c3fae83b3455e1c6fdce57a78af`;
  `git rev-list -n 1 v0.1.0^{}` = `3de73fe73296e99f356324cf5f2825c47256f181`.
- `git push origin v0.1.0` → `* [new tag] v0.1.0 -> v0.1.0` (no force).
- Remote: `git ls-remote --tags origin refs/tags/v0.1.0` =
  `d3504eb1b5f12c3fae83b3455e1c6fdce57a78af	refs/tags/v0.1.0`;
  tag object → commit target `3de73fe73296e99f356324cf5f2825c47256f181`.
  → annotated tag object verified remotely, target = release commit.

## GitHub Release (FASE 13)

- `gh release create v0.1.0 --title "Company OS Monitor v0.1.0" --notes-file …`
  → created: `https://github.com/danielcba/company-os-monitor/releases/tag/v0.1.0`
- Verified: `tag=v0.1.0`, `name=Company OS Monitor v0.1.0`,
  `target=main`, `isDraft=false`, `isPrerelease=false`.
- Notes derived from `CHANGELOG.md` `[0.1.0] - 2026-09-30`; no invented
  features, no commercial content, no license declared (LICENSE stated as an
  owner decision); no artifacts attached.

## End-to-end (FASE 14) and preservation (FASE 15)

- Chain verified: `main` → `3de73fe73296e99f356324cf5f2825c47256f181` →
  CI PASS (run `36752227058`) → annotated tag `v0.1.0` → remote tag verified →
  GitHub Release `Company OS Monitor v0.1.0`.
- `git log --oneline -2`: `3de73fe release: prepare v0.1.0` /
  `df911a8 …` → **no second commit**, no history rewrite, divergence `0	0`.
- Working tree: only pre-existing ` M start.sh`, ` M stop.sh` and the 8
  untracked journals (6 pre-existing + 2 gate journals) — all outside the
  release commit.
- `.env` mtime `2026-09-29 18:21:03 -0300` (unchanged);
  `docs/remediation/*` diff = 0 paths; historical journals unmodified.
- Branch protection unchanged: `strict=true`, contexts
  `["lint-and-test (3.12, 24)", "docker-build"]`, `required_signatures=true`,
  review count `1`, `allow_force_pushes=false`, `allow_deletions=false`.
- Dependabot PR #53: `state=OPEN`, `changedFiles=1` → **not merged, not
  closed, not modified by this task**. (Remote Dependabot branches were
  rebased by the Dependabot bot during a fetch; no action was taken on them.)

## Informational (pre-existing, not introduced by this release)

- GitHub push banner: "GitHub found 7 vulnerabilities on
  danielcba/company-os-monitor's default branch (2 high, 2 moderate, 3 low)"
  → pre-existing repository/dependency state reported by GitHub; the release
  commit changed only docs/metadata (8 paths, no dependency updates).
  → RECOMMENDATION only: triage via the Dependabot security tab in a future,
  separately authorized task.

## License

- `LICENSE` absent; no license selected, created, copied, or SPDX-added.
  **PENDING OWNER DECISION — LICENSE** (not a technical gate of this tag).

## Result

- Commit: `3de73fe73296e99f356324cf5f2825c47256f181`. Push: accepted.
- CI on the exact release SHA: PASS (run `36752227058`).
- Tag `v0.1.0`: created (annotated) and remotely verified.
- GitHub Release `Company OS Monitor v0.1.0`: created and verified.
- HARD STOP encountered: **0**. Sprint 13 not started. No secrets recorded.
  No commercial content.
