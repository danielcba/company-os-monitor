"""GatewayService - validates authority and enforces the Cognitive Boundary.

External non-canonical capability (ADR-0002). It is the R3 enforcement point:

- ``authenticate`` verifies the JWT issued by the user-service (identity +
  Decision Authority role + tenant scope), checking the Redis blacklist for
  revoked tokens.
- ``authorize_action`` decides whether the token's role may execute an action
  (RBAC -> Decision Authority binding, docs/04), including the risk ceiling for
  COMMIT and the cross-tenant authority for superadmin.
- ``check_boundary`` applies the structural Cognitive Boundary rules (R3) and
  the Confidence requirement (R4).
- READ routes expose pipeline data (decisions/reports) strictly within the
  token's tenant scope.
- ``check_service_health`` forwards to the pipeline services' /health.

It NEVER reimplements cognitive logic and NEVER executes actions: it validates
authority and routes (the canonical cycles in each service keep running as-is).
"""
import uuid
from collections import Counter
from datetime import UTC, datetime
from typing import Any, Protocol

import httpx
from libs.access.errors import (
    AuthorizationError,
    InvalidTokenError,
)
from libs.access.rbac import (
    PERM_COMMIT,
    can,
    commit_allowed,
    cross_tenant_allowed,
)
from libs.access.security import JwtService, TokenPayload
from libs.access.tenant_scope import AuthorizationContext, TenantScopeError
from libs.access.token_blacklist import SecurityControlUnavailable, TokenBlacklist
from libs.memory.cognitive_timeline import CognitiveTimelineStoreProtocol
from libs.memory.consolidation import (
    ConsolidationReport,
    ConsolidationStoreProtocol,
)
from libs.memory.context_revision import (
    ContextRevisionReport,
    ContextRevisionStoreProtocol,
)
from libs.memory.insight_transformation import (
    InsightTransformationReport,
    InsightTransformationStoreProtocol,
)
from libs.memory.learning_loop import (
    LearningLoopStoreProtocol,
)
from libs.memory.memory_ledger import (
    LearningMemoryRecord,
    MemoryStoreProtocol,
    PersistLearningMemoryInput,
)
from libs.memory.pattern_refinement import (
    PatternRefinementReport,
    PatternRefinementStoreProtocol,
)

from src.boundary import (
    ACTION_PERMISSION,
    ACTIONS,
    ConfidenceStoreAdapter,
    check_boundary,
    validate_confidence_binding,
)
from src.summary import CognitiveSummaryStore


class CognitiveTraceStoreProtocol(Protocol):
    """Structural type for the Cognitive Trace read model (read contract)."""

    async def get_trace(
        self, *, tenant_id: uuid.UUID, report_id: uuid.UUID
    ) -> dict[str, Any] | None:
        """Build the Cognitive Trace for ``report_id`` within ``tenant_id``."""
        ...

# Default pipeline service health targets (canonical ports; override via env).
# In production, override via GATEWAY_SERVICE_HEALTH env var:
#   GATEWAY_SERVICE_HEALTH=collector=http://collector:8090/health,context=http://context:8091/health,...
DEFAULT_SERVICE_HEALTH: dict[str, str] = {
    "collector": "http://localhost:8090/health",
    "context": "http://localhost:8091/health",
    "pattern": "http://localhost:8092/health",
    "anomaly": "http://localhost:8093/health",
    "hypothesis": "http://localhost:8094/health",
    "confidence": "http://localhost:8095/health",
    "recommendation": "http://localhost:8096/health",
    "decision": "http://localhost:8097/health",
    "report": "http://localhost:8098/health",
    "user": "http://localhost:8099/health",
}


