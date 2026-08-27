# 2026-08-26 — Learning (P7) UI: superficie las 3 read/compute capabilities

## Objetivo
Consistente con la Fase 2B (Cognitive Trace UI), exponer en el frontend las tres
capacidades read/compute de P7 recién añadidas al gateway:
- `GET /tenants/{tid}/patterns/refinement` → Pattern Refinement (P7+P4)
- `GET /tenants/{tid}/contexts/revision` → Context Revision (P7+P2)
- `GET /tenants/{tid}/insights/transformations` → Insight Transformation (R6)

Una sola página **Learning (P7)** (`/learning`) con tres secciones (cards),
cada una consumiendo su endpoint vía TanStack Query. Es read-only: nunca
fabrica nodos ni muta entidades (ADR-0002).

## Diseño (alineado con Cognitive Trace UI / Fase 2B)
- **Tipos** (`apps/web/src/types/cognitive.ts`): `PatternRefinementResponse`,
  `ContextRevisionResponse`, `InsightTransformationResponse` + sus result items.
- **Cliente** (`apps/web/src/api/gateway.ts`): `fetchPatternRefinement`,
  `fetchContextRevision`, `fetchInsightTransformations` (usando `apiFetch`,
  que lanza `ApiError` con `status`).
- **Hook** (`apps/web/src/features/learning/useLearning.ts`): 3 hooks
  `usePatternRefinement` / `useContextRevision` / `useInsightTransformations`
  con `queryKey` por capacidad y `enabled: Boolean(tenantId)`.
- **Página** (`apps/web/src/features/learning/LearningPage.tsx`):
  - Header explicativo (read/compute, sin persistencia; fuente de verdad =
    Outcome Consolidation, sin fabricación).
  - Pattern Refinement: tabla (Pattern, Type, Linked, Corr/Contr, Ratio,
    Strength cur→rec, Action badge keep/degrade/deactivate).
  - Context Revision: tabla (Context, Linked, Corr/Contr, Ratio, Revision badge,
    Suggested competitor). Refleja P2: solo sugiere, nunca activa.
  - Insight Transformations: lista (description, kind badge revised/stable/
    unchanged, prior → updated journaling, linked recs/outcomes, corr/contr).
  - Por sección: `LoadingState` / `SectionError` (403 → `ForbiddenState`,
    404 → `EmptyState`) / `EmptyState` cuando no hay outcomes.
- **Ruta** (`apps/web/src/routes/index.tsx`): lazy `LearningPage` en `/learning`.
- **Sidebar** (`apps/web/src/components/layout/Sidebar.tsx`): nuevo grupo
  "Learning" con item "Learning (P7)" (icono `BookOpen`).
- **Test** (`apps/web/src/tests/learning.test.tsx`): 3 tests — datos en las 3
  secciones, 403 → forbidden, vacío → empty states.

## Verificación
- `npm run typecheck` (tsc -b --noEmit): OK.
- `npm run lint` (oxlint): 0 errores (los warnings son preexistentes de
  `use-auth.tsx`/`command-palette`, no de este cambio).
- `npx vitest run`: 177 tests pasan (3 nuevos incluidos).
- `npm run build` (tsc -b && vite build): OK.
- PR #9 → merge a `main` → `docker-build` GREEN (pendiente de verificar, corre
  el CI completo incl. frontend build + backend pytest).

## Conformidad
- ADR-0002: la UI es solo lectura/provenance; no fabrica nodos ni escribe.
- P2/P4/R6: la presentación refleja fielmente la semántica del backend
  (sugerir competidor, no activar; ajustar soporte, no inventar; journaling de
  la transformación, no explicación causal).
- P1: los conteos vienen de Outcome Consolidation; la UI no recomputa ni
  fabrica verdictos.
