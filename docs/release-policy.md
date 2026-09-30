# Release Policy — Company OS Monitor

**Status:** Active (D2 Option A — Tagged Release)
**Applies to:** the product repository `danielcba/company-os-monitor`.
**Decision origin:** owner decision D2 = Option A (tagged release), recorded in
`journal/2026/2026-09-30-d2-tagged-release-option-a-implementation.md`.

This policy is deliberately minimal and manual. It describes only steps this
repository actually performs; it does not invent operational procedures the
architecture does not use.

## Policy

1. **A release represents the complete product.** One release covers the whole
   `company-os-monitor` platform (services, agents, libraries, web frontend,
   infrastructure) — not individual services.
2. **Versioning follows Semantic Versioning** (MAJOR.MINOR.PATCH). The product
   uses a **single platform version**: every versioned component
   (`pyproject.toml` files, `apps/web/package.json`, README headers) carries the
   same product version.
3. **Official tags use the format `vMAJOR.MINOR.PATCH`** (for example
   `v0.1.0`). Only annotated tags are used for releases; lightweight tags are
   never used for a release.
4. **A release tag must point to a commit that:**
   - is on `main`, and
   - has the required CI checks in PASS (`lint-and-test (3.12, 24)` and
     `docker-build` from `.github/workflows/ci.yml`).
5. **The GitHub Release must correspond exactly to the tag:** same name
   (`vMAJOR.MINOR.PATCH`), target commit = the tagged commit, published once.
6. **No releases over unverified commits.** If CI is missing, failing, or runs
   on a different SHA than the tag target, the release is not created.
7. **Published tags are immutable.** A published tag is never moved, deleted,
   or replaced. Any correction after a release requires a **new version**.
8. **Post-release fixes require a new version** (PATCH at minimum); the release
   history is never rewritten.
9. **Every version change must be traceable:** the version bump, the CHANGELOG
   entry, and the tag belong to the same auditable chain
   (commit → tag → GitHub Release → CHANGELOG).
10. **Conventional Commits remain the commit convention** of the repository
    (de facto since inception; enforced by review, not by tooling).
11. **Journals do not replace the CHANGELOG.** `journal/` is the internal
    append-only decision/audit trail; `CHANGELOG.md` is the product changelog
    for users and releases. Remediation logs under `docs/remediation/` are
    neither.
12. **No complex release automation while a controlled manual process is
    sufficient.** The release sequence is an explicit, reproducible manual
    procedure (see below). Any future release automation is a recommendation
    only and requires its own decision.

## Release procedure (manual, controlled)

```text
1. release preparation commit on main (version alignment + CHANGELOG entry)
2. push (fast-forward)
3. CI on that exact SHA = PASS
4. annotated tag v<X.Y.Z> pointing to that SHA
5. push the tag
6. GitHub Release created on that tag, notes derived from CHANGELOG.md
```

A GitHub Release is never created before the remote tag is verified, and the
tag is never created before CI passes on the final release commit.

## Version source of truth

- **Product version:** `0.1.0` (D2 Option A, first release).
- Python components: `version` in each `pyproject.toml` (17 files, all `0.1.0`).
- Web frontend: `apps/web/package.json` `version` (+ `package-lock.json`
  root entries), kept in sync with the product version.
- Docker: `infrastructure/docker/docker-compose.yml` uses `build:` only — no
  versioned image registry tags exist, therefore **no image tag changes are
  part of the version policy** (documented decision, FASE 3 of D2 Option A).

## Licensing

`LICENSE STATUS = OWNER DECISION REQUIRED`. No license file exists in this
repository, and selecting a license is an owner (legal) decision — this policy
does not select one and does not create one. The release policy above does not
mandate a license file; a license decision remains an owner requirement before
any external distribution that requires one.

## Related documents

- `CHANGELOG.md` — product changelog (release-facing).
- `journal/` — internal append-only decision and audit trail (not a changelog).
- `docs/remediation/` — historical remediation reports (not a changelog).
- `.github/workflows/ci.yml` — required checks referenced by this policy.
