"""User Service - multi-tenant auth + RBAC (external, ADR-0002).

External non-canonical capability (ADR-0002): it verifies identity, emits
signed JWTs with the Decision Authority role and tenant scope, and authorizes
actions on the canonical flow (R3 - Cognitive Boundary). It NEVER produces
cognitive judgments and NEVER executes the pipeline: its only output is
verifiable authority binding (R5) so that every Decision/action has an
auditable commitment authority (core-concepts/decision.md).
"""