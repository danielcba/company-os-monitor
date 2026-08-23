"""User Service Entry Point - external auth/RBAC (ADR-0002).

External non-canonical capability (ADR-0002): it verifies identity, emits
signed JWTs with the Decision Authority role and tenant scope, and authorizes
actions on the canonical flow (R3 - Cognitive Boundary). It NEVER produces
cognitive judgments and never runs the pipeline. Port USER_HEALTH_PORT (8099).
"""
import asyncio
import os

from libs.access.token_blacklist import TokenBlacklist
from libs.access.users import UserStore

from src.auth.security import build_jwt_service_from_env
from src.health import UserServer
from src.service import AuthService


async def main():
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("USER_HEALTH_PORT", "8099"))
    redis_url = os.getenv("JWT_REDIS_URL", "redis://localhost:6379/1")

    user_store = UserStore(dsn)
    await user_store.verify_connection()

    jwt = build_jwt_service_from_env()
    blacklist = TokenBlacklist.from_url(redis_url)
    service = AuthService(user_store, jwt, blacklist=blacklist)
    server = UserServer(service, jwt)

    await server.start(port)

    # The auth service is request-driven (no background cycle): keep the event
    # loop alive serving HTTP requests.
    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await server.stop()
        await user_store.close()


if __name__ == "__main__":
    asyncio.run(main())