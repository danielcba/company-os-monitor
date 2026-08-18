# Company OS Monitor - FASE 3: Perception Layer - Observation Capture & Evidence Organization

## Principio Rector: P1 — The Primacy of Observation

> **Reality is accessed only through observations. Observations are immutable. Meaning is never extracted directly from reality. Meaning emerges later, through reasoning.**

La **Perception Layer** es la única entrada de realidad al sistema. Los agentes son **Observation Capturers** (capacidad cognitiva: Capture). El Collector Service es el **Evidence Organizer** (capacidad cognitiva: Organize). **Ningún componente en esta capa interpreta, predice, o recomienda.**

---

## Cognitive Contracts de la Perception Layer

### 1. Observation Capturer (Agentes) — Concepto: Observation | Familia: Perception | Capacidad: Capture

**Cognitive Contract:**
- **Input**: Hecho, evento, señal o condición en la realidad (servidor Linux, Windows, VMware, red, backup)
- **Transformation**: Capturar el hecho **sin interpretación** — preservar exactamente como ocurrió
- **Output**: **Observation inmutable** con quality_class asignada (Q1-Q4) para calibración de Confidence

**Constraint (P1):** Observation y interpretación **nunca se mezclan**. El agente no decide si "el disco está lleno" — solo captura `disk_free_bytes: 1024000, disk_total_bytes: 1073741824`.

**Trazabilidad (provenance de cada artefacto):** cada artefacto de la Perception Layer porta su *owner* (quién capturó/produjo: `source_id`/`source_type` en Observation; el componente origen en Evidence/Context) y su *claim* (qué afirma: `fact_type`+`fact_value` en Observation; `organization_type`+`description` en Evidence; `mental_model_id`+`coherence_score` en Context). La formalización de campos explícitos `owner`/`claim` queda para Fase 5+; no se cambian los contratos de Sprint 1-4.

---

### 2. Evidence Organizer (Collector Service) — Concepto: Evidence | Familia: Perception | Capacidad: Organize

**Cognitive Contract:**
- **Input**: Una o más Observations (inmutables)
- **Transformation**: Organizar observaciones relacionadas en un cuerpo coherente y objetivo de información de soporte
- **Output**: **Evidence** con Quality Class (Q1-Q4) y peso wᵢ para Confidence Calibration Model

**Constraint (Evidence design implications):** Evidence **nunca interpreta observaciones, predice resultados, ni recomienda acciones**. Su única responsabilidad: organizar observaciones en estructuras coherentes para que Context pueda explicarlas.

---

## Observation Sources (Agentes) — Mapeo a Reality

Cada fuente de realidad tiene su Observation Capturer especializado. Todos producen **Observations inmutables** con schema común.

### Windows (WMI Remoto + WinRM) — Observation Capturer: `windows-agent`

| Observation Type | WQL / Query | Fact Type | Quality Class | Frequency |
|------------------|-------------|-----------|---------------|-----------|
| Eventos Críticos del Sistema | `SELECT * FROM Win32_NTLogEvent WHERE Type = 'Error' OR Type = 'Critical'` | `windows_event_log` | Q1 (Direct Measurement) | 5 min |
| Servicios Detenidos (Auto) | `SELECT * FROM Win32_Service WHERE State = 'Stopped' AND StartMode = 'Auto'` | `windows_service_state` | Q1 | 5 min |
| Usuarios Bloqueados AD | `Search-ADAccount -LockedOut` | `ad_account_lockout` | Q1 | 15 min |
| Usuarios Inactivos AD | `Search-ADAccount -Inactive (Days:$days)` | `ad_account_inactive` | Q2 (Corroborated - multi-DC) | 1 hora |
| CPU Utilization | `Win32_PerfFormattedData_PerfOS_Processor (% Processor Time)` | `cpu_utilization_percent` | Q1 | 1 min |
| Memoria Libre/Total | `Win32_OperatingSystem (FreePhysicalMemory, TotalVisibleMemorySize)` | `memory_free_bytes`, `memory_total_bytes` | Q1 | 1 min |
| Disco Libre/Total | `Win32_LogicalDisk (FreeSpace, Size)` | `disk_free_bytes`, `disk_total_bytes` | Q1 | 5 min |