class GatewayService:
    def __init__(
        self,
        jwt: JwtService,
        decision_store=None,
        report_store=None,
        observation_store=None,
        cognitive_summary_store=None,
        audit_store=None,
        insight_store=None,
        decision_read_store=None,
        recommendation_read_store=None,
        service_health: dict[str, str] | None = None,
        dsn: str | None = None,
        blacklist: TokenBlacklist | None = None,
        confidence_store: ConfidenceStoreAdapter | None = None,
        cognitive_trace_store: CognitiveTraceStoreProtocol | None = None,
        consolidation_store: ConsolidationStoreProtocol | None = None,
        pattern_refinement_store: PatternRefinementStoreProtocol | None = None,
        context_revision_store: ContextRevisionStoreProtocol | None = None,
        insight_transformation_store: InsightTransformationStoreProtocol | None = None,
        memory_store: MemoryStoreProtocol | None = None,
        timeline_store: CognitiveTimelineStoreProtocol | None = None,
        learning_loop_store: LearningLoopStoreProtocol | None = None,
    ):
        self.jwt = jwt
        self.decision_store = decision_store
        self.report_store = report_store
        self._observation_store = observation_store
        self._cognitive_summary_store = cognitive_summary_store
        self._audit_store = audit_store
        self._insight_store = insight_store
        self._decision_read_store = decision_read_store
        self._recommendation_read_store = recommendation_read_store
        self._cognitive_trace_store: CognitiveTraceStoreProtocol | None = (
            cognitive_trace_store
        )
        self._consolidation_store: ConsolidationStoreProtocol | None = (
            consolidation_store
        )
        self._pattern_refinement_store: PatternRefinementStoreProtocol | None = (
            pattern_refinement_store
        )
        self._context_revision_store: ContextRevisionStoreProtocol | None = (
            context_revision_store
        )
        self._insight_transformation_store: InsightTransformationStoreProtocol | None = (
            insight_transformation_store
        )
        self._memory_store: MemoryStoreProtocol | None = memory_store
        self._timeline_store: CognitiveTimelineStoreProtocol | None = timeline_store
        self._learning_loop_store: LearningLoopStoreProtocol | None = (
            learning_loop_store
        )
        self._dsn = dsn
        self.service_health = service_health or dict(DEFAULT_SERVICE_HEALTH)
        self.blacklist = blacklist
        self._confidence_store = confidence_store
        self.total_requests = 0
        self.total_rejected_401 = 0
        self.total_rejected_403 = 0
        self.total_boundary_violations = 0
        self.total_forwarded = 0
        self.total_errors = 0
        self.by_action: Counter[str] = Counter()
        self.last_request_at: datetime | None = None

    # ------------------------------------------------------------------ auth
    async def authenticate(self, authorization_header: str) -> TokenPayload:
        """Verify the Bearer token -> identity + authority + tenant claims.

        Checks the Redis blacklist for revoked tokens before verifying the
        signature. If the token's jti is blacklisted, it is rejected even
        if the signature and expiry are valid.

        Phase 3: Redis unavailability during blacklist check is FAIL-CLOSED
        for this security-critical operation — the token is rejected.
        """
        if not authorization_header.lower().startswith("bearer "):
            self.total_rejected_401 += 1
            raise InvalidTokenError("missing bearer token")
        token = authorization_header.split(" ", 1)[1].strip()
        try:
            payload = self.jwt.verify_access_token(token)
            if self.blacklist and payload.jti:
                is_revoked = await self.blacklist.is_revoked(jti=payload.jti)
                if is_revoked:
                    self.total_rejected_401 += 1
                    raise InvalidTokenError("token has been revoked")
            return payload
        except SecurityControlUnavailable:
            # Redis down during security-critical check — fail closed.
            self.total_rejected_401 += 1
            raise InvalidTokenError(
                "security control unavailable; token cannot be verified"
            )
        except InvalidTokenError:
            self.total_rejected_401 += 1
            raise

    # -------------------------------------------------------------- authorize
    def authorize_action(
        self,
        *,
        token: TokenPayload,
        action: str,
        risk: str | None = None,
        requested_tenant_id: str | None = None,
    ) -> bool:
        """Decision Authority check for an action on the canonical flow.

        Pure RBAC -> authority binding (docs/04). COMMIT is constrained by the
        risk ceiling (admin low/medium, superadmin high); cross-tenant requests
        require superadmin authority.
        """
        if action not in ACTIONS:
            raise ValueError(f"unknown action: {action!r}")
        permission = ACTION_PERMISSION[action]
        if permission == PERM_COMMIT:
            allowed = commit_allowed(token.role, risk)
        else:
            allowed = can(token.role, permission)
        if not allowed:
            return False
        if requested_tenant_id and str(requested_tenant_id) != token.tenant_id:
            return cross_tenant_allowed(token.role)
        return True

    def require_authorized(
        self,
        *,
        token: TokenPayload,
        action: str,
        risk: str | None = None,
        requested_tenant_id: str | None = None,
    ) -> None:
        """Raise AuthorizationError (-> 403) when the action is not authorized."""
        if not self.authorize_action(
            token=token,
            action=action,
            risk=risk,
            requested_tenant_id=requested_tenant_id,
        ):
            self.total_rejected_403 += 1
            raise AuthorizationError(
                f"role {token.role!r} lacks Decision Authority for action "
                f"{action!r}"
            )

    # -------------------------------------------------------------- boundary
    def enforce_boundary(self, action: str, payload: dict[str, Any] | None) -> None:
        """Structural boundary (R3) + Confidence requirement (R4)."""
        try:
            check_boundary(action, payload)
        except Exception:
            self.total_boundary_violations += 1
            raise

    async def verify_confidence_provenance(
        self,
        *,
        tenant_id: str,
        confidence_id: str,
        expected_target_type: str,
        expected_target_id: str | None = None,
    ) -> dict[str, Any]:
        """R4: verify confidence against the store (provenance check).

        The client's confidence_score is IGNORED — the store provides the
        authoritative record. Raises SecurityControlUnavailable if the
        confidence store is not configured (fail-closed).
        """
        if self._confidence_store is None:
            raise SecurityControlUnavailable(
                "confidence store not configured; "
                "cannot verify confidence provenance (fail-closed)"
            )
        return await validate_confidence_binding(
            store=self._confidence_store,
            tenant_id=tenant_id,
            confidence_id=confidence_id,
            expected_target_type=expected_target_type,
            expected_target_id=expected_target_id,
        )

    # -------------------------------------------------------------- tenant
    def _resolve_tenant(
        self, token: TokenPayload, requested_tenant_id: str
    ) -> AuthorizationContext:
        """Create AuthorizationContext and resolve effective tenant (single
        source of truth for all tenant-scoped operations).

        The token's tenant_id is the authority; cross-tenant access requires
        superadmin. Returns the resolved context with effective_tenant_id set.
        """
        ctx = AuthorizationContext.from_token_payload(token)
        try:
            ctx.effective_tenant_id = ctx.resolve(requested_tenant_id)
        except TenantScopeError:
            self.total_rejected_403 += 1
            raise
        return ctx

    def ensure_tenant_access(
        self, token: TokenPayload, requested_tenant_id: str
    ) -> None:
        """Multi-tenant isolation: a token may only read its own tenant unless
        it holds cross-tenant authority (superadmin)."""
        self._resolve_tenant(token, requested_tenant_id)

    # ---------------------------------------------------------------- reads
    async def list_decisions(self, token: TokenPayload, tenant_id: str) -> list[Any]:
        """READ decisions within the token's tenant scope (viewer+)."""
        if self.decision_store is None:
            raise RuntimeError("decision_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        decisions = await self.decision_store.list_decisions(
            tenant_id=uuid.UUID(ctx.effective_tenant_id)
        )
        return [_decision_payload(d) for d in decisions]

    async def list_reports(self, token: TokenPayload, tenant_id: str) -> list[Any]:
        """READ reports within the token's tenant scope (viewer+)."""
        if self.report_store is None:
            raise RuntimeError("report_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        reports = await self.report_store.list_reports(
            tenant_id=uuid.UUID(ctx.effective_tenant_id)
        )
        return [_report_payload(r) for r in reports]

    async def list_audit_logs(
        self,
        token: TokenPayload,
        tenant_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        user_id: str | None = None,
        cognitive_layer: str | None = None,
        cognitive_concept: str | None = None,
        action: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        sort: str = "timestamp_desc",
    ) -> dict[str, Any]:
        """READ audit log entries within the token's tenant scope (viewer+)."""
        if self._audit_store is None:
            raise RuntimeError("audit_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        return await self._audit_store.list_audit_logs(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
            limit=limit,
            offset=offset,
            user_id=user_id,
            cognitive_layer=cognitive_layer,
            cognitive_concept=cognitive_concept,
            action=action,
            date_from=date_from,
            date_to=date_to,
            sort=sort,
        )

    async def list_insights(
        self,
        token: TokenPayload,
        tenant_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        sort: str = "generated_at_desc",
    ) -> dict[str, Any]:
        """READ insights within the token's tenant scope (viewer+)."""
        if self._insight_store is None:
            raise RuntimeError("insight_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        return await self._insight_store.list_insights(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
            limit=limit,
            offset=offset,
            sort=sort,
        )

    async def get_insight(
        self,
        token: TokenPayload,
        tenant_id: str,
        insight_id: str,
    ) -> dict[str, Any] | None:
        """READ one insight with its desglose within the token's tenant scope (viewer+)."""
        if self._insight_store is None:
            raise RuntimeError("insight_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        return await self._insight_store.get_insight(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
            insight_id=uuid.UUID(insight_id),
        )

    async def get_decision(
        self,
        token: TokenPayload,
        tenant_id: str,
        decision_id: str,
    ) -> dict[str, Any] | None:
        """READ one decision with its desglose within the token's tenant scope (viewer+)."""
        if self._decision_read_store is None:
            raise RuntimeError("decision_read_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        return await self._decision_read_store.get_decision(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
            decision_id=uuid.UUID(decision_id),
        )

    async def get_recommendation(
        self,
        token: TokenPayload,
        tenant_id: str,
        recommendation_id: str,
    ) -> dict[str, Any] | None:
        """READ one recommendation with its desglose within the token's tenant scope (viewer+)."""
        if self._recommendation_read_store is None:
            raise RuntimeError("recommendation_read_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        return await self._recommendation_read_store.get_recommendation(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
            recommendation_id=uuid.UUID(recommendation_id),
        )

    async def submit_decision_outcomes(
        self,
        token: TokenPayload,
        tenant_id: str,
        decision_id: str,
        actual_outcomes: list[dict[str, Any]],
        executed_at=None,
    ) -> dict[str, Any]:
        """Submit actual outcomes for a decision (lifecycle update, P1 allows).

        After persisting the outcomes, automatically runs the P7 Learning Loop:
        Consolidation → Pattern Refinement → Context Revision → Insight
        Transformation → Memory Ledger persistence.
        """
        if self._decision_read_store is None:
            raise RuntimeError("decision_read_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        result = await self._decision_read_store.submit_outcomes(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
            decision_id=uuid.UUID(decision_id),
            actual_outcomes=actual_outcomes,
            executed_at=executed_at,
        )

        # Run the automatic Learning Loop (P7) if configured
        if self._learning_loop_store is not None:
            try:
                loop_result = await self._learning_loop_store.run_for_decision(
                    tenant_id=uuid.UUID(ctx.effective_tenant_id),
                    decision_id=uuid.UUID(decision_id),
                )
                result["learning_loop"] = {
                    "consolidation_feedback": loop_result.consolidation.calibration_feedback,
                    "brier": loop_result.consolidation.brier,
                    "ece": loop_result.consolidation.ece,
                    "patterns_refined": len(loop_result.pattern_refinement.results),
                    "contexts_revised": len(loop_result.context_revision.results),
                    "insights_transformed": len(loop_result.insight_transformation.results),
                    "persisted_signals": len(loop_result.persisted),
                }
            except Exception:
                # Learning loop is best-effort; log but don't fail the outcome submission
                import logging

                logging.getLogger(__name__).exception(
                    "Learning loop failed for decision %s", decision_id
                )

        return result

    async def get_cognitive_trace(
        self,
        token: TokenPayload,
        tenant_id: str,
        report_id: str,
    ) -> dict[str, Any] | None:
        """READ the Cognitive Trace for a Report within the token's tenant scope."""
        if self._cognitive_trace_store is None:
            raise RuntimeError("cognitive_trace_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        return await self._cognitive_trace_store.get_trace(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
            report_id=uuid.UUID(report_id),
        )

    async def get_cognitive_timeline(
        self,
        token: TokenPayload,
        tenant_id: str,
        limit_per_concept: int = 20,
        ascending: bool = False,
    ) -> dict[str, Any]:
        """READ the Cognitive Timeline (Investigation) for the tenant scope.

        External read/compute capability (ADR-0002): reconstructs the temporal
        sequence of cognitive events from the canonical read stores. It never
        fabricates events (P1) and creates no new entity.
        """
        if self._timeline_store is None:
            raise RuntimeError("timeline_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        report = await self._timeline_store.build_for_tenant(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
            limit_per_concept=limit_per_concept,
            ascending=ascending,
        )
        return report.to_payload()

    async def get_consolidation(
        self,
        token: TokenPayload,
        tenant_id: str,
    ) -> dict[str, Any]:
        """READ the Memory (P7) Outcome Consolidation for the tenant scope.

        External read/compute capability (ADR-0002): it computes a tenant-scoped
        consolidation of Decisions' expected vs actual outcomes. No new entity is
        created (Memory persistence remains planned per the framework).
        """
        if self._consolidation_store is None:
            raise RuntimeError("consolidation_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        report: ConsolidationReport = await self._consolidation_store.consolidate_for_tenant(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
        )
        return report.model_dump(mode="json")

    async def get_pattern_refinement(
        self,
        token: TokenPayload,
        tenant_id: str,
    ) -> dict[str, Any]:
        """READ the Pattern Refinement (P7) signal for the tenant scope.

        External read/compute capability (ADR-0002): it computes which Patterns
        should be kept/degraded/deactivated based on Decision outcomes. No new
        entity is created (Memory persistence remains planned per the framework).
        """
        if self._pattern_refinement_store is None:
            raise RuntimeError("pattern_refinement_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        report: PatternRefinementReport = (
            await self._pattern_refinement_store.refine_for_tenant(
                tenant_id=uuid.UUID(ctx.effective_tenant_id),
            )
        )
        return report.model_dump(mode="json")

    async def get_context_revision(
        self,
        token: TokenPayload,
        tenant_id: str,
    ) -> dict[str, Any]:
        """READ the Context Revision (P7 + P2) signal for the tenant scope.

        External read/compute capability (ADR-0002): it computes which Contexts
        should be reviewed / consider a competing model, based on Decision
        outcomes. It only *suggests* reconsidering a competitor; it never
        activates or generates a Context (P2). No new entity is created (Memory
        persistence remains planned per the framework).
        """
        if self._context_revision_store is None:
            raise RuntimeError("context_revision_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        report: ContextRevisionReport = await self._context_revision_store.revise_for_tenant(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
        )
        return report.model_dump(mode="json")

    async def get_insight_transformation(
        self,
        token: TokenPayload,
        tenant_id: str,
    ) -> dict[str, Any]:
        """READ the Insight Transformation journal (R6) for the tenant scope.

        External read/compute capability (ADR-0002): it surfaces each Insight's
        journaled transformation (prior_understanding -> mental_model_update) and,
        when outcome data is available, attributes Decision verdicts back to the
        Insight. It does NOT mutate canonical entities (Memory persistence remains
        planned per the framework).
        """
        if self._insight_transformation_store is None:
            raise RuntimeError(
                "insight_transformation_store not configured in gateway"
            )
        ctx = self._resolve_tenant(token, tenant_id)
        report: InsightTransformationReport = (
            await self._insight_transformation_store.journal_for_tenant(
                tenant_id=uuid.UUID(ctx.effective_tenant_id),
            )
        )
        return report.model_dump(mode="json")

    async def persist_learning_memory(
        self,
        token: TokenPayload,
        tenant_id: str,
        *,
        target_type: str,
        target_id: str,
        signal: dict[str, Any],
        provenance: dict[str, Any],
    ) -> dict[str, Any]:
        """Persist a learning signal into the Memory ledger (P7, authorized).

        Idempotent: re-persisting an identical signal for the same target is a
        no-op (the gateway returns the existing record). Canonical entities are
        never mutated (P1); this appends a new, immutable-by-record row.
        """
        if self._memory_store is None:
            raise RuntimeError("memory_store not configured in gateway")
        if target_type not in {"pattern", "context", "insight"}:
            raise ValueError(f"invalid target_type: {target_type}")
        self.require_authorized(
            token=token, action="commit", requested_tenant_id=tenant_id
        )
        ctx = self._resolve_tenant(token, tenant_id)
        record: LearningMemoryRecord = await self._memory_store.persist(
            record=PersistLearningMemoryInput(
                tenant_id=uuid.UUID(ctx.effective_tenant_id),
                target_type=target_type,
                target_id=uuid.UUID(target_id),
                signal=signal,
                provenance=provenance,
            )
        )
        return record.to_payload()

    async def get_learning_memory(
        self,
        token: TokenPayload,
        tenant_id: str,
        *,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> dict[str, Any]:
        """READ the persisted Learning Memory ledger for the tenant scope."""
        if self._memory_store is None:
            raise RuntimeError("memory_store not configured in gateway")
        self.require_authorized(
            token=token, action="read", requested_tenant_id=tenant_id
        )
        ctx = self._resolve_tenant(token, tenant_id)
        records = await self._memory_store.list(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
            target_type=target_type,
            target_id=uuid.UUID(target_id) if target_id else None,
        )
        payloads = [r.to_payload() for r in records]
        return {"memories": payloads, "total": len(payloads)}

    async def list_observations(
        self,
        token: TokenPayload,
        tenant_id: str,
        *,
        limit: int = 50,
        offset: int = 0,
        fact_type: str | None = None,
        source_type: str | None = None,
        quality_class: str | None = None,
        sort: str = "captured_at_desc",
    ) -> dict[str, Any]:
        """READ observations within the token's tenant scope (viewer+)."""
        if self._observation_store is None:
            raise RuntimeError("observation_store not configured in gateway")
        ctx = self._resolve_tenant(token, tenant_id)
        observations = await self._observation_store.list_observations(
            tenant_id=uuid.UUID(ctx.effective_tenant_id),
            limit=limit,
            offset=offset,
            fact_type=fact_type,
            source_type=source_type,
            quality_class=quality_class,
            sort=sort,
        )
        return observations

    async def cognitive_summary(self, *, tenant_id: str) -> dict[str, Any]:
        """READ cognitive summary counts per concept for a tenant (viewer+)."""
        if self._cognitive_summary_store is not None:
            return await self._cognitive_summary_store.tenant_summary(
                tenant_id=uuid.UUID(tenant_id)
            )
        if self._dsn is not None:
            store = CognitiveSummaryStore(self._dsn)
            result = await store.tenant_summary(tenant_id=uuid.UUID(tenant_id))
            await store.close()
            return result
        # No store configured; return empty summary for testing
        return {
            "totals": {
                "observations": 0,
                "evidence": 0,
                "contexts": 0,
                "active_contexts": 0,
                "patterns": 0,
                "anomalies": 0,
                "hypotheses": 0,
                "confidence_scores": 0,
                "recommendations": 0,
                "decisions": 0,
                "reports": 0,
                "servers": 0,
            },
            "status": {
                "hypotheses": {},
                "recommendations": {},
                "decisions": {},
            },
        }

    # ---------------------------------------------------------------- probe
    async def check_service_health(
        self, client: httpx.AsyncClient | None = None
    ) -> list[dict[str, Any]]:
        """Forward to each pipeline service's /health (READ, operational)."""
        results: list[dict[str, Any]] = []
        own_client = client is None
        if own_client:
            client = httpx.AsyncClient(timeout=3.0)
        try:
            for service, url in sorted(self.service_health.items()):
                try:
                    response = await client.get(url)
                    healthy = response.status_code == 200
                    results.append(
                        {
                            "service": service,
                            "url": url,
                            "status": response.status_code,
                            "healthy": healthy,
                        }
                    )
                    if healthy:
                        self.total_forwarded += 1
                except Exception:  # noqa: BLE001 - service unreachable
                    results.append(
                        {
                            "service": service,
                            "url": url,
                            "status": 0,
                            "healthy": False,
                            "error": "unreachable",
                        }
                    )
        finally:
            if own_client:
                await client.aclose()
        return results

    # --------------------------------------------------------------- metrics
    def record(self, *, action: str | None = None) -> None:
        self.total_requests += 1
        self.last_request_at = datetime.now(UTC)
        if action:
            self.by_action[action] += 1

    def metrics(self) -> dict[str, Any]:
        return {
            "total_requests": self.total_requests,
            "total_rejected_401": self.total_rejected_401,
            "total_rejected_403": self.total_rejected_403,
            "total_boundary_violations": self.total_boundary_violations,
            "total_forwarded": self.total_forwarded,
            "total_errors": self.total_errors,
            "requests_by_action": dict(self.by_action),
            "last_request_at": (
                self.last_request_at.isoformat() if self.last_request_at else None
            ),
        }


def _decision_payload(decision) -> dict[str, Any]:
    """JSON-native READ view of a Decision (authority binding included)."""
    return {
        "id": str(decision.id),
        "tenant_id": str(decision.tenant_id),
        "recommendation_id": str(decision.recommendation_id),
        "confidence_id": str(decision.confidence_id),
        "authority_id": str(decision.authority_id),
        "commitment": decision.commitment,
        "risk_tolerance": decision.risk_tolerance,
        "status": decision.status,
        "committed_at": decision.committed_at.isoformat(),
    }


def _report_payload(report) -> dict[str, Any]:
    """JSON-native READ view of a Report row."""
    return {
        "id": str(report.id),
        "tenant_id": str(report.tenant_id),
        "report_type": report.report_type,
        "title": report.title,
        "period_start": (
            report.period_start.isoformat() if report.period_start else None
        ),
        "period_end": report.period_end.isoformat() if report.period_end else None,
        "generated_at": report.generated_at.isoformat(),
    }
