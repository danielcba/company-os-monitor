# 2026-09-26 — Cierre de hallazgos F1/F2/F3/F8/F9 (prompt `correccion_04.md`)

## Objetivo

Cerrar los hallazgos pendientes de la auditoría de release de
`company-os-monitor` sin introducir capacidades funcionales y sin tocar el
Framework: bloqueadores externos de GitHub (F1/F2/F3), contrato `compliance`
(F8) y rutas huérfanas de secret scanning (F9), más auditoría de seguridad,
integridad documental, calidad, migraciones/Docker y contenido comercial.

## Baseline verificado (FASE 0)

- **Monitor HEAD**: `52dbbfac11a9b0410e15003d917b39d648cac025` == `origin/main`
  (branch `main`); sin movimiento durante toda la tarea.
- **Working tree de partida**: 35 modificados + 1 rename staged
  (`.github/secret-scanning.yml -> .github/secret_scanning.yml`) + 6 untracked
  (4 journals de correcciones previas, `tests/architecture/test_migrations_idempotency.py`,
  `tests/security/test_jwt_audience_verification.py`) — preexistentes,
  preservados.
- **Framework HEAD / origin/main**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f`;
  working tree con los mismos 4 modificados + 5 untracked del baseline
  (intocado, verificado igual al cierre).
- **`gh`**: autenticado como `danielcba` (scopes `gist, read:org, repo, workflow`).
- **Autorización**: `AUTHORIZE_COMMIT=NO`, `AUTHORIZE_PUSH=NO`.

## Framework (FASE 1)

Releído como única autoridad: P1–P7 con sus títulos canónicos
(`docs/cognitive-lexicon/cognitive-principles.md`), R1–R7 canónicos
(`docs/cognitive-architecture/cognitive-architecture.md` L448–454, sin usar la
numeración R1–R10 de `ontology.md`), ADR-0001/0002/0003 presentes,
**Memory Layer (operational)** declarado en la arquitectura (§ "Memory Layer
(operational)"), sin shortcut Perception → Action (§ "The Cognitive Boundary").
No hay `.github/AGENTS.md` ni `AGENTS.md` en el Framework (N/A).

## Hallazgos tratados y cambios realizados

### F8 — contrato `compliance` (CORREGIDO, mínimo y coherente)

Contrato real verificado: report-service renderiza **executive / technical /
json** (`service.RENDERABLE_TYPES`) y responde `400 unsupported report type`
para todo lo demás (`health.generate_handler`, con test de regresión previo).

| Archivo | Cambio |
|---|---|
| `libs/action/report.py` | `REPORT_TYPE_COMPLIANCE` eliminado; `REPORT_TYPES` = {executive, technical, json}; comentario explica que `compliance` no tiene renderer y no forma parte del contrato |
| `apps/gateway/api-gateway/src/reports.py` | `REPORT_TYPES` → `("executive", "technical", "json")` + comentario de espejo con `RENDERABLE_TYPES` |
| `apps/web/src/types/cognitive.ts` | `CognitiveReportType` sin `'compliance'` + comentario |
| `apps/web/src/features/reports/ReportsPage.tsx` | rama de badge `Compliance` eliminada; fallback renderiza el valor crudo (sin mal-etiquetar) |
| `docs/04-informes-seguridad.md` | nota factual de estado: Compliance/Operational Dashboard = formatos de diseño sin renderer |
| `apps/services/report-service/tests/test_report_store.py` | +2 tests: coherencia de contrato y aceptación de los 3 tipos soportados |
| `apps/gateway/api-gateway/tests/test_gateway_http.py` | +1 test: vocabulario de lectura del gateway == tipos soportados |

Sin semántica inventada, sin cambio de comportamiento del handler, sin tocar
autorización ni el pipeline cognitivo. La tabla `reports` está vacía en el
scratch de pruebas (0 filas): no existen filas legítimas de `compliance`.

### F9 — `secret_scanning.yml` (CORREGIDO)

`decisions/**` y `rfc/**` **no existen** en Monitor ni son referenciadas por
ninguna política: eran residuo de la copia de la configuración del Framework
(donde esos directorios sí existen). Eliminadas las 2 entradas; resto de
`paths-ignore` intacto (no ampliado); YAML validado. Secret scanning sigue
cubiendo código, infraestructura, workflows y tests.

### F1/F2/F3 — GitHub (CERRADOS VÍA API, con verificación antes/después)

Estado **antes** registrado (`/tmp/opencode/gh04/protection_before.json`,
`repo_before.json`). Solo se usaron endpoints oficiales; sin commits locales.

| ID | Endpoint oficial | Resultado verificado |
|---|---|---|
| F1 | `POST /repos/.../branches/main/protection/required_signatures` | `required_signatures.enabled: false → true`; resto de la protección idéntico (diff campo a campo) |
| F2 | `PATCH .../protection/required_status_checks` | contexts `["CI"] → ["lint-and-test (3.12, 24)", "docker-build"]` (check-runs reales de la rama, app_id 15368 = github-actions); `strict:true` conservado; reviews, force-push, deletions, enforce_admins y demás sin cambios |
| F3 | `PUT /repos/.../vulnerability-alerts` | Dependabot alerts **enabled** (GET rc=0; API de alertas responde `0` en vez de 403) + dependency graph **enabled** (SBOM `SPDX-2.3`) |
| F3 | `PUT /repos/.../automated-security-fixes` | Dependabot security updates `{"enabled":true,"paused":false}`; `security_and_analysis.dependabot_security_updates = enabled` |
| F3+ | `PATCH /repos/...` (`secret_scanning_validity_checks`, `secret_scanning_non_provider_patterns` a `enabled`) | API devuelve 200 pero el estado permanece `disabled` tras relectura → **no aceptado por GitHub para este repositorio** (sub-feature opcional, fuera de F1/F2/F3) |

`.github/dependabot.yml` revalidado: YAML OK, 19 entradas, 17/17
`pyproject.toml` cubiertos, sin duplicados ni claves inválidas.
`GET /repos/.../codeowners/errors` → `{"errors": []}`.

## FASE 4 — configuración de seguridad (sin regresiones)

- Workflows: 5 `uses:` con pinning SHA; `permissions: contents: read`
  (global y por job); `persist-credentials: false` en ambos checkout.
- Sin secretos hardcodeados (búsqueda de patrones → solo placeholder sintético
  en un plan histórico); sin passwords/keys en código no sintéticos.
- JWT fail-closed intacto (`_reject_placeholder` para `REPLACE-WITH`/`CHANGE-ME`,
  audience/issuer cableados, kid/rotación sin cambios).
- Compose `${VAR:?}` fail-closed verificado en entorno limpio: **rc=1** sin
  credenciales / **rc=0** con `.env`.
- `start.sh` aborta con placeholders; `.env.example` solo marcadores.
- `SECURITY.md`, `CODEOWNERS`, `dependabot.yml`, `secret_scanning.yml` revisados.

## FASE 5 — integridad documental y archivos

- Drift "future/planned/sprint 13+" en código/docs activos: **0 hallazgos**.
- Referencias a `company-os-monitor-prompt.md`: solo en el journal que registra
  su eliminación (histórico, no reintroducción).
- Paths `docs/*.md` inexistentes: los que aparecen (`docs/cognitive-architecture/*`,
  `docs/cognitive-lexicon/*`) son **citaciones canónicas del Framework**
  sancionadas por la política de `AGENTS.md` → falso positivo, sin cambio.
- **ADR-0003**: la sección *Context* decía en presente que el Framework define
  Memory como "planned" mientras la arquitectura declara `Memory Layer
  (operational)` → añadida una nota factual de fecha (Context = estado al
  2026-08-30; hoy operacional). Texto histórico no reescrito.
- Archivos: `docs/frontend/frontend-architecture.md` (113 líneas, "Official")
  solapa temáticamente con `docs/frontend/architecture.md` (519 líneas, 23
  referencias) y solo se le cita desde un journal → **conservado** (evidencia no
  inequívoca de obsolescencia; borrarlo rompería una citación histórica).
  `scripts/qa_seed.py` activo (referenciado por README/contract).
  `coverage.xml`, `logs/`, `reports/` → artefactos ignorados. Nada eliminado
  en esta tarea.

## FASE 6/7 — verificaciones ejecutadas

| Gate | Resultado |
|---|---|
| `pytest tests/` (root) | **766 passed** |
| `pytest tests/security tests/architecture` | **321 passed** |
| 12 suites de servicios | **464 passed** (56/39/41/33/53/49/22/3/43/36/34/55) |
| api-gateway | **151 passed, 1 skipped** (+1 test F8) |
| frontend lint / typecheck | **0 errores, 4 warnings** / **0** |
| frontend test / build | **182 passed** (29 archivos) / **OK** |
| `ruff check .` | **All checks passed** (1 error B023 detectado y corregido en el test nuevo) |
| `mypy` libs (70) / gateway (22) / 12 services | **0 issues** |
| `bandit -r apps/ libs/ -ll` | **exit 0** (High 0, Medium 0) |
| `compileall` / `git diff --check` | **OK / OK** |
| Migraciones (scratch PostgreSQL 16) | schema + seed OK; **3×21/21 migraciones OK**; `tables=28`, `constraints=99`, `triggers=19`, `indexes=97`; **0 duplicados**; scratch eliminado; `docker-postgres-1` intacto |
| `docker build` evaluation-service | **rc=0** (imagen eliminada) |
| `docker compose build` / `config` | **rc=0 / rc=1 sin credenciales, rc=0 con `.env`** (imagen `docker-frontend` eliminada) |
| Smoke de imports gateway / report-service | OK (`REPORT_TYPES == RENDERABLE_TYPES`) |

Nota factual: en la **primera** pasada de suites de servicios hubo **1 fallo
transitorio** en `anomaly-service`; no se reprodujo en la pasada aislada (56
passed) ni en la segunda pasada completa (todas en verde). Ningún test fue
deshabilitado, `xfail`-eado ni debilitado.

## FASE 8 — reauditoría comercial

Búsqueda amplia (EN/ES: pricing, price, plans, SaaS, ARR, MRR, churn, revenue,
business model, tiers, customers, cost estimates, competitors, monetization,
precios, planes, facturación, modelo de negocio…): **0 contenidos comerciales
no autorizados**. Únicos "hits": `consider_competitor` de Context Revision
(señal técnica sobre modelos/explicaciones competitivas, P2) — falso positivo.

## FASE 9 — este journal

Entrada nueva append-only; ninguna entrada histórica modificada; journal del
Framework no tocado.

## Bloqueadores externos

- **Ninguno en F1/F2/F3/F8/F9**: los cuatro están verificados cerrados.
- Observaciones (no bloqueantes, no solicitadas): `enforce_admins:false`
  (admins pueden hacer push directo sin cumplir los status checks),
  `require_code_owner_reviews:false`, y las dos sub-features de secret
  scanning que GitHub no aceptó habilitar (FASE 3+).
- Si el matrix de CI cambia (p. ej. `python-version`/`node-version`), el
  required check `lint-and-test (3.12, 24)` debe actualizarse en GitHub
  Settings para no quedar desalineado.

## Estado de tests / estado final

Todas las verificaciones exigidas PASS. Gate: **`READY TO CONTINUE`**.

## Autorización de commit/push

`AUTHORIZE_COMMIT=NO` y `AUTHORIZE_PUSH=NO` → **sin commit y sin push**.
HEAD de Monitor intacto (`52dbbfa`); staging solo con el rename preexistente
`.github/secret_scanning.yml`. Sin `--amend`, sin force-push, sin reescritura
de historia. No se inventó ningún SHA ni se afirma "deployed"/"released".

## Framework modified: NO

## Framework journal modified: NO
