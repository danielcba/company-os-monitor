"""Perception Layer - Observation & Evidence Pydantic Models."""
import uuid
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class QualityClass(StrEnum):
    Q1 = "Q1"  # Direct Measurement
    Q2 = "Q2"  # Corroborated Inference
    Q3 = "Q3"  # Statistical Regularity
    Q4 = "Q4"  # Anecdotal/Single-Source

class ObservationCreate(BaseModel):
    tenant_id: uuid.UUID
    source_id: uuid.UUID
    source_type: str
    fact_type: str
    fact_value: dict[str, Any]
    unit: str
    quality_class: QualityClass
    raw_payload: dict[str, Any]

class EvidenceCreate(BaseModel):
    tenant_id: uuid.UUID
    observation_ids: list[uuid.UUID]
    organization_type: str
    description: str  # NO interpretation, prediction, or recommendation
    quality_class: QualityClass
    weight: float = Field(ge=0.0, le=1.0)