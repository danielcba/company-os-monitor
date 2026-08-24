"""HTTP surface for the API Gateway (Cognitive Boundary enforcement, R3).

Public: /health, /metrics. Everything under /api/v1 requires a Bearer token
issued by the user-service. Routes:

- ``GET  /health``          forward to pipeline /health (any role)
- ``GET  /metrics``         forward to pipeline metrics (any role)
- ``GET  /api/v1/services/health``          forward to pipeline /health (any role)
- ``GET  /api/v1/tenants/{tenant_id}/decisions``  READ decisions, tenant scope
- ``GET  /api/v1/tenants/{tenant_id}/reports``    READ reports, tenant scope
- ``GET  /api/v1/tenants/{tenant_id}/observations``  READ observations, tenant scope
- ``GET  /api/v1/tenants/{tenant_id}/cognitive/summary``  READ cognitive summary, tenant scope
- ``POST /api/v1/actions/{action}``         validate action authority + boundary

The action endpoint NEVER executes the action (the canonical cycle in each
service is the only executor): it is the authority/boundary validation point
(R3, R4, R5) that an external capability would call to trigger a future
execution. 401 = no/invalid token, 403 = authenticated but no authority,
400 = boundary violation (e.g. missing Confidence, R4) or invalid query params.
"""

import os
import uuid
from typing import Any

from aiohttp import web
from aiohttp_cors import ResourceOptions
from aiohttp_cors import setup as cors_setup
from libs.access.errors import (
    AccessError,
    InvalidTokenError,
)
from libs.access.rbac import RISK_TOLERANCES
from libs.access.security import JwtService, TokenPayload

from src.boundary import BoundaryViolationError
from src.constants import VALID_ACTIONS, VALID_COGNITIVE_CONCEPTS, VALID_COGNITIVE_LAYERS
from src.decisions import DecisionNotFoundError, InvalidOutcomesError
from src.observations import VALID_QUALITY_CLASSES
from src.service import GatewayService

VALID_SORTS = {"captured_at_desc", "captured_at_asc"}
AUDIT_VALID_SORTS = {"timestamp_desc", "timestamp_asc"}
INSIGHT_VALID_SORTS = {"generated_at_desc", "generated_at_asc"}
MAX_LIMIT = 200
MIN_LIMIT = 1


def _is_validation_error(err_msg: str) -> bool:
    """Check if AccessError is a validation error (400) vs auth error (403)."""
    return any(kw in err_msg for kw in ("Invalid", "must be", "must be between"))


