# 2026-10-01 — D22: G1–G7 / G9 security remediation & PR triage

Unit: `D22 — G1–G7 / G9 SECURITY REMEDIATION & PR TRIAGE`
(prompt `/home/dcordoba/Documents/tmp/D2_22.md`).

## 1. Dynamic baseline

- After `git fetch --prune --tags`: BRANCH `main`,
  HEAD_SHA = MAIN_REMOTE_SHA = LS_REMOTE_SHA =
  `db1819697352a0c09dc63ff4901f0063be57fc8b`, ALIGN=YES, HEAD tagged
  `v0.1.1`, 0 commits since v0.1.1, tags `v0.1.0`/`v0.1.1` intact,
  releases = 2 (`v0.1.1`, `v0.1.0`).

## 2. Working-tree baseline

- PRE-EXISTING MODIFIED (preserved byte-for-byte, never staged):
  `M docs/release-policy.md` (D13), `M start.sh`, `M stop.sh`
  (diff 3 files, 15+/3− at open and close).
- PRE-EXISTING UNTRACKED: 30 journals (29 + D21) → +1 (this journal) = 31.
- STAGED=0 at open and close; `.env` intact; D19/D20/D21 journals intact.

## 3. Authorization matrix (executed strictly)

- YES: `AUTHORIZE_D22`, `G1_G7_G9_REMEDIATION`,
  `GITHUB_SECURITY_SETTINGS_CHANGE`, `CI_CODE_CHANGE`, `G9_TRIAGE`,
  `G7_TARGET_STATE_DEFINITION`.
- NO (respected): `G6_HISTORICAL_ACCEPTANCE`, `PR_MERGE`, `PR_CLOSE`,
  `PR_REBASE`, `FORCE_PUSH`, `LICENSE_*`, `PVR_ENABLE/DISABLE`,
  `V012_*`, `SPRINT_13`, `COMMIT`, `PUSH`.

## 4. G1 evidence — SCA en CI → **CLOSED**

- Definition (D21): no executed dependency scanner in `ci.yml`; `safety`
  deliberately excluded (`ci.yml:59-61`); only bandit ran.
- Mechanism selection (evidence-based, no arbitrary tool):
  - Python: **pip-audit 2.10.1** (PyPA; no auth account — satisfies the
    documented reason `safety` was excluded; audits the installed CI env
    which resolves the root project = the real dependency surface; fails
    non-zero on known vulns).
  - Node: **npm audit** against the committed `apps/web/package-lock.json`
    (CI already runs `npm ci`).
  - Complementary to Dependabot (alerts + update PRs), not duplicative:
    this is an execution gate at build time.
- Tooling justification: new tooling = `pip-audit==2.10.1` installed
  ad-hoc in the CI step (NOT added to any manifest/lockfile; modifies
  zero project manifests — only `ci.yml`).
- Change performed (minimal, 2 steps in `lint-and-test` only):
  - `Frontend dependency audit (SCA)` → `npm audit` (policy: fail on any
    known vulnerability), inserted after `Frontend tests`.
  - `Dependency audit (SCA)` → `pip install "pip-audit==2.10.1"` +
    `pip-audit --ignore-vuln PYSEC-2026-1325` (policy: fail on any known
    vulnerability; sole documented exception: ecdsa 0.19.2 / PYSEC-2026-1325,
    transitive via python-jose, no fixed release as of 2026-10-02; comment
    in workflow says to remove the exception when a fix ships), inserted
    between `Security scan` and `Upload coverage`.
- Failure semantics VERIFIED (both directions):
  - pip-audit: stale env WITHOUT ignore → exit 1 (6 vulns in
    ecdsa/urllib3/weasyprint); fresh CI-simulated env
    (`uv` venv installing exactly the CI pip set) WITH ignore → exit 0
    ("No known vulnerabilities found, 2 ignored"); urllib3=2.8.0 and
    weasyprint=70.0 (fixed) in fresh resolve.
  - npm audit: clean `apps/web` → exit 0 (0 vulns); control with
    `lodash@4.17.15` in /tmp → exit 1.
- Workflow validated: YAML parse OK; `lint-and-test` = 22 steps.
- Local CI-equivalent (all executed): ruff ✓; mypy libs(70)/gateway(22)/
  services ✓; root pytest **799 passed**; 12 service suites **471 passed**
  (PYTHONPATH=repo root, CI-faithful); gateway **158 passed, 1 skipped**;
  frontend lint/typecheck ✓ + vitest **29 files / 182 tests passed**;
  bandit exit 0; `docker compose config` OK; `docker build`
  evaluation-service:ci ✓; `docker compose build` exit 0.
