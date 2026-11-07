# D48 — CODECOV CI FAILURE CONTROLLED REMEDIATION

```text
RUN_ID=37252838032
PR=55
HEAD_SHA=8e27a7fe1f089ce9e7b24f7768decb6cf72617ed
FAILED_STEP=Upload coverage
CODECOV_ACTION=codecov/codecov-action@ab904c41d6ece82784817410c45d8b8c02684457
OBSERVED_ERROR=EPROTO / TLS handshake failure
```

## A — EVIDENCE

### A.1 Remote Failure Evidence (dada por el run; verificación read-only)

```text
RUN_ID=37252838032, WORKFLOW=CI, RUN_NUMBER=289, EVENT=pull_request
PR=55 (dependabot/pip/main/python-dotenv-gte-1.2.4)
HEAD_SHA=8e27a7fe1f089ce9e7b24f7768decb6cf72617ed
BASE_BRANCH=main, BASE_SHA=33ca6dbeb865e5e420631054ce302ba85c5090d2
CONCLUSION=failure
FAILED_JOB=lint-and-test (3.12, 24), FAILED_STEP=Upload coverage
CODECOV_ACTION=codecov/codecov-action@ab904c41d6ece82784817410c45d8b8c02684457 # v3.1.1
ERROR=Error: write EPROTO ... ssl3_read_bytes:ssl/tls alert handshake failure
GATES PASS antes del fallo: Ruff, MyPy libs, MyPy gateway, MyPy services,
  Root tests, Service tests, Gateway tests, Frontend setup, Frontend tests,
  Frontend dependency audit, Security scan, Dependency audit
docker-build=OMITIDO (job con `needs: lint-and-test`)
PR #55 modifica SOLO pyproject.toml (python-dotenv>=1.0 → >=1.2.4)
CONFIG OBSERVADA: fail_ci_if_error=false
RUNNER: warning de compatibilidad/runtimes de Node.js para acciones heredadas
  → tratado como evidencia contextual, NO como causa raíz.
```

### A.2 Dynamic Baseline (fresco, ANTES de cualquier escritura de esta ejecución)

```text
BRANCH: main
HEAD: 3eaced8c35868ed91cbce81a5c4bd21537aacfec
ORIGIN/MAIN: 33ca6dbeb865e5e420631054ce302ba85c5090d2
LS-REMOTE refs/heads/main: 33ca6dbeb865e5e420631054ce302ba85c5090d2
BASELINE_REMOTE_STATUS: STABLE (origin/main == ls-remote; sin fetch)
LOCAL_DIVERGENCE: PRE-EXISTING — local main 3 commits DETRÁS de origin/main,
  0 adelante (merge de PR #52 asyncpg). NO reconciliada (pull/merge/rebase/
  checkout fuera de autorización). Único archivo distinto HEAD↔origin/main:
  pyproject.toml (fuera de scope, NO tocado). ci.yml: blob idéntico en HEAD
  y en origin/main → el diff aplica sobre el mismo contenido que main remoto.
WORKTREE_DRIFT: PRE-EXISTENTE en 4 paths:
  M .github/workflows/ci.yml   ← remediación funcional YA PRESENTE al entrar
                                 (pin v7.0.0 + continue-on-error + comentarios)
                                 proveniente de la sesión D48 anterior
  M docs/release-policy.md     ← fuera de scope, byte-idéntico al baseline
  M start.sh                   ← fuera de scope, byte-idéntico al baseline
  M stop.sh                    ← fuera de scope, byte-idéntico al baseline
STAGED_DRIFT: NO (índice vacío durante toda la ejecución)
UNTRACKED: 55 (54 journals preexistentes D2..D47 + este journal D48)
Sha256 pre-escritura de este journal:
  docs/release-policy.md   2ed1114f65bcd778e436bb635dcf0982d10cada806272d8dc7cc13a2ceabfabb
  start.sh                 f09451163eb9016421f58e7a558033a77d1e7eb8108d1f77bc6d1bc34a5934b5
  stop.sh                  8be30918497bd5b07c3fb9608d098dc589090884b2b52709fddbcbf03f177170
  .github/workflows/ci.yml ad671838f7da890dab9383c6ea921025be60bd58feae063a4d3d3f2e60060685
  (blob HEAD de ci.yml sin modificar = 13ba00ee02531e8e747c630e50e9257a432a0e67faa2f717c778ef3b3669f4b1)
FRAMEWORK HEAD (company-os-main, solo lectura): 381f56cfa48d092f85846e160d2e1fe6878f9f6f
FRAMEWORK_WRITES: 0 · FRAMEWORK_JOURNAL_WRITES: 0
.env / .env.*: NO abiertos, NO modificados, NO reportados
Mutaciones remotas: 0 (solo git ls-remote y raw.githubusercontent read-only)
```

