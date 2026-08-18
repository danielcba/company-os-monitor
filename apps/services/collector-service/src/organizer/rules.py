"""Evidence Organization Rules - Perception/Organize.

Each rule is a pure function over immutable Observations (P1). It returns a
list of Organizations (or an empty list when no organization applies). Rules
only group and describe facts; they never interpret, predict, or recommend.
"""
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta

from libs.cognitive_core.observation_bus import Observation
from libs.perception.observation import QualityClass


@dataclass(frozen=True)
class Organization:
    """A coherent, factual organization of one or more observations."""

    organization_type: str
    description: str  # factual only - no interpretation or prediction
    observation_ids: list[uuid.UUID]
    quality_class: QualityClass
    tenant_id: uuid.UUID


def _group_by(observations: list[Observation], attr: str) -> dict:
    groups: dict = defaultdict(list)
    for obs in observations:
        groups[getattr(obs, attr)].append(obs)
    return groups


def _within_window(observations: list[Observation], minutes: float) -> bool:
    if len(observations) < 2:
        return True
    times = sorted(obs.captured_at for obs in observations)
    return (times[-1] - times[0]) <= timedelta(minutes=minutes)


def _pair_usage(
    observations: list[Observation], free_type: str, total_type: str
) -> list[tuple[float, list[Observation]]]:
    """Free-percent for paired free/total observations (keyed by resource).

    The key comes from raw_payload (device/datastore/mountpoint); a lone pair
    without a key is matched by source (already scoped by the caller).
    """
    pairs: dict = defaultdict(dict)
    for obs in observations:
        if obs.fact_type == free_type:
            raw = obs.raw_payload
            key = (
                raw.get("device")
                or raw.get("datastore")
                or raw.get("mountpoint")
                or raw.get("repository")
                or "default"
            )
            pairs[key]["free"] = obs
        elif obs.fact_type == total_type:
            raw = obs.raw_payload
            key = (
                raw.get("device")
                or raw.get("datastore")
                or raw.get("mountpoint")
                or raw.get("repository")
                or "default"
            )
            pairs[key]["total"] = obs
    result: list[tuple[float, list[Observation]]] = []
    for pair in pairs.values():
        free_obs = pair.get("free")
        total_obs = pair.get("total")
        if free_obs is None or total_obs is None:
            continue
        total = total_obs.fact_value.get("value") or total_obs.fact_value.get("total_bytes")
        free = free_obs.fact_value.get("value") or free_obs.fact_value.get("free_bytes")
        if total and free is not None:
            result.append((float(free) / float(total) * 100.0, [free_obs, total_obs]))
    return result


def _fact_number(obs: Observation, key: str) -> float | None:
    value = obs.fact_value.get(key)
    if value is None:
        value = obs.fact_value.get("value")
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------------------
# 1) Resource Exhaustion
#    cpu_util > 90% AND memory > 85% AND disk > 85% (same source, 5-min window)
#    Q1 if every observation is Q1, else Q2.
# ---------------------------------------------------------------------------
def _cpu_observations(group: list[Observation]) -> list[tuple[float, Observation]]:
    out = []
    for obs in group:
        if obs.fact_type != "cpu_utilization_percent":
            continue
        value = _fact_number(obs, "value")
        if value is not None:
            out.append((value, obs))
    return out


def _memory_usage(group: list[Observation]) -> list[tuple[float, list[Observation]]]:
    out = []
    for obs in group:
        if obs.fact_type != "memory_usage":
            continue
        total = obs.fact_value.get("total_bytes")
        used = obs.fact_value.get("used_bytes")
        if used is None and total:
            used = total - obs.fact_value.get("free_bytes", 0)
        if total:
            out.append((float(used) / float(total) * 100.0, [obs]))
    for free_pct, pair_obs in _pair_usage(group, "memory_free_bytes", "memory_total_bytes"):
        out.append((100.0 - free_pct, pair_obs))
    return out


