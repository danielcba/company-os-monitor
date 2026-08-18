"""Access layer (EXTERNAL, non-canonical - ADR-0002).

Identity, authentication and authorization for COS-Monitor. Per ADR-0002 this
layer is an external product capability: it AUTORIZES and protects access to
the canonical cognitive flow (R3: the Cognitive Boundary is enforced
architecturally) but NEVER produces cognitive judgments. Its RBAC maps to the
Decision Authority of the Decision concept (the commitment authority under
which a Decision is taken); it is not a permission table but an authority
binding model.
"""