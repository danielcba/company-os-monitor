# D10 — v0.1.1 Release Preparation / Pre-Release Gate

**Date:** 2026-10-01
**Scope:** version/CHANGELOG/README preparation for the PATCH release `0.1.1`
only. No release commit, no push, no tag, no GitHub Release.
**Authorization (strict, non-transitive):**

```
AUTHORIZE_FUTURE_RELEASE = YES        (interpreted only inside this preparation unit)
AUTHORIZE_RELEASE_PREPARATION = YES
AUTHORIZE_COMMIT = NO ; AUTHORIZE_PUSH = NO ; AUTHORIZE_TAG = NO
AUTHORIZE_GITHUB_RELEASE = NO ; AUTHORIZE_DEPENDENCY_REMEDIATION = NO
AUTHORIZE_DEPENDABOT_REVIEW = NO ; AUTHORIZE_DEPENDABOT_MERGE = NO
AUTHORIZE_LICENSE_CHANGE = NO ; AUTHORIZE_SECURITY_TOOLING = NO
AUTHORIZE_JOURNAL_COMMIT = NO
```

Append-only entry. New file. D2–D9 and Framework journals were not modified.
This journal stays untracked (outside any commit).

## 1. Dynamic baseline BEFORE (after `git fetch --prune --tags`)

```
BRANCH                 = main
HEAD_SHA               = d6f4f8d800d50774a6c328112d88f9e2bc75ff98
MAIN_REMOTE_SHA        = d6f4f8d800d50774a6c328112d88f9e2bc75ff98
LS_REMOTE_SHA          = d6f4f8d800d50774a6c328112d88f9e2bc75ff98
DIVERGENCE_HEAD_REMOTE = 0	0
DIVERGENCE_REMOTE_LS   = identical
```

FACT — matches the expected post-D9 baseline `d6f4f8d…` (verified, not
assumed). Fetch also updated Dependabot feature-branch refs (forced updates on
9 remote PR branches = EXTERNAL, server-side, untouched locally).
No `v0.1.1` tag locally or remotely. No baseline HARD STOP.

## 2. Working tree BEFORE (captured first)

```
git diff --stat: start.sh | 2 +-, stop.sh | 11 +++ (12 insertions, 1 deletion)
git diff --cached: empty (staged = 0)
git status --short: 20 lines = 2 modified (start.sh, stop.sh) + 18 untracked journals
.env: present, untouched
```

Classification: `start.sh`, `stop.sh` and all 18 journals (17 previous + D9) =
**PRE-EXISTING**; no `UNKNOWN` difference at start. Nothing staged, no
`git add .` / `git add -A` at any point.

## 3. v0.1.0 anchor revalidation

```
v0.1.0^{}       = 3de73fe73296e99f356324cf5f2825c47256f181
tag object      = d3504eb1b5f12c3fae83b3455e1c6fdce57a78af (local + remote)
GitHub Release  = "Company OS Monitor v0.1.0", Latest, draft=false, releases = 1
```

INTACT — not modified, moved, deleted or re-created. No HARD STOP.

## 4. Release policy verification (FASE 3)

`docs/release-policy.md` read, not modified:

- rule 2 — Semantic Versioning, single platform version for every component;
- rule 3 — tags `vMAJOR.MINOR.PATCH`, annotated only;
- rule 7 — published tags immutable, correction requires a new version;
- rule 8 — **post-release fixes require a new version (PATCH at minimum)**;
- rule 9 — bump + CHANGELOG + tag form one auditable chain;
- rule 11 — journals never replace the CHANGELOG;
- procedure: preparation commit → CI on that SHA → annotated tag → push →
  GitHub Release derived from CHANGELOG.

```
CURRENT VERSION      = 0.1.0 (verified in sources, see inventory)
TARGET PATCH VERSION = 0.1.1
POLICY EVIDENCE      = rule 8 + rule 9 (docs/release-policy.md)
```

## 5. Version inventory BEFORE (exhaustive scan, before touching files)

Tracked files containing `0.1.0`:

| source | occurrences | classification |
|---|---|---|
| 17 `pyproject.toml` (`version = "0.1.0"`) | 1 each = 17 | product version → bump |
| `apps/web/package.json:4` | 1 | product version → bump |
| `apps/web/package-lock.json` (line 3 + `packages[""].version` line 9) | 2 | product version → bump |
| `README_EN.md:3` `Version: 0.1.0` | 1 | product version metadata → bump |
| `README_ES.md:3` `Versión: 0.1.0` | 1 | product version metadata → bump |
| `libs/shared/tracing.py:55` `os.getenv("APP_VERSION", "0.1.0")` | 1 | product version default → bump (see below) |
| `CHANGELOG.md` (section + link) | 2 | history → preserve |
| `docs/release-policy.md` (rule 3 example, snapshot lines 66–67) | 3 | policy doc → not modified (FASE 3) |
| `journal/…d2-tagged-release-option-a-implementation.md` | 14 | append-only history → preserve |
| `README.md` | 0 | no version metadata (index only) → not touched |
| scripts / CI / compose / docs (other) | 0 | no product version reference found |

