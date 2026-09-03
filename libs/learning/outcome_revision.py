"""Outcome Revision model (H3 — append-only outcome history).

Records every submitted outcome revision as an immutable historical record.
Phase 1 (lock-free, append-only): multiple concurrent commits are safe
because this table only supports INSERT.

P6: outcome history is immutable and historically traceable.
P1: append-only — no UPDATE/DELETE allowed (enforced by DB trigger).
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class OutcomeRevision(BaseModel):
    """Immutable outcome revision record (append-only, P6).

    Each revision captures the actual outcomes submitted for a Decision.
    Multiple revisions for the same Decision create an auditable history
    of outcome submissions (last-writer-wins on Decision.actual_outcomes,
    but all revisions are preserved).
    """

    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    tenant_id: uuid.UUID
    decision_id: uuid.UUID
    actual_outcomes: list[dict[str, Any]]
    executed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    model_config = ConfigDict(frozen=True)


def build_outcome_revision(
    *,
    tenant_id: uuid.UUID,
    decision_id: uuid.UUID,
    actual_outcomes: list[dict[str, Any]],
    executed_at: datetime | None = None,
) -> OutcomeRevision:
    """Create a new outcome revision (append-only, P6)."""
    return OutcomeRevision(
        tenant_id=tenant_id,
        decision_id=decision_id,
        actual_outcomes=actual_outcomes,
        executed_at=executed_at,
    )
