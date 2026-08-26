# 2026-08-26 — Fase 2B: UI de Cognitive Trace

## Objetivo
Implementar la interfaz de usuario del Cognitive Trace (Paso 1 del plan de
avance), consumiendo el read model ya expuesto por el gateway en Fase 2A. La UI
es **solo lectura/provenance** (capacidad externa, ADR-0002): no introduce
escritura ni bypass del Cognitive Boundary (R3), ni acción sin confianza (R4).

## Trabajo realizado (frontend, `apps/web`)

- **Hook** `features/cognitive-trace/useCognitiveTrace.ts`: envuelve
  `useQuery` sobre `fetchCognitiveTrace` (ya existente en `api/gateway.ts`),
  keyed por `tenant_id` + `report_id`.
- **Grafo de provenance** `features/cognitive-trace/TraceGraph.tsx`:
  - Capas en orden canónico del pipeline (`report → decision →
    recommendation → confidence → hypothesis → anomaly → pattern → context →
    evidence → observation`), cada nodo con resumen derivado de `data`.
  - Tabla de relaciones (`from → relation → to`) con los `edges` reales.
  - `TraceWarnings`: renderiza `warnings` explícitos cuando la provenance es
    `partial` (nunca se fabrica; coherente con `_validate_provenance` del
    backend).
- **Página** `features/cognitive-trace/CognitiveTracePage.tsx`:
  - Ruta `/action/reports/:reportId/trace` (lazy en `routes/index.tsx`).
  - Badge `complete`/`partial`, conteo de nodos/edges, root report+tenant.
  - Estados: loading, 404 (Report no en tenant → "Report not found in this
    tenant"), 403 (Forbidden), error genérico.
- **CTA en `ReportDetail`**: botón "Cognitive trace" que navega a la ruta del
  trace (usa `useNavigate`); cierra el drawer.
- **Contrato**: tipos ya existentes en `types/cognitive.ts`
  (`CognitiveTraceResponse`); el endpoint ya documentado en
  `frontend-backend-contract.md` (Paso 0).

## Tests
- `apps/web/src/tests/cognitive-trace.test.tsx` (4 tests):
  - cadena de provenance completa (todos los tipos + relaciones);
  - trace `partial` con `warnings` explícitos;
  - 404 → estado tenant-scoped "not found";
  - 403 → Forbidden.
- Ajuste de `apps/web/src/tests/reports.test.tsx`: se envolvió `ReportsPage`
  en `MemoryRouter` (ahora `ReportDetail` usa `useNavigate`) y se restauró el
  import de `userEvent` que se había perdido. Sin cambio de comportamiento de
  producto.

## Validación
- `npm run typecheck`: OK.
- `npm run lint` (oxlint): 0 errores (warnings preexistentes, no de este cambio).
- `npm run test`: **174/174 pass** (incluye los 4 nuevos).
- `npm run build` (tsc + vite): OK.

## Conformidad con el marco
- El trace sigue siendo un **read model** (ADR-0002, R7): la UI solo
  visualiza lo que los stores canónicos ya commitearon; no crea artefactos ni
  etapas cognitivas.
- `completeness`/`warnings` reflejan fielmente la respuesta del backend; la UI
  nunca inventa nodos (P1 trazabilidad, no invención).

## Siguiente paso sugerido
Abrir PR de Fase 2B desde `feature/phase2b-cognitive-trace-ui` → `main` y
validar CI (lint-and-test + docker-build). Tras ello, el producto tiene
Cognitive Trace end-to-end (backend read model + UI).
