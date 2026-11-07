# D29 / D34 — G9 CONTROLLED DEPENDABOT MERGE

Estado: APPEND-ONLY. Este journal se crea por primera vez en la ejecución
autorizada (paquete D34). Los intentos previos de D29/D31/D32/D33 no crearon
journal ni ejecutaron ninguna operación.

---

## A. FACT / EVIDENCE

### A.0 Previous attempts (historical fact)

```text
D29 attempt 1: BLOCKED — G9 AUTHORIZATION INCOMPLETE, MUTATIONS = 0
D31 attempt:   BLOCKED — G9 AUTHORIZATION INCOMPLETE, MUTATIONS = 0
D32 attempt:   BLOCKED — G9 AUTHORIZATION INCOMPLETE, MUTATIONS = 0
D33 attempt:   BLOCKED — G9 AUTHORIZATION INCOMPLETE, MUTATIONS = 0
```

No evidence from those attempts is attributed beyond the blocks themselves.

### A.1 authorization

Authorized input package (D34), provided explicitly by the operator:

```text
AUTHORIZE_G9=YES
AUTHORIZE_PR_MERGE=YES
TARGET_PR=52
```

AUTHORIZATION_GATE = PASS. Authorizations explicit, independent, non-transitive.
Scope: G9 only, merge of PR #52 only. D28 historical authorizations not used.

### A.2 dynamic baseline

`git fetch --prune --tags` executed (Dependabot branches rebased remotely;
`main` not affected).

```text
BRANCH = main
HEAD = 3eaced8c35868ed91cbce81a5c4bd21537aacfec
ORIGIN_MAIN = 3eaced8c35868ed91cbce81a5c4bd21537aacfec
LS_REMOTE = 3eaced8c35868ed91cbce81a5c4bd21537aacfec
HEAD_TAG = NONE
TAGS = v0.1.0, v0.1.1
AHEAD/BEHIND (origin/main...HEAD) = 0 / 0
ALIGN: HEAD ↔ origin/main ↔ ls-remote = 3eaced8... MATCH
STAGED = 0
MODIFIED (pre-existing): docs/release-policy.md, start.sh, stop.sh
UNTRACKED (pre-existing): journals historical set; no D29 journal before this run
```

No unexpected `main` advancement. Baseline = D28 expected SHA.

### A.3 worktree baseline

SHA-256 PRE (identical to POST measured before journal creation):

```text
docs/release-policy.md = 2ed1114f65bcd778e436bb635dcf0982d10cada806272d8dc7cc13a2ceabfabb
start.sh               = f09451163eb9016421f58e7a558033a77d1e7eb8108d1f77bc6d1bc34a5934b5
stop.sh                = 8be30918497bd5b07c3fb9608d098dc589090884b2b52709fddbcbf03f177170
.env                   = a5dbbbbabee11c148b9389c344e28f95530c5dd1001044a02703350d9986d190
```

`.env` content not displayed. Journals D19–D28 present and untouched.
`STAGED = 0`.

### A.4 G1/G2 verification

G1 — remote, `origin/main` (= 3eaced8, D28 commit):

```text
.github/workflows/ci.yml PRESENT
SCA steps present: "Frontend dependency audit (SCA)", "Dependency audit (SCA)",
"Security scan" (bandit); lint/mypy/pytest/docker-build jobs present.
```

G2 — remote, `origin/main`:

```text
.github/secret_scanning.yml PRESENT
paths-ignore = EXACTLY 3 ENTRIES:
  .env.example
  node_modules/**
  .venv*/**/
secret_scanning = enabled
push_protection = enabled
```

Both G1 and G2 demonstrable as CLOSED.

### A.5 branch protection / rules

Dynamic read of `branches/main/protection`:

```text
required_status_checks: strict=true, contexts=[lint-and-test (3.12, 24), docker-build]
required_pull_request_reviews: required_approving_review_count=1,
  require_code_owner_reviews=false, dismiss_stale_reviews=false,
  require_last_push_approval=false
required_signatures: enabled=true
enforce_admins: enabled=false
allow_force_pushes: false
allow_deletions: false
required_linear_history: false
merge_queue: not configured
bypass list: none configured in response
```

Repository merge methods: merge_commit=true, squash=true, rebase=true.

Security analysis (repository endpoint):

```text
secret_scanning = enabled
secret_scanning_push_protection = enabled
dependabot_security_updates = enabled
secret_scanning_non_provider_patterns = disabled
secret_scanning_validity_checks = disabled
open secret scanning alerts = 0
```

### A.6 target PR identity

