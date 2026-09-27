# 2026-09-27 — U6b Documentation drift (prompt `correccion_26.md`)

## Objetivo

Cerrar la unidad **U6b — Documentation drift** del Release Hardening:
corregir contradicciones entre la documentación operativa vigente del Monitor
(`AGENTS*`, `README*`, `cognitive_contract*`, `ADR-0003*`, `state*`,
`tests/.../test_adr_0003*`), el código real y el Framework congelado. Sin
cambios funcionales, sin tocar U6a/U7/Framework.

## Baseline inicial

- **Monitor HEAD / origin/main / ls-remote**:
  `7ca822d7e1eab4c14b9d0c0bc0e1455054ab3b07`
  (`docs: align operational terminology in current code` = U6a, publicada con
  CI run `36352701597` completed/success).
- **divergence**: ahead = 0, behind = 0. **working tree**: 8 M + 4 ?? = 12;
  índice = 0 staged. Sin drift.
- **Framework**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f` == origin/main,
  0 staged, 9 entradas, journal intacto.

## Alcance

8 paths preexistentes ya modificados (candidato U6b heredado de las rondas
c00/c01) + este journal: `AGENTS.md`, `README.md`, `README_EN.md`,
`README_ES.md`, `cognitive_contract.md`,
`adr/ADR-0003-memory-learning-layer-adoption.md`, `state/project-state.md`,
`tests/architecture/test_adr_0003_framework_sync.py`.

## Auditoría — validación del candidato heredado

Cada edit heredado fue verificado contra la realidad (sin fiarse del journal):

- AGENTS: ADR-0003 existe en el Framework (`adr/ADR-0003-adopt-monitor-memory-learning-layer.md`)
  → set canónico ampliado correcto.
- README cognitive-trace: `apps/web/src/features/cognitive-trace/` existe,
  ruta `/action/reports/:reportId/trace` registrada en
  `apps/web/src/routes/index.tsx`, tests presentes.
- README/README_EN/README_ES: Action Layer, Learning Loop, RBAC en gateway,
  `insight-service`/`pattern-service`, "report rendering never calls a model"
  — todos verificados contra código.
- ADR-0003: `libs/learning/evaluation.py` **nunca existió en git**;
  `libs/reasoning/evaluation.py` existe → corrección de path correcta (2 ocurrencias).
- cognitive_contract: títulos P1–P7 y R5–R7 **idénticos** a
  `cognitive-principles.md` y `cognitive-architecture.md` del Framework; filas
  nuevas (Insight Restructuring, Memory Consolidation, Memory Ledger)
  verificadas (`insight-service`, `libs/memory/consolidation.py` con
  Brier/ECE, tabla `learning_memory`).
- state: 11 core concepts ✓, 12 servicios (11 pipeline + user) ✓, 21
  migraciones ✓, 76 env vars ✓, E4 = `state/` (engineering.md E4) ✓, PR #14 =
  Learning Loop ✓.
- test_adr_0003: `+libs/memory/insight_transformation.py` en `files_to_check`
  (guard AC-007 anti-regresión) — coherente con el journal de drift de memoria.

## Drift REAL encontrado y corregido en esta ejecución

1. `AGENTS.md` — "(Fase 4 completada)" era incorrecto/ambiguo: por los docs
   propios del Monitor, **FASE 4 = Reasoning Layer**
   (`docs/03-predictivo-ia-local.md`) y **FASE 6 = Action Layer**
   (`docs/04-informes-seguridad.md:13`). Eliminado el paréntesis de fase; la
   oración conserva solo el hecho verificable (capacidades operativas).
2. `state/project-state.md:3` — "Post-PR #16 Stabilization (H1 + H2 + Docs)":
   la estabilización H1+H2+Docs **es el PR #17** (`gh pr list` → #17 "fix:
   stabilization H1 + H2 + documentation drift"; `docs/post-h5-…:81` →
   "H1-H2 … COMPLETE | PR #17"). Corregido a **Post-PR #17**.
3. `state/project-state.md` § Operations (Phase 3 — Completed) — 4 bullets
   presentados como completados y **verificados como no implementados**:
   - "Cloud-native report storage (S3/GCS abstraction)" — `libs/shared/storage.py`
     **nunca existió en ningún commit** (`git log --all -- <path>` vacío;
     `git cat-file` en `0be8241` = no existe); report-service escribe en
     `REPORT_OUTPUT_DIR` local; sin `StorageBackend`/S3/GCS en el código.
   - "Hot-reload procedural memory" — `libs/shared/config_watcher.py`
     **nunca existió**; sin código de watcher/reload en el repo.
   - "DB latency in health checks" — `verify_connection()` sin timing;
     sin campos de latencia en `health.py`.
   - "OpenAPI spec generation" — sin rastro en código/CI (solo menciones en
     journals/planes).
   Decisión: **eliminados de "Completed" y movidos a "Known Gaps (Planned)"**
   (nada se oculta; la sección queda solo con lo verificado: refactor de
   `service.py` en módulos — creados en `0be8241`, ej.
   `src/anomalies.py`/`decisions.py`/`contexts.py` — y CI/CD GitHub Actions).
4. `state/project-state.md` — "asyncio.gather in 7 services" → **9 servicios**
   (conteo real distinto: anomaly, confidence, context, decision, evaluation,
   hypothesis, insight, pattern, recommendation).

## Archivos NO tocados (y motivos)

- `README.md`/`README_EN.md`/`README_ES.md`, `cognitive_contract.md`,
  `ADR-0003*`: edits heredados verificados correctos; sin drift residual
  (barrido `future/planned/fase futura` = 0 hits de caso 1; "future evidence",
  `future_risks`, headings de sprint y roadmap = históricos/técnicos).
- `ADR-0003` § OUT OF SCOPE ("future phase" ×5): frontera de alcance
  declarada al adoptar el ADR (2026-08-30), no estado actual — conservado.
- `AGENTS.md` § Remediación (195/198, "19 fases"): registro histórico de esa
  ronda — conservado.
- `journal/2026/2026-08-23-remediation.md` y `REMEDIATION_PLAN.md`: afirman
  "Created `libs/shared/storage.py`/`config_watcher.py`/`routes/`" que nunca
  existieron en git. **Journals históricos = solo lectura** (regla del
  prompt): no se modifican; la contradicción se documenta aquí y se corrige
  en `state/`, que es el documento de estado vigente (E4/E5).
- Journals U7 (4 `??`), journal U4, journals del Framework: intactos.

## Validaciones (resultados reales)

- `pytest tests/` → **766 passed**
- `pytest tests/security tests/architecture` → **321 passed**
  (incluye `test_adr_0003_framework_sync.py` con el guard añadido)
- `ruff check .` → rc=0 · `mypy --config-file mypy.ini libs/` → Success, 70
  archivos · `bandit -r apps/ libs/ -ll -c bandit.yaml` → rc=0 ·
  `python3 -m compileall apps libs` → rc=0 · `git diff --check` → rc=0
- Suites de servicios/gateway/frontend no ejecutadas: U6b no introduce ni
  altera código ejecutable (solo `.md` + 1 línea de lista en un test de
  arquitectura ya cubierto por la raíz).
- Fallo ambiental preexistente de `recommendation-service`
  (`test_service_without_hypotheses_is_clean` y correlatos; 3 failed en DB
  compartida, reproducido en clone limpio de `099dbbb` durante U6a) sigue
  documentado; **no tocado, sin skips/xfails**.

## Verificaciones finales

- Higiene del diff: 0 secretos/tokens/TODO/FIXME/print(/console.log;
  contenido comercial: **0**.
- `git diff --cached` = 0 (sin staging).
- Pre-existing: 8 M + journal nuevo = 9 M/?? cambios propios; los 4 journals
  `??` de U7 intactos; U6a (`7ca822d`) intacto y publicado.
- Framework: `381f56c…`, 0 staged, 9 entradas, journal 0 escrituras.
- Nada limpiado, restaurado ni absorbido.

## Autorización

- **commit**: NO creado (`AUTHORIZE_COMMIT=NO`); **push**: NO realizado
  (`AUTHORIZE_PUSH=NO`). Sin SHA futuros. Queda listo para revisión humana.
