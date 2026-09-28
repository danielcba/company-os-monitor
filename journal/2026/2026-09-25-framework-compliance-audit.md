# 2026-09-25 — Auditoría de conformidad con el Framework (prompt `correccion_01.md`)

## Objetivo

Auditoría exhaustiva de conformidad del Monitor con el Framework Company OS
(P1–P7, R1–R7, conceptos, ADR), corrección mínima de deriva documental real,
validación completa de tests/seguridad/CI y reporte con gate.

## Baseline

- **Monitor HEAD**: `52dbbfac11a9b0410e15003d917b39d648cac025`
- **Monitor origin/main**: `52dbbfac11a9b0410e15003d917b39d648cac025` (HEAD == origin/main)
- **Branch**: `main`
- **Working tree al inicio**: cambios sin commit de `correccion_00.md`
  (4 modificados + 1 entrada de journal untracked) — revisados, conservados,
  no revertidos.
- **Framework HEAD / origin/main**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f`
  (igual en ambas), `git stash list` vacío.
- **Framework modificado por esta tarea**: NO (ver "Framework unchanged").
- **Modificaciones preexistentes del checkout local del Framework** (ya
  existían ANTES, sin tocar): ` M .github/workflows/ci.yml`,
  ` M adr/ADR-0002-cos-monitor-is-the-product.md`, ` M decisions/decisions.md`,
  ` M docs/cognitive-lexicon/ontology.md` + untracked `.github/CODEOWNERS`,
  `.github/dependabot.yml`, `.github/secret-scanning.yml`,
  `FW-PRE-COMMIT-REVIEW-REPORT.md`, `SECURITY.md`.
- **`Project/`**: directorios vacíos (0 archivos, sin trackear ni ignorados) —
  reportado, no eliminado (regla de preexistentes).

## Estado canónico verificado en el Framework (autoridad)

- `docs/cognitive-architecture/cognitive-architecture.md` v2.0 — R1–R7
  canónicas; `### Memory Layer (operational)`.
- `docs/cognitive-principles.md` — P1–P7.
- `docs/cognitive-lexicon/ontology.md` — v1.2 con numeración histórica
  **R1–R10**, distinta de R1–R7 (advertencia de `AGENTS.md` revalidada:
  seguir aplicando).
- `docs/cognitive-lexicon/core-concepts/*.md` — **11 conceptos**, Memory #11
  `Official`.
- `adr/ADR-0003-adopt-monitor-memory-learning-layer.md` — **Accepted**
  (2026-08-30), `Memory Layer status: planned → operational`, supersedes la
  restricción "Memory remains planned" de ADR-0002.
- `state/project-state.md` — "All 11 concepts are Official. Memory is
  operational (ADR-0003)".
- E1–E6 canónicas en `docs/engineering/engineering.md`.

## Hallazgos (clasificación)

### Deriva real corregida (documentación activa)

1. `README_EN.md:71`, `README_ES.md:71` — el Learning loop se presentaba como
   `fase futura` / `future phases of the Learning loop` → capacidades
   implementadas que alimentan el Learning Loop (Decision → Outcome →
   Consolidation, P7).
2. `README_EN.md:360`, `README_ES.md:360` — "the future structured matcher"/
   "futuro" respecto del loop → **Learning loop operativo (P7)**.
3. `README.md:135` — Cognitive Trace UI presentada como `future phase` → UI
   implementada en `apps/web/src/features/cognitive-trace/` (ruta + tests
   desde `ReportDetail`).
4. `adr/ADR-0003-memory-learning-layer-adoption.md` (2 ocurrencias) — path
   inexistente `libs/learning/evaluation.py` → `libs/reasoning/evaluation.py`
   (capacidad real; `libs/learning/evaluation.py` nunca existió).
5. `AGENTS.md:21` — set canónico de citación ampliado con
   **ADR-0003 (Memory & Learning Layer — operacional)**.
6. `AGENTS.md:50-51` — "calibración Confidence y Action Layer en fases
   futuras" → capacidades operativas del producto (Fase 4 completada) y parte
   del pipeline canónico.