### A.3 Local Diagnostic (hechos observados en `.github/workflows/ci.yml`)

```text
CODECOV_ACTION: codecov/codecov-action
CODECOV_ACTION_SHA: fb8b3582c8e4def4969c97caa2f19720cb33a72f (pin presente)
CODECOV_ACTION_VERSION: v7.0.0 — verificado read-only en ESTA ejecución
    (git ls-remote):
      refs/tags/v7.0.0    = e53489f4d376d79066609109e7a95a29eb3740b1 (tag object)
      refs/tags/v7.0.0^{} = fb8b3582c8e4def4969c97caa2f19720cb33a72f (commit)
    → coincide con la referencia del prompt; pin por SHA completo (no tag).
RUNTIME_NODE (hechos, sin atribución causal):
    workflow: matrix node-version ["24"] + actions/setup-node
    v3.1.1 (action.yml @ ab904c41): runs.using='node16', main=dist/index.js
    v7.0.0 (action.yml @ fb8b3582): runs.using='composite' (sin runtime Node
      de acción; pasos shell + codecov CLI)
    El runner emitió un warning de compatibilidad/runtimes Node para acciones
    heredadas: EVIDENCIA CONTEXTUAL, no causa raíz demostrada.
FAIL_CI_IF_ERROR: false (presente, MANTENIDO)
CONTINUE_ON_ERROR: true (presente a nivel de step)
JOB_PERMISSIONS: workflow `contents: read`; docker-build `contents: read`;
  sin id-token, sin elevaciones; sin cambios (diff no toca permissions)
CODECOV_TOKEN: AUSENTE — NO añadido (sin input `token:`, sin env, sin secrets)
COVERAGE_GENERATION: step "Root tests" = pytest tests/ --cov=libs --cov-report=xml -v
  → byte-idéntico al HEAD (línea 131 intacta)
COVERAGE_FILE: ./coverage.xml — existe (147784 bytes), XML válido (raíz
  <coverage>), gitignored (.gitignore línea 11). NO regenerado: regenerarlo
  mutaría bytes preexistentes fuera del scope.
DEPENDABOT_COMPATIBILITY: v7.0.0 admite upload tokenless (inputs `token` y
  `use_oidc` opcionales, default 'false') → sin secretos requeridos; inputs
  usados (`files`, `fail_ci_if_error`) existen en v7.0.0 (fail_ci_if_error
  default 'false') → configuración válida y compatible con PRs de Dependabot.
SEMÁNTICA REAL DE fail_ci_if_error=false (verificada en action.yml v7.0.0):
  el input se traduce a CC_FAIL_ON_ERROR y gobierna si el uploader retorna
  código distinto de cero (classificación del resultado del upload DENTRO de
  la acción). NO controla:
    - errores de proceso del step de GitHub Actions no gestionados por esa
      lógica (p. ej. una excepción no capturada en el runtime de la acción);
    - fallos de infraestructura del runner;
    - cualquier camino de fallo anterior/posterior a esa comprobación.
  → El input NO es una garantía de que el step termine en success.
  El run 37252838032 es la demostración empírica: step `failure` con
  fail_ci_if_error=false presente.
Condiciones del workflow que puedan hacer de un error de Codecov un fallo de
  job: ÚNICAMENTE el step `Upload coverage` (último step del job). Con
  `continue-on-error: true` su fallo ya no propaga a la conclusión del job.
YAML syntax: PASS (yaml.safe_load; jobs = lint-and-test, docker-build)
```

