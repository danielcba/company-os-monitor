# SPRINT 9 — RECOMMENDATION (Action: capacidad Propose)

> Persistido desde sesión 2026-08-16. Sesión EVALUADA al inicio.

## Contexto de la sesión previa

- Sprints 1-5 (COMPLETOS): Perception completa + Pattern Detector. 128 tests.
- Sprint 6 (COMPLETO esperado): Anomaly Detector. `ANOMALY_HEALTH_PORT=8093`.
- Sprint 7 (COMPLETO esperado): Hypothesis Generator. `HYPOTHESIS_HEALTH_PORT=8094`.
- Sprint 8 (COMPLETO esperado): Confidence Calibration. `libs/cognitive_core/calibration_model.py` cableado (S/C/ECE/C_final), `libs/learning/confidence.py` nuevo, `CONFIDENCE_HEALTH_PORT=8095`. API lista para target_type='recommendation'/'decision'.
- Infra corriendo: postgres TimescaleDB 127.0.0.1:5433 (db/user/pass = cosmonitor), redis 127.0.0.1:6379. Schema en `infrastructure/docker/init-sql/01-schema.sql` — YA incluye la tabla `recommendations` (VACÍA): id, tenant_id FK, hypothesis_id FK → hypotheses (SET NULL), insight_id FK → insights (SET NULL), confidence_id FK → confidence_scores NOT NULL, action_description TEXT NOT NULL, rationale TEXT NOT NULL, expected_consequences JSONB NOT NULL, alternatives_considered JSONB DEFAULT '[]', confidence_score NUMERIC(5,4) NOT NULL, status VARCHAR(20) DEFAULT 'proposed' (proposed/accepted/rejected/superseded), proposed_at; índice `idx_recommendations_tenant_status`.
- Marco cognitivo (SOLO LECTURA, no tocar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`. Producto: `/home/dcordoba/Documents/Default Project/company-os-monitor/`.
- Documentación fuente del Sprint: concepto `Recommendation` del marco: `/home/dcordoba/Documents/Default Project/company/company-os-main/docs/cognitive-lexicon/core-concepts/recommendation.md` (Familia Action, Capacidad Propose). Reglas conceptuales: **"A recommendation is an offer. A decision is a commitment."** Y la buena recomendación debe declarar: 1) qué hacer, 2) por qué, 3) qué se espera que pase, 4) cuán confiado está el sistema, 5) qué alternativas se consideraron. Y design implications: **"A recommendation is advisory and reversible. A decision is committed and accountable."** y **"The action space must be explicit so that the system knows what it is choosing among."** Diseño de producto: `docs/04-informes-seguridad.md` (FASE 6: Recommendation Service, Action Space por dominio), `docs/01-fundacion-arquitectura.md` (tabla `recommendations`), roadmap `docs/05-negocio-roadmap-backlog.md` (item #9 Recommendation).

### Correcciones de auditoría ya aplicadas (NO reintroducir)

- Citaciones canónicas: usar `P1`-`P7`, design rules `R1`-`R7`, conceptos del marco y ADR-0001/0002. NO inventar números de regla ni reciclar "R8/R9/R10". Trazabilidad/objetividad/provenance factual, sin número de regla. NO citar paths/specs inexistentes.
- Puertos/env: collector `HEALTH_PORT` (8090), context `ACTIVATOR_HEALTH_PORT` (8091), pattern `PATTERN_HEALTH_PORT` (8092), anomaly `ANOMALY_HEALTH_PORT` (8093), hypothesis `HYPOTHESIS_HEALTH_PORT` (8094), confidence `CONFIDENCE_HEALTH_PORT` (8095). El recommendation-service usará `RECOMMENDATION_HEALTH_PORT` (default 8096). NUNCA reutilizar nombres de env.
- **R4 ACTIVA desde Sprint 8**: toda recomendación DEBE llevar Confidence calibrada. En este sprint, la recomendación se forma solo para hipótesis que YA tienen su confidence calibrada (Sprint 8). NO aceptar recomendaciones sin confidence_id.
- **P6**: Recommendation ≠ Decision. La recomendación es advisory y reversible; NUNCA ejecuta acción. La Decision (Sprint 10) es la que se commitea.
- La calibración de Confidence ya NO es PLANNED (Sprint 8 la cableó). `cognitive_tool.py` (LM Studio) sigue fuera de alcance.

## Objetivo

Implementar el **Recommendation Formulator** (Contract cognitivo: Concept=Recommendation, Familia=Action, Capacidad=Propose). Input: Active Context + leading Hypothesis (o Insight, futuro) + Confidence en ese entendimiento + Action Space explícito. Transform: derivar el curso de acción que mejor sirva al propósito actual bajo las constraints del contexto. Output: Recommendation con `rationale` (trazable a evidence/hypothesis/confidence), `expected_consequences` (observables), `confidence_score` y `alternatives_considered` (otras opciones evaluadas con rationale). NO avanzar a Decision (Sprint 10).

Regla conceptual que gobierna el sprint: **"Recommendations structure action as an explicit, comparable, and auditable option, accompanied by its expected consequences and its confidence."** Y el Non-example: "Run the backup now." es una instrucción/orden, NO una recomendación — una recomendación lleva rationale, alternativas y confidence.

## Entorno y comandos (OBLIGATORIO respetar)

- Instalación: `pip install --break-system-packages -e ".[dev]"` (Python 3.14 es externally-managed; `.venv` NO funciona; NO inicializar git).
- NO usar `cd` para ejecutar; usar workdir = raíz del repo. PYTHONPATH por-app:
  `PYTHONPATH="<ruta_app>:<repo_root>" python3 -m pytest <ruta_app/tests> -q`
  con `REPO="/home/dcordoba/Documents/Default Project/company-os-monitor"`.
- Correr TESTS EXISTENTES al final y dejarlos verdes (128 + Sprints 6-8).
- Ruff: reducir violaciones nuevas a cero salvo BLE001. line-length 100.
- Tests de integración con Postgres real: limpiar con `SET session_replication_role = replica` (superuser) y borrar explícitamente las filas hijas.

## Proceso obligatorio (policy del marco)

- **Journaling (E6 / Directive 002)**: entry por sesión en `journal/YYYY/YYYY-MM-DD.md` con el formato del marco (`# Journal — YYYY-MM-DD (Sprint 9 — ...)` + secciones `## Theme`, `## Today's Progress`, `## Discoveries`, `## Decisions`, `## Reflection`, `## Quote of the Day`). Listar archivos cambiados.

## Entregables

1. **Modelo + persistencia de Recommendation** (`libs/action/recommendation.py`, nuevo paquete `action` — el directorio `libs/action/` existe VACÍO):
   - `RecommendationCreate` / `Recommendation` (pydantic `frozen`, P1): campos espejo de la tabla `recommendations` (id, tenant_id, hypothesis_id, insight_id, confidence_id, action_description, rationale, expected_consequences, alternatives_considered, confidence_score, status, proposed_at). `build_recommendation(create)`.
   - `recommendation_id(tenant_id, hypothesis_id, confidence_id, action_description)` determinístico (uuid5, namespace propio) SIN `proposed_at` → dedup idempotente.
   - `RecommendationStore`: INSERT append-only, `verify_connection`, `close`, reads `list_recommendations(tenant_id)`, `list_tenant_ids()`. Análogo a los stores previos.
   - Agregar a `HypothesisStore` (`libs/reasoning/hypothesis.py`) y `ConfidenceStore` (`libs/learning/confidence.py`) los reads que el formulator necesita (solo lectura, P1): `list_hypotheses(tenant_id)` y `get_confidence(target_type, target_id)`/`list_confidence(tenant_id)` — verificar firmas existentes, no romper API.

2. **Action Space Library** (`libs/procedural_memory/action_space.py`, nuevo; procedural memory — acciones permitidas EXPLÍCITAS por dominio, declarativas, NO razonamiento):
   - `ActionSpaceEntry` (dataclass frozen): `action_id` (versionado), `domain` (storage/compute/security/backup/network/observability), `allowed_actions` (frozenset[str]), `purpose` (a qué purposes aplica).
   - Catálogo inicial según `docs/04-informes-seguridad.md` (ej. storage: expand_volume, add_disk, move_data, compress, purge_old, change_retention, enable_dedup; security: reset_credentials, revoke_sessions, enable_mfa, block_ip, isolate_host, rotate_keys; backup: retry_job, change_schedule, change_target, verify_integrity, test_restore; etc.).
   - La recomendación SOLO puede elegir acciones dentro del space explícito de su dominio/purpose.

3. **Formulator** (`apps/services/recommendation-service/src/formulator/`; funciones PURAS, sin I/O, testables):
   - `formulate(hypothesis, confidence, context, action_space) -> RecommendationCreate`: deriva el curso de acción que mejor sirve el propósito, dado el mental model del contexto, la hipótesis (leading) y su confidence.
   - `rationale` SIEMPRE trazable: cita evidence/hypothesis/confidence con hechos (sin lenguaje causal no respaldado).
   - `expected_consequences` (JSONB) = predicciones observables y verificables en términos concretos (ej. "Backup capacity remains above 20% for the next 6 months", verificable por métrica).
   - `alternatives_considered` (JSONB) = otras opciones evaluadas con rationale y razón de rechazo (p. ej. "rejected_reason": "...", "confidence": N). Documentar que las alternativas también llevan confidence (reutilizando el confidence-service si aplica).
   - `confidence_score` = el de la hipótesis calibrada (Sprint 8); la recomendación NO recalcula confidence.
   - MVP: formular SOLO sobre hypothesis (insight_id queda NULL; Insight es Sprint 13).
   - `status` inicial `proposed` (advisory). NO ejecutar nada. NO disparar alertas.
   - Idempotencia: mismos inputs → misma Recommendation (dedup).

4. **Orquestación en `recommendation-service`** (`apps/services/recommendation-service/` — el directorio existe VACÍO; crear completo):
   - Estructura: `src/main.py`, `src/service.py`, `src/health.py`, `src/formulator/`, `tests/`, `pyproject.toml`, `Dockerfile`.
   - R1: `recommendation-service` implementa EXACTAMENTE una capacidad (Propose). No calibra confidence ni commitea decisiones.
   - Ciclo: por tenant, `HypothesisStore.list_hypotheses` (solo candidates con confidence) + `ConfidenceStore` → formulator → `RecommendationStore` persistir (dedup idempotente). NUNCA escribe en artefactos previos (P1). NUNCA lee el observation bus.
   - Métricas en `/metrics` (sin números de regla): `total_recommendations`, `total_recommendation_duplicates`, `total_hypotheses_without_confidence`, `total_errors`, `recommendations_by_status`, `recommendations_by_domain`.
   - Puerto: `RECOMMENDATION_HEALTH_PORT` (default 8096). NO ejecuta acciones (P6; la ejecución es de Decision + autorización).

5. **Schema**: tabla `recommendations` YA existe — usarla tal cual; NO regenerar. Evaluar y JUSTIFICAR trigger de inmutabilidad de contenido (contenido inmutable P1, DELETE bloqueado; `status` como único flippable: proposed/accepted/rejected/superseded es ciclo de vida). Si se adopta, migración idempotente `infrastructure/db-migrations/sprint9-recommendation-content-trigger.sql` + aplicar a la BD. Documentar en journal.

6. **Tests** (unit + integración PG):
   - Una prueba por dominio: hipótesis + confidence + contexto → recomendación con acción del space correcto; `expected_consequences` no vacío; `alternatives_considered` con ≥1 alternativa si hay opciones en el space.
   - R4: sin confidence calibrada para la hipótesis → NO se forma recomendación (assert: se salta o cuenta en métrica).
   - P6: la recomendación es advisory — assert que NO hay efectos secundarios (solo INSERT en recommendations; nada de acciones externas).
   - Anti-orden: `rationale` y `action_description` no son órdenes ("run now") sino propuestas con rationale (assert contra lenguaje imperativo no calificado si corresponde).
   - Dedup: re-ejecución sobre los mismos inputs no duplica filas.
   - Trazabilidad: `recommendation.hypothesis_id` y `recommendation.confidence_id` referencian filas reales; cadena recommendation → hypothesis → confidence → anomaly → pattern → context → evidence → observations.
   - Integración PG: INSERT recommendation, read-back, `confidence_score` persistido.
   - Regresión: TODAS las suites previas verdes (128 + Sprints 6-8 + nuevas).

7. **Docs/env**: README (sección Sprint 9 + cómo correr), `.env.example` (agregar `RECOMMENDATION_HEALTH_PORT=8096`, `RECOMMENDATION_CYCLE_SECONDS`, y flags de action space con defaults). Journal al cierre. NO modificar prompts previos ni journal previo.

## Cumplimiento cognitivo a validar al cerrar

- R1: `recommendation-service` implementa EXACTAMENTE una capacidad (Propose).
- R2: Contract (Input: Active Context + leading Hypothesis + Confidence + Action Space → Transform: derivar curso de acción → Output: Recommendation + rationale + expected consequences + confidence + alternatives) testeado.
- Concepto Recommendation: "an offer, not a commitment"; declara qué/por qué/qué se espera/confianza/alternativas; advisory y reversible.
- P6: Recommendation ≠ Decision; la recomendación nunca ejecuta; la autoridad explícita está en Decision (Sprint 10).
- R4: toda recomendación lleva Confidence calibrada (obligatorio); sin confidence → no se recomienda.
- R6: rationale/explanation son salidas de primera clase (trazables).
- P1: `recommendations` append-only (+ trigger si se decide); re-ejecución no duplica; trazabilidad verificada.
- Action Space explícito: la recomendación solo elige dentro de acciones permitidas (Procedural Memory).
- No avanzar a Decision (Sprint 10), Report (Sprint 11) ni Insight (Sprint 13).

## Criterios de aceptación verificables

- pytest verde: 128 + Sprints 6-8 + nuevos del recommendation-service / recommendation model / action space.
- Corriendo `recommendation-service` contra la PG real (con hypotheses calibradas sembradas): recomendaciones formadas con `confidence_id` NOT NULL, `rationale` trazable, `expected_consequences` no vacío, `alternatives_considered` con rationale; hypotheses sin confidence → métrica `total_hypotheses_without_confidence`, sin filas.
- `status='proposed'` en todas las filas nuevas; ninguna recomendación ejecutada.
- Re-corrida sin duplicados (dedup probado).
- `hypotheses`, `confidence_scores`, `anomalies`, `patterns`, `contexts`, `evidence`, `observations` sin cambios tras el ciclo (P1 verificada).
- Métricas en `:8096/metrics` (recommendation-service con `RECOMMENDATION_HEALTH_PORT=8096`).
