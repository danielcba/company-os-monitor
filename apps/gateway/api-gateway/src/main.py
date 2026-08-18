"""API Gateway Entry Point - Cognitive Boundary enforcement (R3, external).

External non-canonical capability (ADR-0002): validates JWT authority and
routes pipeline access; it NEVER reimplements cognitive logic. Port
GATEWAY_HEALTH_PORT (8100).
"""
import asyncio
import os

from src.health import GatewayServer
from src.service import DEFAULT_SERVICE_HEALTH, GatewayService


def _build_service_health() -> dict[str, str]:
    """Service health map from env (override) or the canonical default ports."""
    override = os.getenv("GATEWAY_SERVICE_HEALTH")
    if not override:
        return dict(DEFAULT_SERVICE_HEALTH)
    mapping: dict[str, str] = {}
    for entry in override.split(","):
        if "=" in entry:
            service, url = entry.strip().split("=", 1)
            mapping[service.strip()] = url.strip()
    return mapping or dict(DEFAULT_SERVICE_HEALTH)


async def main():
    dsn = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://cosmonitor:cosmonitor@localhost:5433/cosmonitor",
    )
    port = int(os.getenv("GATEWAY_HEALTH_PORT", "8100"))

    from libs.access.security import JwtService

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    jwt = JwtService(
        algorithm=algorithm,
        secret_key=os.getenv("JWT_SECRET_KEY"),
        private_key=os.getenv("JWT_PRIVATE_KEY"),
        public_key=os.getenv("JWT_PUBLIC_KEY"),
        access_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")),
        refresh_expire_days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
    )

    # READ routes read pipeline data directly (viewer+): decisions + reports.
    from libs.action.decision import DecisionStore
    from libs.action.report import ReportStore

    decision_store = DecisionStore(dsn)
    report_store = ReportStore(dsn)
    await decision_store.verify_connection()
    await report_store.verify_connection()

    service = GatewayService(
        jwt,
        decision_store=decision_store,
        report_store=report_store,
        service_health=_build_service_health(),
    )
    server = GatewayServer(service, jwt)

    await server.start(port)

    try:
        while True:
            await asyncio.sleep(3600)
    finally:
        await server.stop()
        await decision_store.close()
        await report_store.close()


if __name__ == "__main__":
    asyncio.run(main())