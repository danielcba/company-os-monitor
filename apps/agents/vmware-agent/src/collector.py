"""VMware Observation Capture - P1: Immutable capture only (vSphere API).

Each property produces one Observation per instance (per datastore, per VM,
per snapshot, per ESXi host). The collector never interprets: it captures raw values.
"""
import uuid
from datetime import UTC, datetime
from typing import Any

from libs.perception.observation import ObservationCreate, QualityClass
from pyVim.connect import SmartConnect
from pyVmomi import vim


def connect_vcenter(host: str, user: str, password: str, port: int = 443) -> vim.ServiceContent:
    """Connect to vCenter over HTTPS (TLS) and return the ServiceContent."""
    service_instance = SmartConnect(host=host, user=user, pwd=password, port=port)
    return service_instance.RetrieveContent()


class VMwareCollector:
    def __init__(self, tenant_id: uuid.UUID, source_id: uuid.UUID, content: vim.ServiceContent):
        self.tenant_id = tenant_id
        self.source_id = source_id
        self.content = content

    def _views(self, vim_type: type) -> list[Any]:
        """Return the objects of `vim_type` under the root folder (recursive)."""
        view = self.content.viewManager.CreateContainerView(
            self.content.rootFolder, [vim_type], recursive=True
        )
        try:
            return list(view.view)
        finally:
            view.Destroy()

    def _observation(self, fact_type: str, value: Any, unit: str, raw: dict[str, Any]) -> ObservationCreate:
        return ObservationCreate(
            tenant_id=self.tenant_id,
            source_id=self.source_id,
            source_type="vmware_agent",
            fact_type=fact_type,
            fact_value={"value": value} if not isinstance(value, dict) else value,
            unit=unit,
            quality_class=QualityClass.Q1,
            raw_payload=raw,
        )

    def capture_datastores(self) -> list[ObservationCreate]:
        observations: list[ObservationCreate] = []
        for ds in self._views(vim.Datastore):
            summary = ds.summary
            observations.append(
                self._observation(
                    "datastore_capacity_bytes",
                    summary.capacity,
                    "bytes",
                    {"datastore": summary.name},
                )
            )
            observations.append(
                self._observation(
                    "datastore_free_bytes",
                    summary.freeSpace,
                    "bytes",
                    {"datastore": summary.name},
                )
            )
        return observations

    def capture_vm_power_states(self) -> list[ObservationCreate]:
        return [
            self._observation(
                "vm_power_state",
                {"name": vm.name, "power_state": str(vm.runtime.powerState)},
                "",
                {"vm": vm.summary.config.uuid},
            )
            for vm in self._views(vim.VirtualMachine)
        ]

    def _snapshot_entries(self, snapshots: list[Any]) -> list[tuple[str, datetime]]:
        entries: list[tuple[str, datetime]] = []
        for snapshot in snapshots or []:
            entries.append((snapshot.name, snapshot.createTime))
            entries.extend(self._snapshot_entries(snapshot.childSnapshotList))
        return entries

    def capture_snapshots(self) -> list[ObservationCreate]:
        observations: list[ObservationCreate] = []
        now = datetime.now(UTC)
        for vm in self._views(vim.VirtualMachine):
            snapshot_data = vm.snapshot
            if snapshot_data is None:
                continue
            for name, created_at in self._snapshot_entries(snapshot_data.rootSnapshotList):
                created_at_utc = created_at.replace(tzinfo=UTC)
                age_days = (now - created_at_utc).days
                observations.append(
                    self._observation(
                        "vm_snapshot_age_days",
                        {
                            "vm": vm.name,
                            "snapshot_name": name,
                            "age_days": age_days,
                            "created_at": created_at_utc.isoformat(),
                        },
                        "days",
                        {"vm": vm.summary.config.uuid},
                    )
                )
        return observations

    def capture_host_health(self) -> list[ObservationCreate]:
        observations: list[ObservationCreate] = []
        for host in self._views(vim.HostSystem):
            health_state = host.runtime.healthState
            state = getattr(health_state, "state", str(health_state))
            system_info = host.hardware.systemInfo
            observations.append(
                self._observation(
                    "esxi_host_health",
                    {
                        "host": host.name,
                        "health_state": state,
                        "power_state": str(host.runtime.powerState),
                        "model": system_info.model,
                    },
                    "",
                    {"host": host.name},
                )
            )
        return observations

    def capture_all(self) -> list[ObservationCreate]:
        captures = [
            self.capture_datastores(),
            self.capture_vm_power_states(),
            self.capture_snapshots(),
            self.capture_host_health(),
        ]
        return [obs for obs_list in captures for obs in obs_list]