Generated (untracked, gitignored) build artifacts also show `0.1.0`
(`libs/cos_monitor.egg-info/PKG-INFO`, nested `*.egg-info/PKG-INFO`,
`.venv-py312/…/cos_monitor-0.1.0.dist-info`) → regenerated on install, not part
of the release file set, untouched.

**Decision recorded:** `libs/shared/tracing.py` `APP_VERSION` default was
audited as a product-version source by every prior gate of this repository
(`d2-final-readiness-gate`, `d2-release-publication-gate-final-verification`,
`d2-release-publication-execution`, `post-release-production-readiness-gate`
all assert "`APP_VERSION` default = `0.1.0`" and "contradictory version source
scan: 0 hits"). Nothing in the repository or `.env` sets `APP_VERSION`, so the
default is the effective telemetry `service.version`. Leaving it at `0.1.0`
would be a contradictory version source after the bump → aligned to `0.1.1`
(one string literal, no behaviour change). Reported explicitly instead of
silently included.

## 6. Version preparation executed (FASE 5/6/7)

23 files modified by D10 (all unstaged):

- **17 `pyproject.toml`**: `version = "0.1.0"` → `"0.1.1"` (1 line each).
- **`apps/web/package.json`**: `"version"` → `0.1.1`.
- **`apps/web/package-lock.json`**: both root entries → `0.1.1` (2 lines);
  dependency versions untouched (`undici` `8.11.2`, `jsdom` `30.0.1`).
- **`README_EN.md:3`**: `Version: 0.1.1`.
- **`README_ES.md:3`**: `Versión: 0.1.1`.
- **`libs/shared/tracing.py:55`**: `APP_VERSION` default → `0.1.1`.
- **`CHANGELOG.md`**: new section `## [0.1.1] - 2026-10-01` (real
  preparation date, no invented future date) + link reference
  `[0.1.1]: …/releases/tag/v0.1.1`; `## [0.1.0] - 2026-09-30` and
  `[0.1.0]:` untouched (append-only in historical terms).

CHANGELOG `[0.1.1]` content is limited to verified facts: PR #53 merged
(`d6f4f8d…`), `undici` `8.10.0` → `8.11.2`, 7 previously open Dependabot
alerts now fixed (0 open / 0 dismissed), `npm audit` 0 vulnerabilities,
development/transitive scope with no runtime exposure, validation figures,
LICENSE still absent. No feature claims, no security-tooling claim, no
commercial content, no description of the change as runtime.

Nothing else modified: no dependency versions, no Framework, no Docker base
images, no runtime/infra/security config, no branch protection.

## 7. Version consistency AFTER (FASE 8, exhaustive re-scan)

```
17 pyproject.toml          = "0.1.1" (unique)
apps/web/package.json      = 0.1.1
lockfile top + root        = 0.1.1 / 0.1.1
README_EN.md / README_ES.md= 0.1.1 / 0.1.1
APP_VERSION default        = 0.1.1
CHANGELOG                  = ## [0.1.1] - 2026-10-01 (new) + ## [0.1.0] - 2026-09-30 (intact)
```

Remaining `0.1.0` occurrences and classification:

- `CHANGELOG.md` (3): `EXPECTED CHANGELOG HISTORY` (section, link) +
  `EXPECTED HISTORICAL` (mention of `v0.1.0` inside the 0.1.1 entry).
- `journal/2026/2026-09-30-d2-tagged-release-option-a-implementation.md` (14):
  `EXPECTED HISTORICAL` (append-only journal, never rewritten).
- `docs/release-policy.md:22` `v0.1.0` example: `EXPECTED v0.1.0 ANCHOR`.
- `docs/release-policy.md:66–67` "Product version: 0.1.0 … all 0.1.0":
  `STALE` — documentation snapshot of the previous release. **Not modified**
  because FASE 3 explicitly forbids modifying the release policy; reported as
  a known, intentional omission for a separate authorized unit. Not a build or
  release input; rule 8 of that same policy is what drives this patch.
- gitignored generated artifacts (`*.egg-info`, `.venv` dist-info): build
  output, regenerated on install, not part of the release file set.

```
PRODUCT VERSION REFERENCES = 0.1.1
HISTORICAL v0.1.0 REFERENCES = INTACT
```

## 8. Dependency verification post-D9 (FASE 9 — re-verified, not re-remediated)

```
UNDICI             = 8.11.2 (installed and in lockfile)
DEPENDENCY PATH    = apps/web (dev) → jsdom@30.0.1 → undici (indirect/transitive)
DEPENDABOT         = 0 open, 11 fixed, 0 dismissed
NPM AUDIT          = found 0 vulnerabilities
npm install --dry-run = no changes required (lockfile consistent with package.json 0.1.1)
```

Not converted to a direct dependency; no additional upgrade performed.

## 9. Quality validation (FASE 10, executed after the edits)

| check | result |
|---|---|
| `ruff check .` | All checks passed |
| `mypy --config-file mypy.ini libs/` | Success: no issues found in 70 files |
| `bandit -r apps/ libs/ -ll -c bandit.yaml` | rc=0, "No issues identified." |
| `python -m compileall apps libs` | rc=0 |
| `pytest tests/security tests/architecture` | **354 passed** |
| `pytest tests/` | **799 passed** |
| `npx vitest run` (apps/web) | **29 files / 182 tests** |
| `docker compose … config -q` | rc=0 |
| `npm install --dry-run` (apps/web) | no changes required |
| `npm run build` (production build) | **success** ("built in 1.61s"), `dist/` generated (gitignored) |

```
NEW SKIPS = 0 ; NEW XFAILS = 0 ; REGRESSIONS = 0
```

No HARD STOP: no regression introduced by D10.

## 10. Production artifact as preparation evidence (FASE 11)

Fresh build (not published, not attached to any release):

```
sha256 = sha256:5855bed0351d6b84bc875ef045f6b25a8fbb367a35f4fa679010eb26a05e8cb0
size   = 75341208 bytes
builder = node:24-alpine → runtime = nginx:1.27-alpine (NGINX_VERSION 1.27.5)
node in runtime = ABSENT ; node_modules = ABSENT
undici files = 0 ; jsdom files = 0
RUNTIME EXPOSURE: NONE (no development dependency in the runtime image)
```

## 11. Security state reconfirmation (FASE 12 — verify only)

```
Dependabot open alerts = 0 (fixed = 11, dismissed = 0)
secret scanning open   = 0
code scanning          = 404 "no analysis found" — PRE-EXISTING
```

`AUTHORIZE_SECURITY_TOOLING=NO` → no code scanning activation, no new security
workflow, no policy change. `AUTHORIZE_LICENSE_CHANGE=NO` → no `LICENSE`,
`LICENSE.txt`, `LICENSE.md`, SPDX or `license` field created:
`LICENSE = PENDING OWNER DECISION` (absence re-verified).

## 12. Framework integrity (FASE 14)

`company-os-main` HEAD = `381f56cfa48d092f85846e160d2e1fe6878f9f6f`;
worktree = 9 entries (4 modified + 5 untracked), all PRE-EXISTING.
**0 bytes written** to the Framework; ADRs, decisions, ontology, workflows,
CODEOWNERS, SECURITY.md and Framework journals untouched.

```
FRAMEWORK MODIFIED = NO
FRAMEWORK JOURNAL MODIFIED = NO
```

## 13. Commercial content (FASE 15)

Modified/new content scanned (all D10 diffs + this journal) against the
standard commercial/marketing term list: **0 matches**. Secret/token scan on
the same content: 0 matches.

```
COMMERCIAL CONTENT INTRODUCED = ABSENT
```

## 14. Git state / release boundary (FASE 17–18)

```
D10 MODIFICATIONS: 23 tracked files (17 pyproject + package.json + package-lock
                   + README_EN + README_ES + libs/shared/tracing.py + CHANGELOG.md)
                   53 insertions / 23 deletions (all unstaged)
PRE-EXISTING:      M start.sh, M stop.sh (unchanged since capture), 18 untracked journals
STAGED:            0
UNTRACKED:         19 journals after this file (18 + this one) — no other untracked path
BUILD OUTPUT:      apps/web/dist, *.egg-info, .venv → gitignored (not release files)

RELEASE COMMIT = NOT CREATED        PUSH = NOT PERFORMED
TAG v0.1.1     = NOT CREATED        GITHUB RELEASE v0.1.1 = NOT CREATED
git commit / git push / git tag / gh release create : NOT EXECUTED
branch protection unchanged ; LICENSE unchanged ; security tooling unchanged
SPRINT 13 = NOT STARTED
```

`v0.1.0` re-verified at close: commit/tag/release untouched.
Product version sources now read `0.1.1`; the `v0.1.1` tag still does not
exist (local or remote) and is not implied by this unit.

## 15. Journal (FASE 16)

Created: `journal/2026/2026-10-01-d10-v0-1-1-release-preparation.md`
(append-only, new file, untracked).

```
JOURNAL UPDATED = YES
JOURNAL COMMITTED = NO   (AUTHORIZE_JOURNAL_COMMIT = NO)
```

## 16. Final gate status

```
PRODUCT VERSION (working tree) = 0.1.1
CHANGELOG                      = PREPARED ([0.1.1] - 2026-10-01, [0.1.0] intact)
README VERSION METADATA        = PREPARED (EN/ES = 0.1.1)
VALIDATION                     = PASS (ruff/mypy/bandit/compileall/354/799/29-182/
                                 compose/npm dry-run/production build)
DEPENDABOT OPEN                = 0
v0.1.0                         = INTACT
FRAMEWORK                      = INTACT
JOURNAL                        = UPDATED / UNTRACKED
STAGED                         = 0
D10 = READY FOR SEPARATE RELEASE-COMMIT/PUBLISH UNIT
```

No authorization for the following unit is implied by this one.
