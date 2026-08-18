"""Tests for Windows Collector (mocked WinRM session)."""
import json
import uuid
from types import SimpleNamespace

import pytest

from src.collector import WindowsCollector

TENANT = uuid.UUID("00000000-0000-0000-0000-000000000001")
SOURCE = uuid.UUID("00000000-0000-0000-0000-000000000001")


def fake_session(*scripts):
    """Build a WinRM-like session returning the given JSON payloads in order."""
    queue = list(scripts)

    def run_ps(script):
        if queue:
            payload = queue.pop(0)
        else:
            payload = None
        return SimpleNamespace(
            status_code=0,
            std_out=json.dumps(payload) if payload is not None else "",
            std_err="",
        )

    return SimpleNamespace(run_ps=run_ps)


@pytest.fixture
def collector():
    return WindowsCollector(TENANT, SOURCE, fake_session())


def test_capture_cpu(collector):
    collector.session = fake_session([{"PercentProcessorTime": 42.7}])
    obs = collector.capture_cpu()
    assert len(obs) == 1
    assert obs[0].fact_type == "cpu_utilization_percent"
    assert obs[0].fact_value["value"] == 42.7
    assert obs[0].unit == "percent"
    assert obs[0].quality_class.value == "Q1"
    assert obs[0].source_type == "windows_agent"


def test_capture_memory(collector):
    collector.session = fake_session([{"FreePhysicalMemory": 8388608, "TotalVisibleMemorySize": 16777216}])
    obs = collector.capture_memory()
    assert len(obs) == 2
    types = {o.fact_type: o.fact_value["value"] for o in obs}
    assert types["memory_free_bytes"] == 8388608 * 1024
    assert types["memory_total_bytes"] == 16777216 * 1024
    assert all(o.quality_class.value == "Q1" for o in obs)


def test_capture_disks(collector):
    collector.session = fake_session([
        {"DeviceID": "C:", "FreeSpace": 500000000000, "Size": 1000000000000},
        {"DeviceID": "D:", "FreeSpace": 200000000000, "Size": 500000000000},
    ])
    obs = collector.capture_disks()
    assert len(obs) == 4
    assert obs[0].fact_type == "disk_free_bytes"
    assert obs[0].fact_value["value"] == 500000000000
    assert obs[0].raw_payload["device"] == "C:"
    assert obs[1].fact_type == "disk_total_bytes"
    assert obs[2].fact_value["value"] == 200000000000


def test_capture_services(collector):
    collector.session = fake_session([
        {"Name": "Spooler", "State": "Stopped", "StartMode": "Auto", "DisplayName": "Print Spooler"}
    ])
    obs = collector.capture_services()
    assert len(obs) == 1
    assert obs[0].fact_type == "windows_service_state"
    assert obs[0].fact_value["name"] == "Spooler"
    assert obs[0].fact_value["state"] == "Stopped"
    assert obs[0].quality_class.value == "Q1"


def test_capture_event_log(collector):
    collector.session = fake_session([
        {
            "TimeWritten": "2026-08-14T03:00:00Z",
            "Logfile": "Application",
            "SourceName": "Application Error",
            "EventCode": 1000,
            "Type": "Error",
            "Message": "Faulting application",
        }
    ])
    obs = collector.capture_event_log()
    assert len(obs) == 1
    assert obs[0].fact_type == "windows_event_log"
    assert obs[0].fact_value["event_code"] == 1000
    assert obs[0].fact_value["type"] == "Error"
    assert obs[0].quality_class.value == "Q1"


def test_capture_all_flattens_all_sources(collector):
    collector.session = fake_session(
        [{"PercentProcessorTime": 30.0}],
        [{"FreePhysicalMemory": 1000, "TotalVisibleMemorySize": 2000}],
        [{"DeviceID": "C:", "FreeSpace": 1, "Size": 2}],
        [{"Name": "BITS", "State": "Stopped", "StartMode": "Auto", "DisplayName": "BITS"}],
        [],
    )
    obs = collector.capture_all()
    fact_types = {o.fact_type for o in obs}
    assert fact_types == {
        "cpu_utilization_percent",
        "memory_free_bytes",
        "memory_total_bytes",
        "disk_free_bytes",
        "disk_total_bytes",
        "windows_service_state",
    }