# D26 — G1/G2 SECURITY ACTIVATION

Registro cronológico append-only de la ejecución D26. El journal no es
autorización ni fuente primaria de evidencia; se crea tras el baseline
inicial y se actualiza incrementalmente. Secuencia real:
BASELINE → JOURNAL CREATED → EVIDENCE → DECISION → (STAGING/COMMIT/PUSH
según gates) → DOCUMENTATION. Evidencia demuestra, decisión autoriza,
documentación consolida sin crear hechos nuevos.

## A. EVIDENCE

### A.1 Dynamic Pre-Commit Baseline

```text
EVIDENCE A.1 — DYNAMIC PRE-COMMIT BASELINE
SOURCE: git fetch + git status/diff/rev-parse/ls-remote
COMMAND: git fetch --prune --tags (previo a cualquier escritura)
RAW RESULT:
  BRANCH: main
  HEAD_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
  MAIN_REMOTE_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
  LS_REMOTE_SHA: db1819697352a0c09dc63ff4901f0063be57fc8b
  HEAD↔origin/main: EQUAL
  origin/main↔ls-remote: EQUAL
  ALIGN: YES
  HEAD_TAG: v0.1.1
  TAGS: v0.1.0, v0.1.1
FACTUAL INTERPRETATION: GATE DE BASELINE CUMPLIDO (BRANCH=main;
  HEAD=origin/main=ls-remote; ALIGN=YES). Divergencia: ninguna.
```

### A.2 Working Tree Baseline

```text
EVIDENCE A.2 — WORKING TREE BASELINE
SOURCE: git status/diff (tras A.1)
RAW RESULT:
  G1/G2 MODIFICATIONS: M .github/workflows/ci.yml, M .github/secret_scanning.yml
  PRE-EXISTING MODIFICATIONS: M docs/release-policy.md, M start.sh, M stop.sh
  UNTRACKED: 35 (journals históricos + D22–D26, incl. este journal)
  STAGED: 0
  ENV: .env presente
FACTUAL INTERPRETATION: verificado dinámicamente, no asumido de D25.
  Índice vacío antes de cualquier staging de D26.
```

### A.3 Signing Preflight

```text
EVIDENCE A.3 — SIGNING PREFLIGHT (FASE 4)
COMMAND: git config --get commit.gpgsign/gpg.format/user.signingkey/
  user.name/user.email; ls ~/.ssh/*.pub; gpg --list-keys;
  gpg --list-secret-keys
RAW RESULT:
  commit.gpgsign=unset · gpg.format=unset · user.signingkey=unset
  user.name=danielcba · user.email=daniel.e.cordoba@gmail.com
  ~/.ssh/*.pub: none · gpg keys: 0 · gpg secret keys: 0
SIGNING CAPABILITY: UNAVAILABLE
SIGNING IDENTITY: NOT CONFIGURED
SIGNED COMMIT: NOT FEASIBLE
FACTUAL INTERPRETATION: GATE FASE 4 NO CUMPLIDO →
  STOP · COMMIT NOT CREATED · PUSH NOT PERFORMED.
  Bloqueo registrado aquí en orden cronológico (ocurrido antes de A.4–A.7).
  Sin lectura de claves privadas; sin modificación de config de firma.
  Evidencia read-only A.4–A.7 se recoge después del bloqueo porque es
  verificación no mutante; las fases mutantes A.8–A.15 no se ejecutan.
```

### A.4 G1 Evidence

```text
EVIDENCE A.4 — G1
SOURCE: git diff -- .github/workflows/ci.yml + lectura del archivo
RAW RESULT:
  diff: +16/−0 (2 steps SCA añadidos)
  SCA dependency audit: npm audit (L173), pip-audit==2.10.1 (L185)
  política explícita de fallo: presente (steps con continue-on-error=false
    documentado); excepción PYSEC-2026-1325 (L180, L186)
  YAML safe_load: OK · jobs/steps existentes preservados (0 líneas eliminadas)
  uses non-SHA en diff: 0
FACTUAL INTERPRETATION: diff G1 limitado a los 2 steps SCA con política.
```

### A.5 G2 Evidence

```text
EVIDENCE A.5 — G2
SOURCE: git diff -- .github/secret_scanning.yml + lectura del archivo
RAW RESULT:
  diff: +12/−4 (8 entries → 3)
  paths-ignore: .env.example · node_modules/** · .venv*/** (exactamente 3)
  rationale: presente (header)
  YAML safe_load: OK · entries adicionales: 0
PLATFORM: secret_scanning=enabled · push_protection=enabled (sin cambio)
FACTUAL INTERPRETATION: diff G2 cumple la matriz de 3 entries.
```