**Implementation Notes:**
- Librería: `pywinrm` + `wmi` (Python)
- WinRM sobre HTTPS (TLS 1.3) — cifrado en tránsito
- Credenciales gestionadas via HashiCorp Vault (producción) / python-dotenv (desarrollo)
- Cada query produce **una Observation por instancia** (un registro por servicio, por disco, por evento)

---

### Active Directory (LDAP + PowerShell) — Observation Capturer: `ad-agent`

| Observation Type | Query / Filter | Fact Type | Quality Class | Frequency |
|------------------|----------------|-----------|---------------|-----------|
| Usuarios inactivos 90+ días | `(LastLogonTimestamp < (Now - 90d)) AND (Enabled = TRUE)` | `ad_user_last_logon` | Q2 (Corroborated - replica sync) | 1 hora |
| Contraseñas por vencer | `(PasswordLastSet < (Now - $maxPwdAge + 14d))` | `ad_password_age_days` | Q1 | 1 hora |
| Miembros grupos privilegiados | `Members of: Domain Admins, Enterprise Admins, Schema Admins` | `ad_privileged_group_membership` | Q1 | 15 min |
| Cambios GPO | `gpcFileSysPath` modification timestamps | `ad_gpo_change` | Q2 | 30 min |
| Replication health | `repadmin /showrepl` status | `ad_replication_status` | Q1 | 5 min |

**Implementation Notes:**
- LDAP sobre TLS (StartTLS) para queries de lectura
- PowerShell Remoting (WinRM) para queries operacionales
- Paginación LDAP (`pagedResultsControl`) para dominios grandes
- Quality Class Q2 para LastLogonTimestamp (replica convergence delay)

---

### VMware (vSphere API - pyVmomi) — Observation Capturer: `vmware-agent`

| Observation Type | Property / Query | Fact Type | Quality Class | Frequency |
|------------------|------------------|-----------|---------------|-----------|
| Snapshots antiguos | `snapshot.create_time < (now - 7d)` | `vm_snapshot_age_days` | Q1 | 30 min |
| Datastore capacidad | `datastore.summary.capacity`, `datastore.summary.freeSpace` | `datastore_capacity_bytes`, `datastore_free_bytes` | Q1 | 5 min |
| VM Power State | `vm.runtime.powerState` | `vm_power_state` | Q1 | 1 min |
| CPU Ready / Usage | `vm.summary.quickStats.overallCpuUsage`, `cpuReady` | `vm_cpu_usage_mhz`, `vm_cpu_ready_percent` | Q1 | 1 min |
| Memoria Active / Granted | `vm.summary.quickStats.guestMemoryUsage`, `hostMemoryUsage` | `vm_memory_active_mb`, `vm_memory_granted_mb` | Q1 | 1 min |
| Disco Usage Trend | `collect_historical(vm, 'disk.usage.average', days=30)` | `vm_disk_usage_trend` | Q3 (Statistical Regularity) | 1 hora |
| Host Health | `host.runtime.healthState`, `host.hardware.systemInfo` | `esxi_host_health` | Q1 | 5 min |
| Cluster DRS/HA | `cluster.drsRecommendation`, `cluster.dasConfig` | `cluster_drs_recommendation`, `cluster_ha_status` | Q2 | 15 min |

**Implementation Notes:**
- `pyVmomi` (vSphere SDK for Python)
- Conexión vCenter sobre HTTPS (TLS 1.3), cert verification enabled
- Session pooling para eficiencia (reuse vim.ServiceInstance)
- PropertyCollector con `RetrievePropertiesEx` para batch queries
- Historical collection via `QueryPerf` (Q3 - Statistical Regularity)

---

### Backup (Veeam - REST API) — Observation Capturer: `veeam-agent`

| Observation Type | Endpoint | Fact Type | Quality Class | Frequency |
|------------------|----------|-----------|---------------|-----------|
| Backup Points | `GET /api/backups/{id}/points` | `backup_point_timestamp`, `backup_point_size_bytes` | Q1 | 1 hora post-ventana |
| Job Last Status | `GET /api/jobs/{id}/laststatus` | `backup_job_status`, `backup_job_duration_sec`, `backup_job_processed_bytes` | Q1 | 1 hora post-ventana |
| Repository Capacity | `GET /api/repositories` | `repo_capacity_bytes`, `repo_free_bytes` | Q1 | 30 min |
| Tape/Offsite Status | `GET /api/tapejobs/{id}/laststatus` | `tape_job_status`, `tape_media_pool_free` | Q1 | 1 hora |

