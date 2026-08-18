"""Evidence Organizer Engine - contracts the Perception/Organize capability.

Transforms a batch of immutable Observations into EvidenceCreate records by
applying the domain organization rules. Weights (w_i) are assigned HERE, at
creation time, from the quality class - never retrofitted afterwards.
"""
from libs.cognitive_core.observation_bus import Observation
from libs.perception.observation import EvidenceCreate, QualityClass

from src.organizer.config import OrganizerConfig
from src.organizer.rules import (
    auth_anomaly_evidence,
    backup_failure_evidence,
    network_anomaly_evidence,
    resource_exhaustion_evidence,
    service_degradation_evidence,
    vmware_capacity_evidence,
)

# Canonical midrange weights per quality class (docs/02: Q1 [0.75,1.0],
# Q2 [0.50,0.75), Q3 [0.25,0.50), Q4 [0.00,0.25)). Assigned at creation.
# Values are the EXACT band midpoints, identical to the Calibrate capability's
# quality_class_to_weight (calibration_model.py) so the stored weight and the
# derived evidential weight never diverge (single source of truth).
QUALITY_WEIGHTS: dict[QualityClass, float] = {
    QualityClass.Q1: 0.875,
    QualityClass.Q2: 0.625,
    QualityClass.Q3: 0.375,
    QualityClass.Q4: 0.125,
}


class OrganizerEngine:
    """Pure organizer: no I/O. Returns EvidenceCreate records ready to persist."""

    def __init__(self, config: OrganizerConfig | None = None):
        self.config = config or OrganizerConfig()

    def organize(self, observations: list[Observation]) -> list[EvidenceCreate]:
        """Apply all domain rules to a batch of immutable observations."""
        organizations = []
        organizations += resource_exhaustion_evidence(
            observations, window_minutes=self.config.resource_exhaustion_window_minutes
        )
        organizations += service_degradation_evidence(
            observations, window_minutes=self.config.service_degradation_window_minutes
        )
        organizations += auth_anomaly_evidence(
            observations, window_minutes=self.config.auth_anomaly_window_minutes
        )
        organizations += backup_failure_evidence(
            observations,
            window_minutes=self.config.backup_failure_window_minutes,
            repo_free_threshold=self.config.backup_repo_free_percent,
        )
        organizations += vmware_capacity_evidence(
            observations,
            window_minutes=self.config.vmware_capacity_window_minutes,
            datastore_free_threshold=self.config.vmware_datastore_free_percent,
            snapshot_age_days=self.config.vmware_snapshot_age_days,
        )
        organizations += network_anomaly_evidence(
            observations,
            window_minutes=self.config.network_anomaly_window_minutes,
            error_threshold=self.config.network_anomaly_error_threshold,
        )
        return [self._to_create(organization) for organization in organizations]

    @staticmethod
    def _to_create(organization) -> EvidenceCreate:
        return EvidenceCreate(
            tenant_id=organization.tenant_id,
            observation_ids=organization.observation_ids,
            organization_type=organization.organization_type,
            description=organization.description,
            quality_class=organization.quality_class,
            weight=QUALITY_WEIGHTS[organization.quality_class],
        )