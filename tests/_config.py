"""TEST-ONLY shared configuration for integration tests.

These values are for CI/local integration tests against ephemeral containers.
They are NOT production credentials.  Production MUST set DATABASE_URL.
"""
import os

TEST_DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
)
TEST_DATABASE_URL_SYNC = TEST_DATABASE_URL.replace(
    "postgresql+asyncpg://", "postgresql://"
)