### A.6 Commit Content Review

```text
EVIDENCE A.6 — COMMIT CONTENT REVIEW
COMMAND: git diff -- .github/workflows/ci.yml .github/secret_scanning.yml;
  git diff --check; git diff --name-only
RAW RESULT:
  archivos autorizados con diff G1/G2: exactamente 2
  otros archivos con diff: docs/release-policy.md, start.sh, stop.sh
    (PRE-EXISTING desde antes de D26 — ver A.2; quedan EXCLUIDOS del commit)
  git diff --check: exit 0
  secretos en diff: 0 · contenido comercial en diff: 0
  Framework: sin cambios · release changes: 0
FACTUAL INTERPRETATION: contenido de commit autorizado = sólo los 2 archivos
  G1/G2; los 3 preexistentes no entran en la matriz de staging.
  HARD GATE: ningún archivo no autorizado presente en el ámbito de staging.
```

### A.7 Pre-Commit Tests

```text
EVIDENCE A.7 — PRE-COMMIT TESTS
TEST: YAML validation | COMMAND: python yaml.safe_load (ambos) | RESULT: OK
TEST: whitespace/scope | COMMAND: git diff --check | RESULT: exit 0
TEST: lint | COMMAND: ruff check . | RESULT: OK
TEST: SCA frontend (G1) | COMMAND: npm audit (apps/web) | RESULT: exit 0
TEST: secret-scan config | COMMAND: entries + YAML | RESULT: 3 entries válidos
FACTUAL INTERPRETATION: todos GREEN; 0 fallos; ningún fallo que clasificar.
```

### A.8 Staged Content

```text
EVIDENCE A.8 — STAGED CONTENT: NOT EXECUTED
FACTUAL: staging no ejecutado (gate FASE 4; STAGED=0 verificado en A.2 y A.23).
  FASE 10 no alcanzada. Ningún git add; 0 archivos en el índice.
```

### A.9 Commit Result

```text
EVIDENCE A.9 — COMMIT RESULT: NOT EXECUTED
FACTUAL: 0 commits creados. HEAD = db1819697352a0c09dc63ff4901f0063be57fc8b
  (intacto). verify-commit HEAD = exit=1, %G?=N — HEAD histórico conocido,
  excepción aceptada en D25 (G6), sin cambios; NO es un commit D26.
```

### A.10 Pre-Push State

```text
EVIDENCE A.10 — PRE-PUSH STATE: NOT EXECUTED
FACTUAL: FASE 13 no alcanzada. PRE_PUSH_HEAD = ORIGIN_MAIN =
  LS_REMOTE = db18196… · NEW_COMMIT = none · COMMIT_SIGNATURE = N/A.
```

### A.11 Push Result

```text
EVIDENCE A.11 — PUSH RESULT: NOT EXECUTED
FACTUAL: git push origin main no ejecutado. pushed_at =
  2026-10-01T16:40:35Z sin cambios (A.16). Sin force-push; sin workaround.
  PUSH RESULT: N/A · ERROR: none · REASON: gate FASE 4.
```

### A.12 Post-Push Baseline

```text
EVIDENCE A.12 — POST-PUSH BASELINE: NOT EXECUTED
FACTUAL: no hubo push; FASE 15 no alcanzada. No existe baseline post-push.
```

### A.13 Remote CI

```text
EVIDENCE A.13 — REMOTE CI: NOT EXECUTED
FACTUAL: RUN_ID para D26 = none (no existe commit D26). Ningún run histórico
  usado como resultado de D26.
```

### A.14 G1 Remote Activation

```text
EVIDENCE A.14 — G1 REMOTE ACTIVATION: NOT PERFORMED
FACTUAL: main (db18196) NO contiene los steps SCA de G1 (sin push);
  ejecución remota de pip-audit/npm audit/PYSEC-2026-1325 no verificable.
```

### A.15 G2 Remote Activation

```text
EVIDENCE A.15 — G2 REMOTE ACTIVATION: NOT PERFORMED
FACTUAL: main NO refleja los cambios de secret_scanning.yml (sin push);
  paths-ignore efectivo en main = configuración de plataforma/ramas previa,
  no la restringida de D26.
```

