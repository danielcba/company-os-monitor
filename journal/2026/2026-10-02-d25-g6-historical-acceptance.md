# D25 — G6 FORMAL HISTORICAL ACCEPTANCE

Modelo de tres capas obligatorio: EVIDENCIA (A) → DECISIÓN (B) → DOCUMENTACIÓN (C).
La documentación no constituye prueba; la decisión no altera hechos.

## A. EVIDENCE

### A.1 Dynamic Baseline

Ejecutado `git fetch --prune --tags` antes de cualquier escritura.

```text
EVID-01
SOURCE: git (local + remote)
COMMAND/API: git fetch --prune --tags; git rev-parse HEAD/origin/main;
  git ls-remote origin refs/heads/main; git tag --points-at HEAD; git status
RAW RESULT:
  BRANCH: main
  HEAD_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
  MAIN_REMOTE_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
  LS_REMOTE_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
  HEAD↔origin/main: EQUAL
  origin/main↔ls-remote: EQUAL
  HEAD tagged: v0.1.1; tags: v0.1.0, v0.1.1
  git status: M .github/secret_scanning.yml, M .github/workflows/ci.yml,
    M docs/release-policy.md, M start.sh, M stop.sh; untracked=33; staged=0
  .env present; journals=102
FACTUAL INTERPRETATION: los tres SHAs coinciden; el working tree contiene
  5 archivos modificados y 0 staged en el instante de la observación.
```

### A.2 Current Signature Control

```text
EVID-02
SOURCE: GitHub REST
COMMAND/API: GET /repos/danielcba/company-os-monitor/branches/main/protection/required_signatures
RAW RESULT: {"enabled": true}
FACTUAL INTERPRETATION: el endpoint declara required_signatures activo en main.

EVID-03
SOURCE: GitHub REST
COMMAND/API: GET /repos/.../branches/main/protection
RAW RESULT: {"enforce_admins": false,
  "approving_review_count": 1,
  "contexts": ["lint-and-test (3.12, 24)", "docker-build"]}
FACTUAL INTERPRETATION: la protección de rama exige 1 review y 2 checks;
  enforce_admins está en false.
```

### A.3 Historical Commit Verification

```text
EVID-04
SOURCE: git (local)
COMMAND/API: git verify-commit db1819697352a0c09dc63ff4901f0063be57fc8b;
  git log -1 --format='%H %G?'
RAW RESULT: verify-commit exit=1; %G?=N (sin key)
FACTUAL INTERPRETATION: el commit referenciado no contiene una firma
  criptográfica verificable.

EVID-05
SOURCE: git (local)
COMMAND/API: git show --format=fuller --no-patch db18196…; git log --show-signature -1
RAW RESULT: commit db1819697352a0c09dc63ff4901f0063be57fc8b;
  Author/Committer danielcba; AuthorDate/CommitDate Thu Oct 1 13:29:20 2026 -0300;
  mensaje "release: prepare v0.1.1"; salida sin bloque de firma GPG
FACTUAL INTERPRETATION: los metadatos del commit no incluyen bloque de firma
  verificable.
```

### A.4 Tag / Release Evidence

```text
EVID-06
SOURCE: git
COMMAND/API: git rev-parse v0.1.1^{commit}
RAW RESULT: db1819697352a0c09dc63ff4901f0063be57fc8b
FACTUAL INTERPRETATION: el tag v0.1.1 apunta al commit HEAD.

EVID-07
SOURCE: GitHub REST
COMMAND/API: gh release view v0.1.1
RAW RESULT: {"tag":"v0.1.1","target":"main","published":"2026-10-01T16:40:58Z"}
FACTUAL INTERPRETATION: el release v0.1.1 existe, apunta a main, publicado el
  2026-10-01.

EVID-08
SOURCE: GitHub REST / git
COMMAND/API: gh release list; git tag --list 'v0.1.*'
RAW RESULT: releases = v0.1.1, v0.1.0; tags = v0.1.0, v0.1.1
FACTUAL INTERPRETATION: existen 2 releases y 2 tags; HEAD está en v0.1.1.
```

### A.5 Branch Protection Evidence

EVID-03 (protección de rama completa) + EVID-02 (control de firma) constituyen
el estado de protección observado en el instante de D25 (ver A.1 para fecha
implícita de la sesión: 2026-10-02).

Revalidación de otras unidades (sólo lectura, EVIDENCIA — ver §14 del prompt):

