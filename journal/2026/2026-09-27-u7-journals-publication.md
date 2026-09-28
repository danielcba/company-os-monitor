# 2026-09-27 — U7 publicación de journals c00–c03 (prompt `correccion_28.md`)

## Objetivo

Publicar los 4 journals históricos c00–c03 (sesiones `correccion_00`–`correccion_03`)
que quedaron sin trackear desde esas rondas. Alcance exclusivo: los 4 journals
+ este journal U7. Sin cambios de código, seguridad, configuración ni Framework.

## Baseline (verificado con `git fetch --prune` antes de editar)

- **Monitor**: branch `main`; HEAD = origin/main = ls-remote =
  `079024e8cad6a06b712b607106b756bea88fdebb` (U6b `docs: close U6b documentation drift`,
  CI run `36356219504` completed/success); ahead 0 / behind 0; **4 `??` + 0 `M` + 0 staged**.
- **Framework** (`company-os-main`): HEAD = origin/main =
  `381f56cfa48d092f85846e160d2e1fe6878f9f6f`; índice 0; 9 entradas preexistentes
  (4 M + 5 ??) — idéntico al final. **Framework modificado: NO.**
- U6a (`7ca822d`) e U6b (`079024e`) intactos en la historia; sin amend/rebase/reset.

## Descubrimiento (rutas reales, no inventadas)

Los 4 `??` = el set U7 completo (ningún otro `??` ni `M`):

| id | archivo | líneas |
|---|---|---|
| c00 | `journal/2026/2026-09-24-memory-doc-drift-alignment.md` | 112 |
| c01 | `journal/2026/2026-09-25-framework-compliance-audit.md` | 243 |
| c02 | `journal/2026/2026-09-26-correccion-02-framework-compliance-audit.md` | 137 |
| c03 | `journal/2026/2026-09-26-release-hardening-correccion-03.md` | 156 |

Ninguno es duplicado; ninguno corresponde a U4/U6a/U6b (esos tienen sus propios
journals ya trackeados). **Cero modificaciones locales preexistentes** en los 4
(no hay ` M` sobre ellos) → nada que separar antes del commit.

## Verificación por journal (leídos completos)

- **c00** (`correccion_00`): FACT — baselines reales (`52dbbfa…` existe y es
  ancestro de HEAD); claims verificados contra el repo actual: docstring
  `libs/memory/insight_transformation.py:250` ("persistence lives in the Memory
  Ledger, ADR-0003"), `files_to_check` AC-07 con `insight_transformation.py`
  (test línea 169), frase ADR-0003 en `README.md`. Commit/push: NOT PERFORMED
  (HISTORICAL RECORD — la sesión no estaba autorizada).
- **c01** (`correccion_01`): FACT — rename `.github/secret_scanning.yml` y
  `tests/architecture/test_migrations_idempotency.py` presentes en HEAD ✓;
  112–243 líneas de hallazgos con validaciones numéricas históricas
  (747 passed, etc.). Sin SHA futuros (solo `52dbbfa`/`381f56c`).
- **c02** (`correccion_02`): FACT — `Project/` confirmado ausente (claim de
  eliminación ✓); mismos SHAs históricos; "Commit/NOT PERFORMED" coherente con
  su autorización `AUTHORIZE_COMMIT=NO`.
- **c03** (`correccion_03`): FACT/HISTORICAL — dependabot 19 entradas
  (17 pip + npm + github-actions) verificado por parseo YAML actual ✓;
  `ci.yml` sin `safety` (solo el comentario NOTE que explica su remoción) ✓.
  **OBSERVATION**: la FASE 12 registra `required_signatures=deshabilitado` y
  contexts `["CI"]` del 2026-09-26; la API actual muestra
  `required_signatures=true` y contexts
  `["lint-and-test (3.12, 24)","docker-build"]` — los controles externos
  evolucionaron después de capturado el journal. Es HISTORICAL RECORD: **no se
  reescribe** (reescritura retroactiva = fabricación de evidencia, prohibida).

## Checks de contenido (los 4 journals)

- Secretos/credenciales: **0** (grep de tokens/pem/AKIA).
- SHAs: solo `52dbbfac11a9b0410e15003d917b39d648cac025` (baseline histórico de
  esas sesiones, verificado en la historia) y `381f56c…` (Framework) — **0 SHA
  futuros inventados**.
- Skips/xfails declarados: **0**.
- Contenido comercial: **0** (menciones de "contenido comercial" = auditorías
  reportando su ausencia; `tenants.plan: ausente` = verificación de esquema).
- Referencias/paths internos: 13 paths clave spot-checkeados → todos existen.
- Markdown: estructura H2 consistente en los 4.

## NO tocado

- Journals históricos ya trackeados (incl. `2026-09-26-correccion-04-closure-audit.md`),
  journals U4/U6a/U6b, Framework (0 escrituras), código, `.github`, README,
  state, ADR, configuraciones externas, GitHub settings. Sprint 13 no iniciado.

## Validaciones pre-commit

| Gate | Resultado |
|---|---|
| `git diff --check` | rc=0 |
| `pytest tests/` (raíz, incl. architecture) | **766 passed** |
| `pytest tests/security tests/architecture` | **321 passed** |
| `ruff check .` | rc=0 |
| `mypy --config-file mypy.ini libs/` | Success (70 files) |
| `bandit -r apps/ libs/ -ll -c bandit.yaml` | rc=0 |
| `python3 -m compileall apps libs` | rc=0 |
| Validador markdown propio | No existe en el repo (justificado: gate = `git diff --check` + suite raíz; ningún test escanea `journal/`) |

Justificación de alcance de validación: el commit añade exclusivamente 5
archivos `.md` bajo `journal/`; ningún archivo ejecutable se altera. Fallo
ambiental conocido de `recommendation-service` (DB compartida sandbox):
preexistente, no ejecutado aquí, no reinterpretado como PASS.

## Commit / Push / CI

- Contenido del commit U7 (mostrado antes de `git add`): los 4 journals c00–c03
  + este journal — **5 paths**, mensaje `docs: publish U7 journals c00-c03`.
- **Este journal forma parte del commit cuyo contenido describe**: por tanto no
  inventa su propio SHA ni resultados de CI futuros (regla "no inventar SHA").
  El SHA del commit, la verificación remota y el run de CI se registran en el
  reporte final obligatorio `# U7 JOURNALS c00-c03 — FINAL REPORT` emitido
  tras la operación, sobre la evidencia observada.
- Autorización: `AUTHORIZE_COMMIT=YES`, `AUTHORIZE_PUSH=YES` (prompt 28).
