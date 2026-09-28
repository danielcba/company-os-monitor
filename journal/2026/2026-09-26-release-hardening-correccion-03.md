# 2026-09-26 — Release hardening / production readiness (prompt `correccion_03.md`)

## Objetivo

Auditoría de production readiness de 13 fases aplicando `correccion_03.md`
(`correccion_00/01/02` ya cerrados): baseline, validación normativa,
documentación/drift, contenido comercial, security hardening, GitHub
governance, CI/CD security, database/migrations, dead files, matriz de tests,
revisión de diff, journal, verificación externa de GitHub y criterio de cierre.

## Baseline (FASE 0, capturado al inicio)

- **Monitor HEAD**: `52dbbfac11a9b0410e15003d917b39d648cac025` == `origin/main`,
  branch `main` (sin commits nuevos durante toda la tarea).
- **Framework HEAD / origin/main**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f`.
- **Working tree al inicio**: 22 modificados + 1 rename staged
  (`.github/secret-scanning.yml -> .github/secret_scanning.yml`) + 5 untracked
  (3 journals de correcciones previas, `tests/architecture/test_migrations_idempotency.py`,
  `tests/security/test_jwt_audience_verification.py`) — preexistentes, conservados.
- **Framework sucio preexistente** (intocado, idéntico al cierre): ` M .github/workflows/ci.yml`,
  ` M adr/ADR-0002-cos-monitor-is-the-product.md`, ` M decisions/decisions.md`,
  ` M docs/cognitive-lexicon/ontology.md` + untracked `.github/CODEOWNERS`,
  `.github/dependabot.yml`, `.github/secret-scanning.yml`,
  `FW-PRE-COMMIT-REVIEW-REPORT.md`, `SECURITY.md`.
- **`gh` autenticado** como `danielcba` → FASE 12 verificable por API.
- **Autorización**: `AUTHORIZE_COMMIT=NO`, `AUTHORIZE_PUSH=NO`.

## Estado canónico revalidado (Framework = autoridad)

P1–P7 con sus títulos canónicos, R1–R7 de `cognitive-architecture.md`
(explicitando que NO se usa la numeración R1–R10 de `ontology.md`), pipeline
canónico, Memory operacional (ADR-0003), Learning Loop, Cognitive Boundary y
contracts (14 capacidades, 1:1). Nada inventado (sin P8+/R8+/capacidades nuevas).

## Hallazgos y correcciones de esta ronda

1. **FASE 2 — drift "future/sprint" residual** (solo comentarios/docstrings/copy,
   cero cambio de comportamiento): 14 correcciones en
   `libs/action/recommendation.py`, `libs/action/report.py` (×3),
   `libs/cognitive_core/cognitive_tool.py`, `libs/procedural_memory/decision_policy.py`,
   `libs/reasoning/evaluation_policy.py`, `apps/gateway/api-gateway/src/reports.py`,
   `apps/services/confidence-service/src/service.py`,
   `apps/services/decision-service/src/committer/committer.py` (×3),
   `apps/services/recommendation-service/src/formulator/formulator.py`,
   `apps/services/recommendation-service/tests/test_recommendation_model.py`,
   `apps/web/src/features/reports/{ReportDetail,ReportsPage}.tsx`,
   `README_EN.md`/`README_ES.md` (×3 líneas cada uno).
   Conservados por ser históricos/válidos: headings de sprint en `README_*:398`,
   roadmap `docs/05-negocio-roadmap-backlog.md:51`, referencia histórica
   `libs/access/security.py:13`, `ADR-0005`, `ADR-0003 §OUT OF SCOPE`,
   docstrings de tests, `docs/remediation/*`, `docs/sprint-*-prompt.md`, journals.
2. **Finding (Low, sin cambio) — vocabulario `compliance`**:
   `libs/action/report.py` y `apps/gateway/api-gateway/src/reports.py:30`
   declaran el type `compliance`, pero report-service solo renderiza
   executive/technical/json y lo rechaza con 400
   (`test_generate_handler_rejects_unsupported_type`); `REPORT_TYPES` del
   gateway es constante sin uso; el frontend lo declara. Es vocabulario
   declarado con generación rechazada explícitamente → decisión de producto,
   se reporta y no se cambia.
3. **FASE 5 — `CODEOWNERS`**: eliminadas las 3 rutas huérfanas que solo existen
   en el Framework (`/docs/cognitive-architecture/`, `/docs/cognitive-lexicon/`,
   `/decisions/`). Verificado que todas las rutas restantes existen en Monitor.
4. **FASE 5 — `dependabot.yml`**: reescrito con 19 entradas (17 `pip`: root +
   gateway + 12 services + 3 agents; `npm` `/apps/web`; `github-actions` `/`),
   validado por YAML: 17/17 `pyproject.toml` cubiertos, 0 huérfanos, 0 sin
   cubrir. Eliminada la clave inválida `secret-scanning:` (no pertenece al
   schema de dependabot) dejando constancia de que las exclusiones viven en
   `.github/secret_scanning.yml`.
5. **FASE 5 — secret scanning**: `.github/secret_scanning.yml` es un mecanismo
   soportado por GitHub (`paths-ignore`) y el control está activo según la API
   (`enabled` + push protection `enabled`) → el archivo se conserva sin cambios
   (preserva además el rename staged preexistente). Entradas `decisions/` y
   `rfc/` en `paths-ignore` apuntan a rutas inexistentes en Monitor → reportadas
   como entradas muertas, sin cambiar.
6. **FASE 6 — `safety` en CI**: instalado pero nunca ejecutado; `safety check`
   deprecado desde 01 Jun 2024 (exit 0 sin escanear) y `safety scan` exige
   cuenta autenticada → **removido de `ci.yml`** como configuración muerta,
   con comentario; `bandit` es el gate de seguridad realmente ejecutado.
7. **FASE 6 — codecov**: `fail_ci_if_error: false` documentado en `ci.yml` como
   "informational only, NOT a release gate" (una caída de Codecov no debe
   enrojecer un test run verde).
8. **FASE 7 — migraciones idempotentes**: scratch PostgreSQL 16 efímero
   (puerto 5441) → schema base + **3 pases** de las 21 migraciones
   (`ok=21 fail=0` en los tres), `tables=28`, `constraints=99`,
   `triggers=19`, sin duplicados de constraints ni triggers; scratch eliminado;
   `docker-postgres-1` intacto (`Up (healthy)`).
9. **FASE 8 — dead files** (solo reporte, sin borrados): `SECURITY_REMEDIATION_FINAL_REPORT.md`,
   `pr_body.md`, `docs/c4-observability-contract.md`, `docs/h6-pre-commit-acceptance-report.md`,
   `docs/h7-closure-report.md`, `docs/sprint-*-prompt.md` → tracked,
   referenciados o históricos → **conservar**. `coverage.xml`, `logs/`,
   `reports/` → artefactos locales ya ignorados por `.gitignore`.
   `company-os-monitor-prompt.md` permanece eliminado ✓.

## Validaciones ejecutadas (FASE 9, árbol final)

| Suite / gate | Resultado |
|---|---|
| `pytest tests/` (root) | **766 passed** |
| `pytest tests/security tests/architecture` | **321 passed** |
| 12 suites de servicios | **462 passed** (56/39/41/33/53/49/22/3/43/36/32/55) |
| `tests` del api-gateway | **150 passed, 1 skipped** |
| frontend `lint` | **0 errores, 4 warnings** |
| frontend `typecheck` | **0** |
| frontend `test` | **182 passed** (29 archivos) |
| frontend `build` | **OK** |
| `ruff check .` | **All checks passed** |
| `mypy` libs (70) / gateway (22) / 12 services (76) | **Success, 0 issues** |
| `bandit -r apps/ libs/ -ll -c bandit.yaml` | **exit 0** (High 0, Medium 0, Low 1758 informativo) |
| `python -m compileall apps libs` | **OK** |
| `git diff --check` | **OK** (sin whitespace errors) |
| `docker build` evaluation-service | **rc=0** |
| `docker compose build` (sin credenciales en el entorno) | **rc=0**, artefactos de imagen eliminados |
| `docker compose config` | **rc=1** sin credenciales / **rc=0** con `.env` / **rc=0** con credenciales CI → fail-closed |

## FASE 12 — verificación externa (`gh` API)

| Control | Estado | Evidencia |
|---|---|---|
| `required_signatures` | **deshabilitado** → EXTERNAL BLOCKER | branch protection `main` |
| status checks | `strict:true`, contexts `["CI"]` → **ningún check se llama `CI`** (reales: `lint-and-test (3.12, 24)`, `docker-build`) → control no efectivo | check-runs de PR #18 |
| required reviews | 1 aprobación; `require_code_owner_reviews:false`; `dismiss_stale_reviews:false` | API |
| `enforce_admins` | `false` (admins pueden hacer push directo sin checks) | API |
| force-push / deletion | **restringidos** (`false`/`false`) | API |
| secret scanning | **enabled** + push protection **enabled**; alertas = 0 | API |
| secret scanning `validity_checks` | `disabled` (observación) | API |
| Dependabot | config local válida (19 entradas); **security updates `disabled`** y **alerts `disabled` (HTTP 403)** en el repo | API |
| code scanning | sin análisis (404 "no analysis") → observación | API |
| secrets del repo | **ninguno** (`gh secret list` vacío) | CLI |

## Bloqueadores externos (no resolubles desde el repo)

1. `required_signatures` deshabilitado en `main` (firmas requeridas de commit).
2. Required status check `"CI"` no corresponde a ningún nombre de check real
   (hay que alinear el contexto con los jobs reales en GitHub Settings, o
   añadir un job agregador llamado `CI`; no se fingió resolución por YAML).
3. Dependabot security updates + Dependabot alerts deshabilitados en el repo.
4. `enforce_admins:false` / `require_code_owner_reviews:false` (debilitan la
   protección existente) y `secret_scanning_validity_checks:disabled`.

## Commit / push

No se creó ningún commit ni push (`AUTHORIZE_COMMIT=NO`, `AUTHORIZE_PUSH=NO`).
HEAD de Monitor sin movimiento (`52dbbfa`); staging solo contiene el rename
preexistente `.github/secret_scanning.yml`. Sin `--amend`, sin force-push.
No se eliminó `Project/` ni ningún archivo del que no hubiera evidencia; los
scratch de Docker creados para esta tarea fueron eliminados.

## Resultado

**PASS WITH EXTERNAL BLOCKER** — código y configuración locales correctos y
verificados; los únicos puntos abiertos son controles externos de GitHub
señalados arriba. No se afirma "deployed"/"released"/"production ready".

## Framework modified: NO

## Framework journal modified: NO