```text
EVID-09
SOURCE: git local + GitHub REST
COMMAND/API: grep ci.yml/secret_scanning.yml; gh api (security_and_analysis,
  actions/permissions, code-scanning/default-setup, private-vulnerability-reporting);
  gh pr list; gh api dependabot/alerts?state=open
RAW RESULT: G1 steps presentes (npm audit, pip-audit==2.10.1, PYSEC-2026-1325),
  YAML OK; G2 paths-ignore=3; secret_scanning=enabled, push_protection=enabled,
  validity_checks=disabled, non_provider_patterns=disabled;
  sha_pinning_required=true; threat_model=remote (updated_at 2026-10-01T21:22:18Z);
  PVR={"enabled":false}; PRs abiertas=34; dependabot alerts open=0
FACTUAL INTERPRETATION: los estados de G1–G5/G7/G9/PVR coinciden con los
  registrados en D24.
```

### A.6 Evidence Limits

```text
La evidencia demuestra: ausencia de firma verificable en HEAD; control de firma
  activo; anclaje tag/release; estados de settings observados en el instante.
La evidencia NO demuestra: autenticidad/seguridad del contenido del commit más
  allá de su presencia en el repositorio; comportamiento futuro del control;
  nada sobre commits anteriores no muestreados individualmente (la muestra es
  HEAD; el patrón "sin firma" se extiende al historial previo según la regla de
  %G? de HEAD y la naturaleza del proyecto, no por muestreo exhaustivo).
La matriz de autorización D25 (EVID-10, en C.2) es un documento de decisión,
  no evidencia de plataforma.
```

## B. DECISION

### B.1 Decision

```text
DECISION: ACCEPT HISTORICAL UNSIGNED PROVENANCE EXCEPTION
DEC-01 → EVID-02, EVID-03   (el control de firma está activo y vigente)
DEC-02 → EVID-04, EVID-05   (la excepción histórica existe y es verificable)
DEC-03 → EVID-06, EVID-07, EVID-08 (HEAD/v0.1.1 es el ámbito anclado)
DEC-04 → EVID-10 (FORCE_PUSH=NO, rewrite prohibido en las matrices D22–D25:
  history rewrite NOT PERFORMED, no autorizado)
ACCEPTANCE: explicit, limited, deliberate — ejecutada en D25 bajo
  AUTHORIZE_G6_HISTORICAL_ACCEPTANCE=YES
```

### B.2 Scope

```text
SCOPE: historical commits predating required_signatures enforcement
  (ámbito: HEAD db18196… y predecesores — COMMITS PREDATING
  REQUIRED_SIGNATURES ENFORCEMENT)
CURRENT CONTROL: required_signatures remains enabled for future commits
  (EVID-02)
OUT OF SCOPE: future commits · new unsigned commits · history rewrite ·
  force-push · release changes · tag changes · branch protection changes ·
  workflow/configuration changes · PR changes · G1/G2 activation ·
  G3/G4 remediation · G9 merges · LICENSE · v0.1.2 · Sprint 13 · PVR
```

### B.3 Rationale

```text
DEC-05 → EVID-04, EVID-05, EVID-02:
The historical state (unsigned HEAD and predecessors) is immutable under the
applicable project boundary (no rewrite/force-push authorized in D22–D25), and
the current signature requirement remains active for future commits. The
condition is a historical provenance matter, not a bypass of the active control.
The acceptance is a risk/provenance decision, not a technical remediation.
```

### B.4 Residual Risk

```text
DEC-06 → EVID-04, EVID-06, EVID-07:
RESIDUAL RISK: historical provenance of the v0.1.1-anchored commits lacks a
cryptographic signature; verification of those SHAs relies on repository/release
transport (GitHub tag+release), not on signatures.
NOT classified as: an active vulnerability; a future-control bypass.
```

### B.5 Mitigation

```text
DEC-07 → EVID-02, EVID-03:
MITIGATION: required_signatures remains ENABLED for future commits; branch
protection (1 review, 2 required checks) remains active; no rewrite performed.
FUTURE COMMIT SIGNATURE PROTECTION: ACTIVE.
```

### B.6 Explicit Non-Authorizations

```text
Esta decisión NO autoriza: history rewrite · new signed commit for the
historical commit · commit · push · force-push · branch protection change ·
release change · tag change · PR action · configuration change · G1/G2
activation · G3/G4 remediation · G5/G7 change · LICENSE · v0.1.2 · Sprint 13 ·
PVR. Cada una requiere su propia autorización en unidad separada.
No se usan para el commit histórico los términos FIXED / RE-SIGNED /
REMEDIATED / CRYPTOGRAPHICALLY VERIFIED. Estado correcto: ACCEPTED HISTORICAL
EXCEPTION.
```

