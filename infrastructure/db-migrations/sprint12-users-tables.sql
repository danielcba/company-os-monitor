-- Sprint 12 - Multi-tenant users / roles tables (migration for existing DBs).
--
-- Auth/RBAC is an EXTERNAL non-canonical capability (ADR-0002): the `users`
-- table stores tenant-scoped identities with a Decision Authority role
-- (viewer/operator/admin/superadmin). It authenticates/authorizes and protects
-- access to the canonical flow (R3 - Cognitive Boundary); it never produces
-- cognitive judgments. The RBAC is modeled as Decision Authority binding
-- (docs/04): each role determines which authority may execute which action on
-- the pipeline. `decisions.authority_id` (Sprint 10) may now reference a real
-- `users.id`; the decisions table is NOT modified (authority_id stays a free
-- UUID, the user-service guarantees consistency of who emits tokens).
--
-- `users` is NOT a cognitive artifact: rows are MUTABLE by design (password/
-- role/name changes, is_active deactivation) - no P1 immutability trigger.
-- Refresh strategy decision: STATELESS JWT (access + refresh tokens signed by
-- python-jose; refresh tokens carry their own expiry). No refresh_tokens table
-- and no Redis token store needed in this MVP (documented in Sprint 12
-- journal); the stateless design keeps the boundary simple and auditable.
--
-- Apply on an existing database (installations with a fresh volume apply the
-- same DDL automatically from 01-schema.sql):
--   psql "postgresql://cosmonitor:cosmonitor@127.0.0.1:5433/cosmonitor" -f sprint12-users-tables.sql

CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    name VARCHAR(100),
    role VARCHAR(20) NOT NULL DEFAULT 'viewer'
        CHECK (role IN ('viewer','operator','admin','superadmin')),
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_users_tenant_email ON users(tenant_id, email);
CREATE INDEX IF NOT EXISTS idx_users_tenant_role ON users(tenant_id, role);

-- Sandbox admin (DEVELOPMENT ONLY, documented dev password "cosmonitor",
-- bcrypt rounds=12). Seed exists so dev agents can log into the sandbox; in
-- production users are created via onboarding, never by agents.
INSERT INTO users (id, tenant_id, email, password_hash, name, role, is_active)
VALUES (
    '00000000-0000-0000-0000-0000000000a1',
    '00000000-0000-0000-0000-000000000001',
    'admin@sandbox.local',
    '$2b$12$l2bErlFm31EJSkIlzU5np.l0pjpYEag.o77Ki.lSOp4CDDscivBXa',
    'Sandbox Admin',
    'superadmin',
    TRUE
)
ON CONFLICT (email) DO NOTHING;