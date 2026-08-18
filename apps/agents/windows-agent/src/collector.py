"""Windows Observation Capture - P1: Immutable capture only (WMI over WinRM).

Each query produces one Observation per instance (per disk, per service, per event).
The collector never interprets: it only captures raw values.
"""
import json
import uuid
from typing import Any

from libs.perception.observation import ObservationCreate, QualityClass

CPU_QUERY = """
Get-CimInstance Win32_PerfFormattedData_PerfOS_Processor -Filter "Name='_Total'" |
  Select-Object PercentProcessorTime | ConvertTo-Json -Compress
"""

MEMORY_QUERY = """
Get-CimInstance Win32_OperatingSystem |
  Select-Object FreePhysicalMemory, TotalVisibleMemorySize | ConvertTo-Json -Compress
"""

DISK_QUERY = """
Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" |
  Select-Object DeviceID, FreeSpace, Size | ConvertTo-Json -Compress
"""

SERVICES_QUERY = """
Get-CimInstance Win32_Service -Filter "State='Stopped' AND StartMode='Auto'" |
  Select-Object Name, State, StartMode, DisplayName | ConvertTo-Json -Compress
"""

EVENT_LOG_QUERY = """
Get-CimInstance Win32_NTLogEvent -Filter "Type='Error' OR Type='Critical'" -First 50 |
  Select-Object TimeWritten, Logfile, SourceName, EventCode, Type, Message |
  ConvertTo-Json -Compress
"""


class WindowsCollector:
    def __init__(self, tenant_id: uuid.UUID, source_id: uuid.UUID, session: Any):
        """`session` must expose run_ps(script) returning object with .status_code/.std_out."""
        self.tenant_id = tenant_id
        self.source_id = source_id
        self.session = session

    def _run_ps(self, script: str) -> list[dict[str, Any]]:
        """Run a PowerShell script that emits JSON and return parsed rows."""
        result = self.session.run_ps(script)
        if getattr(result, "status_code", 0) not in (0, None):
            raise RuntimeError(f"WinRM remote script failed: {getattr(result, 'std_err', '')}")
        stdout = getattr(result, "std_out", "") or ""
        if not stdout.strip():
            return []
        payload = json.loads(stdout.strip())
        if isinstance(payload, dict):
            return [payload]
        return payload

    def _observation(
        self, fact_type: str, value: Any, unit: str, raw: dict[str, Any]
    ) -> ObservationCreate:
        return ObservationCreate(
            tenant_id=self.tenant_id,
            source_id=self.source_id,
            source_type="windows_agent",
            fact_type=fact_type,
            fact_value={"value": value} if not isinstance(value, dict) else value,
            unit=unit,
            quality_class=QualityClass.Q1,
            raw_payload=raw,
        )

    def capture_cpu(self) -> list[ObservationCreate]:
        rows = self._run_ps(CPU_QUERY)
        return [
            self._observation(
                "cpu_utilization_percent",
                row["PercentProcessorTime"],
                "percent",
                {"row": row},
            )
            for row in rows
        ]

    def capture_memory(self) -> list[ObservationCreate]:
        observations: list[ObservationCreate] = []
        for row in self._run_ps(MEMORY_QUERY):
            free_bytes = int(row["FreePhysicalMemory"]) * 1024
            total_bytes = int(row["TotalVisibleMemorySize"]) * 1024
            observations.append(
                self._observation(
                    "memory_free_bytes", free_bytes, "bytes", {"row": row}
                )
            )
            observations.append(
                self._observation(
                    "memory_total_bytes", total_bytes, "bytes", {"row": row}
                )
            )
        return observations

    def capture_disks(self) -> list[ObservationCreate]:
        observations: list[ObservationCreate] = []
        for row in self._run_ps(DISK_QUERY):
            device = row["DeviceID"]
            observations.append(
                self._observation(
                    "disk_free_bytes", row["FreeSpace"], "bytes", {"device": device, "row": row}
                )
            )
            observations.append(
                self._observation(
                    "disk_total_bytes", row["Size"], "bytes", {"device": device, "row": row}
                )
            )
        return observations

    def capture_services(self) -> list[ObservationCreate]:
        return [
            self._observation(
                "windows_service_state",
                {
                    "name": row["Name"],
                    "state": row["State"],
                    "start_mode": row["StartMode"],
                    "display_name": row["DisplayName"],
                },
                "",
                {"row": row},
            )
            for row in self._run_ps(SERVICES_QUERY)
        ]

    def capture_event_log(self) -> list[ObservationCreate]:
        return [
            self._observation(
                "windows_event_log",
                {
                    "logfile": row.get("Logfile"),
                    "source": row.get("SourceName"),
                    "event_code": row.get("EventCode"),
                    "type": row.get("Type"),
                    "time_written": row.get("TimeWritten"),
                    "message": row.get("Message"),
                },
                "",
                {"row": row},
            )
            for row in self._run_ps(EVENT_LOG_QUERY)
        ]

    def capture_all(self) -> list[ObservationCreate]:
        captures = [
            self.capture_cpu(),
            self.capture_memory(),
            self.capture_disks(),
            self.capture_services(),
            self.capture_event_log(),
        ]
        return [obs for obs_list in captures for obs in obs_list]