- CI RESULT: remote run NOT TRIGGERED — `COMMIT/PUSH=NO` make a remote run
  of the new workflow impossible in this unit; full local execution of every
  CI step is the verification evidence. Remote activation/validation of the
  new steps = FUTURE ACTION at next authorized push. No PR merged.

## 5. G2 evidence — secret scanning paths-ignore → **CLOSED**

- D21 recorded "9 exclusions"; dynamic count = **8**
  (`docs/**`, `adr/**`, `journal/**`, `.gitignore`, `.env.example`,
  `node_modules/**`, `.venv*/**`, `.opencode/**`) — D21 miscount corrected.
- Per-pattern analysis (evidence-based):
  - `docs/**` — prose dir, tracked; NO false-positive justification;
    broad blind spot → **REMOVED**.
  - `adr/**` — 7 tracked ADR markdown files; no FP justification → **REMOVED**.
  - `journal/**` — tracked prose journals; no FP justification
    (0 secret alerts in history) → **REMOVED**.
  - `.gitignore` — tracked pattern file; no security reason to exclude
    → **REMOVED**.
  - `.opencode/**` — 1 tracked markdown file (transaction-boundary proof);
    no FP justification → **REMOVED**.
  - `.env.example` — credential-shaped placeholders BY DESIGN
    (`CHANGE-ME-TO-A-UNIQUE-REDIS-PASSWORD`, etc.) → **KEPT** (justified).
  - `node_modules/**`, `.venv*/**` — generated, never tracked; standard,
    guards accidental force-add → **KEPT** (harmless).
- Change: `.github/secret_scanning.yml` reduced 8 → 3 entries with header
  documenting the rationale; YAML parse OK; all remaining entries exist.
- Post-verification: `secret_scanning=enabled`, `push_protection=enabled`,
  `alerts_open=0`. File-based activation occurs when the file reaches the
  default branch → FUTURE ACTION at next authorized push.

## 6. G3 evidence — validity checks → **OPEN — BLOCKED**

- PRE: `secret_scanning_validity_checks=disabled` (repo API GET).
- Official endpoint verified (GitHub Docs "Update a repository",
  `security_and_analysis.secret_scanning_validity_checks.status`;
  admin required; `permissions.admin=true`).
- Mutation attempts (all HTTP 200, ZERO state change, fresh GET after each):
  1. `PATCH -f 'security_and_analysis[...][status]=enabled'` (bracket
     notation) → no-op (gh sends literal key; incident logged).
  2. `PATCH --input` correct JSON, default API version → no-op.
  3. Same + `X-GitHub-Api-Version: 2026-03-10` (documented schema
     confirmed applied via `X-Github-Api-Version-Selected`) → no-op.
  4. Combined body incl. known-good key `secret_scanning: enabled` →
     no-op for validity_checks (known-good key echoed enabled).
  5. Cache-busted GETs (`?t=…`) → disabled (not a cache artifact).
- Control probes: invalid enum `status:"bogus"` also returns 200 → the
  endpoint does not validate/reject; it silently ignores what it will not
  apply. Content-Type confirmed `application/json`.
- Interpretation (FACT): documented, permitted mutation is not applied by
  the platform. Most consistent with feature-entitlement gating (public
  free-tier repos: secret scanning + push protection documented free;
  validity checks belong to the Secret Protection feature set) — but no
  canonical doc explicitly states the exclusion for this case, so root
  cause = UNDETERMINED (entitlement vs platform limitation).
- Gate requires effective enablement → cannot close. No regression
  (controls remain: secret_scanning + push_protection enabled).

## 7. G4 evidence — non-provider patterns → **OPEN — BLOCKED**

- PRE: `secret_scanning_non_provider_patterns=disabled`.
- Same documented endpoint/perm/version procedure; mutation attempts
  (200 OK) → state unchanged (fresh GETs, cache-busted). Combined-body
  attempt also no-op. Same control behavior as G3. Root cause
  UNDETERMINED (same class as G3). Gate not satisfiable → OPEN — BLOCKED.

## 8. G5 evidence — SHA pinning → **CLOSED**

- Precondition re-audit: repo-owned workflows = `.github/workflows/ci.yml`
  only (API shows 4 workflows: ci.yml + 3 system dynamic
  [dependabot-updates, update-graph, codeql]); `uses:` = 5/5 full-SHA,
  0 tag/branch refs.
- Official endpoint verified (Docs "Set GitHub Actions permissions for a
  repository", `PUT …/actions/permissions`, `sha_pinning_required`
  boolean, 204).
- MUTATION: `PUT {enabled:true, allowed_actions:"all",
  sha_pinning_required:true}` → **HTTP 204**; fresh GET →
  `sha_pinning_required: true`.
- Post-verification: workflows re-audited → 5 SHA refs, 0 non-SHA.
  `allowed_actions`/`enabled` unchanged.

