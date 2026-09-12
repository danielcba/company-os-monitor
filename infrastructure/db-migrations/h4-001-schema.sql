-- H4.0 Phase A — Foundation Schema
-- Authorized 2026-09-03 (commit e627882). ADR-0004, ADR-0005, ADR-0006, ADR-0007 ACCEPTED.
--
-- Tables created:
--   agent_installations      — persistent agent identity on a host (ADR-0006)
--   agent_credentials        — rotatable auth credentials (ADR-0005, ADR-0006)
--   agent_instances          — ephemeral running process (ADR-0006)
--   metric_batches           — telemetry batch ingestion (ADR-0007)
--   metric_samples           — individual telemetry samples (ADR-0007)
--   observation_outbox       — transactional outbox for Observations (ADR-0004)
--
-- Composite FKs enabled by UNIQUE(tenant_id, id) on parent tables.
-- Append-only / immutability triggers per P1.
-- Partial UNIQUE indexes for at-most-one RUNNING instance (ADR-0006).
-- Idempotency indexes per ADR-0007.

-- ============================================
-- AGENT INSTALLATIONS (ADR-0006)
-- ============================================
CREATE TABLE IF NOT EXISTS agent_installations (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    server_id       UUID NOT NULL REFERENCES servers(id) ON DELETE CASCADE,
    host_fingerprint CHAR(64) NOT NULL,
    agent_type      VARCHAR(50) NOT NULL,
    agent_version   VARCHAR(50) NOT NULL,
    capabilities_json JSONB NOT NULL DEFAULT '{}',
    status          VARCHAR(20) NOT NULL DEFAULT 'PROVISIONED'
        CHECK (status IN ('PROVISIONED', 'ACTIVE', 'DISABLED', 'REVOKED')),
    registered_at   TIMESTAMPTZ,
    last_seen_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    UNIQUE (tenant_id, server_id, agent_type)
);

-- Enable composite FKs from metric_batches and observation_outbox
ALTER TABLE agent_installations
    ADD CONSTRAINT uq_agent_installations_tenant_id
    UNIQUE (tenant_id, id);

CREATE INDEX IF NOT EXISTS idx_agent_installations_tenant_server
    ON agent_installations (tenant_id, server_id);