def _disk_usage(group: list[Observation]) -> list[tuple[float, list[Observation]]]:
    out = []
    for obs in group:
        if obs.fact_type != "disk_usage":
            continue
        total = obs.fact_value.get("total_bytes")
        used = obs.fact_value.get("used_bytes")
        if used is None and total:
            used = total - obs.fact_value.get("free_bytes", 0)
        if total:
            out.append((float(used) / float(total) * 100.0, [obs]))
    for free_pct, pair_obs in _pair_usage(group, "disk_free_bytes", "disk_total_bytes"):
        out.append((100.0 - free_pct, pair_obs))
    return out


def resource_exhaustion_evidence(
    observations: list[Observation],
    window_minutes: float = 5.0,
    cpu_threshold: float = 90.0,
    memory_threshold: float = 85.0,
    disk_threshold: float = 85.0,
) -> list[Organization]:
    results: list[Organization] = []
    for source_id, group in _group_by(observations, "source_id").items():
        cpus = _cpu_observations(group)
        mems = _memory_usage(group)
        disks = _disk_usage(group)
        if not cpus or not mems or not disks:
            continue
        cpu_pct, cpu_obs = max(cpus, key=lambda item: item[0])
        mem_pct, mem_obs = max(mems, key=lambda item: item[0])
        disk_pct, disk_obs = max(disks, key=lambda item: item[0])
        if cpu_pct <= cpu_threshold or mem_pct <= memory_threshold or disk_pct <= disk_threshold:
            continue
        matched = [cpu_obs] + mem_obs + disk_obs
        if not _within_window(matched, window_minutes):
            continue
        quality = (
            QualityClass.Q1
            if all(obs.quality_class == QualityClass.Q1 for obs in matched)
            else QualityClass.Q2
        )
        description = (
            f"Within {window_minutes} min on source {source_id}: "
            f"cpu_utilization_percent={cpu_pct:.1f}, memory_usage_percent={mem_pct:.1f}, "
            f"disk_usage_percent={disk_pct:.1f}."
        )
        results.append(
            Organization(
                organization_type="resource_exhaustion_evidence",
                description=description,
                observation_ids=[obs.id for obs in matched],
                quality_class=quality,
                tenant_id=cpu_obs.tenant_id,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 2) Service Degradation
#    windows_service_state=Stopped(Auto) + windows_event_log Type=Error
#    (same source, 15-min window) -> Q1
# ---------------------------------------------------------------------------
def _service_is_stopped_auto(obs: Observation) -> bool:
    value = obs.fact_value
    return value.get("state") == "Stopped" and value.get("start_mode") == "Auto"


def _event_is_error(obs: Observation) -> bool:
    return str(obs.fact_value.get("type") or "").lower() == "error"


def service_degradation_evidence(
    observations: list[Observation],
    window_minutes: float = 15.0,
) -> list[Organization]:
    results: list[Organization] = []
    for source_id, group in _group_by(observations, "source_id").items():
        stopped = [obs for obs in group if obs.fact_type == "windows_service_state" and _service_is_stopped_auto(obs)]
        errors = [obs for obs in group if obs.fact_type == "windows_event_log" and _event_is_error(obs)]
        if not stopped or not errors:
            continue
        service = stopped[0]
        service_name = service.fact_value.get("name")
        event = next(
            (
                err
                for err in errors
                if service_name
                and str(err.fact_value.get("source") or "").lower() == str(service_name).lower()
            ),
            None,
        )
        if event is None:
            event = errors[0]
        matched = [service, event]
        if not _within_window(matched, window_minutes):
            continue
        description = (
            f"Within {window_minutes} min on source {source_id}: "
            f"windows_service_state service={service.fact_value.get('name')} state=Stopped "
            f"start_mode=Auto; windows_event_log type={event.fact_value.get('type')} "
            f"source={event.fact_value.get('source')} event_code={event.fact_value.get('event_code')}."
        )
        results.append(
            Organization(
                organization_type="service_degradation_evidence",
                description=description,
                observation_ids=[obs.id for obs in matched],
                quality_class=QualityClass.Q1,
                tenant_id=service.tenant_id,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 3) Authentication Anomaly
#    ad_account_lockout + ad_privileged_group_membership change (same tenant,
#    1-hr window) -> Q2
# ---------------------------------------------------------------------------
def _membership_changed(obs: Observation) -> bool:
    value = obs.fact_value
    if value.get("changed") is True or value.get("membership_changed") is True:
        return True
    return value.get("event") == "change"


def auth_anomaly_evidence(
    observations: list[Observation],
    window_minutes: float = 60.0,
) -> list[Organization]:
    results: list[Organization] = []
    for tenant_id, group in _group_by(observations, "tenant_id").items():
        lockouts = [obs for obs in group if obs.fact_type == "ad_account_lockout"]
        changes = [
            obs
            for obs in group
            if obs.fact_type == "ad_privileged_group_membership" and _membership_changed(obs)
        ]
        if not lockouts or not changes:
            continue
        lockout, change = lockouts[0], changes[0]
        if not _within_window([lockout, change], window_minutes):
            continue
        account = lockout.fact_value.get("account") or lockout.fact_value.get("account_name") or "unknown"
        group_name = change.fact_value.get("group") or change.fact_value.get("group_name") or "unknown"
        description = (
            f"Within {window_minutes} min in tenant {tenant_id}: ad_account_lockout "
            f"account={account}; ad_privileged_group_membership changed group={group_name}."
        )
        results.append(
            Organization(
                organization_type="auth_anomaly_evidence",
                description=description,
                observation_ids=[lockout.id, change.id],
                quality_class=QualityClass.Q2,
                tenant_id=tenant_id,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 4) Backup Failure
#    backup_job_status=Failed + repo_free < 10% (same source, 1-hr window) -> Q1
# ---------------------------------------------------------------------------
def _repo_free_candidates(group: list[Observation]) -> list[tuple[float, list[Observation]]]:
    out: list[tuple[float, list[Observation]]] = []
    for obs in group:
        if obs.fact_type != "repo_free_percent":
            continue
        value = _fact_number(obs, "value")
        if value is not None:
            out.append((value, [obs]))
    for free_pct, pair_obs in _pair_usage(group, "repo_free_bytes", "repo_capacity_bytes"):
        out.append((free_pct, pair_obs))
    return sorted(out, key=lambda item: item[0])


def backup_failure_evidence(
    observations: list[Observation],
    window_minutes: float = 60.0,
    repo_free_threshold: float = 10.0,
) -> list[Organization]:
    results: list[Organization] = []
    for source_id, group in _group_by(observations, "source_id").items():
        failed = [
            obs
            for obs in group
            if obs.fact_type == "backup_job_status"
            and str(obs.fact_value.get("status") or "").lower() == "failed"
        ]
        repo_low = _repo_free_candidates(group)
        if not failed or not repo_low:
            continue
        job = failed[0]
        free_pct, repo_obs = repo_low[0]
        if free_pct >= repo_free_threshold:
            continue
        matched = [job] + repo_obs
        if not _within_window(matched, window_minutes):
            continue
        description = (
            f"Within {window_minutes} min on source {source_id}: backup_job_status=Failed "
            f"job={job.fact_value.get('job') or ''}; repo_free_percent={free_pct:.1f}."
        )
        results.append(
            Organization(
                organization_type="backup_failure_evidence",
                description=description,
                observation_ids=[obs.id for obs in matched],
                quality_class=QualityClass.Q1,
                tenant_id=job.tenant_id,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 5) VMware Capacity
#    datastore_free < 15% + vm_snapshot_age_days > 7 (same tenant/cluster,
#    30-min window) -> Q1
# ---------------------------------------------------------------------------
def _datastore_free_candidates(
    group: list[Observation],
) -> list[tuple[float, list[Observation]]]:
    out: list[tuple[float, list[Observation]]] = []
    for obs in group:
        if obs.fact_type != "datastore_free_percent":
            continue
        value = _fact_number(obs, "value")
        if value is not None:
            out.append((value, [obs]))
    for free_pct, pair_obs in _pair_usage(group, "datastore_free_bytes", "datastore_capacity_bytes"):
        out.append((free_pct, pair_obs))
    return sorted(out, key=lambda item: item[0])


def _snapshot_older_than(obs: Observation, days: float) -> bool:
    age = obs.fact_value.get("age_days")
    if age is None:
        age = obs.fact_value.get("value")
    try:
        return age is not None and float(age) > days
    except (TypeError, ValueError):
        return False


def vmware_capacity_evidence(
    observations: list[Observation],
    window_minutes: float = 30.0,
    datastore_free_threshold: float = 15.0,
    snapshot_age_days: float = 7.0,
) -> list[Organization]:
    results: list[Organization] = []
    for tenant_id, group in _group_by(observations, "tenant_id").items():
        datastore_low = _datastore_free_candidates(group)
        snapshots = [
            obs
            for obs in group
            if obs.fact_type == "vm_snapshot_age_days"
            and _snapshot_older_than(obs, snapshot_age_days)
        ]
        if not datastore_low or not snapshots:
            continue
        free_pct, ds_obs = datastore_low[0]
        if free_pct >= datastore_free_threshold:
            continue
        snapshot = snapshots[0]
        matched = ds_obs + [snapshot]
        if not _within_window(matched, window_minutes):
            continue
        description = (
            f"Within {window_minutes} min in tenant {tenant_id}: "
            f"datastore_free_percent={free_pct:.1f}; "
            f"vm_snapshot_age_days={snapshot.fact_value.get('age_days')} "
            f"vm={snapshot.fact_value.get('vm')}."
        )
        results.append(
            Organization(
                organization_type="vmware_capacity_evidence",
                description=description,
                observation_ids=[obs.id for obs in matched],
                quality_class=QualityClass.Q1,
                tenant_id=tenant_id,
            )
        )
    return results


# ---------------------------------------------------------------------------
# 6) Network Anomaly
#    interface_errors > threshold + port_state_change (same source, 15-min
#    window) -> Q2
# ---------------------------------------------------------------------------
def _interface_errors(obs: Observation) -> float:
    value = _fact_number(obs, "value")
    if value is not None:
        return value
    value = _fact_number(obs, "errors")
    return value if value is not None else 0.0


def network_anomaly_evidence(
    observations: list[Observation],
    window_minutes: float = 15.0,
    error_threshold: float = 100.0,
) -> list[Organization]:
    results: list[Organization] = []
    for source_id, group in _group_by(observations, "source_id").items():
        high_errors = [
            obs
            for obs in group
            if obs.fact_type == "interface_errors" and _interface_errors(obs) > error_threshold
        ]
        changes = [obs for obs in group if obs.fact_type == "port_state_change"]
        if not high_errors or not changes:
            continue
        errors_obs = max(high_errors, key=_interface_errors)
        change = changes[0]
        if not _within_window([errors_obs, change], window_minutes):
            continue
        description = (
            f"Within {window_minutes} min on source {source_id}: "
            f"interface_errors={_interface_errors(errors_obs):.0f} "
            f"interface={errors_obs.raw_payload.get('interface') or errors_obs.fact_value.get('interface') or ''}; "
            f"port_state_change detected."
        )
        results.append(
            Organization(
                organization_type="network_anomaly_evidence",
                description=description,
                observation_ids=[errors_obs.id, change.id],
                quality_class=QualityClass.Q2,
                tenant_id=errors_obs.tenant_id,
            )
        )
    return results