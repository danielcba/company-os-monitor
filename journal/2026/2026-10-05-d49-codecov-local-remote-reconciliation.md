# D49 — CODECOV LOCAL/REMOTE STATE RECONCILIATION

Append-only entry. Ningún journal existente fue modificado.
Identificador tomado de la secuencia real del repositorio (máximo previo: `d48`).

```text
COMMIT: NOT AUTHORIZED
PUSH: NOT AUTHORIZED
```

---

## EVIDENCE

### REMOTE (read-only únicamente)

```text
workflow_run = 37252838032  (WORKFLOW=CI, RUN_NUMBER=289, EVENT=pull_request)
failing_job  = lint-and-test (3.12, 24)
failing_step = Upload coverage
remote_error = Error: write EPROTO ... ssl3_read_bytes:ssl/tls alert handshake failure
remote_codecov_version = v3.1.1
  (codecov/codecov-action@ab904c41d6ece82784817410c45d8b8c02684457)
remote_tests = PASS (Python, services, gateway, frontend)
remote_scans = PASS (npm audit, bandit, pip-audit)
coverage.xml generated = PASS
docker-build = skipped (needs lint-and-test)
PR #55 = OPEN (verificado read-only esta ejecución)
  title   = chore(deps): update python-dotenv requirement from >=1.0 to >=1.2.4
  head    = 8e27a7fe1f089ce9e7b24f7768decb6cf72617ed
            (refs/pull/55/head y refs/heads/dependabot/pip/main/python-dotenv-gte-1.2.4
             coinciden en 8e27a7fe... vía git ls-remote)
  base    = main @ 33ca6dbeb865e5e420631054ce302ba85c5090d2
remote main = 33ca6dbeb865e5e420631054ce302ba85c5090d2 (== origin/main, ls-remote)
remote main ci.yml (blob 24a769b4b6bbad830f43bcfaa2390d68e0743116):
  línea 193: uses: codecov/codecov-action@ab904c41... # v3.1.1
  contiene fb8b3582... = 0 ocurrencias
  contiene ab904c41... = 1 ocurrencia
  → REMOTE_CONFIGURATION_CONTAINS_FIX: NO
  → REMOTE_CI_VALIDATED_AFTER_FIX: NO
  → REMOTE_RUN_AFTER_FIX: NO
  → el run 37252838032 permanece histórico con conclusión `failure`.
Limitación honesta de verificación: `gh api` / `gh pr view` / `gh run view`
  agotaron timeout en este entorno (exit 124, 0 bytes); la evidencia remota
  anterior procede de `git ls-remote` (read-only), de `git show origin/main:…`
  con SHA verificado contra ls-remote, y de la lectura read-only de la página
  del PR #55. No se obtuvo la ejecución en vivo de la API de GitHub Actions.
```

### LOCAL

```text
pwd       = /home/dcordoba/Documents/Default Project/company-os-monitor
BRANCH    = main (sin cambio de rama)
HEAD      = 3eaced8c35868ed91cbce81a5c4bd21537aacfec
            (3eaced8 ci: activate G1 dependency audits and restrict G2
             secret-scanning paths)
origin/main = 33ca6dbeb865e5e420631054ce302ba85c5090d2 (== ls-remote)
LOCAL_DIVERGENCE = local main 3 commits DETRÁS de origin/main, 0 adelante;
  único archivo distinto HEAD↔origin/main: pyproject.toml (fuera de alcance,
  NO tocado). Blob de ci.yml idéntico en HEAD y en origin/main (24a769b...).
STAGED: índice vacío (git diff --cached vacío en toda la ejecución)
WORKTREE preexistente (4 modified + 55 untracked):
  M .github/workflows/ci.yml   ← remediación funcional YA PRESENTE al entrar
  M docs/release-policy.md     ← fuera de alcance, preservado byte-for-byte
  M start.sh                   ← fuera de alcance, preservado byte-for-byte
  M stop.sh                    ← fuera de alcance, preservado byte-for-byte
  ?? 54 journals preexistentes (D2..D48) + este journal D49
sha256 verificados antes/después (idénticos):
  docs/release-policy.md  2ed1114f65bcd778e436bb635dcf0982d10cada806272d8dc7cc13a2ceabfabb
  start.sh                f09451163eb9016421f58e7a558033a77d1e7eb8108d1f77bc6d1bc34a5934b5
  stop.sh                 8be30918497bd5b07c3fb9608d098dc589090884b2b52709fddbcbf03f177170
.env / .env.*: NO abiertos, NO modificados, NO reportados
Framework company-os: HEAD 381f56cfa48d092f85846e160d2e1fe6878f9f6f inalterado
```

