# 2026-09-24 — Limpieza de contenido de negocio (prompt `elimina_precios.md`)

## Baseline

- **HEAD**: `2c6ed0731d022855bdd22df60261ec9fbfb6012f`
- **origin/main**: `2c6ed0731d022855bdd22df60261ec9fbfb6012f`
- **HEAD == origin/main**: YES
- **Working tree al inicio**: 4 modificaciones preexistentes sin tocar (`.env.example`,
  `apps/gateway/api-gateway/src/main.py`, `infrastructure/docker/docker-compose.yml`,
  `libs/access/security.py`) + 14 untracked preexistentes (governance/H5 docs/journals)
- **Framework**: `/home/dcordoba/Documents/Default Project/company/company-os-main/`
  (solo lectura, NO modificado)
- **Commit**: autorizado por el humano tras revisión — 3 commits de la sesión
  (governance/security, limpieza no-comercial, journals H5); hashes en `git log`

## Motivo

Prompt `/home/dcordoba/Documents/tmp/elimina_precios.md`: dejar el repositorio
técnicamente coherente y **sin temática de negocio** (tarifas por región y por
nivel, argumentos de negocio, métricas de crecimiento, cifras financieras)
sin degradar arquitectura cognitiva, seguridad, trazabilidad, tests ni contratos.

## company-os-monitor-prompt (archivo eliminado)

- 0 referencias en todo el repo, sin dependencias, contenido obsoleto
  (menciones `InfraDoctor`/`idr_` que ya no existen) → **eliminado** (` D` en git).

## Documentación de contenido de negocio eliminada / neutralizada

- `docs/05-negocio-roadmap-backlog.md` → "FASE 9 y 10: Roadmap y Backlog":
  bloque de modelo de negocio, tablas de tarifas por región y por nivel
  (moneda local/extranjera, tres niveles de servicio), matriz de niveles,
  sprint 23 de captación, fase de salida de producto, métricas de crecimiento
  → renombrado a capacidades técnicas (Shared Procedural Memory,
  SDK Extensibility, Cognitive Value Metrics, etc.). Cross-refs de `docs/05`
  (`:84` → `:47`) actualizadas en
  `docs/cognitive-gate-closure-preimplementation-plan.md:34` y
  `docs/post-h5-next-phase-discovery-report.md:90,194`.
- `docs/04-informes-seguridad.md` (§7): ejemplos con cifras monetarias y campos
  financieros → atributos neutros (Risk/Impact/Scope/Reversibilidad);
  rationale de alternativa con referencia financiera →
  `"Low immediate operational overhead"`.
- `README.md` / `README_ES.md` / `README_EN.md`: tagline inicial → tagline
  técnica neutral; frase sobre invención de cifras financieras → "cifras
  financieras"; índice de `docs/05` → "FASE 9-10".
- `cognitive_contract.md`: tagline del proyecto y entrada de despliegue
  gestionado → tagline neutral y "Multi-tenant" (aislamiento por tenant).
- `docs/01-fundacion-arquitectura.md`: tagline; esquema `tenants` sin `plan`.
- `docs/03-predictivo-ia-local.md`: encabezado de tabla de escala → `Scale`;
  fila de mayor escala → `Large scale`; fila `MVP` sin referencia a presupuesto
  (specs de hardware intactas: RAM/VRAM/CPU/GPU/throughput/tok-s conservados).
- `docs/sprint-11-prompt.md`: campos ejecutivos de riesgo/confianza/cifras
  financieras → "impacto operativo".
- `docs/sprint-12-prompt.md`: columnas de `tenants` sin `plan`.
- `adr/ADR-0004..0007`: sección de desventajas renombrada `### Trade-offs`
  (contenido = trade-offs arquitectónicos, sin cifras).

## Campo `plan` — Caso B (eliminado coherentemente)

Evidencia: cero consumidores funcionales; solo SELECT + display de los tres
niveles de servicio históricos. Eliminado de:

- Schema/seed: `infrastructure/docker/init-sql/01-schema.sql`,
  `02-seed.sql`, `infrastructure/db-migrations/sprint12-users-tables.sql`.
- Backend: `libs/access/users.py` (2 SELECT + `Tenant.plan`),
  `apps/services/user-service/src/health.py` (`_tenant_payload`).
- Frontend: `apps/web/src/types/cognitive.ts`, `TenantsPage.tsx`
  (badges + columna Plan), `TenantSwitcher.tsx`, `admin.test.tsx`.
- Docs: `docs/01`, `docs/sprint-12-prompt.md`.
- Migración idempotente **nueva**: `infrastructure/db-migrations/cleanup-drop-tenants-plan.sql`
  (`ALTER TABLE tenants DROP COLUMN IF EXISTS plan`) → alinea BDs existentes con
  `01-schema.sql` en el próximo `start.sh`.

## Fixtures de tests

Métricas sintéticas de negocio en fixtures de comparación expected vs actual
→ métricas operacionales
(disponibilidad/tasa de error/latencia) en 7 archivos (`test_consolidation`,
`test_learning_loop`, `test_h3_*`, `test_hypothesis_evaluation`): renombre
consistente en ambos lados del matcher textual/substring → misma semántica de
evaluación.

## Validaciones

- `pytest` raíz: **745 passed**
- Services: report **32**, recommendation **36**, decision **53**, user **55**,
  gateway **150 passed / 1 skipped**
- `ruff check .`: All checks passed
- Frontend: `tsc` OK, vitest **182 passed** (29 files), oxlint 0 errors
  (4 warnings preexistentes), `vite build` OK
- Schema/migraciones: `01-schema` + `02-seed` + TODAS las migraciones en BD
  scratch PG16 (`cosmonitor_schemacheck`) → OK, `tenants` sin `plan`, BD descartada
- `git diff --check`: OK
- Búsqueda final (listas §12 + §8, 675 archivos): **0 remanentes de negocio en
  contenido de producto**; restos clasificados TECHNICAL LEGITIMATE (parámetro
  criptográfico de bcrypt, aserciones negativas que impiden campos financieros
  en el reporte ejecutivo, adjetivos de nivel, grupos privilegiados de Active
  Directory, manejo de locks en auditorías h3, `plan` como planificación,
  cadencia `>1 insight/tenant/mes`, trade-offs operacionales en rationales,
  journals históricos con lenguaje coloquial de esfuerzo).
- `company-os-monitor-prompt` (archivo): **0 referencias** en el repo
  (verificado con la búsqueda literal completa del prompt §11).
- Framework Company OS: NO modificado.

## Acción manual pendiente

- **MANUAL GITHUB ACTION REQUIRED**: descripción pública del repo en GitHub
  (metadata, no editable con herramientas locales):
  `COS-Monitor (Company OS Monitor): plataforma de monitoreo y diagnóstico de
  infraestructura IT basada en la arquitectura cognitiva Company OS
  (Perception → Reasoning → Confidence → Action).`

## Commit Authorization Status

**AUTHORIZED** — la limpieza se commiteó en 3 commits de esta sesión
(governance/security, limpieza no-comercial, journals H5); hashes en `git log`
de `main`.

## Push Authorization Status

**PERFORMED** — push a `origin/main` tras autorización, CI verificado verde.