### A.16 Security Regression Check

```text
EVIDENCE A.16 — SECURITY REGRESSION CHECK (comparación BEFORE/AFTER)
SOURCE: GitHub API (idéntico al pre-baseline de A.1)
RAW RESULT:
  secret_scanning=enabled · push_protection=enabled · validity_checks=disabled
  non_provider_patterns=disabled · dependabot_security_updates=enabled
  threat_model=remote (updated_at 2026-10-01T21:22:18Z, sin cambio)
  sha_pinning_required=true · required_signatures=true · PVR={"enabled":false}
  vulnerabilityAlerts totalCount=11 (GraphQL, sin filtro de estado)
  pushed_at=2026-10-01T16:40:35Z (sin cambio)
CLASSIFICATION: G1/G2 = INTENDED (sin activar remoto); todo lo demás =
  NO CHANGE · UNINTENDED: 0 · UNKNOWN: 0
```

### A.17 G6 Regression

```text
EVIDENCE A.17 — G6 REGRESSION
required_signatures = true (sin cambio) · D26 commit firmado = NO EXISTE
  (D26 no produjo commit; el gate lo impidió) · excepción histórica D25 =
  intacta · verify-commit HEAD = exit=1 (%G?=N, histórico)
FACTUAL: la protección de firma sigue activa para futuro; D26 no alteró D25.
```

### A.18 Other Security Controls

```text
EVIDENCE A.18 — OTHER SECURITY CONTROLS (sólo lectura)
G3 = OPEN — PLATFORM / ENTITLEMENT BLOCKED (sin cambios)
G4 = OPEN — PLATFORM / ENTITLEMENT BLOCKED (sin cambios)
G5 gate: sha_pinning_required=true (cumplido) · G7 gate: threat_model=remote
  (cumplido; updated_at sin cambio) — estados literales de gate, no de G1/G2
G9 = OPEN — MERGE POLICY DEFINED, NO MERGES (PRs abiertos: 34; 0 acciones)
  allow_auto_merge=false · allow_merge_commit=true · branch protection
  presente (required_pull_request_reviews/strict) · dependabot alerts API:
  n/a en esta llamada; totalCount=11 en A.16 (GraphQL, todas las fases)
FACTUAL: 0 acciones sobre PRs; 0 remediación G3/G4.
```

### A.19 Release Boundary

```text
EVIDENCE A.19 — RELEASE BOUNDARY
TAGS: v0.1.0, v0.1.1 intactos · HEAD_TAG = v0.1.1 (HEAD = db18196…)
RELEASES GH: v0.1.1, v0.1.0 (2, sin cambio)
CHANGELOG/README/VERSION/LICENSE: sin modificación (los únicos archivos con
  diff son los 5 de A.2; ninguno es CHANGELOG/README/VERSION/LICENSE)
docs/release-policy.md: modificación PRE-EXISTENTE (excluida del commit)
CREADOS: 0 tags · 0 releases · 0 version changes
```

### A.20 Pre-existing State

```text
EVIDENCE A.20 — PRE-EXISTING STATE
docs/release-policy.md, start.sh, stop.sh: M intactos (byte-for-byte)
.env: presente · STAGED: 0
journals D19–D25: 6 archivos presentes, 0 tracked/modified (todos untracked)
UNTRACKED total: 35 (históricos + D26)
OPERACIONES PROHIBIDAS EJECUTADAS: 0 (sin reset/clean/restore/checkout --/stash)
FACTUAL: 0 modificaciones de estado preexistente; el commit D26 (inexistente)
  no contiene ninguno de ellos.
```

### A.21 Framework Integrity

```text
EVIDENCE A.21 — FRAMEWORK INTEGRITY
Framework HEAD = 381f56cfa48d092f85846e160d2e1fe6878f9f6f (esperado)
Framework dirty files = 9 (preexistentes)
FRAMEWORK WRITES = 0 · FRAMEWORK JOURNAL WRITES = 0
FACTUAL: sin hard stop.
```

### A.22 Commercial / Secrets

```text
EVIDENCE A.22 — COMMERCIAL / SECRETS
COMMERCIAL CONTENT INTRODUCED = 0 (escaneo del journal y de los diffs: 0)
SECRETS INTRODUCED = 0 (escaneo: 0; sin tokens/credenciales registrados)
```

### A.23 Final Git Baseline

