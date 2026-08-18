"""API Gateway - Cognitive Boundary enforcement (R3), external ADR-0002.

The gateway is the architectural enforcement point of the Cognitive Boundary
(R3: Perception/Reasoning never execute action without explicit authorization).
It verifies the JWT (identity + Decision Authority role + tenant scope) issued
by the user-service and applies the boundary rules of
``procedural_memory/cognitive_boundary.yaml`` (docs/04): only the canonical
flow may advance (perception -> reasoning -> action), actions require authority
binding (R5), and Recommendation -> Decision requires a Confidence present
(R4). It NEVER reimplements cognitive logic: it validates and forwards/routes.
"""