CREATE INDEX IF NOT EXISTS idx_agent_installations_tenant_status
    ON agent_installations (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_installations_host_fingerprint
    ON agent_installations (host_fingerprint);

-- ============================================
-- AGENT CREDENTIALS (ADR-0005, ADR-0006)
-- ============================================
CREATE TABLE IF NOT EXISTS agent_credentials (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    installation_id UUID NOT NULL REFERENCES agent_installations(id) ON DELETE CASCADE,
    public_key_hash CHAR(64),
    status          VARCHAR(20) NOT NULL DEFAULT 'ACTIVE'
        CHECK (status IN ('ACTIVE', 'REVOKED', 'EXPIRED')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at      TIMESTAMPTZ,

    UNIQUE (tenant_id, installation_id, id)
);

CREATE INDEX IF NOT EXISTS idx_agent_credentials_installation
    ON agent_credentials (installation_id);
CREATE INDEX IF NOT EXISTS idx_agent_credentials_tenant_status
    ON agent_credentials (tenant_id, status);

-- ============================================
-- AGENT INSTANCES (ADR-0006)
-- ============================================
CREATE TABLE IF NOT EXISTS agent_instances (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id           UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    installation_id     UUID NOT NULL REFERENCES agent_installations(id) ON DELETE CASCADE,
    credential_id       UUID NOT NULL REFERENCES agent_credentials(id) ON DELETE CASCADE,
    host_fingerprint    CHAR(64) NOT NULL,
    status              VARCHAR(20) NOT NULL DEFAULT 'RUNNING'
        CHECK (status IN ('RUNNING', 'STOPPED')),
    registered_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_heartbeat_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    stopped_at          TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- At most one RUNNING instance per installation (ADR-0006 §6)
CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_instances_active
    ON agent_instances (installation_id)
    WHERE status = 'RUNNING';

CREATE INDEX IF NOT EXISTS idx_agent_instances_tenant_installation
    ON agent_instances (tenant_id, installation_id);
CREATE INDEX IF NOT EXISTS idx_agent_instances_tenant_status
    ON agent_instances (tenant_id, status);
CREATE INDEX IF NOT EXISTS idx_agent_instances_credential
    ON agent_instances (credential_id);
CREATE INDEX IF NOT EXISTS idx_agent_instances_last_heartbeat
    ON agent_instances (last_heartbeat_at);

-- ============================================
-- METRIC BATCHES (ADR-0007)
-- ============================================
CREATE TABLE IF NOT EXISTS metric_batches (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    installation_id UUID NOT NULL,
    instance_id     UUID NOT NULL,
    credential_id   UUID NOT NULL,
    batch_id        UUID NOT NULL,
    payload_hash    CHAR(64) NOT NULL,
    captured_at     TIMESTAMPTZ NOT NULL,
    received_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    sample_count    INTEGER NOT NULL,

    -- Idempotency: same tenant + installation + batch_id + payload_hash = duplicate (202)
    -- Different payload_hash = conflict (409)
    UNIQUE (tenant_id, installation_id, batch_id, payload_hash)
);

-- Composite FK to agent_installations (enabled by UNIQUE(tenant_id, id) on parent)
ALTER TABLE metric_batches
    ADD CONSTRAINT fk_metric_batches_installation
    FOREIGN KEY (tenant_id, installation_id)
    REFERENCES agent_installations(tenant_id, id)
    ON DELETE CASCADE;

-- Enable composite FKs from metric_samples
ALTER TABLE metric_batches
    ADD CONSTRAINT uq_metric_batches_tenant_id
    UNIQUE (tenant_id, id);

CREATE INDEX IF NOT EXISTS idx_metric_batches_tenant_installation
    ON metric_batches (tenant_id, installation_id);
CREATE INDEX IF NOT EXISTS idx_metric_batches_tenant_batch
    ON metric_batches (tenant_id, batch_id);
CREATE INDEX IF NOT EXISTS idx_metric_batches_instance
    ON metric_batches (instance_id);
CREATE INDEX IF NOT EXISTS idx_metric_batches_credential
    ON metric_batches (credential_id);
CREATE INDEX IF NOT EXISTS idx_metric_batches_captured_at
    ON metric_batches (captured_at);

-- Append-only trigger (ADR-0007 §6): metric_batches is IMMUTABLE
CREATE OR REPLACE FUNCTION prevent_metric_batches_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'metric_batches is append-only (immutable per ADR-0007). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS metric_batches_immutable_trigger ON metric_batches;
CREATE TRIGGER metric_batches_immutable_trigger
    BEFORE UPDATE OR DELETE ON metric_batches
    FOR EACH ROW EXECUTE FUNCTION prevent_metric_batches_update();

-- ============================================
-- METRIC SAMPLES (ADR-0007)
-- ============================================
CREATE TABLE IF NOT EXISTS metric_samples (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    batch_id        UUID NOT NULL,
    sequence        INTEGER NOT NULL,
    fact_type       VARCHAR(100) NOT NULL,
    fact_value      JSONB NOT NULL,
    unit            VARCHAR(20) NOT NULL,
    labels          JSONB DEFAULT '{}',

    -- Uniqueness: one sample per sequence per batch per tenant
    UNIQUE (tenant_id, batch_id, sequence)
);

-- Composite FK to metric_batches (enabled by UNIQUE(tenant_id, id) on parent)
ALTER TABLE metric_samples
    ADD CONSTRAINT fk_metric_samples_batch
    FOREIGN KEY (tenant_id, batch_id)
    REFERENCES metric_batches(tenant_id, id)
    ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_metric_samples_tenant_batch
    ON metric_samples (tenant_id, batch_id);

-- Append-only trigger (ADR-0007 §6): metric_samples is IMMUTABLE
CREATE OR REPLACE FUNCTION prevent_metric_samples_update()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'metric_samples is append-only (immutable per ADR-0007). No UPDATE/DELETE allowed.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS metric_samples_immutable_trigger ON metric_samples;
CREATE TRIGGER metric_samples_immutable_trigger
    BEFORE UPDATE OR DELETE ON metric_samples
    FOR EACH ROW EXECUTE FUNCTION prevent_metric_samples_update();

-- ============================================
-- OBSERVATION OUTBOX (ADR-0004)
-- ============================================
CREATE TABLE IF NOT EXISTS observation_outbox (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id       UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    installation_id UUID NOT NULL,
    batch_id        UUID NOT NULL,
    credential_id   UUID NOT NULL,
    payload_hash    CHAR(64) NOT NULL,
    observation     JSONB NOT NULL,
    status          VARCHAR(20) NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'published', 'failed', 'dead_letter')),
    attempts        INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error      TEXT,
    published_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Idempotency: same tenant + installation + batch_id + payload_hash = duplicate
    UNIQUE (tenant_id, installation_id, batch_id, payload_hash)
);

-- Composite FK to agent_installations (enabled by UNIQUE(tenant_id, id) on parent)
ALTER TABLE observation_outbox
    ADD CONSTRAINT fk_observation_outbox_installation
    FOREIGN KEY (tenant_id, installation_id)
    REFERENCES agent_installations(tenant_id, id)
    ON DELETE CASCADE;

CREATE INDEX IF NOT EXISTS idx_observation_outbox_publish
    ON observation_outbox (status, next_attempt_at)
    WHERE status IN ('pending', 'failed');
CREATE INDEX IF NOT EXISTS idx_observation_outbox_tenant_installation
    ON observation_outbox (tenant_id, installation_id);
CREATE INDEX IF NOT EXISTS idx_observation_outbox_batch
    ON observation_outbox (batch_id);

-- Content immutability trigger (ADR-0004 §1):
-- Only lifecycle fields (status, attempts, next_attempt_at, last_error, published_at) may change
CREATE OR REPLACE FUNCTION prevent_outbox_content_update()
RETURNS TRIGGER AS $$
BEGIN
    IF NEW.id IS DISTINCT FROM OLD.id
       OR NEW.tenant_id IS DISTINCT FROM OLD.tenant_id
       OR NEW.installation_id IS DISTINCT FROM OLD.installation_id
       OR NEW.batch_id IS DISTINCT FROM OLD.batch_id
       OR NEW.credential_id IS DISTINCT FROM OLD.credential_id
       OR NEW.payload_hash IS DISTINCT FROM OLD.payload_hash
       OR NEW.observation IS DISTINCT FROM OLD.observation
       OR NEW.created_at IS DISTINCT FROM OLD.created_at THEN
        RAISE EXCEPTION 'Outbox content is immutable. Only lifecycle fields (status, attempts, next_attempt_at, last_error, published_at) may change.';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS outbox_content_immutable_trigger ON observation_outbox;
CREATE TRIGGER outbox_content_immutable_trigger
    BEFORE UPDATE ON observation_outbox
    FOR EACH ROW EXECUTE FUNCTION prevent_outbox_content_update();

-- ============================================
-- MACHINE JWT BLACKLIST (ADR-0005 §5, §8)
-- ============================================
-- Separate from the Redis-backed human JWT blacklist (libs/access/token_blacklist.py).
-- Machine JWTs use a DB-based blacklist to support atomic single-use registration
-- tokens (INSERT-then-check) and durable revocation across gateway restarts.
CREATE TABLE IF NOT EXISTS machine_jwt_blacklist (
    jti         VARCHAR(64) PRIMARY KEY,
    blacklisted_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Idempotent insert guard: duplicate JTI → constraint violation → fail-closed
CREATE INDEX IF NOT EXISTS idx_machine_jwt_blacklist_blacklisted_at
    ON machine_jwt_blacklist (blacklisted_at);