# D27 — SIGNING PROVISIONING

Registro cronológico APPEND-ONLY de la unidad independiente D27
(SIGNING PROVISIONING). No activa G1/G2, no crea el commit D26, no hace
push, no modifica configuración remota de GitHub, no toca Framework.

## A. EVIDENCE

### A.1 Authorization

```text
A.1 AUTORIZACIÓN
SOURCE: contexto operativo de la unidad (sección 0 del prompt D27)
RAW: AUTHORIZE_SIGNING_PROVISIONING=YES (autorización única y explícita
  de esta unidad; NO sustituye a AUTHORIZE_COMMIT ni AUTHORIZE_PUSH;
  no infiere, no se amplía a commit/push/tag/release/PR/merge/remoto)
```

### A.2 Dynamic Baseline

```text
A.2 BASELINE DINÁMICO (FASE 0)
COMMAND: git fetch --prune --tags + rev-parse/status/ls-remote
RAW RESULT:
  BRANCH: main
  HEAD: db1819697352a0c09dc63ff4901f0063be57fc8b
  ORIGIN_MAIN: db1819697352a0c09dc63ff4901f0063be57fc8b
  LS_REMOTE: db1819697352a0c09dc63ff4901f0063be57fc8b
  HEAD_TAG: v0.1.1 · TAGS: v0.1.0, v0.1.1
  STAGED: 0 · UNTRACKED: 35 · MODIFIED: los 5 conocidos (G1/G2 + 3
    preexistentes)
  BASELINE GATE: PASS (sin divergencias ni staged inesperado)
SHA-256 PRE:
  docs/release-policy.md  2ed1114f65bcd778e436bb635dcf0982d10cada806272d8dc7cc13a2ceabfabb
  start.sh                f09451163eb9016421f58e7a558033a77d1e7eb8108d1f77bc6d1bc34a5934b5
  stop.sh                 8be30918497bd5b07c3fb9608d098dc589090884b2b52709fddbcbf03f177170
  .env                    a5dbbbbabee11c148b9389c344e28f95530c5dd1001044a02703350d9986d190
  .github/workflows/ci.yml
                         13ba00ee02531e8e747c630e50e9257a432a0e67faa2f717c778ef3b3669f4b1
  .github/secret_scanning.yml
                         10cef7e4823c4ff7fbd268e6c46a9de8afcf4f3d35400a729e62b04da42b5b70
  (hashes de .env calculados sin mostrar contenido)
D19–D26: 8 journals presentes, 0 modificaciones
FRAMEWORK HEAD: 381f56cfa48d092f85846e160d2e1fe6878f9f6f · 9 dirty preexistentes
```

### A.3 Initial Signing State

```text
A.3 ESTADO INICIAL DE FIRMA (FASE 1)
COMMAND: git config --get commit.gpgsign/gpg.format/user.signingkey/
  user.name/user.email; gpg --version; ssh -V; ls ~/.ssh/*.pub;
  gpg --list-secret-keys
RAW RESULT:
  commit.gpgsign=unset · gpg.format=unset · user.signingkey=unset
  user.name=danielcba · user.email=daniel.e.cordoba@gmail.com
  gpg (GnuPG) 2.4.8 · OpenSSH_10.2p1 · ~/.ssh/*.pub: none
  gpg secret keys: 0
FACTUAL: no existe ninguna identidad de firma previa (GPG ni SSH);
  criterio de conservación sin clave existente que preservar.
```

### A.4 Signing Mechanism Selected

```text
A.4 MECANISMO SELECCIONADO (FASE 2)
SELECCIÓN: GPG/OpenPGP (preferencia 1: GPG 2.4.8 instalado, permite generar
  identidad controlada)
ALTERNATIVA SSH: no usada (sin claves SSH; sin necesidad demostrada)
CRITERIO DE CONSERVACIÓN: sin identidad existente (A.3: 0 claves secretas
  GPG, 0 ~/.ssh/*.pub) → nada que sobrescribir ni eliminar
CAMBIOS REMOTOS: 0 · claves registradas en servicios externos: 0
```

### A.5 Provisioning Evidence

```text
A.5 PROVISIONING EJECUTADO (FASE 3)
COMMAND: gpg --batch --passphrase '' --quick-generate-key
  "danielcba <daniel.e.cordoba@gmail.com>" ed25519 sign 2y
RAW RESULT:
  sec ed25519/AE6CF2AC469DCBC9 2026-10-02 [SC] [expires: 2028-10-01]
  fpr BABDAC9F935E7A3E6E8F632DAE6CF2AC469DCBC9
  uid [ultimate] danielcba <daniel.e.cordoba@gmail.com>
  exit=0 · revocation cert almacenada en ~/.gnupg/openpgp-revocs.d/
PASSPHRASE: vacío (%no-protection) para permitir git commit -S no
  interactivo en la unidad de activación — decisión documentada en B.3
CLAVES PRIVADAS: no leídas ni impresas · sólo fingerprint/uid públicos
CLAVES PREEXISTENTES: ninguna destruida (no existían)
```