---

## ROOT CAUSE

Se mantiene SIN CAMBIOS la conclusión de D48 (no se reabre, no se refuerza):

```text
JOB_FAILURE_CAUSE:
  `Upload coverage` terminó en `failure` debido a un error de transporte
  TLS/EPROTO reportado durante la operación de red del uploader; el job
  `lint-and-test` concluyó `failure` y `docker-build` cayó por `needs`.

ROOT_CAUSE_OF_TRANSPORT_ERROR:
  UNDETERMINED / NOT PROVEN
  → El origen exacto del EPROTO no fue demostrado.

CONTRIBUTING_FACTOR (no causalidad demostrada):
  CF-1 pin de generación anterior v3.1.1 (runs.using: node16) en runner con
       runtimes Node heredados forzados — correlación observada.
  CF-2 fail_ci_if_error=false solo gobierna la clasificación del resultado
       del uploader y no cubre fallos de proceso del step — insuficiencia
       DEMOSTRADA por el propio run.
  CF-3 ausencia de barrera continue-on-error a nivel de step.

UNCONFIRMED_HYPOTHESIS:
  H-1 excepción TLS no capturada dentro del bundle JS de v3.1.1.
  H-2 supresión de la recurrencia del EPROTO tras el upgrade del pin.
  H-3 el warning de runtime Node como causa raíz del EPROTO.
```

No se convierten en causa raíz demostrada: warning de runtime Node,
Codecov v3.1.1, incompatibilidad hipotética, excepción TLS no observada.
La única corrección **demostrada** de propagación es `continue-on-error: true`.
La actualización del action se conserva como **hardening preventivo**, no
como prueba de la causa raíz del EPROTO.

---

## DECISION

```text
FUNCTIONAL_REMEDIATION_ALREADY_PRESENT: YES
FUNCTIONAL_REMEDIATION_PRESENT_AT_BASELINE: YES
FUNCTIONAL_REMEDIATION_APPLIED_IN_EXECUTION: NO
FUNCTIONAL_MUTATION_BY_D49: 0
DOCUMENTATION_UPDATE: YES
No re-aplicar la remediación funcional de Codecov.
No modificar la configuración funcional de `.github/workflows/ci.yml`.
```

---

## CHANGE

```text
PREEXISTING_FUNCTIONAL_STATE (ya presente antes de D48, verificado):
  uses: codecov/codecov-action@fb8b3582c8e4def4969c97caa2f19720cb33a72f # v7.0.0
  continue-on-error: true
  with:
    files: ./coverage.xml
    fail_ci_if_error: false
  ab904c41d6ece82784817410c45d8b8c02684457 AUSENTE del worktree

D48_EXECUTION_MUTATION:
  comments only en el step `Upload coverage`
  journal D48
  (sin modificación ejecutable de la configuración Codecov)

D49_EXECUTION_MUTATION:
  0 cambios funcionales
  1 escritura documental: este journal (nuevo archivo, append-only,
  ningún journal existente modificado)

CORRECCIÓN DOCUMENTAL QUE ESTA ENTRADA APORTA (supersede explícito):
  El journal D48 declara `IMPLEMENTATION_PERFORMED: YES`. Esa etiqueta debe
  leerse exclusivamente como "comment-only + journal" y NO como si D48
  hubiera implementado la remediación funcional. Queda corregida por
  sustitución semántica con los campos canónicos:
    FUNCTIONAL_REMEDIATION_PRESENT_AT_BASELINE: YES
    FUNCTIONAL_REMEDIATION_APPLIED_IN_EXECUTION: NO
    DOCUMENTATION_UPDATE: YES
  (El contenido previo del D48 no fue alterado: corrección append-only.)

EQUIVALENCIA DE REFERENCIA VERIFICADA (git ls-remote, read-only):
  refs/tags/v6^{}     = fb8b3582c8e4def4969c97caa2f19720cb33a72f
  refs/tags/v7.0.0^{} = fb8b3582c8e4def4969c97caa2f19720cb33a72f
  → el mismo commit es destino de `v6` y de `v7.0.0`; el comentario `# v7.0.0`
    en el worktree es factualmente correcto y satisface también la referencia
    `@v6` solicitada, sin necesidad de mutar la línea.
  refs/tags/v7^{} = 303a32d7a59b442fa8d48b6a1cc6825c09c847a5 (distinto; no usado)