```text
REPOSITORY: danielcba/company-os-monitor
PR number = 52
title = chore(deps): update asyncpg requirement from >=0.29 to >=0.31.0
author = app/dependabot (dependabot[bot])
state = OPEN
draft = false
base = main
head branch = dependabot/pip/main/asyncpg-gte-0.31.0
head SHA = 0494603e67f79342467c8a1b03b3165cb65d3ab4
changed files = 1, additions = 1, deletions = 1, commits = 1
created = 2026-09-27T20:48:29Z
```

### A.7 Dependabot scope

Diff of PR #52 (single file `pyproject.toml`):

```diff
-  "asyncpg>=0.29",
+  "asyncpg>=0.31.0",
```

dependency = asyncpg; old constraint `>=0.29`; new constraint `>=0.31.0`.
No other files. No Framework, journals, LICENSE, VERSION, CHANGELOG, README,
secret scanning, push protection, branch protection, CI policy, release files.

### A.8 security / commercial / secret gate

```text
COMMERCIAL CONTENT INTRODUCED = 0
SECRETS INTRODUCED = 0
CREDENTIALS INTRODUCED = 0
UNAUTHORIZED SECURITY CONTROL CHANGES = 0
```

Diff is a one-line dependency constraint change. No secret printed.

### A.9 CI and status checks

Required checks per branch protection, evaluated on `TARGET_PR_HEAD_SHA`
= `0494603e67f79342467c8a1b03b3165cb65d3ab4`:

```text
lint-and-test (3.12, 24) = completed / success (run 36892987239)
docker-build             = completed / success (run 36892987239)
```

Both required checks PASS on the exact head SHA. No missing checks.

### A.10 reviews

```text
required approvals = 1 (branch protection)
actual approvals = 0 (reviews: [])
changes requested = 0
dismissed reviews = 0
code owner requirement = false
reviewDecision = REVIEW_REQUIRED
```

No review generated. No approval performed (not authorized by merge authorization).

### A.11 signature gate

Head commit `0494603e67f79342467c8a1b03b3165cb65d3ab4`:

```text
verification.verified = true
verification.reason = valid
committer = GitHub <noreply@github.com> (GitHub-signed Dependabot commit)
verified_at = 2026-10-01T16:34:11Z
```

`required_signatures` remains enabled. No signing configuration changed.
No key uploaded. No bypass used.

### A.12 merge method

```text
docs/release-policy.md (local, pre-existing, read-only): no merge/squash/rebase rules found
repository allows: merge commit, squash, rebase
branch protection merge queue: not configured
mergeStateStatus = BEHIND (strict status checks require up-to-date branch)
```

Merge method not exercised: execution stopped before merge.

### A.13 pre-merge gate

```text
AUTHORIZE_G9 = YES                     PASS
AUTHORIZE_PR_MERGE = YES               PASS
TARGET_PR = 52                         PASS
PR #52 OPEN                            PASS
BASE = main                            PASS
DRAFT = false                          PASS
AUTHOR = dependabot[bot]               PASS
HEAD SHA = 0494603e... unchanged        PASS
required checks = PASS                 PASS
required signature (head verified)     PASS
scope dependency-only                  PASS
G1 = CLOSED                            PASS
G2 = CLOSED                            PASS
main baseline unchanged (3eaced8...)   PASS
mergeable = MERGEABLE                  PASS
mergeStateStatus = BEHIND              FAIL — strict up-to-date requirement unmet
required reviews = 0 of 1              FAIL — review gate unmet
mergeable gate overall                 FAIL
```

### A.14 controlled merge

```text
MERGE NOT EXECUTED — hard stop at review gate (FASE 8) and merge-state gate.
NO gh pr merge issued. NO direct push. NO bypass. NO force push.
MERGES PERFORMED BY D29/D34 = 0
```

### A.15 post-merge remote baseline

N/A — no merge occurred. Final remote state re-verified:

```text
LS_REMOTE origin main = 3eaced8c35868ed91cbce81a5c4bd21537aacfec
HEAD = 3eaced8c35868ed91cbce81a5c4bd21537aacfec
ORIGIN_MAIN = 3eaced8c35868ed91cbce81a5c4bd21537aacfec
```

### A.16 post-merge PR state

N/A — PR #52 remains OPEN, head unchanged
(`0494603e67f79342467c8a1b03b3165cb65d3ab4`), not merged, not closed,
not modified.

### A.17 post-merge CI

N/A — no new `main` SHA was produced.

### A.18 dependency verification

N/A — asyncpg update not present on `main` (merge not executed).

### A.19 security regression

Pre-state captured; no mutation executed; post-state measured identical:

```text
required_signatures: enabled (unchanged)
secret_scanning: enabled (unchanged)
push_protection: enabled (unchanged)
dependabot_security_updates: enabled (unchanged)
non_provider_patterns: disabled (unchanged)
validity_checks: disabled (unchanged)
branch protection: unchanged (read-only GET operations)
REMOTE SETTINGS CHANGED BY D29/D34 = 0
SECURITY REGRESSIONS = NONE
```

