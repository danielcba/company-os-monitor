"""Unit tests for the OrganizerEngine (rules applied across domains) and for
Evidence creation (quality class + weight assigned at creation, idempotent)."""
import uuid
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest
from libs.cognitive_core.observation_bus import Observation
from libs.perception.evidence import build_evidence, evidence_id
from libs.perception.observation import QualityClass

from src.organizer import QUALITY_WEIGHTS, OrganizerConfig, OrganizerEngine
from src.organizer.rules import Organization

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
SOURCE = uuid.UUID("00000000-0000-0000-0000-000000000002")
NOW = datetime.now(UTC)


def obs(
    fact_type,
    fact_value,
    *,
    tenant=TENANT,
    source=SOURCE,
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
        captured_at=NOW,
        quality_class=quality,
        raw_payload=raw_payload or {},
    )


def make_all_domains_observations():
    """One synthetic observation set that triggers all six organization rules."""
    source_a = uuid.UUID("00000000-0000-0000-0000-00000000000a")
    source_b = uuid.UUID("00000000-0000-0000-0000-00000000000b")
    return [
        # resource exhaustion
        obs("cpu_utilization_percent", {"value": 96.0}, source=source_a),
        obs("memory_usage", {"used_bytes": 90, "total_bytes": 100}, source=source_a),
        obs("disk_usage", {"used_bytes": 92, "total_bytes": 100}, source=source_a),
        # service degradation
        obs(
            "windows_service_state",
            {"name": "spooler", "state": "Stopped", "start_mode": "Auto"},
            source=source_a,
        ),
        obs(
            "windows_event_log",
            {"type": "Error", "source": "spooler", "event_code": 7031},
            source=source_a,
        ),
        # auth anomaly
        obs("ad_account_lockout", {"account": "jsmith"}),
        obs("ad_privileged_group_membership", {"group": "Domain Admins", "changed": True}),
        # backup failure
        obs("backup_job_status", {"job": "full", "status": "Failed"}, source=source_b),
        obs("repo_free_bytes", {"value": 5}, raw_payload={"repository": "repo-1"}, source=source_b),
        obs("repo_capacity_bytes", {"value": 100}, raw_payload={"repository": "repo-1"}, source=source_b),
        # vmware capacity
        obs("datastore_free_bytes", {"value": 10}, raw_payload={"datastore": "ds-1"}),
        obs("datastore_capacity_bytes", {"value": 100}, raw_payload={"datastore": "ds-1"}),
        obs("vm_snapshot_age_days", {"vm": "web-01", "age_days": 12}),
        # network anomaly
        obs("interface_errors", {"value": 512}, raw_payload={"interface": "Gi0/1"}, source=source_b),
        obs("port_state_change", {"port": "Gi0/1", "state": "down"}, source=source_b),
    ]


def test_engine_detects_all_six_domains():
    engine = OrganizerEngine(OrganizerConfig())
    creations = engine.organize(make_all_domains_observations())
    org_types = {c.organization_type for c in creations}
    assert org_types == {
        "resource_exhaustion_evidence",
        "service_degradation_evidence",
        "auth_anomaly_evidence",
        "backup_failure_evidence",
        "vmware_capacity_evidence",
        "network_anomaly_evidence",
    }


def test_engine_assign_descriptive_and_weight_at_creation():
    engine = OrganizerEngine(OrganizerConfig())
    creations = engine.organize(make_all_domains_observations())
    by_type = {c.organization_type: c for c in creations}
    assert by_type["resource_exhaustion_evidence"].quality_class.value == "Q1"
    assert by_type["resource_exhaustion_evidence"].weight == 0.875
    assert by_type["auth_anomaly_evidence"].quality_class.value == "Q2"
    assert by_type["auth_anomaly_evidence"].weight == 0.625
    assert by_type["network_anomaly_evidence"].quality_class.value == "Q2"
    assert by_type["network_anomaly_evidence"].weight == 0.625
    for create in creations:
        assert create.weight == QUALITY_WEIGHTS[create.quality_class]

    description = by_type["resource_exhaustion_evidence"].description
    for forbidden in ("predicci", "recommend", "disco lleno", "causes"):
        assert forbidden.lower() not in description.lower()


def test_build_evidence_is_deterministic_and_covers_content():
    engine = OrganizerEngine(OrganizerConfig())
    creations = engine.organize(make_all_domains_observations())
    first = [build_evidence(c) for c in creations]
    second = [build_evidence(c) for c in creations]
    assert [e.id for e in first] == [e.id for e in second]
    created = {e.organization_type for e in first}
    assert "resource_exhaustion_evidence" in created
    assert all(0.0 <= e.weight <= 1.0 for e in first)


def test_evidence_id_stable_across_reorganization():
    tenant = TENANT
    ids = [uuid.uuid4(), uuid.uuid4()]
    first = evidence_id(tenant, "resource_exhaustion_evidence", ids)
    second = evidence_id(tenant, "resource_exhaustion_evidence", list(reversed(ids)))
    assert first == second
    other_type = evidence_id(tenant, "backup_failure_evidence", ids)
    assert first != other_type


def test_organization_is_frozen():
    organization = Organization(
        organization_type="resource_exhaustion_evidence",
        description="facts",
        observation_ids=[uuid.uuid4()],
        quality_class=QualityClass.Q1,
        tenant_id=TENANT,
    )
    with pytest.raises(FrozenInstanceError):
        organization.organization_type = "other"