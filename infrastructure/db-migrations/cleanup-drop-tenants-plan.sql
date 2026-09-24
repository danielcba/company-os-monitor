-- Cleanup: drop the legacy tenants.plan column.
--
-- tenants.plan was a legacy informational label with no functional consumer:
-- no code path read or branched on it (backend SELECT/model, API payload and
-- frontend UI no longer reference it). The column is dropped so existing
-- databases stay aligned with 01-schema.sql, which no longer defines it.
--
-- Idempotent: safe to re-run on every startup (DROP COLUMN IF EXISTS).

ALTER TABLE tenants DROP COLUMN IF EXISTS plan;
