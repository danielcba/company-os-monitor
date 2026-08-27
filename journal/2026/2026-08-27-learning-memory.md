# 2026-08-27 — Learning Memory ledger (P7 persistence, authorized)

## Autorización
El usuario autorizó la persistencia de Memory (hasta ahora "remains planned"
por ADR-0002). Decisión confirmada vía pregunta: persistir en un **nuevo ledger
`learning_memory`** (inmutable por registro, nunca muta entidades canónicas —
P1) y disparar vía **POST explícito idempotente**.

## Diseño
- Nueva entidad `learning_memory` (append-only). Columnas: `id, tenant_id,
  target_type (pattern|context|insight), target_id, signal JSONB, provenance
  JSONB, signal_hash, created_at`.
- Idempotencia: UNIQUE `(tenant_id, target_type, target_id, signal_hash)` →
  re-POST de señal idéntica es no-op (`ON CONFLICT DO NOTHING`).
- Inmutabilidad: trigger `learning_memory_immutable_trigger` (BEFORE UPDATE OR
  DELETE) — P1.
- El gateway NO importa `libs.reasoning`/`libs.perception` (boundary R3):
  el store vive en `libs/memory/memory_ledger.py` y consume su propia conexión
  (patrón `DecisionStore`).

## Implementación
- `infrastructure/db-migrations/learning-memory-ledger.sql` (idempotente) +
  `01-schema.sql` (fresh build) con tabla + trigger + índices + unique index.
- `libs/memory/memory_ledger.py`: `MemoryStore`, `MemoryStoreProtocol`,
  `PersistLearningMemoryInput`, `LearningMemoryRecord`, `compute_signal_hash`.
- Gateway: `service.py` (`persist_learning_memory`, `get_learning_memory`,
  autorización `commit`/`read`), `health.py` (rutas `GET`/`POST
  /tenants/{tid}/memory`), `main.py` (wire `MemoryStore(dsn)`).
- Frontend `/learning`: sección "Persisted Memory" + botón "Save to Memory" por
  fila en las 3 señales (P7), que invoca `POST /memory` vía `usePersistLearningMemory`.

## Conformidad
- P1: ledger append-only; canónicas jamás mutadas.
- P2: Context Revision solo sugiere competidor; el ledger lo registra, no activa.
- P4: Pattern Refinement ajusta soporte; el ledger lo registra, no inventa.
- R6: Insight Transformation journaling; el ledger guarda señal + provenance.
- R3/ADR-0002: external capability; POST autorizado es el único write path.

## Verificación
- Backend: `tests/memory/test_memory_ledger.py` (hash/idempotencia),
  `apps/gateway/api-gateway/tests/test_memory_ledger.py` (HTTP GET/POST, 401/403/
  cross-tenant/validación), `tests/architecture/test_cognitive_invariants.py::
  test_learning_memory_ledger_migration_is_complete`. ruff + mypy limpios.
- Frontend: `learning.test.tsx` (render ledger + flujo Save to Memory). typecheck/
  lint/build OK; 179 tests pasan.
- PR #10 → merge → `docker-build` GREEN (pendiente de verificar en CI).
