"""Unit tests for the Evidence organization rules (pure functions).

One test per domain rule (positive and negative) plus quality-class logic.
Synthetic observations only - no database involved.
"""
import uuid
from datetime import UTC, datetime, timedelta

from libs.cognitive_core.observation_bus import Observation

from src.organizer.rules import (
    auth_anomaly_evidence,
    backup_failure_evidence,
    network_anomaly_evidence,
    resource_exhaustion_evidence,
    service_degradation_evidence,
    vmware_capacity_evidence,
)

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
SOURCE = uuid.UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime.now(UTC)


def obs(
    fact_type,
    fact_value,
    *,
    tenant=TENANT,
    source=SOURCE,
    captured_at=None,
    quality="Q1",
    raw_payload=None,
):
    return Observation(
        tenant_id=tenant,
        source_id=source,
        source_type="test_agent",
        fact_type=fact_type,
        fact_value=fact_value,
        unit="",
        captured_at=captured_at or NOW,
        quality_class=quality,
        raw_payload=raw_payload or {},
    )


# ---------------------------------------------------------------------------
# Resource Exhaustion
# ---------------------------------------------------------------------------
def test_resource_exhaustion_positive_q1():
    observations = [
        obs("cpu_utilization_percent", {"value": 94.2}),
        obs("memory_usage", {"used_bytes": 88, "total_bytes": 100}),
        obs("disk_usage", {"used_bytes": 91, "total_bytes": 100}),
    ]
    result = resource_exhaustion_evidence(observations, window_minutes=5)
    assert len(result) == 1
    assert result[0].organization_type == "resource_exhaustion_evidence"
    assert result[0].quality_class.value == "Q1"
    assert result[0].observation_ids == [o.id for o in observations]
    desc = result[0].description
    assert "cpu_utilization_percent=94.2" in desc
    assert "memory_usage_percent=88.0" in desc
    assert "disk_usage_percent=91.0" in desc
    for forbidden in ("disco lleno", "lleno", "warning", "risk"):
        assert forbidden.lower() not in desc.lower()


def test_resource_exhaustion_q2_when_any_observation_q2():
    observations = [
        obs("cpu_utilization_percent", {"value": 94.2}),
        obs("memory_usage", {"used_bytes": 88, "total_bytes": 100}, quality="Q2"),
        obs("disk_usage", {"used_bytes": 91, "total_bytes": 100}),
    ]
    result = resource_exhaustion_evidence(observations, window_minutes=5)
    assert len(result) == 1
    assert result[0].quality_class.value == "Q2"


def test_resource_exhaustion_negative_below_threshold():
    observations = [
        obs("cpu_utilization_percent", {"value": 50.0}),
        obs("memory_usage", {"used_bytes": 88, "total_bytes": 100}),
        obs("disk_usage", {"used_bytes": 91, "total_bytes": 100}),
    ]
    assert resource_exhaustion_evidence(observations, window_minutes=5) == []


def test_resource_exhaustion_window_violation():
    observations = [
        obs("cpu_utilization_percent", {"value": 94.2}, captured_at=NOW),
        obs("memory_usage", {"used_bytes": 88, "total_bytes": 100}, captured_at=NOW),
        obs(
            "disk_usage",
            {"used_bytes": 91, "total_bytes": 100},
            captured_at=NOW + timedelta(minutes=10),
        ),
    ]
    assert resource_exhaustion_evidence(observations, window_minutes=5) == []


def test_resource_exhaustion_pairs_free_and_total_bytes():
    observations = [
        obs("cpu_utilization_percent", {"value": 95.0}),
        obs("memory_free_bytes", {"value": 10}, raw_payload={}),
        obs("memory_total_bytes", {"value": 100}, raw_payload={}),
        obs("disk_free_bytes", {"value": 5}, raw_payload={"device": "C:"}),
        obs("disk_total_bytes", {"value": 100}, raw_payload={"device": "C:"}),
    ]
    result = resource_exhaustion_evidence(observations, window_minutes=5)
    assert len(result) == 1
    assert result[0].quality_class.value == "Q1"


# ---------------------------------------------------------------------------
# Service Degradation
# ---------------------------------------------------------------------------
def test_service_degradation_positive_q1():
    observations = [
        obs(
            "windows_service_state",
            {"name": "spooler", "state": "Stopped", "start_mode": "Auto"},
        ),
        obs(
            "windows_event_log",
            {"type": "Error", "source": "spooler", "event_code": 7031},
        ),
    ]
    result = service_degradation_evidence(observations, window_minutes=15)
    assert len(result) == 1
    assert result[0].organization_type == "service_degradation_evidence"
    assert result[0].quality_class.value == "Q1"
    assert "state=Stopped" in result[0].description
    assert "type=Error" in result[0].description


def test_service_degradation_negative_event_not_error():
    observations = [
        obs(
            "windows_service_state",
            {"name": "spooler", "state": "Stopped", "start_mode": "Auto"},
        ),
        obs(
            "windows_event_log",
            {"type": "Information", "source": "spooler", "event_code": 6006},
        ),
    ]
    assert service_degradation_evidence(observations, window_minutes=15) == []


def test_service_degradation_negative_service_not_stopped_auto():
    observations = [
        obs(
            "windows_service_state",
            {"name": "spooler", "state": "Running", "start_mode": "Auto"},
        ),
        obs("windows_event_log", {"type": "Error", "source": "spooler", "event_code": 7031}),
    ]
    assert service_degradation_evidence(observations, window_minutes=15) == []


