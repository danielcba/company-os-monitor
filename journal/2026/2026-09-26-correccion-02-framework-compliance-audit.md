# 2026-09-26 — Auditoría de conformidad, seguridad y governance (prompt `correccion_02.md`)

## Objetivo

Auditoría senior de conformidad con el Framework Company OS (P1–P7, R1–R7,
conceptos, ADR), seguridad (JWT/audience/placeholders, adversarial suite),
migraciones, governance de GitHub, estructura de tests, DIF review y reporte
final con gate. Aplica `correccion_02.md`; `correccion_00.md` y
`correccion_01.md` ya están cerrados.

## Baseline

- **Monitor HEAD**: `52dbbfac11a9b0410e15003d917b39d648cac025`
- **Monitor origin/main**: `52dbbfac11a9b0410e15003d917b39d648cac025` (HEAD == origin/main), branch `main`.
- **Working tree al inicio**: cambios sin commit de `correccion_00/01`
  (12 modificados + 1 rename staged + 3 untracked) — revisados, conservados.
- **Framework HEAD / origin/main**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f`.
- **Framework modificado por esta tarea**: NO.
- **Framework preexistente sucio** (intocado, verificado al cierre idéntico al
  baseline): ` M .github/workflows/ci.yml`, ` M adr/ADR-0002-cos-monitor-is-the-product.md`,
  ` M decisions/decisions.md`, ` M docs/cognitive-lexicon/ontology.md` +
  untracked `.github/CODEOWNERS`, `.github/dependabot.yml`,
  `.github/secret-scanning.yml`, `FW-PRE-COMMIT-REVIEW-REPORT.md`, `SECURITY.md`.
- **Autorización**: `AUTHORIZE_COMMIT=NO`, `AUTHORIZE_PUSH=NO` → todo queda en
  el working tree, **sin commit y sin push**.
- **`Project/`** (0 archivos, sin trackear): eliminado con `rmdir -p` según
  FASE 13 de `correccion_02.md`. Corrige la nota de 2026-09-25
  ("reportado, no eliminado"): la instrucción de esta ronda autoriza
  explícitamente el borrado.

## Estado canónico revalidado (Framework = autoridad)

- `docs/cognitive-principles.md` — P1–P7 con sus títulos canónicos exactos
  (P1 "The Primacy of Observation", P5 "Calibrated Confidence", P3
  "Stable Concepts, Transformative Intelligence").
- `docs/cognitive-architecture/cognitive-architecture.md` — R1–R7 canónicas.
- Learning Loop = ciclo continuo con sub-capacidades (Consolidation, Pattern
  Refinement, Context Revision, Insight Transformation, Memory Ledger);
  Memory Layer operational (ADR-0003); 11 conceptos Official; E1–E6.
- Advertencia de `AGENTS.md` revalidada: no usar la numeración R1–R10 de
  `ontology.md`.

## Hallazgos y correcciones

1. **FASE 2 — drift "future phase"** (docs, cero cambio de comportamiento):
   8 correcciones de comentarios/docstrings en `libs/action/decision.py` (4),
   `apps/services/decision-service/src/committer/committer.py` (2),
   `.../main.py`, `.../service.py`, `.../tests/test_decision_store.py`.
   Se conservaron por precisar (verificados contra código):
   `libs/action/report.py:44`, `libs/reasoning/evaluation_policy.py:18`,
   `formulator.py:397`, `hypothesis.py:75`.
2. **FASE 3A — placeholders JWT fail-closed**: `libs/access/security.py`
   (`_reject_placeholder`, marcadores `REPLACE-WITH`/`CHANGE-ME`/`...`),
   `.env.example` comentado, `start.sh` aborta si el `.env` trae plantilla,
   `libs/access/middleware.py` docstring sin secreto literal. El `.env` local
   (gitignored) traía `JWT_SECRET_KEY=REPLACE-WITH-A-UNIQUE-SECRET-KEY` →
   regenerado (`openssl rand -hex 32`). 7 tests nuevos.
3. **FASE 3B — try/except vacíos reales**: `test_wrong_audience_rejected` y
   `test_wrong_issuer_rejected` ahora exigen `InvalidTokenError` con
   `match="audience"/"issuer"`; verificado por mutación que el patrón anterior
   pasaba de forma vacua.
4. **FASE 4 — audience**: `apps/services/report-service/src/main.py` no pasaba
   `issuer`/`audience` a `JwtService` → rechazaba tokens gateway válidos
   ("Invalid audience"); cableado. 8 tests nuevos en
   `tests/security/test_jwt_audience_verification.py`. Decisión: **no** se
   añade `aud` a los machine tokens (ADR-0005 §2 documenta el claim set sin
   `aud`; cambiarlo exigiría enmienda de ADR); la rama `verify_aud=False`
   demostrada es condicional a configuración, no permanente.
5. **FASE 5/7/8 — Contracts/principios**: `cognitive_contract.md` completado
   (§Principios Clave = P1–P7 + R1–R7 con títulos canónicos; tabla de
   capacidades con Insight Restructuring, Memory Consolidation, Memory Ledger;
   §9.6 Memory operacional por ADR-0003). Trazabilidad de tests por principio
   verificada.
6. **FASE 9 — migraciones**: 3 pasadas completas en scratch `postgres:16`
   (base `01-schema.sql` + 21 migrations, orden glob, `ON_ERROR_STOP=1`):
   ok=21 fail=0 en las 3 pasadas; constraints 99 → 99 estables; 28 tablas;
   19 triggers no internos; los 5 `ADD CONSTRAINT` de `h4-001-schema.sql`
   persisten. Scratch eliminado; `docker-postgres-1` preexistente intacto.
7. **FASE 10/11 — governance y CI (solo reporte, sin modificar)**:
   `CODEOWNERS` con 3 rutas huérfanas (`/docs/cognitive-architecture/`,
   `/docs/cognitive-lexicon/`, `/decisions/`); `dependabot.yml` **HEAD inválido**
   (`secret-scanning:` como clave) — corregido solo en el working tree, GitHub
   lo rechazará hasta que se haga commit; rename `secret_scanning.yml` staged;
   CI: 5 `uses:` todos SHA-pinned, `permissions: contents: read`,
   `persist-credentials: false`; sin `continue-on-error`. A reportar:
   `cosmonitor` hardcodeado en CI, `fail_ci_if_error: false`, `safety`
   instalado sin ejecutarse, dependabot no cubre los 17 `pyproject` anidados.
   Los controles de GitHub (secret scanning/dependabot activos) **no son
   verificables desde el checkout** → file configured, GitHub control NOT VERIFIED.
8. **FASE 12/13 — contenido y directorios**: 0 violaciones de contenido
   comercial; `company-os-monitor-prompt.md` ausente; `Project/` eliminado
   (ver Baseline).
9. **Nuevo en esta sesión — `start.sh` perdía la credencial Redis**: las URLs
   del `.env.example` pasaron a ser `redis://<password>@host` (Redis corre con
   `--requirepass`), pero la normalización `redis://redis:* → redis://localhost:6379`
   del host-side solo matcheaba URLs sin credencial → con plantilla real los
   servicios host no podrían autenticar. Corregido: solo se reescribe el host
   (`s#^(redis://)([^@]*@)?redis:#\1\2localhost:#`), preservando credencial y
   sufijo de db. 4 tests nuevos que **ejecutan** el bloque extraído de
   `start.sh` (`tests/security/test_d01_failclosed.py`). Además el `.env`
   local quedó alineado con `.env.example`: `REDIS_PASSWORD` generado y
   embebido en `REDIS_URL`/`OBSERVATION_BUS_URL`, `JWT_REDIS_URL` añadido.