class GatewayServer:
    def __init__(self, service: GatewayService, jwt: JwtService):
        self.service = service
        self.jwt = jwt
        self.app = web.Application()
        self._setup_cors()
        # Add security headers middleware.
        from libs.shared.security_headers import security_headers_middleware
        self.app.middlewares.append(security_headers_middleware())
        self.app.router.add_get("/health", self.health_handler)
        self.app.router.add_get("/metrics", self.metrics_handler)
        self.app.router.add_get(
            "/api/v1/services/health", self.services_health_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/decisions", self.decisions_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/decisions/{decision_id}", self.decision_detail_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/reports", self.reports_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/observations", self.observations_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/cognitive/summary", self.cognitive_summary_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/audit", self.audit_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/insights", self.insights_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/insights/{insight_id}", self.insight_detail_handler
        )
        self.app.router.add_get(
            "/api/v1/tenants/{tenant_id}/recommendations/{recommendation_id}", self.recommendation_detail_handler
        )
        self.app.router.add_post(
            "/api/v1/tenants/{tenant_id}/decisions/{decision_id}/outcomes", self.decision_outcomes_handler
        )
        self.app.router.add_post("/api/v1/actions/{action}", self.action_handler)
        self.runner = None

    def _setup_cors(self) -> None:
        allowed_origins = [
            o.strip()
            for o in os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:5173").split(",")
            if o.strip()
        ]
        cors = cors_setup(
            self.app,
            defaults={
                origin: ResourceOptions(
                    allow_credentials=True,
                    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                    allow_headers=["Authorization", "Content-Type"],
                    expose_headers=["Authorization"],
                )
                for origin in allowed_origins
            },
        )
        for route in self.app.router.routes():
            cors.add(route)

    async def start(self, port: int = 8100):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", port)
        await site.start()

    async def stop(self) -> None:
        if self.runner is not None:
            await self.runner.cleanup()

    async def health_handler(self, request):
        return web.json_response({
            "status": "healthy" if self.service.total_errors == 0 else "degraded",
            "requests": self.service.total_requests,
            "rejected_401": self.service.total_rejected_401,
            "rejected_403": self.service.total_rejected_403,
            "errors": self.service.total_errors,
        })

    async def metrics_handler(self, request):
        return web.json_response(self.service.metrics())

    async def services_health_handler(self, request):
        try:
            await self._authenticate(request)  # enforce auth (401 if invalid)
            self.service.record(action="read:services_health")
            results = await self.service.check_service_health()
            return web.json_response({"services": results})
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def _validate_tenant_id(self, tenant_id: str) -> str:
        """Validate tenant_id is a proper UUID, return normalized str or raise."""
        try:
            import uuid
            uuid.UUID(tenant_id)
        except ValueError:
            raise AccessError("Invalid tenant_id format")
        return tenant_id

    async def _validate_uuid(self, value: str, field_name: str) -> str:
        """Validate a UUID field, return normalized str or raise."""
        try:
            import uuid
            uuid.UUID(value)
        except ValueError:
            raise AccessError(f"Invalid {field_name} format")
        return value

    async def _parse_observations_query(self, query) -> dict[str, Any]:
        """Parse and validate observations query parameters."""
        try:
            limit = int(query.get("limit", "50"))
        except ValueError:
            raise AccessError("Invalid limit parameter")
        if limit < MIN_LIMIT or limit > MAX_LIMIT:
            raise AccessError(f"limit must be between {MIN_LIMIT} and {MAX_LIMIT}")

        try:
            offset = int(query.get("offset", "0"))
        except ValueError:
            raise AccessError("Invalid offset parameter")
        if offset < 0:
            raise AccessError("offset must be non-negative")

        fact_type = query.get("fact_type")
        source_type = query.get("source_type")
        quality_class = query.get("quality_class")
        if quality_class and quality_class not in VALID_QUALITY_CLASSES:
            raise AccessError(f"Invalid quality_class: {quality_class}")

        sort = query.get("sort", "captured_at_desc")
        if sort not in VALID_SORTS:
            raise AccessError(f"Invalid sort: {sort}")

        return {
            "limit": limit,
            "offset": offset,
            "fact_type": fact_type,
            "source_type": source_type,
            "quality_class": quality_class,
            "sort": sort,
        }

    async def decisions_handler(self, request):
        try:
            token = await self._authenticate(request)
            self.service.record(action="read:decisions")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            decisions = await self.service.list_decisions(token, tenant_id)
            return web.json_response({"decisions": decisions})
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def reports_handler(self, request):
        try:
            token = await self._authenticate(request)
            self.service.record(action="read:reports")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            reports = await self.service.list_reports(token, tenant_id)
            return web.json_response({"reports": reports})
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def observations_handler(self, request):
        try:
            token = await self._authenticate(request)
            self.service.record(action="read:observations")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            query_params = await self._parse_observations_query(request.query)
            observations = await self.service.list_observations(token, tenant_id, **query_params)
            return web.json_response(observations)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            status = 400 if _is_validation_error(str(exc)) else 403
            return web.json_response({"error": str(exc)}, status=status)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def cognitive_summary_handler(self, request):
        try:
            token = await self._authenticate(request)
            self.service.record(action="read:cognitive_summary")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            summary = await self.service.cognitive_summary(tenant_id=tenant_id)
            return web.json_response(summary)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def audit_handler(self, request):
        try:
            token = await self._authenticate(request)
            self.service.record(action="read:audit")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            query = request.query
            try:
                limit = int(query.get("limit", "50"))
            except ValueError:
                raise AccessError("Invalid limit parameter")
            if limit < 1 or limit > 200:
                raise AccessError("limit must be between 1 and 200")
            try:
                offset = int(query.get("offset", "0"))
            except ValueError:
                raise AccessError("Invalid offset parameter")
            if offset < 0:
                raise AccessError("offset must be non-negative")

            sort = query.get("sort", "timestamp_desc")
            if sort not in AUDIT_VALID_SORTS:
                raise AccessError(f"Invalid sort: {sort}")

            cognitive_layer = query.get("cognitive_layer")
            if cognitive_layer and cognitive_layer not in VALID_COGNITIVE_LAYERS:
                raise AccessError(f"Invalid cognitive_layer: {cognitive_layer}")
            cognitive_concept = query.get("cognitive_concept")
            if cognitive_concept and cognitive_concept not in VALID_COGNITIVE_CONCEPTS:
                raise AccessError(f"Invalid cognitive_concept: {cognitive_concept}")
            action_filter = query.get("action")
            if action_filter and action_filter not in VALID_ACTIONS:
                raise AccessError(f"Invalid action: {action_filter}")

            user_id = query.get("user_id")
            if user_id:
                try:
                    uuid.UUID(user_id)
                except ValueError:
                    raise AccessError("Invalid user_id format")

            date_from = query.get("date_from")
            if date_from:
                try:
                    _dt = __import__("datetime").datetime
                    _dt.fromisoformat(date_from)
                except ValueError:
                    raise AccessError("Invalid date_from format, use ISO 8601")

            date_to = query.get("date_to")
            if date_to:
                try:
                    _dt = __import__("datetime").datetime
                    _dt.fromisoformat(date_to)
                except ValueError:
                    raise AccessError("Invalid date_to format, use ISO 8601")

            result = await self.service.list_audit_logs(
                token=token,
                tenant_id=tenant_id,
                limit=limit,
                offset=offset,
                user_id=user_id,
                cognitive_layer=cognitive_layer,
                cognitive_concept=cognitive_concept,
                action=action_filter,
                date_from=date_from,
                date_to=date_to,
                sort=sort,
            )
            return web.json_response(result)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            status = 400 if _is_validation_error(str(exc)) else 403
            return web.json_response({"error": str(exc)}, status=status)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def insights_handler(self, request):
        try:
            token = await self._authenticate(request)
            self.service.record(action="read:insights")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            query = request.query
            try:
                limit = int(query.get("limit", "50"))
            except ValueError:
                raise AccessError("Invalid limit parameter")
            if limit < 1 or limit > 200:
                raise AccessError("limit must be between 1 and 200")
            try:
                offset = int(query.get("offset", "0"))
            except ValueError:
                raise AccessError("Invalid offset parameter")
            if offset < 0:
                raise AccessError("offset must be non-negative")

            sort = query.get("sort", "generated_at_desc")
            if sort not in INSIGHT_VALID_SORTS:
                raise AccessError(f"Invalid sort: {sort}")

            result = await self.service.list_insights(
                token=token,
                tenant_id=tenant_id,
                limit=limit,
                offset=offset,
                sort=sort,
            )
            return web.json_response(result)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            status = 400 if _is_validation_error(str(exc)) else 403
            return web.json_response({"error": str(exc)}, status=status)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def insight_detail_handler(self, request):
        try:
            token = await self._authenticate(request)
            self.service.record(action="read:insight_detail")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            insight_id = await self._validate_uuid(request.match_info["insight_id"], "insight_id")
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            result = await self.service.get_insight(token, tenant_id, insight_id)
            if result is None:
                return web.json_response({"error": "Insight not found"}, status=404)
            return web.json_response(result)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=400 if _is_validation_error(str(exc)) else 403)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def decision_detail_handler(self, request):
        try:
            token = await self._authenticate(request)
            self.service.record(action="read:decision_detail")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            decision_id = await self._validate_uuid(request.match_info["decision_id"], "decision_id")
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            result = await self.service.get_decision(token, tenant_id, decision_id)
            if result is None:
                return web.json_response({"error": "Decision not found"}, status=404)
            return web.json_response(result)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=400 if _is_validation_error(str(exc)) else 403)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def recommendation_detail_handler(self, request):
        try:
            token = await self._authenticate(request)
            self.service.record(action="read:recommendation_detail")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            recommendation_id = await self._validate_uuid(request.match_info["recommendation_id"], "recommendation_id")
            self.service.require_authorized(
                token=token, action="read", requested_tenant_id=tenant_id
            )
            result = await self.service.get_recommendation(token, tenant_id, recommendation_id)
            if result is None:
                return web.json_response({"error": "Recommendation not found"}, status=404)
            return web.json_response(result)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=400 if _is_validation_error(str(exc)) else 403)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def decision_outcomes_handler(self, request):
        """Submit actual outcomes for a decision (lifecycle update, P1 allows)."""
        try:
            token = await self._authenticate(request)
            self.service.record(action="write:decision_outcomes")
            tenant_id = await self._validate_tenant_id(request.match_info["tenant_id"])
            decision_id = await self._validate_uuid(request.match_info["decision_id"], "decision_id")
            self.service.require_authorized(
                token=token, action="commit", requested_tenant_id=tenant_id
            )
            body = await request.json()
            actual_outcomes = body.get("actual_outcomes", [])
            executed_at_str = body.get("executed_at")

            from datetime import datetime as _dt

            executed_at = _dt.fromisoformat(executed_at_str) if executed_at_str else None

            result = await self.service.submit_decision_outcomes(
                token=token,
                tenant_id=tenant_id,
                decision_id=decision_id,
                actual_outcomes=actual_outcomes,
                executed_at=executed_at,
            )
            return web.json_response(result, status=200)
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except InvalidOutcomesError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except DecisionNotFoundError as exc:
            return web.json_response({"error": str(exc)}, status=404)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=500)

    async def action_handler(self, request):
        """Validate an action against authority + boundary (never executes).

        Body may carry ``confidence_id``/``confidence_score`` (R4 for
        propose/commit), ``risk_tolerance`` (commit ceiling) and an optional
        ``tenant_id`` (cross-tenant requires superadmin).

        R4 enforcement: for propose/commit actions, the confidence_id is
        verified against the confidence store (provenance check). The client's
        confidence_score is IGNORED — the store provides the authoritative score.
        """
        try:
            token = await self._authenticate(request)
            action = request.match_info["action"]
            payload = await request.json()
            self.service.record(action=action)

            self.service.enforce_boundary(action, payload)
            risk = payload.get("risk_tolerance", "low")
            if action == "commit" and risk not in RISK_TOLERANCES:
                return web.json_response(
                    {"error": f"unknown risk_tolerance: {risk!r}"}, status=400
                )
            requested_tenant_id = payload.get("tenant_id")
            self.service.require_authorized(
                token=token,
                action=action,
                risk=risk if action == "commit" else None,
                requested_tenant_id=requested_tenant_id,
            )
            # R4: verify confidence provenance for propose/commit actions.
            confidence_verified = None
            if action in ("propose", "commit") and payload.get("confidence_id"):
                tenant_for_confidence = requested_tenant_id or token.tenant_id
                provenance = await self.service.verify_confidence_provenance(
                    tenant_id=tenant_for_confidence,
                    confidence_id=payload["confidence_id"],
                    expected_target_type=payload.get("target_type", "hypothesis"),
                    expected_target_id=payload.get("target_id"),
                )
                confidence_verified = provenance.get("verified", False)
            return web.json_response(
                {
                    "authorized": True,
                    "action": action,
                    "authority": {
                        "user_id": token.user_id,
                        "role": token.role,
                        "tenant_id": token.tenant_id,
                    },
                    "confidence_verified": confidence_verified,
                    "note": (
                        "validated by the Cognitive Boundary (R3); execution "
                        "happens in the canonical service cycle, not here"
                    ),
                }
            )
        except InvalidTokenError as exc:
            return web.json_response({"error": str(exc)}, status=401)
        except BoundaryViolationError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        except AccessError as exc:
            return web.json_response({"error": str(exc)}, status=403)
        except Exception:  # noqa: BLE001 - surface as API error
            self.service.total_errors += 1
            return web.json_response({"error": "Internal server error"}, status=400)

    async def _authenticate(self, request) -> TokenPayload:
        """Verify the Bearer token -> identity + authority + tenant claims."""
        return await self.service.authenticate(request.headers.get("Authorization", ""))