### A.4 Root Cause

```text
OBSERVED_FACT:
- `Upload coverage` terminó en failure.
- El proceso reportó EPROTO / TLS handshake failure durante una operación de
  red.
- Los 12 gates anteriores pasaron; docker-build se omitió solo por `needs`.
- `fail_ci_if_error=false` estaba configurado.
- El fallo ocurrió dentro del step de Codecov.

JOB_FAILURE_CAUSE:
- Demostrado: el step `Upload coverage` terminó en `failure` debido a un error
  de transporte TLS/EPROTO reportado durante la operación de red del uploader.
  Con ello el job `lint-and-test` concluyó `failure` (y `docker-build` cayó
  por dependencia `needs`, no por un fallo propio).

ROOT_CAUSE_OF_TRANSPORT_ERROR:
- UNDETERMINED / NOT PROVEN.
- El origen exacto del EPROTO no fue demostrado: no existe evidencia directa
  que encadene causalmente el error de handshake con un componente concreto
  (runtime de la acción, stack TLS del runner, endpoint/proxy de Codecov,
  red del runner, versión de la acción). Con la evidencia disponible solo se
  dispone de correlación, no de causalidad.

CONTRIBUTING_FACTOR (factores que pueden haber contribuido; etiquetados como
tales, no como causa demostrada):
- CF-1: el pin era una acción de generación anterior (v3.1.1,
  runs.using='node16') ejecutada en un runner que informó runtimes Node
  heredados forzados → superficie de compatibilidad obsoleta (correlación
  observada, causalidad no demostrada).
- CF-2: `fail_ci_if_error=false` es un control insuficiente de por sí: solo
  gobierna la clasificación del resultado del uploader dentro de la acción y
  no cubre fallos de proceso del step. Por eso el requisito "Codecov no puede
  bloquear el job" no quedaba garantizado antes de la remediación (esto SÍ
  está demostrado por el propio run).
- CF-3: no había ninguna barrera a nivel de GitHub Actions
  (`continue-on-error` ausente) que aislara al job de un fallo del proveedor.

UNCONFIRMED_HYPOTHESIS:
- H-1 (NO tratada como hecho): "una excepción TLS no manejada dentro del
  bundle JS de v3.1.1 se propagó fuera de la lógica gobernada por
  fail_ci_if_error=false". Es técnicamente plausible y consistente con el
  formato del error, pero no fue verificada: no se reprodujo el fallo, no se
  inspeccionó el código ejecutado en el run, no hay stack trace del step.
  Se mantiene como hipótesis.
- H-2 (NO tratada como hecho): que el upgrade a v7.0.0 elimine la
  recurrencia del EPROTO. No verificable sin un workflow run posterior
  (WORKFLOW_RERUN fuera de autorización en D48).
- H-3 (NO tratada como hecho): que el warning de runtime Node del runner sea
  la causa raíz del EPROTO. Es evidencia contextual de compatibilidad, sin
  cadena causal demostrada.
- python-dotenv / PR #55 NO son causa: sin evidencia (los gates de
  dependencias pasaron en el mismo run); la PR no fue tocada.

SEPARACIÓN EXPLÍCITA:
- causa demostrada del failure del step = fallo TLS/EPROTO en `Upload coverage`
  (JOB_FAILURE_CAUSE).
- mitigación destinada a impedir que Codecov vuelva a bloquear el job =
  `continue-on-error: true` (+ pin mantenida). Esta mitigación NO es evidencia
  del origen del EPROTO.
```

### A.5 Remediation