## 9. G6 evidence — signed commits → **OPEN — FORMAL ACCEPTANCE REQUIRED**

- CURRENT STATE: `branches/main/protection/required_signatures` =
  `enabled: true` (control ACTIVE for future commits);
  `enforce_admins: false` (admin bypass window for review/signature rules).
- HISTORICAL EXCEPTION: HEAD `db18196…` `%G? = N`,
  `git verify-commit HEAD` exit 1 (commit predates/evaded enforcement).
- WHY REWRITE PROHIBITED: rebase/filter/force-push forbidden by unit rules
  and standing discipline (history immutable; release tags anchored to
  these SHAs).
- RISK: unsigned historical tip; verification relies on platform state
  (tags, branch protection) rather than cryptographic commit signature.
- ACCEPTANCE REQUIRED: `G6_HISTORICAL_ACCEPTANCE=NO` in D22 → remains
  explicitly pending; not closed via `required_signatures=true`.

## 10. G7 evidence — threat model → **CLOSED (target defined, no mutation needed)**

- Official semantics (GitHub Docs "Editing your configuration of default
  setup" + CodeQL workflow config reference + API schema):
  `threat_model: 'remote' | 'remote_and_local'`; `remote` = default
  (network sources only); `remote_and_local` adds local sources (CLI,
  env, filesystem, DB, stdin). Threat models = **public preview**,
  supported **only for Java/Kotlin and C#** during preview.
- Repository languages analyzed: actions, javascript,
  javascript-typescript, python, typescript → **no Java/Kotlin/C#** →
  `remote_and_local` would be inert for this repository today.
- Framework/ADR/policy inspection: `grep threat.model` over
  company-os-main/docs → 0 refs; product docs mention the term only
  incidentally (`docs/03-predictivo-ia-local.md` prose,
  `docs/security/frontend-token-security-design.md` frontend-only threat
  model). No canonical policy requires extended local-source taint
  modeling.
- TARGET STATE = `remote` (official default; docs recommend it when only
  network requests are untrusted — matches COS-Monitor attack surface:
  HTTP API + ingested telemetry; env/files/DB are operator-controlled).
- RATIONALE documented above; mutation NOT required; POST verified:
  `default-setup` GET → `threat_model: "remote"`, `updated_at`
  unchanged (`2026-10-01T21:22:18Z`) → no remote change occurred.

## 11. G9 dynamic PR inventory (recalculated)

- OPEN = **34** (#19–#52); total ever = 53; MERGED = 19 (incl. #53 undici
  security bump 2026-10-01); CLOSED-unmerged = 0; Dependabot alerts open = 0.
- All authored by `app/dependabot`, none draft, **0 labels** (despite
  `dependabot.yml` configuring `security`/`dependencies`), bodies =
  version updates ("permit the latest version"/"Bumps …").
- Classifications (dynamic states + checks re-pulled):
  - **29 × BLOCKED BY REVIEW, checks 2/2 SUCCESS** (merge gate = required
    1 approval): #52 #51 #50 #49 #48 #47 #46 #45 #44 #43 #42 #41 #40 #39
    #38 #37 #36 #35 #34 #33 #32 #31 #30 #29 #28 #27 #24 #23 #21.
  - **4 × BEHIND / REQUIRES REBASE, checks 2/2 SUCCESS** (actions
    ecosystem): #26 (checkout), #22 (setup-python), #20 (codecov),
    #19 (setup-node) — each modifies only `.github/workflows/ci.yml`.
  - **1 × BLOCKED BY CI**: #25 — `lint-and-test (3.12, 24)` FAILURE.
- DUPLICATE: none (same-title pairs #52/#33, #23/#24 target different
  manifests: root vs `/apps/services/user-service`). SUPERSEDED: none.
- PR #25 ROOT CAUSE (from run `36892881359` log):
  `Error: Incompatible React versions: react 19.3.0 vs react-dom 19.2.8`
  (Dependabot grouped `react` + `@types/react` bump to ^19.3.0 but left
  `react-dom` at ^19.2.8; React requires exact match) → all 29 vitest
  suites fail at suite load, "no tests" executed; docker-build skipped.
  AFFECTED JOB: `lint-and-test (3.12, 24)` / Frontend tests.
  AFFECTED DEPENDENCY: `react`/`react-dom` in `/apps/web`.
  MINIMAL FIX: bump `react-dom` to ^19.3.0 in lockstep (or Dependabot
  grouping react/react-dom) → OUT OF D22 SCOPE (app files / dependabot
  config not authorized) → FUTURE UNIT.
- No PR merged/closed/rebased; no force-push; Dependabot branches untouched.

## 12. Changes performed (complete list)

- Remote (settings): 1 effective mutation — G5
  `PUT /repos/…/actions/permissions` (`sha_pinning_required: false→true`,
  204). G3/G4 authorized PATCH attempts: 6 requests, all HTTP 200,
  ZERO state change (incidents logged above). Nothing else mutated.
- Local (files, uncommitted): `.github/workflows/ci.yml` (+14 lines: 2 SCA
  steps + policy comments) and `.github/secret_scanning.yml` (8→3
  exclusions + rationale header). No other file touched; no staging.

## 13. Tests

- LOCAL RESULT: see §4 — 799 root / 471 service / 158 gateway+1 skipped /
  182 frontend / ruff / mypy(3 blocks) / bandit 0 / SCA 0 vulns (policy) /
  compose config OK / 2 docker builds OK.
- CI RESULT: not triggered (COMMIT/PUSH=NO); RUN ID = N/A; FAILED JOB =
  none; FINAL STATE = local CI-equivalent GREEN; remote validation of the
  new workflow = FUTURE ACTION at authorized push.

## 14. Security regression check (BEFORE→AFTER, FASE 1 vs FASE 10)

- code scanning: identical (configured, 5 languages, weekly,
  `threat_model=remote`, `updated_at` unchanged) → NO CHANGE.
- secret_scanning / push_protection / dependabot_security_updates:
  enabled → enabled → NO CHANGE.
- validity_checks, non_provider_patterns: disabled → disabled →
  INTENDED-NO-OP (G3/G4 blocked attempts; no regression).
- alerts: codeql 0, secrets 0, dependabot 0 → 0,0,0 → NO CHANGE.
- actions permissions: `sha_pinning_required false→true` → **INTENDED (G5)**;
  `enabled`/`allowed_actions` unchanged.
- workflow permissions: read / can_approve false → unchanged.
- branch protection: reviews 1, strict, 2 contexts, enforce_admins false
  → unchanged. required_signatures: true → unchanged.
- PVR: disabled → disabled. Security policy:
  `isSecurityPolicyEnabled=true` (GraphQL; REST nulls are a
  field-availability artifact, not a change) → unchanged.
- SBOM 200, vulnerability-alerts 204, workflows=4 → unchanged.
- UNINTENDED: none. UNKNOWN: none relevant. TOTAL GITHUB MUTATIONS
  EFFECTIVE: 1 (G5, authorized).

## 15. Framework integrity

- FRAMEWORK HEAD: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` (expected,
  verified open+close); 9 dirty pre-existing entries (identical);
  framework writes = 0; framework journal writes = 0.

## 16. Pre-existing worktree integrity

- The 3 modified files byte-for-byte preserved (diff stat unchanged at
  close: 3 files, 15+/3−); 30 pre-existing journals preserved untracked
  (now 31 with this one); D19/D20/D21 journals untouched; `.env` intact;
  no reset/clean/restore/checkout/stash; staged=0 at close.

## 17. Commercial / secrets integrity

- COMMERCIAL CONTENT INTRODUCED = 0 (word-boundary scan, FASE 13 set +
  extended, over ci.yml diff, secret_scanning.yml and this journal).
- SECRETS INTRODUCED = 0 (secret-pattern scan over the same set).
  No credential material used anywhere (gh token never echoed).

## 18. Release boundary

- `pushed_at` unchanged (`2026-10-01T16:40:35Z`) → zero remote git
  activity; HEAD=`db18196…`=`v0.1.1`; tags/releases untouched;
  CHANGELOG/README/versions untouched; `license=null` (LICENSE unit still
  NOT AUTHORIZED). `v0.1.2` remains BLOCKED + NOT AUTHORIZED.

## 19. Final dispositions

- G1 `CLOSED` · G2 `CLOSED` · G3 `OPEN — BLOCKED` · G4 `OPEN — BLOCKED` ·
  G5 `CLOSED` · G6 `OPEN — FORMAL ACCEPTANCE REQUIRED` · G7 `CLOSED` ·
  G9 `OPEN — triage complete, 34 PRs classified, 0 merged`.
- FUTURE ACTIONS (require new explicit authorization): push+remote-CI
  validation unit (activates G1 steps + G2 file); G3/G4 re-attempt after
  platform/entitlement determination; G6 formal acceptance; G9 per-PR
  merge unit (actions PRs after G1/G5 now eligible post-rebase; #25 fix
  unit); then LICENSE → v0.1.2 → Sprint 13; PVR separate
  (`AUTHORIZE_PVR_ENABLE`).
- COMMIT=NO · PUSH=NO · TAG=NO · GITHUB_RELEASE=NO ·
  VERSION_CHANGE=NO · INCIDENTS: 6 ineffective authorized PATCH requests
  (G3/G4), fully disclosed above, zero impact.
