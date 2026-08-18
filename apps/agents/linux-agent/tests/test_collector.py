"""Tests for Linux Collector."""
import uuid
from unittest.mock import Mock, patch

import pytest

from src.collector import LinuxCollector


@pytest.fixture
def collector():
    return LinuxCollector(
        tenant_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        source_id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
    )

def test_capture_cpu(collector):
    with (
        patch("psutil.cpu_percent", return_value=45.5),
        patch("psutil.cpu_times") as mock_times,
    ):
        mock_times.return_value = Mock(_asdict=lambda: {"user": 100, "system": 50})
        obs = collector.capture_cpu()
    
    assert obs.fact_type == "cpu_utilization_percent"
    assert obs.fact_value["value"] == 45.5
    assert obs.unit == "percent"
    assert obs.quality_class.value == "Q1"
    assert obs.source_type == "linux_agent"

def test_capture_memory(collector):
    with patch("psutil.virtual_memory") as mock_mem:
        mock_mem.return_value = Mock(
            free=8000000000,
            total=16000000000,
            used=8000000000,
            _asdict=lambda: {"free": 8000000000, "total": 16000000000, "used": 8000000000}
        )
        obs = collector.capture_memory()
    
    assert obs.fact_type == "memory_usage"
    assert obs.fact_value["free_bytes"] == 8000000000
    assert obs.fact_value["total_bytes"] == 16000000000
    assert obs.unit == "bytes"
    assert obs.quality_class.value == "Q1"

def test_capture_disk(collector):
    with patch("psutil.disk_usage") as mock_disk:
        mock_disk.return_value = Mock(
            free=500000000000,
            total=1000000000000,
            used=500000000000,
            _asdict=lambda: {"free": 500000000000, "total": 1000000000000, "used": 500000000000}
        )
        obs = collector.capture_disk("/")
    
    assert obs.fact_type == "disk_usage"
    assert obs.fact_value["free_bytes"] == 500000000000
    assert obs.unit == "bytes"
    assert obs.quality_class.value == "Q1"

def test_capture_all(collector):
    with (
        patch("psutil.cpu_percent", return_value=30.0),
        patch("psutil.cpu_times") as mock_times,
        patch("psutil.virtual_memory") as mock_mem,
        patch("psutil.disk_usage") as mock_disk,
    ):
        mock_times.return_value = Mock(_asdict=dict)
        mock_mem.return_value = Mock(
            free=8000000000, total=16000000000, used=8000000000,
            _asdict=dict
        )
        mock_disk.return_value = Mock(
            free=500000000000, total=1000000000000, used=500000000000,
            _asdict=dict
        )
        observations = collector.capture_all()
    
    assert len(observations) == 3
    fact_types = {o.fact_type for o in observations}
    assert fact_types == {"cpu_utilization_percent", "memory_usage", "disk_usage"}