```text
PREVIOUS_ACTION: codecov/codecov-action@ab904c41d6ece82784817410c45d8b8c02684457 # v3.1.1
FINAL_ACTION:    codecov/codecov-action@fb8b3582c8e4def4969c97caa2f19720cb33a72f # v7.0.0
FINAL_SHA: fb8b3582c8e4def4969c97caa2f19720cb33a72f
  (SHA completo verificado contra refs/tags/v7.0.0^{} en esta ejecución;
   NO se usa @v7 / @v7.0.0 / @main)
FAIL_CI_IF_ERROR: false (MANTENIDO → Codecov NON_GATING)
CONTINUE_ON_ERROR: true (presente a nivel de step)
REMEDIATION_APPLIED: YES (estado del repositorio: la remediación funcional
  completa está presente en `.github/workflows/ci.yml`)
REMEDIATION_NOT_NEEDED: NO (la remediación está justificada por el run)
REMEDIATION_TYPE: CORRECTIVE+PREVENTIVE_HARDENING
  CORRECTIVE — `continue-on-error: true` corrige el DEFECTO DEMOSTRADO de
    configuración: antes de la remediación una falla del step de Codecov sí
    puso el job en rojo a pesar de `fail_ci_if_error=false` (requisito
    "Codecov non-gating" no garantizado). Con la protección a nivel de step el
    requisito queda garantizado estructuralmente. Esto corrige la propagación
    del fallo, NO el origen del EPROTO.
  PREVENTIVE_HARDENING — el upgrade del pin v3.1.1 → v7.0.0 es compatibility
    hardening: versión mantenida, `runs.using: composite` (sin runtime de
    acción heredado), mismos inputs, sin token ni permisos. NO se presenta
    como corrección de la causa raíz del EPROTO porque esa causa no está
    demostrada.
ESTA EJECUCIÓN (mutación realizada):
  - NO re-aplicó la remediación funcional (ya presente al obtener el baseline;
    verificada, no duplicada).
  - Mutación aplicada: SOLO corrección de redacción dentro del mismo step
    `Upload coverage` (comment-only, no funcional). El comentario anterior
    afirmaba como hecho la hipótesis H-1 y describía v3.1.1 como "Node
    20-era" cuando action.yml declara `runs.using: node16`; la redacción nueva
    refleja explícitamente que el origen del EPROTO no fue determinado.
  - Ninguna línea ejecutable cambió en esta ejecución.
Verificación del estado funcional presente:
  - único hunk `@@ -193 +193,12 @@` confinado al step `Upload coverage`
  - `uses:` pin + `continue-on-error: true` + `fail_ci_if_error: false` intactos
  - comandos de CI byte-idénticos al HEAD (ruff, mypy×3, pytest×3, npm ci/lint/
    typecheck/test, npm audit, bandit, pip-audit, docker build)
NO modificados: PR #55, python-dotenv, pyproject.toml, poetry.lock,
  requirements*, package*.json, tests/, Dockerfiles, otros workflows,
  .github/secret_scanning.yml, LICENSE, archivos de aplicación, gates,
  coverage generation, Dependabot, permisos, secretos, Framework company-os.
```

### A.6 Validation

```text
LOCAL_VALIDATION (= LOCAL_CONFIGURATION_STATUS = PASS):
  YAML syntax = PASS (yaml.safe_load; jobs = lint-and-test, docker-build)
  intended diff only = PASS (único hunk, confinado a `Upload coverage`;
    11+/1-, de los cuales solo `uses:` y `continue-on-error:` son ejecutables)
  existing CI commands unchanged = PASS (todo `run:` byte-idéntico al HEAD)
  coverage.xml generation = PASS a nivel de configuración (comando intacto
    línea 131; pytest 9.1.1 + pytest-cov cargados, flags --cov/--cov-report=xml
    disponibles; artefacto ./coverage.xml presente y XML válido). NO
    regenerado para preservar bytes preexistentes y no ejecutar la suite.
  Codecov configuration = NON_GATING (fail_ci_if_error: false +
    continue-on-error: true)
  permissions unchanged = PASS (contents: read a nivel workflow y en
    docker-build; diff no toca permissions)
  no secret/token introduced = PASS (sin token, id-token, secrets, elevaciones)
  no unrelated workflow changes = PASS (único path en .github/: ci.yml)
  pre-existing state preserved = PASS (sha256 de docs/release-policy.md,
    start.sh, stop.sh idénticos al baseline; índice vacío; 54 journals
    untracked intactos; .env* no abiertos)
  Framework writes = 0 (HEAD 381f56cf... inalterado)
  remote mutations = 0

REMOTE_VALIDATION:
  REMOTE_CI_STATUS = PENDING_VALIDATION
  Sin COMMIT/PUSH/WORKFLOW_RERUN autorizados no existe ningún run posterior
  que ejecute la configuración corregida. NO se declara PASS remoto. Sin
  conexión al endpoint de Codecov y sin credenciales reales.
```

