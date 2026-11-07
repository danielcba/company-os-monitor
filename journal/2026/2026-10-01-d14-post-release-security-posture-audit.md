# 2026-10-01 — D14: post-release security posture audit

Unit: `D14 — POST-RELEASE SECURITY POSTURE AUDIT` (prompt
`/home/dcordoba/Documents/tmp/D2_14.md`).

Authorization matrix: `AUTHORIZE_D14=YES`, `AUTHORIZE_SECURITY_AUDIT=YES`,
`AUTHORIZE_SECURITY_VERIFICATION=YES`, `AUTHORIZE_GITHUB_SECURITY_VERIFICATION=YES`,
`AUTHORIZE_CI_SECURITY_VERIFICATION=YES`; everything else `NO` (no security
tooling changes, no Code Scanning changes, no commit/push/tag/GitHub Release,
no future release, no release preparation, no LICENSE, no dependency remediation,
no Dependabot review/merge, no journal commit, no Sprint 13, no Framework writes).
Audit-only: 0 functional files modified by this unit.

## Dynamic baseline (after `git fetch --prune --tags`)

- BRANCH `main`; HEAD = origin/main = ls-remote =
  `db1819697352a0c09dc63ff4901f0063be57fc8b`; divergences `0 0` / `0 0`

## Release anchors (read-only)

- `v0.1.0`: commit `3de73fe73296e99f356324cf5f2825c47256f181`, tag object
  `d3504eb1b5f12c3fae83b3455e1c6fdce57a78af` (local+remote) — intact
- `v0.1.1`: tag object `50fc5852ddf5aa9df762c97614a829ac4010a09d` →
  `db18196…` (local+remote) = current `main` — intact
- GitHub Releases: `v0.1.1` published (draft=false, prerelease=false),
  `v0.1.0` published — both intact; total = 2

## Working tree baseline

- `M docs/release-policy.md` (D13, uncommitted as authorized — preserved),
  `M start.sh`, `M stop.sh` (pre-existing — preserved), staged = 0,
  22 untracked journals, `.env` untouched; D14 modified 0 functional files

## Secret Scanning

- `secret_scanning = enabled`; `secret_scanning_non_provider_patterns = disabled`;
  `secret_scanning_validity_checks = disabled` (from repo `security_and_analysis`)
- Alerts: open = 0, resolved = 0 (REST, both states)
- Config file `.github/secret_scanning.yml` (tracked) declares `paths-ignore`
  for `docs/**`, `adr/**`, `journal/**`, `.gitignore`, `.env.example`,
  `node_modules/**`, `.venv*/**`, `.opencode/**`
- No alert dismissed/modified; no configuration change

## Push Protection

- `secret_scanning_push_protection = enabled` — ACTIVE at repository level
- Effect over `main`: control enabled repo-wide; path-level exclusions come from
  the `paths-ignore` above (behavior not directly observable via API)
- No change made

## Dependabot

- `dependabot_security_updates = enabled` (ACTIVE)
- Alerts: open = 0, fixed = 11, dismissed = 0; GraphQL `vulnerabilityAlerts
  totalCount = 11` (all in fixed state per REST)
- `undici`: open = 0; manifest at HEAD = `undici 8.11.2` (via `jsdom@30.0.1`);
  local `npm audit` = 0 vulnerabilities
- Version updates: `.github/dependabot.yml` tracked (pip ×17, npm, docker…);
  workflows `Dependabot Updates` and `Dependency Graph` active
- No remediation, no PR merge, no dismissal performed

## Code Scanning

- REST `code-scanning/alerts?state=open` → 404 `no analysis found`;
  REST `code-scanning/analyses` → 404 `no analysis found` → ANALYSES: absent
- Repository tree: no `codeql*`, `sarif`, `semgrep`, `sast` workflow →
  advanced setup ABSENT (fact)
- Default setup: NOT DETECTED (no accessible API evidence; not converted to
  ABSENT); distinction preserved: "no analysis found" ≠ "Code Scanning disabled"
- `AUTHORIZE_CODE_SCANNING=NO` → nothing enabled/configured

## GitHub Actions security posture

- Workflows: 1 repo workflow `.github/workflows/ci.yml` + 2 GitHub-managed
  dynamic (`Dependabot Updates`, `Dependency Graph`) — no security-scanner
  workflow beyond CI's bandit step
- `permissions:` top-level `contents: read` (ci.yml:9–10) and job-level
  `permissions: contents: read` for `docker-build` (ci.yml:189–190) → no write
  permission anywhere
- `persist-credentials: false` on both `actions/checkout` steps (ci.yml:44, 195)
- `pull_request_target`: NONE (repo `.github/` grep)
- `secrets.` references: NONE → no secret exposure in workflows; codecov step is
  informational (`fail_ci_if_error: false`, no token)
- Action pinning: 5/5 `uses:` pinned to full commit SHA with version comments
  (checkout ×2, setup-python, setup-node, codecov-action)
- Repo Actions settings: `allowed_actions=all`, `sha_pinning_required=false`,
  `default_workflow_permissions=read`
- In-CI security gate: `bandit -r apps/ libs/ -ll -c bandit.yaml` (ci.yml:169–170,
  part of required job `lint-and-test (3.12, 24)`); no `npm audit`/`pip-audit`/
  CodeQL step (0 references)