7. `state/project-state.md` — 11 Core Concepts (Memory operational,
   ADR-0003); ADR-0001/0002/0003 honored; E1–E6 6/6 (E4 gap closed);
   12 servicios (11 pipeline + user-service) + gateway; 21 migraciones SQL;
   76 env vars en `.env.example` (contado, ver abajo).
8. `cognitive_contract.md` (§ Arquitectura por Capas) — tabla de contratos
   completada para que "All with Cognitive Contracts" sea cierto con los 11
   conceptos: filas añadidas `Reasoning | Insight Restructuring`,
   `Learning | Memory Consolidation`, `Learning | Memory Ledger` (sin borrar
   ninguna fila existente; orden del Learning loop preservado).
9. `.env.example` (seguridad/ops, FASE 8) — `REDIS_PASSWORD` era requerido por
   `docker-compose.yml` (`${REDIS_PASSWORD:?}`) pero **nunca declarado** en la
   plantilla, y las URLs `REDIS_URL`/`OBSERVATION_BUS_URL`/`JWT_REDIS_URL`
   no llevaban clave frente a un Redis con `requirepass`. Declaración de la
   variable con placeholder no usable + URLs con el mismo placeholder. Es
   plantilla de documentación: sin cambio de comportamiento (el arranque
   sigue fallando si falta o está vacía — fail-closed verificado abajo).

### Clasificados como históricos / fuera de alcance (NO editados)

- `ANALYSIS_REPORT.md`, `docs/framework-monitor-sync-audit.md` (snapshot con
  branch/SHA), `SECURITY_REMEDIATION_FINAL_REPORT.md` (2026-09-18, "Sin
  commit"), `COGNITIVE_GATE_AUDIT.md`, `MON-PRE-COMMIT-REVIEW-REPORT.md`,
  `REMEDIATION_PLAN.md`, `pr_body.md`, `docs/remediation/*`,
  `docs/sprint-*-prompt.md`.
- Journals históricos: solo lectura (los archivos modificados en esta tarea
  no incluyen ninguno; la única entrada de journal añadida es esta).
- `docs/frontend/architecture.md` — `planned` de endpoints/nav = AC-03
  aprobada (estado UI, no capacidad cognitiva).
- `adr/ADR-0003…` § OUT OF SCOPE ("future phase") — frontera de alcance
  declarada al adoptar el ADR (2026-08-30), no afirmación de estado actual.
- `docs/01-fundacion-arquitectura.md:51` "calibración Confidence futura" —
  falso positivo semántico (la calibración está operativa y así se documenta
  en su § correspondiente; la frase describe la planificación histórica del
  Sprint 5/6).
- `README.md:174` "future structured matcher" — refiere al matcher de
  evidencias, no a una capacidad del Learning loop.
- `docs/cognitive-gate-closure-preimplementation-plan.md:191`
  ("customers"), `docs/post-h5-next-phase-discovery-report.md:213`
  ("stakeholder pressure") — preguntas de planificación, sin verdad de
  capacidades ni oferta comercial; 0 violaciones de contenido comercial.
- Clasificación de Hypothesis Evaluation como `Reasoning` (Monitor) vs
  "Learning sub-capability" (Framework §Evaluation) — **ambigüedad interna
  del Framework**, no contradicción verificable: no se cambió nada.

### Hallazgos de seguridad/CI

- **`.github/dependabot.yml:42-47` — MEDIUM — CORREGIDO**: clave de nivel
  superior `secret-scanning:` fuera del schema de Dependabot (GitHub doc:
  claves de nivel superior solo `version`, `updates`, `registries`). Un archivo
  inválido hace que GitHub rechace toda la config de Dependabot (updates y PRs
  automáticos de dependencias). Corrección: bloque eliminado; los patrones
  `github_token`/`private_key` son patrones por defecto de Secret Scanning, y
  `jwt_secret` no tiene mecanismo de archivo soportado. Dejado comentario que
  documenta dónde vive la config de secret-scan.
- **`.github/secret-scanning.yml` — MEDIUM — CORREGIDO**: nombre incorrecto.
  GitHub solo lee `.github/secret_scanning.yml` (underscore) con `paths-ignore`;
  el archivo con guion era inerte. Corrección: `git mv` al nombre correcto,
  contenido intacto (schema `paths-ignore` verificado contra la documentación
  oficial).
- `libs/access/security.py:439` — `verify_aud=False` **condicional** (solo
  cuando no hay `JWT_AUDIENCE` configurado), no bypass permanente.
- `tests/security/test_d01_failclosed.py` — posible vacuidad de pruebas
  `try/except` (spot-check) — reportado.
- `JWT_SECRET_KEY=REPLACE-WITH-A-UNIQUE-SECRET-KEY` en `.env.example` —
  placeholder de plantilla explícito; el código exige no-vacío y no fija
  default. Riesgo de despliegue si se copia literalmente — reportado, sin
  cambio de código.
- Positivos verificados: CI con actions SHA-pinned + `persist-credentials:
  false` + `permissions: contents: read`, sin `continue-on-error`/auto-commit;
  tenant isolation y Cognitive Boundary con evidencia PASS; `start.sh` y
  compose fail-closed; sin secretos reales en código ni plantillas.

### Hallazgos Docker / migraciones (FASE 10)

- **`infrastructure/db-migrations/h4-001-schema.sql` — HIGH — CORREGIDO**:
  cinco `ADD CONSTRAINT` sin guardar (líneas 40, 124, 131, 177, 223).
  PostgreSQL no admite `ADD CONSTRAINT IF NOT EXISTS`, así que la **segunda**
  corrida de migraciones aborta con `relation "uq_agent_installations_tenant_id"
  already exists`; `start.sh:266` ejecuta
  `apply_migrations || die "DB migrations failed"` → **la plataforma no puede
  reiniciarse**, contradiciendo el propio mensaje "applying DB migrations
  (idempotent)". Reproducido en una BD PostgreSQL 16 limpia (base
  `init-sql` + 21 migraciones): primera corrida OK, segunda corría y fallaba
  exactamente ahí. Corrección: los cinco `ADD CONSTRAINT` envueltos en bloques
  `DO $$ … $$` con verificación en `pg_constraint` (mismo patrón que ya usa
  `h3-learning-execution.sql`); definiciones idénticas, sin cambio semántico.
