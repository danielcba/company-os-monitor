# 2026-10-01 — D21: Pending security / release backlog sequencing

Unit: `D21 — PENDING SECURITY / RELEASE BACKLOG SEQUENCING`
(prompt `/home/dcordoba/Documents/tmp/D2_21.md`). Inventory, dependency and
sequencing phase only. Authorization matrix: `AUTHORIZE_D21=YES`,
`G1_G7_G9_AUDIT=YES`; everything mutating set to `NO`
(`G1_G7_G9_REMEDIATION=NO`, `PR_MERGE=NO`, `LICENSE_AUDIT=NO`,
`LICENSE_CHANGE=NO`, `PVR_ENABLE=NO`, all `V012_*=NO`, `SPRINT_13=NO`,
`COMMIT=NO`, `PUSH=NO`). Read-only API usage throughout; zero mutations.

## FASE 0 — dynamic baseline (after `git fetch --prune --tags`)

- BRANCH `main`; HEAD_SHA = MAIN_REMOTE_SHA = LS_REMOTE_SHA =
  `db1819697352a0c09dc63ff4901f0063be57fc8b`; HEAD↔origin EQUAL;
  origin↔ls-remote EQUAL; ALIGN: YES; HEAD tagged `v0.1.1`
- PRE-EXISTING MODIFICATIONS: 3 (`M docs/release-policy.md` (D13),
  `M start.sh`, `M stop.sh`) — diff 3 files, 15+/3−, preserved byte-for-byte
- PRE-EXISTING UNTRACKED: 29 journals (all preserved);
  STAGED: 0; ENV: `.env` present; TAGS: v0.1.0, v0.1.1; RELEASES: 2
  (`v0.1.1`, `v0.1.0`)

## FASE 1 — pending units inventory (evidence-based)