```text
EVIDENCE A.23 — FINAL GIT BASELINE (FASE 28)
FINAL_HEAD: db1819697352a0c09dc63ff4901f0063be57fc8b
FINAL_ORIGIN_MAIN: db1819697352a0c09dc63ff4901f0063be57fc8b
FINAL_LS_REMOTE: db1819697352a0c09dc63ff4901f0063be57fc8b
FINAL_ALIGNMENT: YES
D26_COMMIT_SHA: none (0 commits)
D26_COMMIT_SIGNED: N/A (0 commits; gate FASE 4)
PUSH_RESULT: NOT EXECUTED
REMOTE_CI_RUN_ID: none for D26
REMOTE_CI_RESULT: NOT EXECUTED
STAGED: 0 · UNTRACKED: 35 · worktree: mismos 5 modified
HEAD_TAG: v0.1.1
```

## B. DECISION

### B.1 Initial Scope Decision

```text
DECISION B.1 — INITIAL SCOPE DECISION (FASE 3; registrada tras A.2)
AUTHORIZED FILES:
  .github/workflows/ci.yml
  .github/secret_scanning.yml
EXCLUDED: all other files (docs/release-policy.md, start.sh, stop.sh,
  .env, journal/** — ver A.2, A.6)
COMMIT COUNT: 1 (previsto)
PUSH: one push of the D26 commit only (previsto)
JOURNAL: excluded from commit
→ DEC-01 → A.1, A.2. Esta decisión no es evidencia.
```

### B.2 Commit Decision

```text
DECISION B.2 — COMMIT DECISION (FASE 9 no alcanzada: gate FASE 4)
DECISION: NOT CREATED — BLOCKED AT SIGNING GATE
  CREATE ONE SIGNED COMMIT FOR G1/G2: NO EJECUTABLE (SIGNED COMMIT NOT
  FEASIBLE)
FILES previstos: .github/workflows/ci.yml, .github/secret_scanning.yml
EXCLUDED: all other files · SIGNATURE: REQUIRED (no disponible)
COMMIT COUNT: 0
→ DEC-02 → A.1, A.2, A.3, A.4, A.5, A.6, A.7
Estado G1/G2 durante esta decisión: READY.
La decisión bloqueada no equivale a activación remota.
Ningún commit unsigned creado; ningún --no-gpg-sign; sin amend.
```

### B.3 Commit Execution Authorization Confirmed

```text
DECISION B.3 — COMMIT EXECUTION AUTHORIZATION CONFIRMED: NO
FACTUAL: FASE 11 no alcanzada. La autorización previa de matriz
  (B.1) no basta sin SIGNING CAPABILITY=AVAILABLE (A.3). Sin commit,
  sin B.3-positiva, sin amend.
→ DEC-03 → A.3, A.8, A.9
```

### B.4 Push Decision

```text
DECISION B.4 — PUSH DECISION: NOT AUTHORIZED TO EXECUTE (gate previo)
FACTUAL: FASE 12/14 no alcanzadas. PUSH previsto en B.1 queda supeditado
  a un commit firmado que no existe (A.9). Fuerza: nunca.
→ DEC-04 → A.3, A.9, A.10, A.11
```

### B.5 Remote Activation State

```text
DECISION B.5 — REMOTE ACTIVATION STATE
FACTUAL: sin push no hay transición READY→ACTIVE.
G1 = READY — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION PENDING
G2 = READY — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION PENDING
→ DEC-05 → A.11, A.12, A.14, A.15
Nunca se usa "CLOSED + REMOTE ACTIVATION PENDING" (término contradictorio
prohibido por la máquina de estados).
```

### B.6 CI Acceptance Decision

```text
DECISION B.6 — CI ACCEPTANCE DECISION: NOT EXECUTED
FACTUAL: sin commit D26 no existe run que aceptar; RUN_ID=none (A.13).
Sin verde declarado sobre runs históricos. Sin segundo push para eludir nada.
→ DEC-06 → A.13
```

### B.7 G1 Final Disposition

```text
DECISION B.7 — G1 FINAL DISPOSITION
G1 = READY — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION PENDING
CONDICIONES CLOSED — REMOTE ACTIVATION AND CI VERIFIED: 0/7 cumplidas
  (commit signed NO · push successful NO · main contains D26 SHA NO ·
   remote CI on D26 SHA NO · required checks GREEN N/A ·
   SCA executed remotely NO · no security regression = sí, pero insuficiente)
→ DEC-07 → A.9, A.11, A.12, A.13, A.14, A.16
Cierre NO realizado por inferencia.
```

