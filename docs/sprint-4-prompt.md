# SPRINT 4 — CONTEXT ACTIVATOR (Perception: capacidad Explain)

> Persistido desde sesión 2026-08-14. Sesión EVALUADA al inicio.

## Contexto de la sesión previa

- Sprint 1 (COMPLETO): linux-agent (psutil) → Observation Bus (Redis Stream "observations"). `observation_bus.py` con `Observation` (pydantic frozen, P1), `publish`/`consume`/`ack`.
- Sprint 2 (COMPLETO): multi-agente (windows-agent vía pywinrm/WMI, vmware-agent vía pyVmomi) + collector-service que consume Redis Streams y persiste Observations en Postgres (append-only, dedup idempotente por (id, captured_at), ack tras INSERT). E2E verificado.
- Sprint 3 (COMPLETO, 55/55 tests: linux 4, windows 6, vmware 6, collector-service 39): Evidence Organizer. `libs/perception/evidence.py` (EvidenceStore, id determinístico uuid5, ON CONFLICT DO NOTHING), `apps/services/collector-service/src/organizer/` (6 reglas puras por dominio, QUALITY_WEIGHTS Q1→0.875, Q2→0.625, Q3→0.375, Q4→0.125 asignados en creación), tabla `evidence` con trigger `evidence_immutable_trigger`. 8 observations y 3 evidence reales en la PG.
- Infra corriendo: postgres TimescaleDB 127.0.0.1:5433 (db/user/pass = cosmonitor), redis 127.0.0.1:6379. Schema en `infrastructure/docker/init-sql/01-schema.sql` — YA incluye la tabla `contexts` (vacía, con índice `idx_contexts_tenant_active`).
- Marco cognitivo (SOLO LECTURA, no tocar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`. Producto: `/home/dcordoba/Documents/Default Project/company-os-monitor/`.
- Documentación fuente del Sprint: `docs/01-fundacion-arquitectura.md` (tabla `contexts`), `docs/02-motor-recoleccion.md`, y el concepto `Context` del marco: `/home/dcordoba/Documents/Default Project/company/company-os-main/docs/cognitive-lexicon/core-concepts/context.md`.

## Objetivo

Completar la Perception Layer implementando el **Context Activator** (Contract cognitivo: Concept=Context, Familia=Perception, Capacidad=Explain). Input: Evidence inmutables ya persistidas en Postgres + Mental Models + Purpose. Transform: competencia de coherencia explicativa entre modelos mentales candidatos SIN fabricar significado (P2). Output: fila en tabla `contexts` (Active Context) con `mental_model_id`, `coherence_score` y `competing_models`, trazable a sus `evidence_ids`.

Regla conceptual del marco que debe gobernar el sprint: **el Context nunca se genera directamente; se activa por competencia de coherencia** (P2). El sistema no "inventa" significado: selecciona el modelo mental más coherente con la evidencia disponible para un propósito.

## Entorno y comandos (OBLIGATORIO respetar)

- Instalación: `pip install --break-system-packages -e ".[dev]"` (Python 3.14 es externally-managed; `.venv` NO funciona; NO inicializar git).
- NO usar `cd` para ejecutar; usar workdir. PYTHONPATH por-app (los paquetes `src/` y `tests/` colisionan si se corren juntas):
  `PYTHONPATH="<ruta_app_src>:<repo_root>" python3 -m pytest <ruta_app/tests> -q`
  con `REPO="/home/dcordoba/Documents/Default Project/company-os-monitor"`.
- Correr TESTS EXISTENTES al final y dejarlos verdes (linux-agent 4, windows-agent 6, vmware-agent 6, collector-service 39).
- Ruff: reducir violaciones nuevas a cero salvo BLE001 (patrón deliberado `except Exception` del repositorio). line-length 100.
- auth en tests de integración con Postgres real: para limpiar datos usar `SET session_replication_role = replica` (superuser) y borrar explícitamente las filas hijas (el trigger de inmutabilidad y la FK cascade sobre hypertable bloquean el DELETE directo; el cascade NORMAL falla por el trigger).

## Proceso obligatorio (policy del marco)

- **Journaling (E6 / Directive 002)**: en cada punto de cambio canónico (cada sesión que crea/modifica/borra archivos) dejar un entry en `journal/YYYY/YYYY-MM-DD.md` siguiendo el formato del marco: `# Journal — YYYY-MM-DD` + secciones `## Theme`, `## Today's Progress`, `## Discoveries`, `## Decisions`, `## Reflection`, `## Quote of the Day`. Listar los archivos que cambiaron.

## Entregables

1. **Modelos mentales** (catálogo por dominio, en `libs/perception/context.py` o módulo dedicado): cada mental model define qué tipo de evidence explica, para qué purpose(s) es relevante, y una firma de coherencia. Deben ser definiciones declarativas (dataclass/pydantic), NO razonamiento.
   - Candidatos mínimos por dominio existente: `resource_pressure`, `service_failure`, `auth_compromise`, `capacity_risk`, `connectivity_degradation` — mapeando a los `organization_type` de Sprint 3 (`resource_exhaustion_evidence`, `service_degradation_evidence`, `auth_anomaly_evidence`, `backup_failure_evidence`, `vmware_capacity_evidence`, `network_anomaly_evidence`).

2. **Modelo + persistencia de Context** (`libs/perception/context.py`):
   - `Context` (pydantic `frozen`, P1): id, tenant_id, evidence_ids, mental_model_id, purpose, coherence_score, competing_models, activated_at, is_active.
   - `build_context(create)` + `ContextStore` análogo a `EvidenceStore`: INSERT append-only (`activated_at`), `verify_connection`, `close`. Dedup idempotente (re-ejecución del mismo context activado sobre la misma evidencia no duplica; id derivado de tenant+purpose+evidence_ids con uuid5, como en Sprint 3).
   - La tabla `contexts` YA existe en el schema (id, tenant_id, evidence_ids UUID[], mental_model_id, purpose, coherence_score NUMERIC(3,2), competing_models JSONB, activated_at, is_active, índice idx_contexts_tenant_active). NO regenere la tabla; úsela tal cual. Si se agrega una migración/check, documentarla.
   - IMPORTANTE (P1 vs is_active): la fila de context es inmutable en su contenido-evidencia (evidence_ids, mental_model_id, purpose, coherence_score, competing_models); `is_active` es un estado de ciclo de vida (un mismo propósito puede re-activarse con nueva evidencia). Decisión de diseño: ¿trigger que bloquee UPDATE/DELETE de columnas de contenido? Evaluar y JUSTIFICAR la elección (no romper la capacidad de desactivar el contexto previo al activar uno nuevo).

3. **Competencia de coherencia explicativa** (módulo en `apps/services/context-service/src/activator/` o equivalente; funciones puras, testables):
   - Para un tenant + purpose dado, con un batch de evidence (usando `weight` y `quality_class` de las evidence): calcular el `coherence_score` de cada mental model candidato compatible, NO interpretando (solo emparejando tipos de evidence y ponderando por weight).
   - Seleccionar el mental model con mayor coherencia → Active Context. Guardar en `competing_models` la lista de candidatos evaluados con sus scores (rastreabilidad y audibilidad de la "competencia" P2).
   - Regla crítica: Context describe la interpretación seleccionada como la más coherente con la evidencia disponible (P2); NUNCA afirma causalidad ni predice ("datastore x por debajo del 15%, coherente con el modelo capacity_risk" y NO "la infra va a fallar"). R3: NO saltar a Reasoning (Pattern es Sprint 5).

4. **Orquestación en `context-service`** (NUEVO app `apps/services/context-service/`): R1 exige que la capacidad Explain viva en un componente separado de Organize (el collector-service NO debe activar context).
   - Lee evidence desde Postgres (batched por tenant + purpose), corre la competencia de coherencia, escribe el Active Context en `contexts` (dedup idempotente; desactiva el contexto activo previo del mismo tenant+purpose cuando corresponde).
   - Expone `/health` y `/metrics` (observabilidad operativa del servicio): total_contexts, errors, contexts_by_mental_model, contexts_by_purpose.

5. **Tests** (unit + integración PG):
   - Una prueba por mental model con evidence sintéticas (coherencia máxima = el modelo correcto gana; y Negativo).
   - Lógica de coherencia scoring (peso por weight/quality_class; empate → decisión documentada).
   - Dedup de context (re-ejecución no duplica; desactivación del previo).
   - Integración: INSERT context en Postgres, read-back, `competing_models` persistido, ciclo is_active, trigger de contenido (si se adopta).
   - Verificar que los 55 tests previos siguen verdes.

6. **Docs de trabajo**: actualizar README (estado Sprint 4 + cómo correr el context-service), `.env.example` si se agregan variables. Journal de la sesión al cierre. NO modificar `docs/sprint-3-prompt.md` ni el journal previo.

## Cumplimiento cognitivo a validar al cerrar

- R1: `context-service` implementa EXACTAMENTE una capacidad (Explain). El collector-service no activa context.
- R2: Contract (Input: Evidence inmutables + Mental Models + Purpose → Transform: competencia de coherencia → Output: Active Context con coherence_score y competing_models) testeado.
- P2: Context nunca fabrica significado: selecciona la interpretación más coherente con la evidencia. Test que demuestre que ante la misma evidencia, el score premia al modelo correcto sin aserciones causales.
- P1: Context nunca modifica Evidence ni Observations; `evidence` se mantiene append-only.
- (P2): description objetiva (Context describe la interpretación, nunca causalidad); trazabilidad context.evidence_ids → evidence (que existan) y de la evidence a sus observation_ids.
- (P1): coherencia y competing_models asignados en la creación, nunca retrofitted.
- No iniciar Pattern/Reasoning (FASE 5) — eso es Sprint 5.

## Criterios de aceptación verificables

- pytest verde en las 5+1 apps (esperado: 55 previos + nuevos del context-service/activator).
- Corriendo el context-service contra la PG real (8 observations, 3 evidence existentes) aparece al menos 1 fila en `contexts` con `evidence_ids` válidos (que referencien evidence reales), `mental_model_id`, `coherence_score` y `competing_models` poblados. Si el dataset real no dispara ninguna competencia, usar siembra temporaria en tests de integración.
- `competing_models` registra la competencia (candidatos + scores), no solo el ganador.
- El re-corrido no duplica contexts (dedup probado).