### B.7 Final G6 Disposition

```text
G6 = CLOSED — HISTORICAL EXCEPTION ACCEPTED
  (válido únicamente porque AUTHORIZE_G6_HISTORICAL_ACCEPTANCE=YES fue
   efectivamente utilizado en D25 y la evidencia requerida fue verificada en D25)

CONTROL: required_signatures = ENABLED (CLOSED/ACTIVE)
HISTORICAL EXCEPTION: ACCEPTED
HISTORY REWRITE: NOT PERFORMED
FUTURE COMMITS: STILL PROTECTED
```

## C. DOCUMENTATION

### C.1 Audit Record

Única escritura de D25: este journal (`journal/2026/2026-10-02-d25-g6-historical-acceptance.md`),
untracked, STAGED=NO. Mutaciones: GitHub=0, PR=0, branch protection=0,
security settings=0, releases=0, tags=0, commits=0, pushes=0.
Evidencia de cierre (baseline final, registrado como evidencia): FINAL_HEAD =
FINAL_ORIGIN_MAIN = FINAL_LS_REMOTE = `db1819697352a0c09dc63ff4901f0063be57fc8b`,
ALIGN=YES, COMMITS_CREATED=0, PUSHES_PERFORMED=0, TAGS_CHANGED=0,
RELEASES_CHANGED=0.

### C.2 Authorization Record

```text
AUTHORIZE_D25=YES
G6_ACCEPTANCE_REVIEW=YES
AUTHORIZE_G6_HISTORICAL_ACCEPTANCE=YES      ← utilizado en esta unidad
COMMIT=NO  PUSH=NO  TAG=NO  GITHUB_RELEASE=NO
PR_MERGE=NO  PR_CLOSE=NO  PR_REBASE=NO  FORCE_PUSH=NO
G1_G2_ACTIVATION=NO  G3_G4_REMEDIATION=NO  G5_CHANGE=NO  G7_CHANGE=NO
LICENSE_AUDIT=NO  LICENSE_CHANGE=NO
PVR_ENABLE=NO  PVR_DISABLE=NO
V012_*=NO  SPRINT_13=NO
LÍMITE ABSOLUTO respetado: la aceptación autorizó únicamente la decisión
  formal de aceptar la excepción histórica documentada.
```

### C.3 Chronology

```text
D24: G6 = OPEN — FORMAL ACCEPTANCE REQUIRED (hecho factual cerrado, decisión
  humana pendiente)
D25: evidencia verificada (A) → decisión ejecutada (B) → este registro (C)
D25: G6 = CLOSED — HISTORICAL EXCEPTION ACCEPTED
No se modificó D24 ni ningún journal previo (D19–D24 intactos).
```

### C.4 Traceability

```text
DEC-01 → EVID-02, EVID-03
DEC-02 → EVID-04, EVID-05
DEC-03 → EVID-06, EVID-07, EVID-08
DEC-04 → EVID-10 (autorizaciones D22–D25: rewrite/force-push no autorizados)
DEC-05 → EVID-04, EVID-05, EVID-02
DEC-06 → EVID-04, EVID-06, EVID-07
DEC-07 → EVID-02, EVID-03
EVID-09 = revalidación de otras unidades (G1–G5/G7/G9/PVR sin cambios)
Framework: HEAD 381f56cfa48d092f85846e160d2e1fe6878f9f6f (idéntico open/close),
  9 dirty preexistentes, FRAMEWORK WRITES = 0.
Commercial/Secrets: scans de este journal = 0/0.
Release boundary: v0.1.0/v0.1.1/releases/tags/HEAD sin cambio; CHANGELOG/README/
  VERSION/LICENSE/release-policy.md sin modificación.
```

### C.5 Future Unit Boundary

```text
Siguiente unidad (exclusiva, con autorización independiente):
  COMMIT=YES + PUSH=YES — activación remota de G1/G2 limitada a
  .github/workflows/ci.yml y .github/secret_scanning.yml
  (excluidos: journals, docs/release-policy.md, start.sh, stop.sh, .env)
Posterior, cada una en unidad propia: CI remoto → merge controlado G9 →
  LICENSE → v0.1.2 readiness → Sprint 13. PVR completamente separado.
No combinar G6/commit/push/CI/merges/LICENSE/v0.1.2/Sprint 13/PVR.
```
