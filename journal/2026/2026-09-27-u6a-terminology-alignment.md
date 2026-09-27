# 2026-09-27 — U6a Terminología de código (prompt `correccion_23.md`)

## Objetivo

Preparar la unidad **U6a — Terminología de código / alineación semántica del
código vigente** (identificada en `correccion_08`): eliminar del código vigente
las referencias obsoletas tipo `future sprint` / `future phase` / `planned` que
contradicen el estado operacional real adoptado, exclusivamente en
comentarios, docstrings y copy de estado — cero cambio funcional, cero cambio
de seguridad. U6b (deriva documental) y U7 (journals c00–c03) quedan fuera.

## Baseline

- **Monitor HEAD / origin/main / ls-remote**: `099dbbb29b14da161178b502dc4e588379bc254e`
  (`chore: harden dependabot and repository governance` = U5, publicada con CI
  run `36349259900` completed/success — `lint-and-test (3.12, 24)` success,
  `docker-build` success).
- **divergence**: ahead = 0, behind = 0. **working tree**: 25 M + 4 ?? = 29
  entradas; índice real = 0 staged. Sin drift antes de actuar.
- **Framework**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` == origin/main,
  0 staged, 9 entradas, journal intacto.

## Paths evaluados (17 — la auditoría decía "16" pero listaba 7+1+7+2 = 17)

Servicios (7): `apps/services/confidence-service/src/service.py`,
`apps/services/decision-service/src/committer/committer.py`,
`apps/services/decision-service/src/main.py`,
`apps/services/decision-service/src/service.py`,
`apps/services/decision-service/tests/test_decision_store.py`,
`apps/services/recommendation-service/src/formulator/formulator.py`,
`apps/services/recommendation-service/tests/test_recommendation_model.py`.
Gateway (1): `apps/gateway/api-gateway/src/reports.py`.
Libs (7): `libs/action/decision.py`, `libs/action/recommendation.py`,
`libs/action/report.py`, `libs/cognitive_core/cognitive_tool.py`,
`libs/memory/insight_transformation.py`,
`libs/procedural_memory/decision_policy.py`,
`libs/reasoning/evaluation_policy.py`.
Frontend (2): `apps/web/src/features/reports/ReportDetail.tsx`,
`apps/web/src/features/reports/ReportsPage.tsx`.

## Atribución hunk por hunk

Cada hunk del diff worktree vs HEAD es comentario/docstring/copy. Evidencia en
los journals pendientes de U7 (ya redactados, aún sin publicar):

1. `confidence-service/src/service.py` (1 hunk, comentario) — c03 FASE 2.
2. `decision-service/.../committer/committer.py` (5 hunks) — c02 FASE 2 (2) +
   c03 FASE 2 (3). Sustituye "future phases — Sprints 11/12" por referencias
   reales: `libs/action/executor.py`, `libs/learning/learning_loop.py`.
3. `decision-service/src/main.py` (1), `.../service.py` (1),
   `.../tests/test_decision_store.py` (1, solo comentario — el `UPDATE` y el
   assert intactos) — c02 FASE 2.
4. `recommendation-service/.../formulator.py` (1, docstring) — c03 FASE 2
   (c02 lo conservó; c03 lo corrigió). En esta sesión se corrigió un artefacto
   de espaciado introducido por esa corrección (`score.     Per-alternative`
   → `score. Per-alternative`), sin cambio de semántica.
5. `recommendation-service/tests/test_recommendation_model.py` (1, comentario
   tras el assert — el assert `is None` intacto) — c03 FASE 2.
6. `gateway/api-gateway/src/reports.py` (1, docstring residual de U6a) —
   c03 FASE 2. No arrastra hunks de U1/U3: esos ya están commiteados; el diff
   worktree contiene solo este hunk.
7. `libs/action/decision.py` (4 hunks) — c02 FASE 2 (×4).
8. `libs/action/recommendation.py` (1), `libs/action/report.py` (2),
   `libs/cognitive_core/cognitive_tool.py` (1),
   `libs/procedural_memory/decision_policy.py` (1),
   `libs/reasoning/evaluation_policy.py` (1) — c03 FASE 2.
9. `libs/memory/insight_transformation.py` (1) — journal
   `2026-09-24-memory-doc-drift-alignment.md` §3, texto verbatim:
   "(Memory persistence remains planned per the framework)" →
   "(Memory persistence lives in the Memory Ledger, ADR-0003)".
10. Frontend `ReportsPage.tsx` (1, copy JSX) — c03 FASE 2.
11. Frontend `ReportDetail.tsx` (1, copy JSX) — ver investigación abajo.

Ningún archivo contiene hunks de otra unidad sin commitear: el diff completo
de los 17 paths (349 líneas) es 100% terminológico. Los hunks de U1/U3/U4/U5
ya están en commits publicados; no hay mezcla que separar.

## Investigación — `ReportDetail.tsx` (resuelta, incluido)

La auditoría lo marcó "SIN-REF en journals"; la investigación lo desmiente:

1. **Journal `2026-09-26-release-hardening-correccion-03.md` (c03), FASE 2**,
   lista explícitamente
   `apps/web/src/features/reports/{ReportDetail,ReportsPage}.tsx` entre las
   correcciones de drift "future/sprint" de solo comentarios/copy.
2. **Diff completo = 1 hunk, 3 líneas de copy JSX** dentro del div explicativo:
   "LM Studio arrives in a future sprint" → "report rendering never calls a
   model" — mismo tratamiento textual que `ReportsPage.tsx` y el docstring de
   `libs/action/report.py`.
3. **Sin cambio de comportamiento**: no toca props, estado, routing,
   `useNavigate`, tipos, componentes ni seguridad; solo texto visible.
4. `git log --follow`: los últimos commits del archivo son la UI de Cognitive
   Trace (Fase 2B) y la remediación; el cambio actual no proviene de ellos.

**Decisión: incluido en U6a.**

## Terminología — barridos y decisiones

- Barrido sobre `future|planned|sprint|phase|later|not yet|coming|will be|
  deferred`: **0 hits en las líneas añadidas** del diff U6a.
- Residuales en los 17 archivos, clasificados y **conservados** (casos 2/3):
  referencias históricas "Sprint 8/10/11" (origen del concepto), docstrings de
  tests "Gate para Sprint 11", y enunciados "MVP" que siguen siendo factualmente
  exactos (matcher determinístico, ejecución externa) — tal como decidieron
  c02/c03 ("conservados por ser históricos/válidos"). No se reescribe historia.
- Solo se modificó el caso 1 (documentación que describía el estado actual de
  forma obsoleta: "future sprint/phase", "planned", "Sprint 12 reemplaza",
  "LM Studio arrives in a future sprint").
- Afirmaciones nuevas verificadas contra el código: `libs/action/executor.py`,
  `libs/learning/learning_loop.py`, `libs/learning/learning_execution_store.py`
  existen; `LMStudioHypothesisTool` existe y tiene tests en hypothesis-service;
  ningún runtime de servicio lo importa hoy; tabla `insights` existe
  (`init-sql/01-schema.sql:279`) y el servicio de Insight existe.

## Tests (resultados reales, 2026-09-27)

- root `pytest tests/` → **766 passed**
- `tests/security tests/architecture` → **321 passed**
- confidence-service → **41 passed**; decision-service → **53 passed**;
  gateway → **151 passed, 1 skipped**
- recommendation-service → **35 passed, 1 failed** —
  `test_service_without_hypotheses_is_clean` (`errors == 0` vs `10`). **Fallo
  preexistente y ambiental, NO causado por U6a**: reproduce idénticamente en un
  clone limpio de `099dbbb` sin cambios; raíz: el test asume 0 tenants en la DB
  compartida del sandbox y hoy hay 10 — cada `_formulate_tenant` lanza sobre
  los stubs `SimpleNamespace` y el contador sube. No pertenece a U6a; no se
  toca el sandbox (`docker-postgres-1` intacto).
- frontend `npm run lint` → 0 errores (4 warnings preexistentes);
  `typecheck` rc=0; `vitest run` → **182 passed (29 files)**; `build` → OK.
- `ruff check .` → All checks passed (rc=0); `mypy --config-file mypy.ini
  libs/` → Success, 0 issues en 70 archivos (rc=0); `bandit -r apps/ libs/ -ll
  -c bandit.yaml` → rc=0; `python3 -m compileall apps libs` → rc=0;
  `git diff --check` → rc=0.

## Verificaciones

- **Funcionalidad intacta**: las líneas cambiadas son exclusivamente
  comentarios, docstrings y copy JSX de estado; ningún import, ruta, control
  flow, tipo, payload, schema ni aserción alterados (verificado con
  `git diff -U0`).
- **Seguridad**: el diff U6a no toca `libs/access/*`, JWT, issuer/audience,
  `AuthorizationContext`, tenant scope, Redis, `.env`, `start.sh` ni
  migraciones (0 paths).
- **Higiene**: 0 secretos/tokens/credenciales, 0 `curl|bash`, 0 permisos
  `write`, 0 `continue-on-error`/`if: always()` nuevos, 0 skip/xfail/assertions
  debilitados, 0 TODO/FIXME/print(/console.log.
- **Contenido comercial**: 0 hits (pricing/ARR/MRR/churn/precios/…).
- **Framework**: intacto (`381f56c…`, 0 staged, 9 entradas, journal 0
  escrituras).
- **Journals**: históricos sin modificar; los 4 journals ?? de U7 intactos;
  `2026-09-26-correccion-04-closure-audit.md` intacto; journal del Framework
  intacto.

## Estado de autorización

- **commit**: NO creado (`AUTHORIZE_COMMIT=NO`); solo commit candidate en
  índice temporal (`GIT_INDEX_FILE`) que contiene los 17 paths U6a + este
  journal; índice real permanece vacío.
- **push**: NO realizado (`AUTHORIZE_PUSH=NO`).
- Sin SHA futuros: este documento no afirma publicación de nada.

## Siguientes unidades (pendientes, no ejecutadas)

- **U6b** — deriva documental: `AGENTS.md`, `README.md`, `README_EN.md`,
  `README_ES.md`, `cognitive_contract.md`, `ADR-0003`,
  `state/project-state.md`, `tests/architecture/test_adr_0003_framework_sync.py`.
- **U7** — publicación de los journals c00–c03 (4 entradas `??`).