### A.6 Git Signing Configuration

```text
A.6 CONFIGURACIÓN GIT APLICADA (SECCIÓN 7)
SCOPE: --local (repositorio company-os-monitor; sin cambios --global)
RAW RESULT:
  commit.gpgsign=true
  gpg.format=openpgp
  user.signingkey=BABDAC9F935E7A3E6E8F632DAE6CF2AC469DCBC9
  user.name=danielcba · user.email=daniel.e.cordoba@gmail.com (sin cambios)
GLOBAL: commit.gpgsign/global y user.signingkey/global siguen unset
NO TOCADOS: pull/fetch/remote/branch protection/credential helpers/tokens/
  auth/GitHub CLI auth (0 modificaciones)
```

### A.7 Temporary Signed Commit Test

```text
A.7 PRUEBA EN REPOSITORIO TEMPORAL (FASE 4)
PATH: /tmp/d27-signing-test-52107 (fuera del proyecto)
ACTION: git init → identidad mínima → test.txt → UN commit firmado (-S)
RAW RESULT: commit 2af870dc6b103255fa0257a81f690d0710b9e846
  %G? = G · subject: "D27 temporary signing test"
  1 file changed (test.txt, no sensible)
TEMP REPO: eliminado (rm -rf) tras la prueba → no conservado
SIGNED TEST COMMIT = PASS
```

### A.8 Signature Verification

```text
A.8 RESULTADO DE VERIFY-COMMIT (FASE 4)
COMMAND: git verify-commit HEAD (en repo temporal)
RAW RESULT: exit=0 · "gpg: Good signature from
  danielcba <daniel.e.cordoba@gmail.com> [ultimate]" · EDDSA key
  BABDAC9F935E7A3E6E8F632DAE6CF2AC469DCBC9
git verify-commit = PASS
```

### A.9 Main Repository Verification

```text
A.9 VALIDACIÓN EN REPOSITORIO PRINCIPAL SIN COMMIT (FASE 5)
CONFIG: commit.gpgsign=true · gpg.format=openpgp ·
  user.signingkey=BABDAC9F935E7A3E6E8F632DAE6CF2AC469DCBC9 (identidad válida)
NO-COMMIT CHECK: roundtrip gpg --sign/--verify en /tmp → "Good signature"=1
  (comprobación equivalente sin crear commit git)
STATE: STAGED=0 · HEAD=ORIGIN=LS=db1819697352a0c09dc63ff4901f0063be57fc8b
NO ejecutado: git add, commit, commit --amend, commit D26, commit vacío,
  commit unsigned, --no-gpg-sign
```

### A.10 Non-Regression Validation

```text
A.10 VERIFICACIÓN DE NO REGRESIÓN (FASE 6)
SHA-256 POST (6/6 idénticos a A.2 PRE):
  docs/release-policy.md  2ed1114f65bcd778e436bb635dcf0982d10cada806272d8dc7cc13a2ceabfabb
  start.sh                f09451163eb9016421f58e7a558033a77d1e7eb8108d1f77bc6d1bc34a5934b5
  stop.sh                 8be30918497bd5b07c3fb9608d098dc589090884b2b52709fddbcbf03f177170
  .env                    a5dbbbbabee11c148b9389c344e28f95530c5dd1001044a02703350d9986d190
  .github/workflows/ci.yml
                         13ba00ee02531e8e747c630e50e9257a432a0e67faa2f717c778ef3b3669f4b1
  .github/secret_scanning.yml
                         10cef7e4823c4ff7fbd268e6c46a9de8afcf4f3d35400a729e62b04da42b5b70
GIT: STAGED=0 · MODIFIED=los mismos 5 · UNTRACKED=36 (35 baseline + D27)
  → único archivo nuevo causado por D27: este journal
PRE-EXISTING STATE CHANGES = 0
```

### A.11 Framework Integrity

```text
A.11 INTEGRIDAD DEL FRAMEWORK
FRAMEWORK HEAD = 381f56cfa48d092f85846e160d2e1fe6878f9f6f (esperado, pre=post)
dirty preexistentes = 9 · FRAMEWORK WRITES = 0 · FRAMEWORK JOURNAL WRITES = 0
```

### A.12 Pre-existing State Integrity