### B.8 G2 Final Disposition

```text
DECISION B.8 — G2 FINAL DISPOSITION
G2 = READY — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION PENDING
CONDICIONES CLOSED — REMOTE ACTIVATION VERIFIED: 0/5 cumplidas
  (push successful NO · main contains G2 config NO · effective config NO ·
   secret_scanning/push_protection enabled = sí, pero sin activación ·
   no security regression = sí, pero insuficiente)
→ DEC-08 → A.11, A.15, A.16
Cierre NO realizado por inferencia.
```

### B.9 Security Regression Decision

```text
DECISION B.9 — SECURITY REGRESSION DECISION
DECISION: NO SECURITY REGRESSION — 0 settings cambiados
INTENDED: G1/G2 (locales, sin activar) · NO CHANGE: todo lo demás
UNINTENDED: 0 · UNKNOWN: 0 → sin hard stop
→ DEC-09 → A.16, A.17, A.18, A.20, A.21, A.22
```

## C. DOCUMENTATION

### C.1 Journal Metadata

```text
D26 JOURNAL:
  FILE: journal/2026/2026-10-02-d26-g1-g2-remote-activation.md
  CREATED: tras EVIDENCE A.1 (baseline inicial), antes de cualquier
    acción mutante de D26
  UNTRACKED: YES (git status: ?? sobre este archivo)
  STAGED=NO (índice vacío al crear; el journal queda fuera del commit)
  ESTRUCTURA: A.1–A.23 · B.1–B.9 · C.1–C.6
```

### C.2 Commit Record

```text
COMMIT: NOT CREATED · SIGNED: N/A · FILES: 0
SIGNING GATE (A.3): FAIL — commit.gpgsign/gpg.format/user.signingkey unset;
  0 claves GPG; 0 claves SSH propias
SCOPE previsto (unidad futura): exclusivamente
  .github/workflows/ci.yml y .github/secret_scanning.yml
```

### C.3 Push Record

```text
PUSH: NOT EXECUTED · FORCE: never
pushed_at sin cambios: 2026-10-01T16:40:35Z
HEAD = origin/main = ls-remote = db18196… (ALIGN YES)
```

### C.4 CI Record

```text
REMOTE CI: NOT EXECUTED · RUN_ID: none for D26
REMOTE CI RESULT: NOT EXECUTED
Sin uso de runs históricos como resultado de D26.
```

### C.5 Traceability

```text
DEC-01 (B.1 scope)        → A.1, A.2
DEC-02 (B.2 commit)       → A.1–A.7
DEC-03 (B.3 confirmación) → A.3, A.8, A.9
DEC-04 (B.4 push)         → A.3, A.9, A.10, A.11
DEC-05 (B.5 estado)       → A.11, A.12, A.14, A.15
DEC-06 (B.6 CI)           → A.13
DEC-07 (B.7 G1)           → A.9, A.11, A.12, A.13, A.14, A.16
DEC-08 (B.8 G2)           → A.11, A.15, A.16
DEC-09 (B.9 regresión)    → A.16–A.18, A.20–A.22
CHRONOLOGY: gate FASE 4 (A.3) ocurrió ANTES de A.4–A.7; registrado en su
  posición cronológica. Secciones A.8–A.15 = fases mutantes no alcanzadas.
  D24/D25 no modificados; normalización READY operativa desde D26.
SCANS journal: comercial 0/0 · secretos 0 · sección A sin palabras de
  decisión (0 ocurrencias CLOSED/APPROVED/ACCEPTED/SAFE/RECOMMENDED)
```

### C.6 Future Unit Boundary

```text
PREREQUISITO (unidad propia, autorización separada): SIGNING PROVISIONING —
  generar/configurar clave de firma (GPG o SSH) + identidad git; verificar
  con git verify-commit en commit de prueba local. No incluir en D26.
DESPUÉS: unidad de activación (COMMIT=YES + PUSH=YES) — staging exacto de
  los 2 archivos → commit firmado único → push → READY → ACTIVE →
  verificación CI → CLOSED.
Siguiente unidad tras G1/G2 CLOSED: G9 CONTROLLED DEPENDABOT MERGE
  (autorización específica de merge), luego LICENSE → v0.1.2 readiness →
  Sprint 13. PVR completamente separado.
JOURNAL FINAL: UNTRACKED · STAGED = NO · fuera del commit G1/G2.
```