| UNIT | CURRENT STATE | EVIDENCE | DEPENDENCIES | BLOCKING? | AUTHORIZATION REQUIRED | NEXT ACTION |
|---|---|---|---|---|---|---|
| G1 SCA in CI | OPEN | `.github/workflows/ci.yml` has no executed dependency scanner; deliberate `safety` exclusion documented at `ci.yml:59-61`; only bandit runs (`ci.yml:169`) | none technical; shares `ci.yml` with G9-actions PRs | YES for G-chain closure | `G1_G7_G9_REMEDIATION=YES` | add minimal executed SCA step |
| G2 secret-scanning paths-ignore | OPEN | `.github/secret_scanning.yml` (tracked) `paths-ignore`: `docs/**`, `adr/**`, `journal/**`, `.gitignore`, `.env.example`, `node_modules/**`, `.venv*/**`, `.opencode/**` (9 entries) | none | YES for G-chain | remediation auth | reduce exclusions to non-content paths |
| G3 validity checks | OPEN | `secret_scanning_validity_checks: disabled` (repo API) | none | YES for G-chain | remediation auth (+repo setting) | enable validity checks |
| G4 non-provider patterns | OPEN | `secret_scanning_non_provider_patterns: disabled` | none | YES for G-chain | remediation auth (+repo setting) | enable non-provider patterns |
| G5 sha pinning enforcement | OPEN | `GET /actions/permissions` → `sha_pinning_required: false`; workspace pins are 5/5 SHA (`ci.yml:42,47,52,177,193`) | interacts with G9-actions PRs (merges must preserve pins) | YES for G-chain | remediation auth (+repo setting) | set `sha_pinning_required=true` |
| G6 signed commits | OPEN (partially mitigated) | `branches/main/protection/required_signatures` → `enabled: true` (enforcement ON for future commits); HEAD `db18196…` signature `%G? = N`, `git verify-commit` exit 1 (historical, immutable without prohibited history rewrite); `enforce_admins: false` | remediation would require history rewrite (prohibited) | YES for G-chain (needs formal acceptance decision) | remediation/acceptance auth | document acceptance of historical HEAD |
| G7 CodeQL threat model | OPEN (target state undefined) | `code-scanning/default-setup` → `threat_model: "remote"`, `state: configured`, `updated_at 2026-10-01T21:22:18Z`; local threat-model docs exist only for frontend token design | target state must be defined before any change | YES for G-chain | remediation auth + spec decision | define desired threat-model state |
| G9 Dependabot PRs | OPEN — 34 open (was reported as 30 in D18; dynamic count now authoritative) | `gh pr list --state open` → 34 (#19–#52), all `app/dependabot`, none draft; 0 carry labels despite `dependabot.yml` config; all bodies = version updates ("permit the latest version"/"Bumps …") | actions PRs #19/#20/#22/#26 modify `ci.yml` (conflict risk with G1) and must preserve G5 pins | YES for G-chain | `PR_MERGE=NO` (per-PR authorization later) | triage/review unit (not executed) |
| LICENSE | OPEN — no license exists | no `LICENSE`/`COPYING` file; no license mention found in READMEs | sequenced after G-closure per FASE 6 | gate for v0.1.2 | `LICENSE_AUDIT=NO`, `LICENSE_CHANGE=NO` | future independent unit |
| PVR ENABLEMENT | EVALUATED (D20 CLOSED), ENABLEMENT NOT AUTHORIZED | D20 report; `GET /private-vulnerability-reporting` → `{"enabled":false}` | independent of all chains | no | `AUTHORIZE_PVR_ENABLE=YES` | separate unit |
| v0.1.2 | NOT AUTHORIZED + BLOCKED by gate | gate requires G-closed + LICENSE resolved (not met); tags/releases intact | depends on G + LICENSE | YES | all `V012_*=NO` | after G+LICENSE |
| SPRINT 13 | NOT AUTHORIZED + BLOCKED by gate | FASE 9 gate unmet | depends on all above | YES | `SPRINT_13=NO` | last |

## G9 — full PR inventory (34 open)

- CI gate = `lint-and-test (3.12, 24)` + `docker-build`; branch protection:
  1 approving review, strict status checks, both contexts
- 29 PRs: `mergeStateStatus=BLOCKED` (missing required review), checks
  2/2 SUCCESS — #52 #51 #50 #49 #48 #47 #46 #45 #44 #43 #42 #41 #40 #39
  #38 #37 #36 #35 #34 #33 #32 #31 #30 #29 #28 #27 #24 #23 #21
- 4 PRs: `BEHIND` (head behind main; rebase needed), checks 2/2 SUCCESS —
  #26 (actions/checkout 4.4.0→7.0.1), #22 (setup-python 5.6.0→7.0.0),
  #20 (codecov 3.1.6→7.1.1), #19 (setup-node 4.4.0→7.0.0); each modifies
  only `.github/workflows/ci.yml`
- 1 PR: #25 (react + @types/react) `BLOCKED` + `lint-and-test` **FAILURE**
  (run 36892881359), docker-build SKIPPED
- Merged historically: 19 (#1–#18 + #53 undici security bump, 2026-10-01);
  total PRs ever: 53; open Dependabot alerts: 0 (no CVE-driven urgency)
- Supersession: none found — same-title pairs (#52/#33 asyncpg,
  #23/#24 python-dotenv) target different manifests (root vs
  `/apps/services/user-service`); each PR maps to one of 18 dependabot
  entries (16 pip + npm + github-actions)
- No PR closed, no PR merged, no force-push, no history rewrite (0
  mutations; `PR_MERGE=NO` respected)

## FASE 2 — dependency chain (evidence-based)

```text
BASELINE (D20/D21 dynamic)
  → G1–G7 / G9  (security closure; shared ci.yml conflict noted)
  → LICENSE     (independent technically; sequence per FASE 6 policy;
                 no contradicting evidence found)
  → v0.1.2 READINESS (gate: G closed + LICENSE resolved + baselines verified)
  → SPRINT 13   (gate: all above + no blockers)
PVR ENABLEMENT: independent unit (evaluation DONE in D20; enablement NOT AUTHORIZED)
```

- Demonstrated technical dependencies: G9-actions PRs ⊗ G5 (pins must be
  preserved on merge) and G9-actions PRs ⊗ G1 (same file `ci.yml` → merge
  order/rebase coordination required). G6 infeasible to "fix" without
  prohibited history rewrite → acceptance decision required for closure.

## FASE 4 — merge policy compliance

- Merges executed: 0; PRs closed: 0; `PR_MERGE=NO` respected for all 34.
- Per-PR authorization for a future unit must be independent; no generic
  audit authorization is inferred as merge authorization.

## FASE 11 — framework integrity

- FRAMEWORK HEAD: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` (expected);
  9 dirty pre-existing entries; framework writes = 0; framework journal
  writes = 0 → UNMODIFIED.

## FASE 12 — pre-existing state protection

- 3 modified files untouched; 29 journals preserved; `.env` intact;
  no `reset/clean/restore/checkout --/stash`; this journal is the only new
  file (untracked, staged=NO).

## FASE 13 — content discipline

- Commercial content introduced: 0 (word-boundary scan, FASE 13 set +
  extended list). Secrets introduced: 0.

## FASE 14 — hard stops

- SECURITY regression: none · RELEASE boundary: intact (tags/releases
  unchanged) · PRE-EXISTING state: intact · FRAMEWORK: intact ·
  UNAUTHORIZED mutation: none (0 mutating API calls).

## Final classification (per pending item)

- G1 `OPEN` · G2 `OPEN` · G3 `OPEN` · G4 `OPEN` · G5 `OPEN` ·
  G6 `OPEN (acceptance decision pending)` · G7 `OPEN (target undefined)` ·
  G9 `OPEN (34 PRs, 0 merged, 0 authorized)`
- LICENSE `OPEN / NOT AUTHORIZED` · PVR `EVALUATED; ENABLEMENT NOT AUTHORIZED` ·
  v0.1.2 `BLOCKED + NOT AUTHORIZED` · SPRINT 13 `BLOCKED + NOT AUTHORIZED`
- None closed, none superseded, none declared NOT APPLICABLE.

## Final result

- `D21: CLOSED — BACKLOG SEQUENCING COMPLETED (AUDIT ONLY)`
- PRIORITY ORDER confirmed: 1) G1–G7/G9 2) LICENSE 3) v0.1.2 readiness
  4) SPRINT 13; PVR separate unit.
- COMMIT = NO · PUSH = NO · TAG = NO · RELEASE = NO.
