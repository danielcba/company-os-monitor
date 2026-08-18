-- COS-Monitor seed data (development sandbox)
-- Runs on first container boot after 01-schema.sql (both are in docker-entrypoint-initdb.d).
-- In production, tenants are created via onboarding; agents must never create them.

-- Sandbox tenant used by all development agents (TENANT_ID default).
INSERT INTO tenants (id, name, slug, plan, settings)
VALUES (
    '00000000-0000-0000-0000-000000000001',
    'Sandbox Tenant',
    'sandbox',
    'professional',
    '{"source": "seed"}'::jsonb
)
ON CONFLICT (id) DO NOTHING;

-- Sandbox admin (Sprint 12, DEVELOPMENT ONLY). Auth/RBAC is an EXTERNAL
-- capability (ADR-0002): this seed exists so development agents can log into
-- the sandbox tenant with a documented dev credential - it is NOT a real
-- product identity. The bcrypt hash below is for the DEVELOPMENT password
-- "cosmonitor" (rounds=12). In production users are created via onboarding
-- with real secrets; agents must never create privileged identities.
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