**Implementation Notes:**
- Veeam REST API v1/v2 (Bearer token auth, short-lived)
- Pagination (`$top`, `$skip`) para repositorios grandes
- Rate limiting respetado (Veeam API limits)
- Quality Class Q1 — mediciones directas del sistema de backup

---

### Redes (Nmap + SNMP) — Observation Capturer: `network-agent`

| Observation Type | Command / Query | Fact Type | Quality Class | Frequency |
|------------------|-----------------|-----------|---------------|-----------|
| Descubrimiento Hosts | `nmap -sS -T4 -O -oX output.xml <CIDR>` | `network_host_discovered`, `host_os_fingerprint`, `host_open_ports` | Q2 (Corroborated - multi-scan) | 4 horas |
| SNMP Interface Stats | `snmpwalk -v2c -c <community> <ip> 1.3.6.1.2.1.2.2` (ifTable) | `interface_in_octets`, `interface_out_octets`, `interface_errors`, `interface_discards` | Q1 | 1 min |
| SNMP CPU/Memory | `snmpwalk ... 1.3.6.1.4.1.9.9.109` (Cisco) / vendor MIBs | `device_cpu_percent`, `device_memory_percent` | Q1 | 5 min |
| Cambios Topología | Diff estado puertos (15 min vs actual) | `port_state_change`, `vlan_change`, `neighbor_change` | Q2 | 15 min |
| BGP/OSPF Neighbors | `snmpwalk ... bgpPeerState`, `ospfNbrState` | `routing_neighbor_state` | Q1 | 1 min |

**Implementation Notes:**
- `python-nmap` wrapper para Nmap XML parsing
- `pysnmp` para SNMP v2c/v3 (AuthPriv para producción)
- MIBs vendor-specific cargadas dinámicamente
- Nmap `--max-retries 2 --host-timeout 30s` para red controlada
- Quality Class Q2 para discovery (false positives/negatives posibles)

---

## Evidence Organization Rules (Collector Service)

El Collector Service recibe **Observations** de todos los agentes y produce **Evidence** aplicando reglas de organización:

### Reglas de Organización por Dominio

| Dominio | Evidence Type | Observation Patterns Organized | Quality Class Logic |
|---------|---------------|--------------------------------|---------------------|
| **Resource Exhaustion** | `resource_exhaustion_evidence` | cpu_util > 90% + memory > 85% + disk > 85% (same host, 5-min window) | Q1 if all metrics Q1; Q2 if any Q2 |
| **Service Degradation** | `service_degradation_evidence` | windows_service_state=Stopped(Auto) + event_log=Error (same service, 15-min window) | Q1 |
| **Authentication Anomaly** | `auth_anomaly_evidence` | ad_account_lockout + ad_privileged_group_membership_change (same tenant, 1-hr window) | Q2 |
| **Backup Failure** | `backup_failure_evidence` | backup_job_status=Failed + repo_free < 10% (same repo, 1-hr window) | Q1 |
| **VMware Capacity** | `vmware_capacity_evidence` | datastore_free < 15% + vm_snapshot_age > 7d (same cluster, 30-min window) | Q1 |
| **Network Anomaly** | `network_anomaly_evidence` | interface_errors > threshold + port_state_change (same switch, 15-min window) | Q2 |

### Evidence Quality Class Assignment (per Evidence Spec)

| Quality Class | Criteria | Weight Range (wᵢ) | Confidence Impact |
|---------------|----------|-------------------|-------------------|
| **Q1 — Direct Measurement** | Observaciones capturadas directamente del sistema de interés (instrument reading, primary record) | wᵢ ∈ [0.75, 1.0] | Highest reliability |
| **Q2 — Corroborated Inference** | Múltiples observaciones independientes convergen en la misma organización (multi-source, coordinated) | wᵢ ∈ [0.50, 0.75) | High reliability |
| **Q3 — Statistical Regularity** | Organización soportada por métodos agregados/muestreo con metodología documentada | wᵢ ∈ [0.25, 0.50) | Medium reliability |
| **Q4 — Anecdotal / Single-Source** | Organización descansando en una observación o fuente no repetible | wᵢ ∈ [0.00, 0.25) | Lowest reliability; weight capped |

