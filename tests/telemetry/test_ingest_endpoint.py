"""H4.0-B2 — Ingest Endpoint Unit Tests.

Tests the ingest_handler logic by mocking dependencies.
Does NOT require a running database or aiohttp test client.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from libs.telemetry.ingest_service import IngestResult


def _mock_gateway_server() -> MagicMock:
    """Create a mock GatewayServer with required attributes."""
    server = MagicMock()
    server.jwt = MagicMock()
    server.machine_jwt = MagicMock()
    server.service = MagicMock()
    server.service.blacklist = AsyncMock()
    server.service.blacklist.is_revoked = AsyncMock(return_value=False)
    server.service._dsn = "postgresql://test"
    server.service.total_errors = 0
    return server


def _mock_request(
    auth_header: str = "Bearer test-token",
    json_body: dict | None = None,
    json_error: bool = False,
) -> MagicMock:
    """Create a mock aiohttp Request."""
    request = MagicMock()
    request.headers = {"Authorization": auth_header}
    if json_error:
        request.json = AsyncMock(side_effect=Exception("invalid JSON"))
    elif json_body is not None:
        request.json = AsyncMock(return_value=json_body)
    else:
        request.json = AsyncMock(return_value={
            "batch_id": str(uuid.uuid4()),
            "captured_at": datetime.now(UTC).isoformat(),
            "samples": [
                {
                    "sequence": 1,
                    "fact_type": "cpu_utilization_percent",
                    "fact_value": {"value": 45.2},
                    "unit": "percent",
                    "labels": {},
                }
            ],
        })
    return request


class TestIngestHandlerAuth:
    """Authentication validation in ingest_handler."""

    @pytest.mark.asyncio
    async def test_missing_auth_header(self) -> None:
        from src.ingest import ingest_handler

        server = _mock_gateway_server()
        request = _mock_request(auth_header="")
        response = await ingest_handler(server, request)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_invalid_token(self) -> None:
        from src.ingest import ingest_handler
        from libs.access.errors import InvalidTokenError

        server = _mock_gateway_server()
        server.machine_jwt.decode = MagicMock(side_effect=InvalidTokenError("bad token"))
        request = _mock_request()
        response = await ingest_handler(server, request)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_non_machine_token(self) -> None:
        from src.ingest import ingest_handler

        server = _mock_gateway_server()
        server.machine_jwt.decode = MagicMock(return_value={"token_type": "access"})
        request = _mock_request()
        response = await ingest_handler(server, request)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_missing_claims(self) -> None:
        from src.ingest import ingest_handler

        server = _mock_gateway_server()
        server.machine_jwt.decode = MagicMock(return_value={
            "token_type": "machine_access",
            "tenant_id": str(uuid.uuid4()),
        })
        request = _mock_request()
        response = await ingest_handler(server, request)
        assert response.status == 401

    @pytest.mark.asyncio
    async def test_revoked_token(self) -> None:
        from src.ingest import ingest_handler

        server = _mock_gateway_server()
        server.machine_jwt.decode = MagicMock(return_value={
            "token_type": "machine_access",
            "tenant_id": str(uuid.uuid4()),
            "installation_id": str(uuid.uuid4()),
            "instance_id": str(uuid.uuid4()),
            "sub": str(uuid.uuid4()),
            "jti": "test-jti",
        })
        server.service.blacklist.is_revoked = AsyncMock(return_value=True)
        request = _mock_request()
        response = await ingest_handler(server, request)
        assert response.status == 401


class TestIngestHandlerMalformedJson:
    """JSON parsing validation."""

    @pytest.mark.asyncio
    async def test_malformed_json(self) -> None:
        from src.ingest import ingest_handler

        server = _mock_gateway_server()
        server.machine_jwt.decode = MagicMock(return_value={
            "token_type": "machine_access",
            "tenant_id": str(uuid.uuid4()),
            "installation_id": str(uuid.uuid4()),
            "instance_id": str(uuid.uuid4()),
            "sub": str(uuid.uuid4()),
        })
        request = _mock_request(json_error=True)
        response = await ingest_handler(server, request)
        assert response.status == 400


class TestIngestHandlerSuccess:
    """Successful ingestion returns 202."""

    @pytest.mark.asyncio
    async def test_successful_ingestion(self) -> None:
        from src.ingest import ingest_handler

        server = _mock_gateway_server()
        server.machine_jwt.decode = MagicMock(return_value={
            "token_type": "machine_access",
            "tenant_id": str(uuid.uuid4()),
            "installation_id": str(uuid.uuid4()),
            "instance_id": str(uuid.uuid4()),
            "sub": str(uuid.uuid4()),
        })

        obs_id = uuid.uuid4()
        result = IngestResult(
            batch_id=uuid.uuid4(),
            observation_ids=[obs_id],
            ingested_at=datetime.now(UTC),
        )

        with patch("libs.telemetry.ingest_service.TelemetryIngestService") as MockSvc:
            mock_instance = MockSvc.return_value
            mock_instance.ingest_batch = AsyncMock(return_value=result)
            request = _mock_request()
            response = await ingest_handler(server, request)

        assert response.status == 202
        import json
        body = json.loads(response.body)
        assert body["status"] == "accepted"
        assert len(body["observation_ids"]) == 1


class TestIngestHandlerConflict:
    """Conflict detection returns 409."""

    @pytest.mark.asyncio
    async def test_payload_conflict(self) -> None:
        from src.ingest import ingest_handler
        from libs.telemetry.ingest_service import PayloadConflictError

        server = _mock_gateway_server()
        server.machine_jwt.decode = MagicMock(return_value={
            "token_type": "machine_access",
            "tenant_id": str(uuid.uuid4()),
            "installation_id": str(uuid.uuid4()),
            "instance_id": str(uuid.uuid4()),
            "sub": str(uuid.uuid4()),
        })

        batch_id = uuid.uuid4()
        with patch("libs.telemetry.ingest_service.TelemetryIngestService") as MockSvc:
            mock_instance = MockSvc.return_value
            mock_instance.ingest_batch = AsyncMock(
                side_effect=PayloadConflictError(batch_id, "abc123hash")
            )
            request = _mock_request()
            response = await ingest_handler(server, request)

        assert response.status == 409
        import json
        body = json.loads(response.body)
        assert body["error"] == "payload_conflict"


class TestIngestHandlerValidation:
    """Validation errors return 400."""

    @pytest.mark.asyncio
    async def test_validation_error(self) -> None:
        from src.ingest import ingest_handler
        from libs.telemetry.ingest_service import ValidationError

        server = _mock_gateway_server()
        server.machine_jwt.decode = MagicMock(return_value={
            "token_type": "machine_access",
            "tenant_id": str(uuid.uuid4()),
            "installation_id": str(uuid.uuid4()),
            "instance_id": str(uuid.uuid4()),
            "sub": str(uuid.uuid4()),
        })

        with patch("libs.telemetry.ingest_service.TelemetryIngestService") as MockSvc:
            mock_instance = MockSvc.return_value
            mock_instance.ingest_batch = AsyncMock(
                side_effect=ValidationError("samples must be a non-empty array")
            )
            request = _mock_request()
            response = await ingest_handler(server, request)

        assert response.status == 400
