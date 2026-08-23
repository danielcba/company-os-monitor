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
    from libs.action.decision import DecisionStore
    from libs.action.report import ReportStore
    from libs.cognitive_core.summary import CognitiveSummaryStore
    from src.observations import ObservationReadStore
    from sqlalchemy.ext.asyncio import create_async_engine

    algorithm = os.getenv("JWT_ALGORITHM", "HS256")
    jwt = JwtService(
        algorithm=algorithm,
        secret_key=os.getenv("JWT_SECRET_KEY"),
        private_key=os.getenv("JWT_PRIVATE_KEY"),
        public_key=os.getenv("JWT_PUBLIC_KEY"),
        access_expire_minutes=int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "15")),
        refresh_expire_days=int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "7")),
    )

    # Create async engine once and share across stores
    engine = create_async_engine(dsn)

    # READ routes read pipeline data directly (viewer+): decisions + reports + observations.
    decision_store = DecisionStore(dsn)
    report_store = ReportStore(dsn)
    observation_store = ObservationReadStore(dsn, pool_size=10, max_overflow=20)
    summary_store = CognitiveSummaryStore(engine)
    await decision_store.verify_connection()
    await report_store.verify_connection()
    await observation_store.verify_connection()

    service = GatewayService(
        jwt,
        decision_store=decision_store,
        report_store=report_store,
        observation_store=observation_store,
        cognitive_summary_store=summary_store,
        service_health=_build_service_health(),
        dsn=dsn,
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
        await observation_store.close()
        await summary_store.close()


if __name__ == "__main__":
    asyncio.run(main())
