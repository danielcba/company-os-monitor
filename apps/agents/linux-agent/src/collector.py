"""Linux Observation Capture - P1: Immutable capture only."""
import uuid

import psutil
from libs.perception.observation import ObservationCreate, QualityClass


class LinuxCollector:
    def __init__(self, tenant_id: uuid.UUID, source_id: uuid.UUID):
        self.tenant_id = tenant_id
        self.source_id = source_id
    
    def capture_cpu(self) -> ObservationCreate:
        cpu_percent = psutil.cpu_percent(interval=1)
        return ObservationCreate(
            tenant_id=self.tenant_id,
            source_id=self.source_id,
            source_type="linux_agent",
            fact_type="cpu_utilization_percent",
            fact_value={"value": cpu_percent},
            unit="percent",
            quality_class=QualityClass.Q1,
            raw_payload={"cpu_times": psutil.cpu_times()._asdict()}
        )
    
    def capture_memory(self) -> ObservationCreate:
        mem = psutil.virtual_memory()
        return ObservationCreate(
            tenant_id=self.tenant_id,
            source_id=self.source_id,
            source_type="linux_agent",
            fact_type="memory_usage",
            fact_value={"free_bytes": mem.free, "total_bytes": mem.total, "used_bytes": mem.used},
            unit="bytes",
            quality_class=QualityClass.Q1,
            raw_payload=mem._asdict()
        )
    
    def capture_disk(self, mountpoint: str = "/") -> ObservationCreate:
        disk = psutil.disk_usage(mountpoint)
        return ObservationCreate(
            tenant_id=self.tenant_id,
            source_id=self.source_id,
            source_type="linux_agent",
            fact_type="disk_usage",
            fact_value={"free_bytes": disk.free, "total_bytes": disk.total, "used_bytes": disk.used},
            unit="bytes",
            quality_class=QualityClass.Q1,
            raw_payload={"mountpoint": mountpoint, **disk._asdict()}
        )
    
    def capture_all(self) -> list[ObservationCreate]:
        return [self.capture_cpu(), self.capture_memory(), self.capture_disk()]