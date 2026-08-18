"""Configuration for the Evidence Organizer.

Windows/thresholds per domain default to the documented values in
docs/02-motor-recoleccion.md and can be overridden via environment variables.
"""
import os


def _env_float(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    return float(raw)


class OrganizerConfig:
    """Time windows (minutes) and thresholds used by the organization rules.

    All values are captured at Evidence creation time (no retrofitting).
    """

    def __init__(
        self,
        *,
        resource_exhaustion_window_minutes: float = 5.0,
        service_degradation_window_minutes: float = 15.0,
        auth_anomaly_window_minutes: float = 60.0,
        backup_failure_window_minutes: float = 60.0,
        vmware_capacity_window_minutes: float = 30.0,
        network_anomaly_window_minutes: float = 15.0,
        network_anomaly_error_threshold: float = 100.0,
        backup_repo_free_percent: float = 10.0,
        vmware_datastore_free_percent: float = 15.0,
        vmware_snapshot_age_days: float = 7.0,
    ):
        self.resource_exhaustion_window_minutes = resource_exhaustion_window_minutes
        self.service_degradation_window_minutes = service_degradation_window_minutes
        self.auth_anomaly_window_minutes = auth_anomaly_window_minutes
        self.backup_failure_window_minutes = backup_failure_window_minutes
        self.vmware_capacity_window_minutes = vmware_capacity_window_minutes
        self.network_anomaly_window_minutes = network_anomaly_window_minutes
        self.network_anomaly_error_threshold = network_anomaly_error_threshold
        self.backup_repo_free_percent = backup_repo_free_percent
        self.vmware_datastore_free_percent = vmware_datastore_free_percent
        self.vmware_snapshot_age_days = vmware_snapshot_age_days

    @property
    def max_window_minutes(self) -> float:
        """Longest rule window - used to retain buffered observations."""
        return max(
            self.resource_exhaustion_window_minutes,
            self.service_degradation_window_minutes,
            self.auth_anomaly_window_minutes,
            self.backup_failure_window_minutes,
            self.vmware_capacity_window_minutes,
            self.network_anomaly_window_minutes,
        )

    @classmethod
    def from_env(cls) -> "OrganizerConfig":
        return cls(
            resource_exhaustion_window_minutes=_env_float(
                "RESOURCE_EXHAUSTION_WINDOW_MINUTES", 5.0
            ),
            service_degradation_window_minutes=_env_float(
                "SERVICE_DEGRADATION_WINDOW_MINUTES", 15.0
            ),
            auth_anomaly_window_minutes=_env_float("AUTH_ANOMALY_WINDOW_MINUTES", 60.0),
            backup_failure_window_minutes=_env_float(
                "BACKUP_FAILURE_WINDOW_MINUTES", 60.0
            ),
            vmware_capacity_window_minutes=_env_float(
                "VMWARE_CAPACITY_WINDOW_MINUTES", 30.0
            ),
            network_anomaly_window_minutes=_env_float(
                "NETWORK_ANOMALY_WINDOW_MINUTES", 15.0
            ),
            network_anomaly_error_threshold=_env_float(
                "NETWORK_ANOMALY_ERROR_THRESHOLD", 100.0
            ),
            backup_repo_free_percent=_env_float("BACKUP_REPO_FREE_PERCENT", 10.0),
            vmware_datastore_free_percent=_env_float(
                "VMWARE_DATASTORE_FREE_PERCENT", 15.0
            ),
            vmware_snapshot_age_days=_env_float("VMWARE_SNAPSHOT_AGE_DAYS", 7.0),
        )