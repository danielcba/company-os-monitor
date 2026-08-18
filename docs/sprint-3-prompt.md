# SPRINT 3 — EVIDENCE ORGANIZER (Perception: capacidad Organize)

> Persistido desde sesión 2026-08-14. Sesión EVALUADA al inicio.

## Contexto de la sesión previa

- Sprint 1 (COMPLETO): linux-agent (psutil) → Observation Bus (Redis Stream "observations"). `observation_bus.py` con `Observation` (pydantic frozen, P1), `publish`/`consume`/`ack` (se agregó `ObservationBus.ack()`).
- Sprint 2 (COMPLETO, 21/21 tests): multi-agente (windows-agent vía pywinrm/WMI, vmware-agent vía pyVmomi) + collector-service que consume Redis Streams y persiste Observations en Postgres (append-only, dedup idempotente, ack tras INSERT). E2E verificado: 12 observaciones reales persistidas, 0 errores, 0 duplicados.
- Infra corriendo: postgres TimescaleDB 127.0.0.1:5433 (db/user/pass = cosmonitor), redis 127.0.0.1:6379. Schema en `infrastructure/docker/init-sql/01-schema.sql`. Seed tenant sandbox en `02-seed.sql` (id `00000000-0000-0000-0000-000000000001`, ya insertado).
- Marco cognitivo (SOLO LECTURA, no tocar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`. Producto: `/home/dcordoba/Documents/Default Project/company-os-monitor/`.
- Documentación fuente del Sprint: `docs/02-motor-recoleccion.md` (sección "Evidence Organization Rules (Collector Service)" y "Evidence Quality Class Assignment").

## Objetivo

Completar la Perception Layer implementando el **Evidence Organizer** (Contract cognitivo: Concept=Evidence, Familia=Perception, Capacidad=Organize). Input: Observations inmutables ya persistidas en Postgres (batched por tenant + ventana temporal + dominio). Transform: reglas de organización por dominio SIN interpretar/predes/recomendar. Output: fila en tabla `evidence` con quality_class (Q1-Q4) y peso w_i asignados EN LA CREACIÓN (nunca retrofitear).

## Entorno y comandos (OBLIGATORIO respetar)

- Instalación: `pip install --break-system-packages -e ".[dev]"` (Python 3.14 es externally-managed; `.venv` NO funciona; NO inicializar git).
- NO usar `cd` para ejecutar; usar workdir. PYTHONPATH por-app (los paquetes `src/` y `tests/` colisionan si se corren juntas):
  `PYTHONPATH="<ruta_app_src>:<repo_root>" python3 -m pytest <ruta_app/tests> -q`
  con `REPO="/home/dcordoba/Documents/Default Project/company-os-monitor"`.
- Correr TESTS EXISTENTES al final y dejarlos verdes (linux-agent 4, windows-agent 6, vmware-agent 6, collector-service 5).
- Ruff: reducir violaciones nuevas a cero salvo BLE001 (patrón deliberado `except Exception` del repositorio). line-length 100.
- auth en tests de integración con Postgres real: para limpiar datos usar `SET session_replication_role = replica` (superuser) y borrar explícitamente las filas hijas (el trigger de inmutabilidad y la FK cascade sobre hypertable bloquean el DELETE directo; el cascade NORMAL falla por el trigger).

## Proceso obligatorio (policy del marco)

- **Journaling (E6 / Directive 002)**: en cada punto de cambio canónico (cada sesión que crea/modifica/borra archivos) dejar un entry en `journal/YYYY/YYYY-MM-DD.md` siguiendo el formato del marco: `# Journal — YYYY-MM-DD` + secciones `## Theme`, `## Today's Progress`, `## Discoveries`, `## Decisions`, `## Reflection`, `## Quote of the Day`. El journal registra avances, cambios y diarios.

## Entregables

1. **Persistencia de Evidence** (`libs/perception/`): repo append-only para la tabla `evidence` (id, tenant_id, observation_ids UUID[] NOT NULL, organization_type, description, quality_class CHECK Q1-Q4, weight NUMERIC(3,2) CHECK 0-1, organized_at), análogo a `ObservationStore` (INSERT + dedup, verify_connection, close). OJO: schema actual NO tiene trigger de inmutabilidad en `evidence` — agregar trigger equivalente al de `observations` para reforzar P1 (append-only) y verificar con test.

2. **Reglas de organización por dominio** (módulo en `apps/services/collector-service/src/organizer/` o equivalente; funciones puras, testables con observaciones sintéticas):
   - `resource_exhaustion_evidence`: cpu_util>90% + mem>85% + disk>85% (mismo source_id, ventana 5 min) → Q1 si todas las obs son Q1, Q2 si alguna Q2.
   - `service_degradation_evidence`: windows_service_state=Stopped(StartMode=Auto) + windows_event_log Type=Error (mismo source_id, ventana 15 min) → Q1.
   - `auth_anomaly_evidence`: ad_account_lockout + cambio en ad_privileged_group_membership (mismo tenant, 1 h) → Q2.
   - `backup_failure_evidence`: backup_job_status=Failed + repo_free<10% (mismo source_id, 1 h) → Q1.
   - `vmware_capacity_evidence`: datastore_free<15% + vm_snapshot_age_days>7 (mismo tenant/cluster, 30 min) → Q1.
   - `network_anomaly_evidence`: interface_errors>umbral + port_state_change (mismo switch/source_id, 15 min) → Q2.
   - Weight w_i por Quality Class (rango de docs/02): Q1→midrange [0.75,1.0], Q2→[0.50,0.75), etc. Asignar en creación.
   - Regla crítica: description debe ser objetiva/factual (organiza observaciones; NUNCA "disco lleno", solo hechos). R3: NO saltar a Reasoning todavía.

3. **Orquestación en collector-service**: tras persistir el batch de observations (loop existente de Sprint 2), correr el organizer por ventana/tenant y escribir las evidence resultantes (dedup idempotente). Exponer métricas de organizaciones (total_evidence, errors, organization_type por dominio) en /metrics.

4. **Tests** (unit + integración PG):
   - Una prueba por regla con observaciones sintéticas (mismo dominio=True y Negativo).
   - Lógica de Quality Class de evidence (Q1 vs Q2 según composición; description sin interpretación).
   - Dedup de evidence (re-ejecución no duplica).
   - Integración: INSERT evidence en Postgres, read-back, inmutabilidad (trigger bloquea UPDATE/DELETE).
   - Verificar que los 21 tests previos siguen verdes.

5. **Docs de trabajo**: actualizar README (estado Sprint 3 + cómo correr) y .env.example si se agregan variables (ej. ventanas por dominio, umbrales). Journal de la sesión al cierre.

## Cumplimiento cognitivo a validar al cerrar

- R1: componente = exactamente una capacidad (Organize).
- R2: Contract (Input: Observation inmutables → Transform: reglas → Output: Evidence Q1-Q4 + w_i) testeado.
- P1: Evidence nunca modifica observaciones; filas append-only.
- Calidad: class y weight asignados en la creación, sin retrofitting para encajar conclusiones.
- No iniciar Context/Reasoning (FASE 4) — eso es Sprint 4.

## Criterios de aceptación verificables

- pytest verde en las 5 apps (esperado: tests previos + nuevos del organizer/evidence).
- Corriendo collector-service contra la PG real con las observaciones ya persistidas, aparece al menos 1 fila en `evidence` (según datos que existan; si el dataset sintético no dispara reglas, usar siembra temporaria en tests de integración) con observation_ids válidos.
- Trigger de inmutabilidad de evidence probado.