"""POST /api/v1/telemetry/ingest handler (ADR-0007 §1).

Machine-authenticated endpoint for telemetry batch ingestion.
Validates JWT, extracts identity claims, delegates to TelemetryIngestService.
"""
from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from aiohttp import web
from libs.access.errors import InvalidTokenError

if TYPE_CHECKING:
    from src.health import GatewayServer


async def ingest_handler(self: GatewayServer, request: web.Request) -> web.Response:
    """POST /api/v1/telemetry/ingest — telemetry batch ingestion (ADR-0007 §1).

    Machine token provides tenant_id, installation_id, instance_id, credential_id.
    Request body contains batch_id, captured_at, samples[].
    """
    from libs.telemetry.ingest_service import (
        PayloadConflictError,
        TelemetryIngestService,
        ValidationError,
    )

    try:
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.lower().startswith("bearer "):
            return web.json_response({"error": "missing bearer token"}, status=401)

        token_str = auth_header.split(" ", 1)[1].strip()

        if not self.machine_jwt:
            return web.json_response({"error": "machine auth not configured"}, status=503)

        try:
            claims = self.machine_jwt.decode(token_str)
        except InvalidTokenError:
            return web.json_response({"error": "invalid machine access token"}, status=401)

        if claims.get("token_type") != "machine_access":
            return web.json_response({"error": "not a machine access token"}, status=401)

        tenant_id_raw = claims.get("tenant_id")
        installation_id_raw = claims.get("installation_id")
        instance_id_raw = claims.get("instance_id")
        credential_id_raw = claims.get("sub")

        if not all([tenant_id_raw, installation_id_raw, instance_id_raw, credential_id_raw]):
            return web.json_response({"error": "token missing required claims"}, status=401)

        try:
            tenant_id = uuid.UUID(str(tenant_id_raw))
            installation_id = uuid.UUID(str(installation_id_raw))
            instance_id = uuid.UUID(str(instance_id_raw))
            credential_id = uuid.UUID(str(credential_id_raw))
        except ValueError:
            return web.json_response({"error": "invalid UUID in token claims"}, status=401)

        if self.service.blacklist and claims.get("jti"):
            is_revoked = await self.service.blacklist.is_revoked(jti=claims["jti"])
            if is_revoked:
                return web.json_response({"error": "token has been revoked"}, status=401)

        try:
            body = await request.json()
        except Exception:  # noqa: BLE001
            return web.json_response({"error": "invalid JSON"}, status=400)

        dsn = self.service._dsn
        if not dsn:
            return web.json_response({"error": "service unavailable"}, status=503)

        svc = TelemetryIngestService(dsn)
        result = await svc.ingest_batch(
            tenant_id=tenant_id,
            installation_id=installation_id,
            instance_id=instance_id,
            credential_id=credential_id,
            body=body,
        )

        return web.json_response(
            {
                "batch_id": str(result.batch_id),
                "status": "accepted",
                "observation_ids": [str(oid) for oid in result.observation_ids],
                "ingested_at": result.ingested_at.isoformat(),
            },
            status=202,
        )

    except PayloadConflictError as exc:
        return web.json_response(
            {
                "error": "payload_conflict",
                "message": str(exc),
                "existing_batch_id": str(exc.batch_id),
                "existing_payload_hash": exc.existing_hash,
            },
            status=409,
        )
    except ValidationError as exc:
        return web.json_response({"error": str(exc)}, status=400)
    except Exception:  # noqa: BLE001 - surface as API error
        self.service.total_errors += 1
        return web.json_response({"error": "Internal server error"}, status=500)