**Regla crítica:** La clase se asigna **en la creación**, nunca se retrofitea para encajar una conclusión (Evidence spec).

---

## Perception Layer Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            REALITY                                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐ ┌─────────────┐          │
│  │   Linux     │ │  Windows    │ │  VMware     │ │  Network/   │          │
│  │  Servers    │ │  Servers    │ │  vCenter    │ │  Backup     │          │
│  └──────┬──────┘ └──────┬──────┘ └──────┬──────┘ └──────┬──────┘          │
└─────────┼───────────────┼───────────────┼───────────────┼──────────────────┘
          │               │               │               │
          ▼               ▼               ▼               ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      PERCEPTION LAYER                                       │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  OBSERVATION CAPTURERS (Agentes) — Concept: Observation            │   │
│  │  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌────────────┐      │   │
│  │  │linux-agent │ │windows-agent│ │vmware-agent│ │network-agent│      │   │
│  │  │(psutil/SSH)│ │(WMI/WinRM) │ │(pyVmomi)   │ │(nmap/SNMP) │      │   │
│  │  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └─────┬──────┘      │   │
│  │        │              │              │              │              │   │
│  │        └──────────────┼──────────────┼──────────────┘              │   │
│  │                       ▼              ▼              ▼              │   │
│  │            ┌─────────────────────────────────────────────────┐    │   │
│  │            │        OBSERVATION BUS (immutable queue)        │    │   │
│  │            │  - tenant_id, source_id, fact_type, fact_value,  │    │   │
│  │            │    unit, captured_at, quality_class, raw_payload │    │   │
│  │            └────────────────────────┬────────────────────────┘    │   │
│  └─────────────────────────────────────┼─────────────────────────────┘   │
│                                        │                                 │
│                                        ▼                                 │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  EVIDENCE ORGANIZER (Collector Service) — Concept: Evidence        │   │
│  │  Input: Observations (batched by tenant, time window, domain)      │   │
│  │  Transform: Organization Rules (domain-specific patterns above)    │   │
│  │  Output: Evidence (Q1-Q4, weighted, organized_at, description)     │   │
│  │                                                                     │   │
│  │  ┌─────────────────────────────────────────────────────────────┐  │   │
│  │  │ EVIDENCE STORE (PostgreSQL/TimescaleDB - evidence table)    │  │   │
│  │  └─────────────────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                        │
                                        ▼ (Evidence enables Context)
┌─────────────────────────────────────────────────────────────────────────────┐
│                      REASONING LAYER (FASE 4)                               │
│  Context Activation → Pattern Detection → Anomaly Detection →              │
│  Hypothesis Generation → Insight Restructuring                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Design Implications (per Cognitive Architecture)

1. **R1/R2 Compliance**: Cada agente implementa **exactly one** capacidad cognitiva (Observation Capture) con **Cognitive Contract definido**. Collector Service implementa **exactly one** capacidad (Evidence Organization) con **Cognitive Contract definido**.

2. **P1 Enforcement**: Agentes **nunca interpretan**. `disk_free_bytes: 1024000` ≠ "disco lleno". La interpretación ocurre en Context Activation (FASE 4).

3. **R3 Boundary**: Observation Bus es el **cognitive boundary** — raw input no puede saltar a Reasoning/Action sin pasar por Evidence → Context.

4. **Evidence → Confidence Pipeline**: Quality Class (Q1-Q4) asignada en Evidence creation → weight wᵢ → Confidence Calibration Model (FASE 4). No retrofitting.

5. **Immutability**: Observations son **append-only** (INSERT only, no UPDATE/DELETE). Evidence organiza Observations existentes, nunca las modifica.

6. **Multi-tenant Isolation**: `tenant_id` en every Observation y Evidence. No cross-tenant contamination en Perception Layer.

7. **Observability**: Cada Observation Capturer expone health metrics (capture latency, error rate, last successful capture) para metacognitive monitoring.