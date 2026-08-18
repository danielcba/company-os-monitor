"""Tests for VMware Collector (mocked vSphere objects)."""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pyVmomi import vim

from src.collector import VMwareCollector, connect_vcenter

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
SOURCE = uuid.UUID("00000000-0000-0000-0000-000000000001")


def make_view(objects):
    return SimpleNamespace(view=objects, Destroy=lambda: None)


def make_content(views_by_type):
    view_manager = SimpleNamespace(
        CreateContainerView=lambda folder, vtypes, recursive: make_view(
            views_by_type.get(vtypes[0], [])
        )
    )
    return SimpleNamespace(viewManager=view_manager, rootFolder=SimpleNamespace())


def datastore(name, capacity, free):
    return SimpleNamespace(
        summary=SimpleNamespace(name=name, capacity=capacity, freeSpace=free)
    )


def vm(name, uuid_, power_state, snapshot=None):
    return SimpleNamespace(
        name=name,
        runtime=SimpleNamespace(powerState=power_state),
        summary=SimpleNamespace(config=SimpleNamespace(uuid=uuid_)),
        snapshot=snapshot,
    )


def host(name, health, power_state):
    return SimpleNamespace(
        name=name,
        runtime=SimpleNamespace(
            healthState=SimpleNamespace(state=health), powerState=power_state
        ),
        hardware=SimpleNamespace(systemInfo=SimpleNamespace(model="PowerEdge R740")),
    )


@pytest.fixture
def collector():
    return VMwareCollector(TENANT, SOURCE, make_content({}))


def test_capture_datastores(collector):
    collector.content = make_content(
        {vim.Datastore: [datastore("ds1", 2_000_000_000_000, 500_000_000_000)]}
    )
    obs = collector.capture_datastores()
    assert len(obs) == 2
    assert obs[0].fact_type == "datastore_capacity_bytes"
    assert obs[0].fact_value["value"] == 2_000_000_000_000
    assert obs[1].fact_type == "datastore_free_bytes"
    assert obs[1].fact_value["value"] == 500_000_000_000
    assert all(o.quality_class.value == "Q1" for o in obs)
    assert obs[0].source_type == "vmware_agent"


def test_capture_vm_power_states(collector):
    collector.content = make_content(
        {
            vim.VirtualMachine: [
                vm("web-01", "u1", "poweredOn"),
                vm("db-01", "u2", "poweredOff"),
            ]
        }
    )
    obs = collector.capture_vm_power_states()
    assert len(obs) == 2
    states = {o.fact_value["name"]: o.fact_value["power_state"] for o in obs}
    assert states == {"web-01": "poweredOn", "db-01": "poweredOff"}
    assert all(o.quality_class.value == "Q1" for o in obs)


def test_capture_snapshots(collector):
    created = datetime(2026, 7, 2, tzinfo=UTC)
    child = SimpleNamespace(
        name="child-snap", createTime=created, childSnapshotList=[]
    )
    root = SimpleNamespace(name="root-snap", createTime=created, childSnapshotList=[child])
    no_snap = vm("no-snap", "u3", "poweredOn", snapshot=None)
    with_snap = vm("srv-01", "u1", "poweredOn", snapshot=SimpleNamespace(rootSnapshotList=[root]))
    collector.content = make_content({vim.VirtualMachine: [no_snap, with_snap]})

    obs = collector.capture_snapshots()
    assert len(obs) == 2
    by_name = {o.fact_value["snapshot_name"]: o for o in obs}
    assert set(by_name) == {"root-snap", "child-snap"}
    assert by_name["root-snap"].fact_value["vm"] == "srv-01"
    expected_age = (datetime.now(UTC) - created).days
    assert by_name["root-snap"].fact_value["age_days"] == expected_age
    assert by_name["root-snap"].unit == "days"


def test_capture_host_health(collector):
    collector.content = make_content(
        {vim.HostSystem: [host("esxi-01", "green", "poweredOn")]}
    )
    obs = collector.capture_host_health()
    assert len(obs) == 1
    assert obs[0].fact_type == "esxi_host_health"
    assert obs[0].fact_value["host"] == "esxi-01"
    assert obs[0].fact_value["health_state"] == "green"
    assert obs[0].fact_value["model"] == "PowerEdge R740"
    assert obs[0].quality_class.value == "Q1"


def test_capture_all_flattens_all_sources(collector):
    collector.content = make_content(
        {
            vim.Datastore: [datastore("ds1", 100, 50)],
            vim.VirtualMachine: [vm("v1", "u1", "poweredOn")],
            vim.HostSystem: [host("esxi-01", "green", "poweredOn")],
        }
    )
    obs = collector.capture_all()
    fact_types = {o.fact_type for o in obs}
    assert fact_types == {
        "datastore_capacity_bytes",
        "datastore_free_bytes",
        "vm_power_state",
        "esxi_host_health",
    }


def test_connect_vcenter(monkeypatch):
    fake_si = SimpleNamespace(RetrieveContent=lambda: SimpleNamespace(name="content"))
    monkeypatch.setattr(
        "src.collector.SmartConnect",
        lambda **kwargs: fake_si,
    )
    content = connect_vcenter("vcenter.local", "user", "secret", port=443)
    assert content.name == "content"