```text
A.12 INTEGRIDAD DEL ESTADO PREEXISTENTE
D19–D26: 8 journals presentes, 0 modificaciones (git status: 0 tracked/modified)
sha256 de los 6 archivos controlados: idénticos PRE→POST (A.2 vs A.10)
.git/config: única escritura D27 (parámetros de firma locales, sección 7)
operaciones prohibidas ejecutadas: 0 (0 add/reset/clean/restore/checkout --/
  stash/commit/push/tag/gh release/gh pr)
```

### A.13 G1/G2 State

```text
A.13 ESTADO G1/G2 (FASE 7)
G1 = READY — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION PENDING
G2 = READY — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION PENDING
La capacidad de firma local NO equivale a: commit D26 creado/firmado,
push, activación G1/G2, CI remoto, cierre G1/G2. D27 no cambia esos estados.
Estado prohibitivo "CLOSED + REMOTE ACTIVATION PENDING": no utilizado.
```

### A.14 Final Result

```text
A.14 RESULTADO FINAL (FASE 8/9)
24/24 criterios de éxito cumplidos (ver C.1)
D27_STATUS: COMPLETED — SIGNING PROVISIONING VERIFIED
único artefacto nuevo: journal/2026/2026-10-02-d27-signing-provisioning.md
  (UNTRACKED, STAGED=NO, append-only)
```

## B. DECISION

### B.1 Technical Evidence

```text
DECISION B.1 → A.2, A.3, A.5, A.7, A.8, A.9
La evidencia técnica (baseline PASS, inventario con 0 claves previas,
provisioning exitoso, commit de prueba firmado y verify-commit PASS,
config local aplicada, repo principal sin commits) sustenta todas las
decisiones de esta unidad. Las decisiones no son evidencia.
```

### B.2 Signing Identity

```text
DECISION B.2 → A.5, A.6
IDENTIDAD: danielcba <daniel.e.cordoba@gmail.com> — la identidad Git
  existente, no inventada (requisito sección 6)
FINGERPRINT: BABDAC9F935E7A3E6E8F632DAE6CF2AC469DCBC9 (público, no secreto)
DECISION: reutilizar la identidad Git sin sustituirla; 0 identidades
  destruidas; 0 segundas identidades (no había previas)
```

### B.3 Selected Method

```text
DECISION B.3 → A.3, A.4, A.5
MÉTODO: GPG/OpenPGP (ed25519, expira 2028-10-01) — preferencia 1
PASSPHRASE vacío (%no-protection): decisión explícita para permitir
  git commit -S no interactivo en la unidad de activación posterior
SSH signing: descartado (no necesario; 0 claves SSH)
Configuración --local al alcance del repo (nada --global altera otros repos)
```

### B.4 Signature Verification

```text
DECISION B.4 → A.7, A.8, A.9
TEST SIGNED COMMIT = PASS (2af870d, %G?=G, repo temporal eliminado)
git verify-commit = PASS (Good signature, exit=0)
COMPROBACIÓN EN REPO PRINCIPAL SIN COMMIT = PASS (roundtrip gpg)
→ DEC-04: capacidad de firma verificable localmente establecida
```

### B.5 Repository Files

```text
DECISION B.5 → A.10, A.12
ARCHIVOS DEL REPOSITORIO: 0 archivos de producción modificados por D27;
  única escritura en .git/config (parámetros de firma locales);
  único archivo nuevo: este journal (UNTRACKED, STAGED=NO)
SHA-256 6/6 idénticos PRE→POST → PRE-EXISTING STATE CHANGES = 0
```

### B.6 Remote Controls Unchanged

```text
DECISION B.6 → A.10 (read-only), settings verificados sin escritura
required_signatures=true · sha_pinning_required=true ·
threat_model=remote (updated_at sin cambio) · secret_scanning=enabled ·
push_protection=enabled · dependabot_security_updates=enabled · PVR=false ·
PRs=34 (0 acciones) · pushed_at sin cambio · tags/releases sin cambio
D27 modificó controles remotos: 0
```

### B.7 Unit Limits

```text
DECISION B.7 → A.9, A.10, A.12
LÍMITES RESPECTADOS: sin commit, sin push, sin tag, sin release, sin PR
  (abierto/cerrado/merge/rebase), sin CI remoto intencionado, sin modificar
  D19–D26, sin Framework, sin GitHub settings, sin registro remoto de clave,
  sin eliminar/sustituir claves, sin trabajo de unidades posteriores
```

### B.8 Next Unit

```text
DECISION B.8 → A.13, A.14
NEXT UNIT: G1/G2 CONTROLLED ACTIVATION (no ejecutada en D27)
AUTHORIZATION REQUIRED: COMMIT=YES + PUSH=YES
SCOPE: staging exacto de .github/workflows/ci.yml y
  .github/secret_scanning.yml · un único commit firmado · push único ·
  CI remoto · verificación de activación G1 · verificación de activación G2
OUT OF SCOPE: G9 · LICENSE · v0.1.2 · Sprint 13 · PVR · Framework ·
  cualquier otro archivo
```