# ---------------------------------------------------------------------------
# Authentication Anomaly
# ---------------------------------------------------------------------------
def test_auth_anomaly_positive_q2():
    observations = [
        obs("ad_account_lockout", {"account": "jsmith"}),
        obs(
            "ad_privileged_group_membership",
            {"group": "Domain Admins", "changed": True},
        ),
    ]
    result = auth_anomaly_evidence(observations, window_minutes=60)
    assert len(result) == 1
    assert result[0].organization_type == "auth_anomaly_evidence"
    assert result[0].quality_class.value == "Q2"
    assert "account=jsmith" in result[0].description


def test_auth_anomaly_negative_lockout_only():
    observations = [obs("ad_account_lockout", {"account": "jsmith"})]
    assert auth_anomaly_evidence(observations, window_minutes=60) == []


def test_auth_anomaly_separates_tenants():
    other_tenant = uuid.UUID("00000000-0000-0000-0000-000000000009")
    observations = [
        obs("ad_account_lockout", {"account": "jsmith"}),
        obs(
            "ad_privileged_group_membership",
            {"group": "Domain Admins", "changed": True},
            tenant=other_tenant,
        ),
    ]
    assert auth_anomaly_evidence(observations, window_minutes=60) == []


# ---------------------------------------------------------------------------
# Backup Failure
# ---------------------------------------------------------------------------
def test_backup_failure_positive_q1():
    observations = [
        obs("backup_job_status", {"job": "weekly-full", "status": "Failed"}),
        obs("repo_free_bytes", {"value": 5}, raw_payload={"repository": "repo-1"}),
        obs("repo_capacity_bytes", {"value": 100}, raw_payload={"repository": "repo-1"}),
    ]
    result = backup_failure_evidence(observations, window_minutes=60)
    assert len(result) == 1
    assert result[0].organization_type == "backup_failure_evidence"
    assert result[0].quality_class.value == "Q1"
    assert "backup_job_status=Failed" in result[0].description
    assert "repo_free_percent=5.0" in result[0].description


def test_backup_failure_negative_repo_not_low():
    observations = [
        obs("backup_job_status", {"job": "weekly-full", "status": "Failed"}),
        obs("repo_free_bytes", {"value": 30}, raw_payload={"repository": "repo-1"}),
        obs("repo_capacity_bytes", {"value": 100}, raw_payload={"repository": "repo-1"}),
    ]
    assert backup_failure_evidence(observations, window_minutes=60) == []


def test_backup_failure_negative_job_not_failed():
    observations = [
        obs("backup_job_status", {"job": "weekly-full", "status": "Succeeded"}),
        obs("repo_free_bytes", {"value": 5}, raw_payload={"repository": "repo-1"}),
        obs("repo_capacity_bytes", {"value": 100}, raw_payload={"repository": "repo-1"}),
    ]
    assert backup_failure_evidence(observations, window_minutes=60) == []


# ---------------------------------------------------------------------------
# VMware Capacity
# ---------------------------------------------------------------------------
def test_vmware_capacity_positive_q1():
    observations = [
        obs(
            "datastore_free_bytes",
            {"value": 10},
            raw_payload={"datastore": "ds-1"},
        ),
        obs(
            "datastore_capacity_bytes",
            {"value": 100},
            raw_payload={"datastore": "ds-1"},
        ),
        obs("vm_snapshot_age_days", {"vm": "web-01", "age_days": 12}),
    ]
    result = vmware_capacity_evidence(observations, window_minutes=30)
    assert len(result) == 1
    assert result[0].organization_type == "vmware_capacity_evidence"
    assert result[0].quality_class.value == "Q1"
    assert "datastore_free_percent=10.0" in result[0].description
    assert "age_days=12" in result[0].description


def test_vmware_capacity_negative_snapshot_recent():
    observations = [
        obs(
            "datastore_free_bytes",
            {"value": 10},
            raw_payload={"datastore": "ds-1"},
        ),
        obs(
            "datastore_capacity_bytes",
            {"value": 100},
            raw_payload={"datastore": "ds-1"},
        ),
        obs("vm_snapshot_age_days", {"vm": "web-01", "age_days": 3}),
    ]
    assert vmware_capacity_evidence(observations, window_minutes=30) == []


def test_vmware_capacity_negative_datastore_not_low():
    observations = [
        obs("datastore_free_bytes", {"value": 40}, raw_payload={"datastore": "ds-1"}),
        obs(
            "datastore_capacity_bytes",
            {"value": 100},
            raw_payload={"datastore": "ds-1"},
        ),
        obs("vm_snapshot_age_days", {"vm": "web-01", "age_days": 12}),
    ]
    assert vmware_capacity_evidence(observations, window_minutes=30) == []


# ---------------------------------------------------------------------------
# Network Anomaly
# ---------------------------------------------------------------------------
def test_network_anomaly_positive_q2():
    observations = [
        obs("interface_errors", {"value": 512}, raw_payload={"interface": "Gi0/1"}),
        obs("port_state_change", {"port": "Gi0/1", "state": "down"}),
    ]
    result = network_anomaly_evidence(
        observations, window_minutes=15, error_threshold=100
    )
    assert len(result) == 1
    assert result[0].organization_type == "network_anomaly_evidence"
    assert result[0].quality_class.value == "Q2"
    assert "interface_errors=512" in result[0].description
    assert "Gi0/1" in result[0].description


def test_network_anomaly_negative_below_threshold():
    observations = [
        obs("interface_errors", {"value": 50}, raw_payload={"interface": "Gi0/1"}),
        obs("port_state_change", {"port": "Gi0/1", "state": "down"}),
    ]
    assert (
        network_anomaly_evidence(observations, window_minutes=15, error_threshold=100)
        == []
    )


def test_network_anomaly_negative_no_state_change():
    observations = [
        obs("interface_errors", {"value": 512}, raw_payload={"interface": "Gi0/1"})
    ]
    assert network_anomaly_evidence(observations, window_minutes=15) == []