### A.20 G1/G2/G6 integrity

```text
G1 = CLOSED (still demonstrable)
G2 = CLOSED (still demonstrable)
G6 = CLOSED — HISTORICAL EXCEPTION ACCEPTED (not reinterpreted, not edited)
D24/D25 journals untouched
```

### A.21 release boundary

```text
remote tags: v0.1.0, v0.1.1 only
releases: v0.1.0, v0.1.1 only (no changes)
TAGS_CHANGED = 0
GITHUB_RELEASES_CHANGED = 0
VERSION_CHANGES = 0
PR #52 touches only pyproject.toml
```

### A.22 pre-existing state integrity

SHA-256 POST = SHA-256 PRE for all four controlled files (values in A.3).
Journals D19–D28 present and unmodified.
Only local change attributable to this unit: creation of this journal file
(not staged, not part of any PR/merge).

### A.23 framework integrity

```text
FRAMEWORK HEAD (PRE, measured this run) = 381f56cfa48d092f85846e160d2e1fe6878f9f6f
matches expected baseline
FRAMEWORK WRITES BY THIS UNIT = 0
FRAMEWORK JOURNAL WRITES BY THIS UNIT = 0
Framework worktree state untouched (read-only rev-parse/status)
```

### A.24 scans

```text
COMMERCIAL CONTENT = 0
SECRETS = 0
```

### A.25 final evidence

```text
STAGED = 0
DIRECT PUSH = NO
BYPASS USED = NO
FORCE PUSH = NO
MERGES = 0
PULL REQUESTS MODIFIED = 0
UNAUTHORIZED MUTATIONS = 0
```

---

## B. DECISION

### B.1 authorization decision

PASS. Three explicit values provided in the D34 package; non-transitive
historical authorizations not used.

### B.2 target PR eligibility decision

PASS. PR #52 is OPEN, base=main, non-draft, authored by dependabot[bot],
title matches expected asyncpg update.

### B.3 scope decision

PASS. Dependency-only change (`asyncpg>=0.29` → `asyncpg>=0.31.0` in
`pyproject.toml`), 1 file. No out-of-scope changes.

### B.4 CI acceptance decision

PASS. Both required checks (`lint-and-test (3.12, 24)`, `docker-build`)
completed with success on the exact head SHA `0494603e...`.

### B.5 review acceptance decision

FAIL. Branch protection requires 1 approving review; PR #52 has 0 approvals;
`reviewDecision = REVIEW_REQUIRED`. Merge authorization does not authorize
approval, self-approval, or artificial reviews. No review was generated.

### B.6 signature acceptance decision

PASS for the head commit (GitHub-verified Dependabot signature, reason=valid).
No signing configuration touched.

### B.7 merge decision

NOT EXECUTED. Two independent blocking conditions:
1. review gate unsatisfied (0 of 1 approvals) — hard stop;
2. `mergeStateStatus = BEHIND` with `strict = true` — up-to-date requirement
   unmet; an "update branch" action would create a commit and change the PR
   head SHA after validation, which is outside this unit's authorization.
No workaround attempted (no branch update, no bypass, no rule change).

### B.8 post-merge acceptance decision

N/A — no merge occurred.

### B.9 security regression decision

NONE. Zero remote mutations; settings measured identical pre/post.

### B.10 final G9 disposition

```text
G9 = OPEN — MERGE NOT COMPLETED / NOT VERIFIED
D34/D29 STATUS = BLOCKED — REQUIRED REVIEW GATE UNSATISFIED
```

G9 is not closed by inference. All 31 closure criteria are not met
(criteria 17–24 require an executed merge).

### B.11 next unit boundary

Not applicable — G9 not closed. Resolution requires a separate, explicit
authorization path: an approving review (separate authorization, not implied
by merge authorization) and/or an out-of-date branch remediation decision.
Neither may be performed inside D29/D34.

---

## C. FINAL STATUS

```text
C.1 D29_STATUS: BLOCKED — REQUIRED REVIEW GATE UNSATISFIED
C.2 TARGET_PR: 52
C.3 PR_HEAD_SHA: 0494603e67f79342467c8a1b03b3165cb65d3ab4
C.4 MERGE_SHA: NONE
C.5 MERGE_METHOD: NONE (not executed)
C.6 PR_MERGED: NO — PR #52 remains OPEN
C.7 POST_MERGE_CI: N/A — no new main SHA
C.8 G9: OPEN — MERGE NOT COMPLETED / NOT VERIFIED
C.9 FINAL_DISPOSITION: hard stop at FASE 8 (reviews) and merge-state gate;
    zero mutations beyond creation of this journal
```