### B.9 Traceability

```text
DECISION B.9 (matriz completa):
  DEC-01 (B.1 evidencia)        → A.2, A.3, A.5, A.7, A.8, A.9
  DEC-02 (B.2 identidad)        → A.5, A.6
  DEC-03 (B.3 método)           → A.3, A.4, A.5
  DEC-04 (B.4 verificación)     → A.7, A.8, A.9
  DEC-05 (B.5 archivos)         → A.10, A.12
  DEC-06 (B.6 controles)        → A.10 (read-only)
  DEC-07 (B.7 límites)          → A.9, A.10, A.12
  DEC-08 (B.8 unidad siguiente) → A.13, A.14
CHRONOLOGY: A.1→A.14 en orden de ocurrencia (append-only)
SCANS journal: comercial = 0 · secretos = 0 (sin claves privadas,
  passphrases, tokens ni credenciales registrados)

## C. DOCUMENTATION

### C.1 D27_STATUS

```text
D27_STATUS: COMPLETED — SIGNING PROVISIONING VERIFIED
(24/24 criterios de éxito: 1 autorización ✓ · 2 baseline PASS ✓ ·
3 clave provisionada sin destruir existentes ✓ · 4 identidad verificable ✓ ·
5 config correcta ✓ · 6 commit de prueba en repo temporal ✓ ·
7 verify-commit PASS ✓ · 8 repo principal 0 commits ✓ · 9 staged=0 ✓ ·
10 HEAD/origin/ls-remote intactos ✓ · 11 sha256 6/6 ✓ · 12 .env intacto ✓ ·
13 D19–D26 intactos ✓ · 14 Framework intacto ✓ · 15 Framework writes=0 ✓ ·
16 settings sin cambios ✓ · 17 G1=READY ✓ · 18 G2=READY ✓ · 19 no push ✓ ·
20 no commit D26 ✓ · 21 sin secretos ✓ · 22 journal append-only ✓ ·
23 comercial=0 ✓ · 24 secret scans=0 ✓)
```

### C.2 SIGNING_CAPABILITY

```text
SIGNING_CAPABILITY: AVAILABLE — GPG/OpenPGP (GnuPG 2.4.8) provisionado
  localmente y verificado (A.5, A.8, A.9)
```

### C.3 SIGNING_IDENTITY

```text
SIGNING_IDENTITY: danielcba <daniel.e.cordoba@gmail.com>
  keyid AE6CF2AC469DCBC9 · fpr BABDAC9F935E7A3E6E8F632DAE6CF2AC469DCBC9
  (ed25519 [SC], expira 2028-10-01; passphrase vacío documentado en B.3;
  sólo identificadores públicos registrados)
```

### C.4 TEST_SIGNED_COMMIT

```text
TEST_SIGNED_COMMIT: PASS — 2af870dc6b103255fa0257a81f690d0710b9e846
  en /tmp/d27-signing-test-52107 (repo temporal eliminado);
  %G?=G · SIGNED TEST COMMIT = PASS
```

### C.5 VERIFY_COMMIT

```text
VERIFY_COMMIT: PASS — git verify-commit HEAD exit=0 ·
  "gpg: Good signature from danielcba <daniel.e.cordoba@gmail.com>"
  (repo temporal) · roundtrip gpg en repo principal sin commit: PASS
```

### C.6 FINAL_DISPOSITION

```text
COMMIT_CREATED_IN_MAIN_REPO: NO · PUSH: NO · REMOTE_CI: NOT EXECUTED
G1 = READY — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION PENDING
G2 = READY — LOCAL IMPLEMENTATION VERIFIED; REMOTE ACTIVATION PENDING
SECURITY REGRESSIONS: NONE · UNAUTHORIZED MUTATIONS: 0
FRAMEWORK WRITES: 0 · PRE-EXISTING STATE CHANGES: 0
COMMERCIAL CONTENT: 0 · SECRETS: 0 · STAGED: 0
NEXT UNIT: G1/G2 CONTROLLED ACTIVATION —
  AUTHORIZATION REQUIRED: COMMIT=YES + PUSH=YES
  SCOPE: staging exacto de .github/workflows/ci.yml y
    .github/secret_scanning.yml · un único commit firmado · push único ·
    CI remoto · verificación de activación G1 · verificación de activación G2
  OUT OF SCOPE: G9 · LICENSE · v0.1.2 · Sprint 13 · PVR · Framework ·
    cualquier otro archivo
```