## B — ANALYSIS

El run 37252838032 NO es un fallo funcional: los 12 gates de calidad, tests
y seguridad pasaron; el único step rojo es `Upload coverage` y `docker-build`
solo se omitió por `needs`.

```text
TEST_FAILURE: NO
CODE_QUALITY_FAILURE: NO
SECURITY_FAILURE: NO
DEPENDENCY_FAILURE: NO
EXTERNAL_CODECOV_FAILURE: YES
```

## C — DECISION

```text
D48_STATUS: COMPLETED
EXECUTION_STATUS: COMPLETED
ROOT_CAUSE_STATUS: PARTIALLY_IDENTIFIED
LOCAL_CONFIGURATION_STATUS: PASS
REMOTE_CI_STATUS: PENDING_VALIDATION
CODECOV_STATUS: NON_GATING
REMEDIATION_APPLIED: YES
REMEDIATION_NOT_NEEDED: NO
REASON: El fallo del job está localizado y caracterizado con certeza
  (`Upload coverage` → fallo de transporte TLS/EPROTO, con los 12 gates
  previos en PASS), y la remediación presente (pin v7.0.0 por SHA completo +
  continue-on-error, manteniendo fail_ci_if_error=false) está justificada y
  validada localmente; el origen exacto del EPROTO permanece NO demostrado,
  por lo que la causa raíz se declara parcialmente identificada y no se
  atribuye a ningún componente. Validación remota pendiente por ausencia de
  autorización para commit/push/rerun en D48.
```

Nota explícita: **el origen exacto del EPROTO no fue demostrado.**
`ROOT_CAUSE_STATUS=IDENTIFIED` NO se declara: solo se conoce con certeza que
el uploader/step falló con EPROTO/TLS.

Invariante cumplido: D48_STATUS=COMPLETED == EXECUTION_STATUS=COMPLETED.

## D — EXECUTION RESULT

```text
IMPLEMENTATION_PERFORMED: YES (comment-only en el step autorizado; sin
  cambio de ninguna línea ejecutable en esta ejecución)
FILES_MODIFIED: .github/workflows/ci.yml (solo bloque de comentarios del step
  `Upload coverage`);
  journal/2026/2026-10-05-d48-codecov-ci-failure-remediation.md
  (única y última escritura de esta ejecución)
FUNCTIONAL_MUTATIONS: 0 (pin, continue-on-error y fail_ci_if_error
  verificados intactos; ningún `run:` alterado)
DOCUMENTATION_MUTATIONS: 2 (comentario de ci.yml + journal D48)
LOCAL_VALIDATION: PASS
REMOTE_MUTATIONS: 0
WORKFLOW_RERUN: 0
COMMIT: NOT AUTHORIZED
PUSH: NOT AUTHORIZED
TAGS: 0
RELEASES: 0
PR_MUTATIONS: 0
FRAMEWORK_WRITES: 0
FRAMEWORK_JOURNAL_WRITES: 0
```

## E — RELEASE BOUNDARY

```text
D48: COMPLETED (remediación local verificada; efecto en CI solo tras un
  commit/push futuros autorizados por separado — sin rerun remoto en D48)
G3: BLOCKED / NOT AUTHORIZED
G4: BLOCKED / NOT AUTHORIZED
PVR: OUT OF SCOPE / NOT AUTHORIZED
v0.1.2: BLOCKED / NOT AUTHORIZED
Sprint 13: BLOCKED / NOT AUTHORIZED
```

