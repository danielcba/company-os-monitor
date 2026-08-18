# SPRINT 10 — DECISION (Action: capacidad Commit)

> Persistido desde sesión 2026-08-16. Sesión EVALUADA al inicio.

## Contexto de la sesión previa

- Sprints 1-5 (COMPLETOS): Perception completa + Pattern Detector. 128 tests.
- Sprint 6 (COMPLETO esperado): Anomaly Detector. `ANOMALY_HEALTH_PORT=8093`.
- Sprint 7 (COMPLETO esperado): Hypothesis Generator. `HYPOTHESIS_HEALTH_PORT=8094`.
- Sprint 8 (COMPLETO esperado): Confidence Calibration. `CONFIDENCE_HEALTH_PORT=8095`.
- Sprint 9 (COMPLETO esperado): Recommendation. `libs/action/recommendation.py`, `libs/procedural_memory/action_space.py`, `RECOMMENDATION_HEALTH_PORT=8096`.
- Infra corriendo: postgres TimescaleDB 127.0.0.1:5433 (db/user/pass = cosmonitor), redis 127.0.0.1:6379. Schema en `infrastructure/docker/init-sql/01-schema.sql` — YA incluye la tabla `decisions` (VACÍA): id, tenant_id FK, recommendation_id FK → recommendations NOT NULL, confidence_id FK → confidence_scores NOT NULL, authority_id UUID NOT NULL (user_id o policy_id), commitment TEXT NOT NULL, expected_outcomes JSONB NOT NULL (predicciones falsificables), risk_tolerance VARCHAR(20) DEFAULT 'low' (low/medium/high), status VARCHAR(20) DEFAULT 'committed' (committed/executing/completed/rolled_back), committed_at, executed_at, actual_outcomes JSONB (para el learning loop); índice `idx_decisions_tenant_status`.
- Marco cognitivo (SOLO LECTURA, no tocar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`. Producto: `/home/dcordoba/Documents/Default Project/company-os-monitor/`.
- Documentación fuente del Sprint: concepto `Decision` del marco: `/home/dcordoba/Documents/Default Project/company/company-os-main/docs/cognitive-lexicon/core-concepts/decision.md` (Familia Action, Capacidad Commit). Reglas conceptuales: **"A decision ends deliberation. It does not end learning."** Y el apartado Falsifiability: **"Its expected outcomes must be stated in observable, verifiable terms before the decision is executed."** y **"This rule converts every decision from an act of authority into an experiment."** Y el design implication: **"Company OS must record every decision with its full trace: evidence, context, hypotheses, confidence, alternatives, and expected outcomes."** Diseño de producto: `docs/04-informes-seguridad.md` (FASE 6: Decision Service, schema `decisions`, expected_outcomes falsificables), `docs/01-fundacion-arquitectura.md` (tabla `decisions`), roadmap `docs/05-negocio-roadmap-backlog.md` (item #10 Decision — el gate cognitivo Q1).

### Correcciones de auditoría ya aplicadas (NO reintroducir)

- Citaciones canónicas: usar `P1`-`P7`, design rules `R1`-`R7`, conceptos del marco y ADR-0001/0002. NO inventar números de regla ni reciclar "R8/R9/R10". Trazabilidad/objetividad/provenance factual, sin número de regla. NO citar paths/specs inexistentes.
- Puertos/env: collector `HEALTH_PORT` (8090), context `ACTIVATOR_HEALTH_PORT` (8091), pattern `PATTERN_HEALTH_PORT` (8092), anomaly `ANOMALY_HEALTH_PORT` (8093), hypothesis `HYPOTHESIS_HEALTH_PORT` (8094), confidence `CONFIDENCE_HEALTH_PORT` (8095), recommendation `RECOMMENDATION_HEALTH_PORT` (8096). El decision-service usará `DECISION_HEALTH_PORT` (default 8097). NUNCA reutilizar nombres de env.
- **R4 ACTIVA**: toda decisión DEBE llevar Confidence calibrada (desde Sprint 8). **P6**: Recommendation ≠ Decision. La Decision se commitea con authority binding. **R5**: toda decisión se registra con rationale y expected outcomes falsificables.
- **auth/users NO existen aún**: `authority_id` es un UUID (user_id o policy_id). El binding de autoridad real (roles/RBAC) es Sprint 12 (`user-service`). En este sprint, el authority se modela como referencia opcional: se puede usar el tenant admin (seed) o un policy_id declarativo; documentar que Sprint 12 lo reemplazará con roles reales. NO bloquear el flujo por falta de auth.

## Objetivo

Implementar el **Decision Committer** (Contract cognitivo: Concept=Decision, Familia=Action, Capacidad=Commit). Input: una o más Recommendations + sus Confidence scores + Purpose y constraints + Risk tolerance + Authority (commitment authority). Transform: seleccionar el curso de acción que mejor balancee valor esperado y riesgo, y comprometerse con él. Output: Decision con rationale registrado, expected outcomes como predicciones FALSIFICABLES en términos observables, confidence score asociado y authority bajo la que se tomó. Este sprint cierra el **gate cognitivo Q1** del roadmap (docs/05): la primera Decision commitida con outcomes falsificables e inicio del learning loop (comparación expected vs actual a 30/60/90 días).

Regla conceptual que gobierna el sprint: **"Every meaningful effect of Company OS on the world passes through decisions."** Y la falsifiability: los expected outcomes se declaran ANTES de ejecutar; si el outcome observado coincide → decisión y Confidence confirmadas; si contradice → el Context, Hypothesis o la calibración deben revisarse.

## Entorno y comandos (OBLIGATORIO respetar)

- Instalación: `pip install --break-system-packages -e ".[dev]"` (Python 3.14 es externally-managed; `.venv` NO funciona; NO inicializar git).
- NO usar `cd` para ejecutar; usar workdir = raíz del repo. PYTHONPATH por-app:
  `PYTHONPATH="<ruta_app>:<repo_root>" python3 -m pytest <ruta_app/tests> -q`
  con `REPO="/home/dcordoba/Documents/Default Project/company-os-monitor"`.
- Correr TESTS EXISTENTES al final y dejarlos verdes (128 + Sprints 6-9).
- Ruff: reducir violaciones nuevas a cero salvo BLE001. line-length 100.
- Tests de integración con Postgres real: limpiar con `SET session_replication_role = replica` (superuser) y borrar explícitamente las filas hijas.

## Proceso obligatorio (policy del marco)

- **Journaling (E6 / Directive 002)**: entry por sesión en `journal/YYYY/YYYY-MM-DD.md` con el formato del marco (`# Journal — YYYY-MM-DD (Sprint 10 — ...)` + secciones `## Theme`, `## Today's Progress`, `## Discoveries`, `## Decisions`, `## Reflection`, `## Quote of the Day`). Listar archivos cambiados.

## Entregables

1. **Modelo + persistencia de Decision** (`libs/action/decision.py`, nuevo):
   - `DecisionCreate` / `Decision` (pydantic `frozen`, P1): campos espejo de la tabla `decisions` (id, tenant_id, recommendation_id, confidence_id, authority_id, commitment, expected_outcomes, risk_tolerance, status, committed_at, executed_at, actual_outcomes). `build_decision(create)`.
   - `decision_id(tenant_id, recommendation_id, confidence_id)` determinístico (uuid5, namespace propio) SIN `committed_at` → dedup idempotente.
   - `DecisionStore`: INSERT append-only, `verify_connection`, `close`, reads `list_decisions(tenant_id)`, `list_tenant_ids()`, y (para el learning loop futuro y el report service) `list_decisions_by_status(tenant_id, status)`.
   - Agregar a `RecommendationStore` (`libs/action/recommendation.py`) el read que el committer necesita: `list_recommendations(tenant_id)` (solo lectura, P1) — verificar firma existente.

2. **Decision Policy Library** (`libs/procedural_memory/decision_policy.py`, nuevo; procedural memory — reglas de commitment declarativas, NO razonamiento):
   - `DecisionPolicyEntry` (dataclass frozen): `policy_id` (versionado), `domain`, `min_confidence_for_commit` (umbral según riesgo: ej. ≥0.75 commit, ≥0.9 irreversible — alineado con docs/03: "Decision > 0.75 to commit; > 0.9 for irreversible"), `allowed_risk_tolerance` (low/medium/high por dominio), `requires_authority` (bool).
   - La decisión SOLO se commitea si el confidence_score de la recomendación supera el umbral del policy del dominio y el risk_tolerance es permitido.

3. **Committer** (`apps/services/decision-service/src/committer/`; funciones PURAS, sin I/O, testables):
   - `commit(recommendation, confidence, policy, authority) -> DecisionCreate`: selecciona la recomendación (MVP: una por ciclo), valida umbral de confidence contra el policy, establece `commitment` (curso de acción definitivo), `expected_outcomes` (predicciones observables y verificables, con deadline y métrica de verificación — análogo a `docs/04`: {"prediction": "...", "verifiable_by": "...", "deadline": "..."}), `risk_tolerance` y `authority_id`.
   - `rationale` registrado con traza completa: evidence → context → pattern → anomaly → hypothesis → confidence → recommendation → decision (R5). El `commitment` es una sentencia definitiva (Non-example: "Let's keep an eye on it." es intención indefinida, NO decisión).
   - `status` inicial `committed`. NO ejecutar acciones reales (MVP): el servicio registra la decisión y sus outcomes esperados; la ejecución/actualización de outcomes y el learning loop quedan para fases siguientes (P7 / Memory). Documentar explícitamente que `executed_at`/`actual_outcomes` se pueblan en el learning loop.
   - No hay users aún: `authority_id` = policy declarativo o tenant admin (documentar; Sprint 12).
   - Idempotencia: mismos inputs → misma Decision (dedup).

4. **Orquestación en `decision-service`** (`apps/services/decision-service/` — el directorio existe VACÍO; crear completo):
   - Estructura: `src/main.py`, `src/service.py`, `src/health.py`, `src/committer/`, `tests/`, `pyproject.toml`, `Dockerfile`.
   - R1: `decision-service` implementa EXACTAMENTE una capacidad (Commit). No forma recomendaciones ni calibra confidence.
   - Ciclo: por tenant, `RecommendationStore.list_recommendations` (solo status='proposed' con confidence) + `ConfidenceStore` + `DecisionPolicy` → committer → `DecisionStore` persistir (dedup idempotente). NUNCA escribe en artefactos previos (P1). NUNCA lee el observation bus.
   - Métricas en `/metrics` (sin números de regla): `total_decisions`, `total_decision_duplicates`, `total_recommendations_below_confidence`, `total_errors`, `decisions_by_status`, `decisions_by_risk_tolerance`.
   - Puerto: `DECISION_HEALTH_PORT` (default 8097). El committer NO ejecuta acciones del mundo real (P6; ejecución + autorización real en Sprints 11-12).

5. **Schema**: tabla `decisions` YA existe — usarla tal cual; NO regenerar. Evaluar y JUSTIFICAR trigger de inmutabilidad de contenido (contenido inmutable P1, DELETE bloqueado; `status` como único flippable: committed/executing/completed/rolled_back es ciclo de vida; `executed_at`/`actual_outcomes` como campos de ciclo de vida actualizables SOLO por el flujo de aprendizaje). Si se adopta, migración idempotente `infrastructure/db-migrations/sprint10-decision-content-trigger.sql` + aplicar a la BD. Documentar en journal (especialmente: qué columnas son contenido vs ciclo de vida).

6. **Tests** (unit + integración PG):
   - Una prueba por policy: recomendación con confidence ≥ umbral → Decision commitida con expected_outcomes falsificables; y Negativo: confidence < umbral → NO se commitea (métrica `total_recommendations_below_confidence`).
   - Falsifiabilidad (R5/Popper): todo `expected_outcomes` tiene `prediction`, `verifiable_by` y `deadline` en términos observables (assert).
   - P6: la decisión se registra, NO ejecuta (assert: no hay efectos secundarios externos; solo INSERT en decisions).
   - Anti-indefinición: `commitment` es una sentencia definitiva, no intención vaga (assert contra "keep an eye"/"probably").
   - Dedup: re-ejecución sobre los mismos inputs no duplica filas.
   - Trazabilidad: `decision.recommendation_id` y `decision.confidence_id` referencian filas reales; cadena decision → recommendation → confidence → hypothesis → anomaly → pattern → context → evidence → observations completa.
   - Integración PG: INSERT decision, read-back, `status='committed'`, `risk_tolerance` persistido.
   - Regresión: TODAS las suites previas verdes (128 + Sprints 6-9 + nuevas).

7. **Docs/env**: README (sección Sprint 10 + cómo correr + gate cognitivo Q1), `.env.example` (agregar `DECISION_HEALTH_PORT=8097`, `DECISION_CYCLE_SECONDS`, `DECISION_MIN_CONFIDENCE=0.75`, `DECISION_MIN_CONFIDENCE_IRREVERSIBLE=0.9` con defaults). Journal al cierre. NO modificar prompts previos ni journal previo.

## Cumplimiento cognitivo a validar al cerrar

- R1: `decision-service` implementa EXACTAMENTE una capacidad (Commit).
- R2: Contract (Input: Recommendation(s) + Confidence + Purpose/Constraints + Risk Tolerance + Authority → Transform: seleccionar y comprometer → Output: Decision + rationale + expected outcomes falsificables + confidence + authority) testeado.
- Concepto Decision: compromiso definitivo con owner, timeline y expected outcomes; "ends deliberation, does not end learning".
- Falsifiability: expected outcomes declarados ANTES de ejecutar, en términos observables y verificables; la comparación expected vs actual es el primary learning signal (P7 / learning loop, fases siguientes).
- R4: toda decisión lleva Confidence calibrada (obligatorio; umbral por policy).
- R5: traza completa registrada con rationale.
- P6: Decision se commitea con authority binding; Recommendation es advisory y reversible; Perception/Reasoning informan pero no ejecutan.
- P1: `decisions` append-only (+ trigger si se decide); re-ejecución no duplica; trazabilidad verificada.
- Gate cognitivo Q1 alcanzado: primera Decision commitida con outcomes falsificables.
- No avanzar a Report (Sprint 11), Auth/RBAC (Sprint 12) ni Insight (Sprint 13).

## Criterios de aceptación verificables

- pytest verde: 128 + Sprints 6-9 + nuevos del decision-service / decision model / decision policy.
- Corriendo `decision-service` contra la PG real (con recommendations propuestas + confidence sembradas): decisiones commitidas con `expected_outcomes` falsificables (prediction + verifiable_by + deadline), `commitment` definitivo, `authority_id` presente; recommendations con confidence < umbral → métrica `total_recommendations_below_confidence`, sin filas.
- `status='committed'` en todas las filas nuevas; ninguna decisión ejecutada (no hay ejecución externa en MVP).
- Re-corrida sin duplicados (dedup probado).
- `recommendations`, `confidence_scores`, `hypotheses`, `anomalies`, `patterns`, `contexts`, `evidence`, `observations` sin cambios tras el ciclo (P1 verificada).
- Métricas en `:8097/metrics` (decision-service con `DECISION_HEALTH_PORT=8097`).
- (Gate para Sprint 11): `DecisionStore` expone reads para que report-service pueda formatear decisiones (list_decisions con status y período).