- **`tests/architecture/test_h4_phase_a_schema.py` — MEDIUM — REPORTADO +
  regresión añadida**: el docstring declara que verifica "migration
  idempotency" pero no existe ninguna prueba de idempotencia (grep: solo la
  línea del docstring); por eso la suite no detectó el defecto. Se añadió
  `tests/architecture/test_migrations_idempotency.py` (estático, sin BD):
  falla si cualquier migración vuelve a contener un `ADD CONSTRAINT` sin
  bloque `DO` guardado. Verificado en negativo: el SQL antiguo dispara el
  test, el corregido pasa.
- Verificación FASE 10 sobre BD limpia PostgreSQL 16 (contenedor temporal,
  `infrastructure/docker/init-sql` montado, aislado del `docker-postgres-1`
  preexistente que NO se tocó):
  - base `init-sql`: 12 tablas; schema tras migraciones: 28 tablas con las 17
    tablas canónicas (Observation…Report, Insight, `learning_memory`,
    `hypothesis_evaluations`, `users`, `agent_installations`,
    `machine_jwt_blacklist`); 19 triggers de inmutabilidad (P1).
  - migraciones: **pase 1 = 21/21 OK; pase 2 = 21/21 OK; pase 3 = 21/21 OK**
    (idempotencia comprobada tras la corrección).
  - `tenants.plan`: **ausente** (0 columnas).
  - Redis: password incorrecta → `AUTH failed: WRONGPASS`; correcta → `PONG`
    (también con la forma exacta del healthcheck de compose).
  - PostgreSQL (TCP): password incorrecta → `InvalidPasswordError`; correcta →
    `SELECT 1` OK.
  - `docker compose config`: `rc=1` fail-closed sin `REDIS_PASSWORD`;
    `rc=0` con credenciales.
  - build de imágenes: `docker compose build frontend` → **OK**
    (`docker-frontend:latest` construida; artefacto eliminado tras la
    verificación).