Estos valores describen límites y resultados de otras actividades; D48 no los
ejecuta ni los resuelve.

## F — FINAL STATEMENT

Run afectado: 37252838032 (CI #289, `pull_request`, head
`8e27a7fe1f089ce9e7b24f7768decb6cf72617ed`, base `33ca6dbe...`).
PR afectada: #55 — modifica solo `python-dotenv>=1.0 → >=1.2.4`; NO se le
atribuye el fallo.
Paso que falló: `Upload coverage` en `lint-and-test (3.12, 24)` con
`Error: write EPROTO ... ssl/tls alert handshake failure`.
Gates anteriores: los 12 PASS (Ruff, MyPy×3, Root/Service/Gateway tests,
Frontend setup/tests/audit, Security scan, Dependency audit); `docker-build`
omitido solo por `needs`.

Causa del failure observada: el step terminó en `failure` debido a un error
de transporte TLS/EPROTO reportado durante la operación de red del uploader
(JOB_FAILURE_CAUSE, demostrado).
Origen exacto del EPROTO: NO DEMOSTRADO (ROOT_CAUSE_OF_TRANSPORT_ERROR =
UNDETERMINED/NOT PROVEN) → `ROOT_CAUSE_STATUS=PARTIALLY_IDENTIFIED`.
Factores contribuyentes (etiquetados, no causas demostradas): CF-1 pin de
generación anterior `v3.1.1` (`runs.using: node16`) bajo runtimes Node
heredados informados por el runner (correlación); CF-2 `fail_ci_if_error=false`
solo gobierna la clasificación del resultado del uploader y no cubre fallos
de proceso del step — insuficiencia DEMOSTRADA por el propio run; CF-3
ausencia de barrera `continue-on-error` a nivel de step. Hipótesis no
confirmadas: H-1 excepción TLS no capturada en v3.1.1 fuera de la lógica de
`fail_ci_if_error`; H-2 supresión de recurrencia con v7.0.0; H-3 el warning
de runtime Node como causa raíz.

Remediación realmente aplicada en el repositorio:
`codecov/codecov-action@fb8b3582c8e4def4969c97caa2f19720cb33a72f # v7.0.0`
(SHA completo, verificado contra `refs/tags/v7.0.0^{}` = `fb8b3582...`, tag
object `e53489f4...`; `runs.using: composite`) + `continue-on-error: true`,
con `fail_ci_if_error: false` mantenido → Codecov NON_GATING.
Corrección vs hardening: `continue-on-error: true` es la parte CORRECTIVE
(corrige el defecto demostrado de que una falla de Codecov podía enrojar el
job); el upgrade del pin es PREVENTIVE_HARDENING / compatibility hardening y
NO se presenta como corrección de la causa raíz del EPROTO.
En esta ejecución no se re-aplicó la remediación funcional; la única mutación
fue la corrección de redacción del comentario del step (el comentario previo
afirmaba como hecho la hipótesis H-1 y describía v3.1.1 como "Node 20-era"
frente al `runs.using: node16` verificado).

Validación local: `LOCAL_CONFIGURATION_STATUS=PASS` (YAML, diff confinado,
comandos intactos, NON_GATING, permisos intactos, sin token, estado
preexistente preservado, `FRAMEWORK_WRITES=0`).
Estado remoto: `REMOTE_CI_STATUS=PENDING_VALIDATION`.
Archivos realmente modificados en esta ejecución: `.github/workflows/ci.yml`
(solo comentarios del step) y este journal.
Sin commit, push, tag, release, merge, PR mutation, workflow rerun ni ninguna
otra mutación remota (`REMOTE_MUTATIONS=0`, `WORKFLOW_RERUN=0`).
Framework `company-os` preservado: HEAD `381f56cf...` inalterado,
`FRAMEWORK_WRITES=0`, `FRAMEWORK_JOURNAL_WRITES=0`. `.env`/`.env.*` no abiertos.