- Other: plaintext ephemeral CI service credentials in workflow
  (postgres/redis test creds, `ci-build-only` build env) — CI-scoped, non-production

## Branch protection (`main`)

- `required_approving_review_count = 1`; `required_signatures.enabled = true`;
  `strict = true`; contexts `["lint-and-test (3.12, 24)", "docker-build"]`;
  `allow_force_pushes = false`; `allow_deletions = false`
- Other: `enforce_admins = false`, `required_linear_history = false`,
  `required_conversation_resolution = false`, `dismiss_stale_reviews = false`,
  `require_code_owner_reviews = false`; rulesets count = 0
- Unchanged vs D12 baseline (re-queried twice, same values)

## Security control inventory

- Secret Scanning: ACTIVE
- Push Protection: ACTIVE (with tracked `paths-ignore` config)
- Secret Scanning non-provider patterns: INACTIVE (disabled)
- Secret Scanning validity checks: INACTIVE (disabled)
- Dependabot security updates: ACTIVE (0 open / 11 fixed / 0 dismissed)
- Dependabot version updates: ACTIVE (config + dynamic workflow)
- Dependency graph: ACTIVE (20 manifests indexed; dynamic workflow)
- Code Scanning analyses: ABSENT (404 no analysis found); default setup:
  UNKNOWN (not detected)
- SAST in CI (bandit, Python): ACTIVE (required job)
- npm/pip audit in CI: ABSENT (npm audit run manually = 0)
- Branch protection: ACTIVE (reviews, signatures, strict checks, no force-push,
  no deletion)
- Workflow default permissions (`read`): ACTIVE
- Actions SHA pinning (workflow-level): ACTIVE; repo enforcement flag: OFF
- CODEOWNERS: PRESENT (enforcement of code-owner review: OFF)
- SECURITY.md / security policy URL: ACTIVE
- Private vulnerability reporting: UNKNOWN (field not observable via API)

## Gap analysis (evidence-based, no scoring)

- BLOCKER: none — no concrete condition impeding adequate operation of current
  release security (0 open dependency/secret alerts, required CI green,
  protection controls enabled)
- HIGH: none identified with concrete evidence
- MEDIUM:
  1. Code Scanning not configured — analyses absent, no CodeQL/SARIF workflow;
     SAST coverage = bandit (Python) inside CI only; JS/TS without SAST.
     Evidence: two 404 `no analysis found`; tree grep empty.
     Remediation needed: enable default setup or add advanced workflow.
     AUTHORIZED NOW = NO.
  2. Signature-control/evidence mismatch — `required_signatures=true` yet recent
     `main` history contains unsigned commits (e.g. release commit
     `db18196…` `%G? = N`, pushed successfully). Evidence: `git log --format=%G?`
     vs protection API. Impact: commit-integrity control may not cover direct
     admin pushes. Remediation: verify enforcement scope / adopt signed commits.
     AUTHORIZED NOW = NO.
- LOW:
  1. No `npm audit`/`pip-audit` step in CI (dependency checks rely on enabled
     Dependabot security updates). AUTHORIZED NOW = NO.
  2. Push protection path exclusions (`paths-ignore` covers `docs/**`,
     `journal/**`, `adr/**`, etc.) reduce scanned area; effect not observable.
     AUTHORIZED NOW = NO.
  3. `secret_scanning_validity_checks` and `non_provider_patterns` disabled →
     narrower detection. AUTHORIZED NOW = NO.
  4. Repo setting `sha_pinning_required = false` (workflow pins SHAs manually
     but enforcement is not mandated). AUTHORIZED NOW = NO.
- OBSERVATIONS:
  - CI uses plaintext ephemeral service credentials (CI-scoped test values).
  - `enforce_admins=false`, `rulesets=0`, `dismiss_stale=false`,
    `require_code_owner_reviews=false`, `required_linear_history=false`,
    `required_conversation_resolution=false` — current policy-accepted settings.
  - Private vulnerability reporting state UNKNOWN (API not observable); SECURITY.md
    directs disclosure via GitHub Security Advisory.
  - codecov action external, informational, no token referenced.

## Post-release security consistency

- v0.1.1 intact; main aligned (HEAD = origin = ls-remote = tag target);
  dependency alerts 0 open; secret alerts 0 open; Push Protection enabled;
  Dependabot enabled; Code Scanning has no analyses (gap recorded);
  required CI checks passing on the release SHA (run 36892577152 success);
  branch protection unchanged
- Result: `GAPS DETECTED` (2 MEDIUM + 4 LOW, 0 BLOCKER) — no absolute claim of
  being "secure"; gaps are recorded, not remediated (none authorized)

## Framework integrity

- SHA `381f56cfa48d092f85846e160d2e1fe6878f9f6f` unchanged; 9 pre-existing dirty
  entries; `company-os-main/journal` diff = 0; 0 writes attributable to D14

## Commercial content

- Introduced by D14: 0 (word-boundary scan of this journal → 0 hits;
  0 secret-pattern hits)

## Final status

`D14: CLOSED` — audit-only, no mutation, no hard stop triggered.