## Archivos modificados en esta tarea (correccion_01)

`.env.example`, `AGENTS.md`, `README.md`, `README_EN.md`, `README_ES.md`,
`adr/ADR-0003-memory-learning-layer-adoption.md`, `cognitive_contract.md`,
`state/project-state.md`, `.github/dependabot.yml`,
`.github/secret-scanning.yml` → `.github/secret_scanning.yml` (rename),
`infrastructure/db-migrations/h4-001-schema.sql` (idempotencia),
`tests/architecture/test_migrations_idempotency.py` (nuevo, regresión)
(+ la entrada de journal de este archivo).
Además se conservan los cambios de `correccion_00.md`:
`libs/memory/insight_transformation.py` (docstring) y
`tests/architecture/test_adr_0003_framework_sync.py` (AC-07).

Total del working tree: 12 modificados + 1 renombrado + 3 archivos nuevos
(2 entradas de journal + 1 test) sin trackear.

## NO modificados

- Framework (`company-os-main`): 0 cambios propios.
- Journals históricos: 0 cambios.
- Nada fuera de `docs`, `README*.md`, `AGENTS.md`, `state/`, `cognitive_contract.md`,
  `adr/`, `.env.example`, `.github/dependabot.yml` + rename
  `.github/secret_scanning.yml`, `libs/` docstring y `tests/architecture/`.
- Ningún cambio de lógica cognitiva, esquema, API, seguridad de runtime,
  CI/CD ni frontend (los dos cambios de `.github/` son de configuración de
  gobernanza: hacen válido/aplicable un archivo que GitHub ignoraba).

## Validaciones ejecutadas (resultado final exacto)

| Comando | Resultado |
|---|---|
| `pytest tests/` (raíz) | **747 passed** (48.81s) |
| `pytest tests/security tests/architecture` (post-edits) | **300 + 2 nuevas = 302 passed** |
| Suites por servicio (12) | anomaly 56, collector 39, confidence 41, context 33, decision 53, evaluation 49, hypothesis 22, insight 3, pattern 43, recommendation 36, report 32, user 55 → **462 passed** |
| `pytest apps/gateway/api-gateway/tests` | **150 passed, 1 skipped** |
| Migraciones PostgreSQL 16 (BD limpia) | **pase 1/2/3 = 21/21 OK cada uno** |
| `ruff check .` | **All checks passed** |
| `mypy --config-file mypy.ini libs/` | **no issues (70 source files)** |
| `bandit -r apps/ libs/ -ll -c bandit.yaml` | **High: 0, Medium: 0** |
| `python -m compileall apps libs` | **rc=0** |
| `git diff --check` | **OK** (sin whitespace errors) |
| YAML schema `.github/dependabot.yml` / `.github/secret_scanning.yml` | **OK** (solo `version`+`updates`; `paths-ignore`) |
| Frontend `npm run lint` (oxlint) | **0 errors** (4 warnings preexistentes) |
| Frontend `npm run typecheck` (tsc -b --noEmit) | **OK** |
| Frontend `npm run test` (vitest) | **29 files / 182 tests passed** |
| Frontend `npm run build` | **OK** |
| `docker compose … config` sin `REDIS_PASSWORD` | **rc=1** (fail-closed: `REDIS_PASSWORD is required`) |
| `docker compose … config` con credenciales | **rc=0** (config válido) |

## Framework unchanged

`git status --short` del Framework idéntico al baseline: mismas 4
modificaciones + 5 untracked preexistentes, ninguna nueva; HEAD
`381f56c` == `origin/main`; `git stash list` vacío. Journal del Framework:
sin cambios.

## Commit

**NOT PERFORMED** (sin `AUTHORIZE_COMMIT=YES`).

## Push

**NOT PERFORMED** (sin `AUTHORIZE_PUSH=YES`).
