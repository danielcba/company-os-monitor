# 2026-09-24 — Alineación documental de estado de Memory (prompt `correccion_00.md`)

## Baseline

- **Monitor HEAD**: `52dbbfac11a9b0410e15003d917b39d648cac025`
- **Monitor origin/main**: `52dbbfac11a9b0410e15003d917b39d648cac025` (HEAD == origin/main)
- **Branch**: `main`
- **Working tree al inicio**: **Clean** (`nothing to commit, working tree clean`) —
  ninguna modificación ni archivo sucio preexistente en `company-os-monitor`.
- **Framework HEAD consultado**: `381f56cfa48d092f85846e160d2e1fe6878f9f6f`
  (`origin/main` tras `git fetch`, igual a HEAD local) —
  `/home/dcordoba/Documents/Default Project/company/company-os-main/`
- **Framework modificado por esta tarea**: NO (ver "Framework unchanged" abajo).
- **Modificaciones preexistentes del checkout local del Framework** (ya existían
  ANTES de esta tarea, sin tocar): ` M .github/workflows/ci.yml`,
  ` M adr/ADR-0002-cos-monitor-is-the-product.md`, ` M decisions/decisions.md`,
  ` M docs/cognitive-lexicon/ontology.md` + untracked
  `.github/CODEOWNERS`, `.github/dependabot.yml`, `.github/secret-scanning.yml`,
  `FW-PRE-COMMIT-REVIEW-REPORT.md`, `SECURITY.md`.

## Estado canónico vigente de Memory (Framework)

- `adr/ADR-0003-adopt-monitor-memory-learning-layer.md` — Status **Accepted**
  (2026-08-30); "Memory is no longer planned"; `Memory Layer status: planned →
  operational`; supersedes la restricción "Memory remains planned" de ADR-0002.
- `docs/cognitive-architecture/cognitive-architecture.md:91` —
  "### Memory Layer (operational)" (realiza P7).
- `docs/cognitive-lexicon/ontology.md:67` — concepto `Memory` #11, estado
  **Official**.
- `state/project-state.md:79` — "All 11 concepts are Official. Memory is
  operational (ADR-0003)"; línea 115: 2026-08-30 planned → operational.

## Problema detectado

Deriva documental **activa** (no histórica): documentación corriente/normativa
del Monitor presentaba a Memory como capacidad `planned` del Framework,
contradiciendo ADR-0003 vigente.

## Archivos modificados

1. `README.md` (§ "Framework / Monitor Relationship") — "Where the Framework
   lists a capability as *planned* (e.g. Memory)…" → Memory es capacidad
   **operacional** del Framework (ADR-0003); el Monitor es su implementación
   de referencia. Autoría arquitectónica (Framework = autoridad, Monitor =
   producto, ADR-0002) intacta; "The framework is never edited by this
   repository" conservado.
2. `cognitive_contract.md` (§ 9.6) — equivalente en español de la misma
   frase, misma corrección.
3. `libs/memory/insight_transformation.py` (docstring de
   `InsightTransformationStore`, solo comentario) — "(Memory persistence
   remains planned per the framework)" → "(Memory persistence lives in the
   Memory Ledger, ADR-0003)". Sin cambio de lógica ni de comportamiento.
4. `tests/architecture/test_adr_0003_framework_sync.py` —
   `files_to_check` de AC-07 (`test_code_comments_no_stale_planned`) ampliado
   con `libs/memory/insight_transformation.py` para impedir regresión de
   exactamente este comentario obsoleto. Solo lista de archivos verificados:
   no altera comportamiento.

## NO modificados (registros históricos / fuera de alcance)

- `adr/ADR-0003-memory-learning-layer-adoption.md` (Context/Problem del ADR:
  estado en el momento de la decisión, espejo del Context del ADR-0003 del
  Framework).
- `docs/framework-monitor-sync-audit.md` (auditoría anclada a
  SHAs `9b8c064`, evidencia citada por el ADR).
- `ANALYSIS_REPORT.md` (banner `HISTORICAL RECORD — Pre-Remediation Analysis
  (2026-08-23)`).
- `docs/post-h5-next-phase-discovery-report.md`,
  `docs/cognitive-gate-closure-preimplementation-plan.md`,
  `docs/sprint-*-prompt.md`, journals previos, `README_EN.md`/`README_ES.md`
  (sin la frase; checklist `[x]` Memory/Learning loop), `state/project-state.md`
  (ya 7/7 con P7 Memory operational).

## Motivo arquitectónico

La arquitectura guía al código, nunca al revés (R7): el Framework es la fuente
de verdad y ADR-0003 (Accepted, 2026-08-30) fija Memory como capacidad
operacional. Toda documentación corriente del Monitor que presente Memory como
`planned` contradice la autoridad arquitectónica y constituye deriva
documental. La corrección se limita a documentación: no se redefine ninguna
capacidad, no se añade capacidad nueva, no se toca lógica cognitiva, esquemas,
APIs, seguridad, CI/CD ni frontend.

## Validaciones ejecutadas

- Búsqueda global de contradicciones sobre Memory: 0 restantes en documentación
  **activa**; solo permanecen en registros históricos (ADR-0003 del Monitor,
  `docs/framework-monitor-sync-audit.md`, `ANALYSIS_REPORT.md`, journals).
- Referencias activas al Framework: P1–P7, R1–R7, conceptos canónicos,
  ADR-0001/ADR-0002/ADR-0003 (ADR-0004..0008 existen en el Monitor; ningún ADR
  citado atribuido al Framework sin existir).
- `pytest tests/architecture/` → **191 passed**
- `pytest tests/` → **745 passed**
- `ruff check .` → All checks passed
- `mypy --config-file mypy.ini libs/` → Success (70 source files)
- `git diff --check` → OK (sin errores)
- Framework unchanged: `git status --short` del Framework idéntico al baseline
  (mismas 4 modificaciones + 5 untracked preexistentes, ninguna nueva);
  `git stash list` vacío; HEAD `381f56c` == `origin/main`.

## Estado del working tree final

4 archivos modificados, 0 añadidos, 0 eliminados (la entrada de journal de este
archivo es el único archivo nuevo). Sin cambios funcionales ni de comportamiento.

## Commit

**NOT PERFORMED**

## Push

**NOT PERFORMED**