```

---

## VALIDATION (LOCAL)

```text
git diff --check                              = exit 0 (PASS)
actionlint                                    = NO DISPONIBLE en el entorno
fallback PyYAML parser real (python3 yaml)    = "YAML syntax: OK" exit 0
inspección estructural GitHub Actions         = OK
  name=CI · jobs=[lint-and-test, docker-build]
  Upload coverage dentro de lint-and-test     = OK
  matrix node = ["24"]
  workflow permissions = {contents: read}
  docker-build permissions = {contents: read}
assertions estructurales (complementarias)    = OK
  fb8b3582... presente
  files: ./coverage.xml presente
  fail_ci_if_error: false presente
  continue-on-error: true presente
  ab904c41... AUSENTE
ruff check .                                  = exit 0 ("All checks passed!")
  (aviso preexistente de deprecación de settings top-level en
   apps/services/evaluation-service/pyproject.toml — no introducido aquí)
coverage.xml NO regenerado (bytes preexistentes preservados)
grep de otros workflows                       = solo existe .github/workflows/ci.yml;
                                                ninguna otra invocación de Codecov
diff confinado al step `Upload coverage`      = único hunk @@ -193 +193,12 @@
                                                (solo `uses:` y `continue-on-error:`
                                                son ejecutables)
LOCAL_CONFIGURATION_STATUS = PASS
```

---

## REMOTE ACTIONS

```text
REMOTE WRITE OPERATIONS: 0
COMMIT: NOT PERFORMED  (COMMIT: NOT AUTHORIZED)
PUSH: NOT PERFORMED    (PUSH: NOT AUTHORIZED)
MERGE: NOT PERFORMED
RERUN: NOT PERFORMED
PR MUTATION: NOT PERFORMED
RELEASE/TAG: NOT PERFORMED
BRANCH CHANGE: NOT PERFORMED
FRAMEWORK WRITES: 0
FRAMEWORK JOURNAL WRITES: 0

REMOTE READ OPERATIONS (esta ejecución):
  git ls-remote origin  ×1 (main, rama actual, refs/pull/55/*, rama dependabot)
  git ls-remote codecov/codecov-action ×1 (v6, v6.0.1, v7, v7.0.0 anotados)
  gh api / gh pr view / gh run view ×4 intentos → timeout (sin datos)
  lectura read-only de la página del PR #55 ×1
  git show origin/main:.github/workflows/ci.yml ×1 (SHA ya verificado vs ls-remote)
```

La existencia del cambio local NO implica que el remoto esté actualizado.
No se afirma que GitHub refleje el fix: no hubo push.

---

## AUTHORIZATION STATE

```text
LOCAL MODIFICATION OF ci.yml : authorized for a minimal fix (not required this run)
JOURNAL WRITE                : authorized, append-only, single write
COMMIT                       : NOT AUTHORIZED
PUSH                         : NOT AUTHORIZED
MERGE / PR MUTATION / RERUN  : NOT AUTHORIZED
TAG / RELEASE                : NOT AUTHORIZED
FETCH / PULL / REBASE / RESET / CLEAN / CHECKOUT : NOT PERFORMED
SECRETS / TOKENS / OIDC / PERMISSION CHANGES     : NOT PERFORMED
PYTHON-DOTENV / PYPROJECT / TESTS / OTHER WORKFLOWS / FRAMEWORK : NOT MODIFIED
Las autorizaciones NO son transitivas entre ámbitos LOCAL y REMOTO.
```