## Pruebas

| Nivel | Resultado |
|---|---|
| Root `pytest tests/` | **766 passed** |
| `tests/security` (incl. 15 adversariales) | **128 passed** (adversariales: 96) |
| `tests/architecture` | incluidos en root; invariants P1/P7 OK |
| 12 suites de servicios | **462 passed** |
| `api-gateway` | **150 passed, 1 skipped** |
| Frontend `npm run lint` | 0 errors, 4 warnings |
| Frontend `npm run typecheck` | OK |
| Frontend `npm run test` | **182 passed** (29 archivos) |
| Frontend `npm run build` | OK |
| `ruff check .` | All checks passed |
| `mypy --config-file mypy.ini libs/` | Success, 70 files |
| `bandit -r apps/ libs/ -ll -c bandit.yaml` | exit 0 (High 0, Medium 0) |
| `compileall apps libs` | OK |
| `git diff --check` | OK |
| Migraciones (3 pasadas) | 21/21 ×3, constraints estables |
| `docker compose config` sin credenciales | rc=1 (fail-closed: `REDIS_PASSWORD`/`POSTGRES_PASSWORD` requeridas) |
| `docker compose config` con credenciales | rc=0 (frontend, postgres, redis) |
| `docker build -f .../evaluation-service/Dockerfile` | rc=0 (2m34s) |
| `docker compose build` | rc=0; artefactos de build eliminados |
| Contenido comercial / directorios | 0 violaciones; prompt ausente; `Project/` eliminado |

## Resultado

Todas las fases cerradas con evidencia; sin cambios de comportamiento no
justificados; Framework intacto. Estado final del working tree: **sin commit,
sin push**.

## Framework modified: NO

## Framework journal modified: NO
