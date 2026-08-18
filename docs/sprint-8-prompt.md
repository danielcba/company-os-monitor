# SPRINT 8 — CONFIDENCE CALIBRATION (Learning: capacidad Calibrate)

> Persistido desde sesión 2026-08-16. Sesión EVALUADA al inicio.

## Contexto de la sesión previa

- Sprints 1-5 (COMPLETOS): Perception completa + Pattern Detector. 128 tests.
- Sprint 6 (COMPLETO esperado): Anomaly Detector. `ANOMALY_HEALTH_PORT=8093`.
- Sprint 7 (COMPLETO esperado): Hypothesis Generator. `libs/reasoning/hypothesis.py`, `libs/procedural_memory/hypothesis_templates.py`, `HYPOTHESIS_HEALTH_PORT=8094`.
- Infra corriendo: postgres TimescaleDB 127.0.0.1:5433 (db/user/pass = cosmonitor), redis 127.0.0.1:6379. Schema en `infrastructure/docker/init-sql/01-schema.sql` — YA incluye la tabla `confidence_scores` (VACÍA): id, tenant_id FK, target_type (hypothesis/recommendation/decision), target_id UUID, evidential_support NUMERIC(5,4), explanatory_coherence NUMERIC(5,4), historical_calibration NUMERIC(5,4), confidence_score NUMERIC(5,4), alpha NUMERIC(3,2) DEFAULT 0.50, calibration_justification TEXT, calibration_error_estimate NUMERIC(5,4), computed_at; índice `idx_confidence_target`.
- Marco cognitivo (SOLO LECTURA, no tocar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`. Producto: `/home/dcordoba/Documents/Default Project/company-os-monitor/`.
- Documentación fuente del Sprint: concepto `Confidence` del marco: `/home/dcordoba/Documents/Default Project/company/company-os-main/docs/cognitive-lexicon/core-concepts/confidence.md` (Familia Learning, Capacidad Calibrate). Reglas conceptuales: **"Confidence is not a feeling. It is a measurement."** Y **"Confidence must be computed, not intuited."** Y el Calibration Model completo (S(H|E), C(H), Brier, ECE, C_final = [α·S + (1−α)·C]·(1−ECE), parámetros α=0.5, M=10, L₀=0 fijos a priori y publicados). Y el design implication: **"Every judgment that influences action must carry a confidence score and the reasons for it."** Diseño de producto: `docs/03-predictivo-ia-local.md` (FASE 4: Confidence Service, Calibration Model formal), `docs/01-fundacion-arquitectura.md` (tabla `confidence_scores`), roadmap `docs/05-negocio-roadmap-backlog.md` (item #8 Confidence Calibration basic — R4: ningún juicio influye acción sin Confidence).

### Correcciones de auditoría ya aplicadas (NO reintroducir)

- Citaciones canónicas: usar `P1`-`P7`, design rules `R1`-`R7`, conceptos del marco y ADR-0001/0002. NO inventar números de regla ni reciclar "R8/R9/R10". Trazabilidad/objetividad/provenance factual, sin número de regla. NO citar paths/specs inexistentes.
- Puertos/env: collector `HEALTH_PORT` (8090), context `ACTIVATOR_HEALTH_PORT` (8091), pattern `PATTERN_HEALTH_PORT` (8092), anomaly `ANOMALY_HEALTH_PORT` (8093), hypothesis `HYPOTHESIS_HEALTH_PORT` (8094). El confidence-service usará `CONFIDENCE_HEALTH_PORT` (default 8095). NUNCA reutilizar nombres de env.
- **ESTE ES EL SPRINT QUE CABLEA la calibración.** `libs/cognitive_core/calibration_model.py` existe con la matemática (evidential_support, brier_score, ece_score, final_confidence, QUALITY_CLASS_RANGES, CalibrationParams) pero `explanatory_coherence()` es placeholder (retorna 0.5, PLANNED). Este sprint lo CONECTA al pipeline. `cognitive_tool.py` (LM Studio) queda fuera de alcance.
- R4: a partir de este sprint, todo juicio que influya acción debe llevar Confidence calibrada. En la práctica: las hypotheses del Sprint 7 deberán poder recibir su Confidence aquí; las Recommendations (Sprint 9) y Decisions (Sprint 10) la usarán como input obligatorio.

## Objetivo

Implementar el **Confidence Calibrator** (Contract cognitivo: Concept=Confidence, Familia=Learning, Capacidad=Calibrate). Input: el juicio bajo evaluación (Hypothesis) + su evidential support + su explanatory coherence + el historial de rendimiento de juicios similares. Transform: Calibration Model. Output: `confidence_score` (C_final), `calibration_justification` (por qué ese score) y `calibration_error_estimate`. Es la **capacidad transversal** que habilita el Action Layer (R4).

Regla conceptual que gobierna el sprint: **"Confidence is an estimate of reliability, which must itself be calibrated and can be wrong."** Y la falsificabilidad del modelo: **"The calibration factor is measured from outcomes only; it is never adjusted to justify a particular confidence."** El score se COMPUTA con parámetros fijos publicados; jamás se tunifica para que "suene bien".

## Entorno y comandos (OBLIGATORIO respetar)

- Instalación: `pip install --break-system-packages -e ".[dev]"` (Python 3.14 es externally-managed; `.venv` NO funciona; NO inicializar git).
- NO usar `cd` para ejecutar; usar workdir = raíz del repo. PYTHONPATH por-app:
  `PYTHONPATH="<ruta_app>:<repo_root>" python3 -m pytest <ruta_app/tests> -q`
  con `REPO="/home/dcordoba/Documents/Default Project/company-os-monitor"`.
- Correr TESTS EXISTENTES al final y dejarlos verdes (128 + Sprints 6-7).
- Ruff: reducir violaciones nuevas a cero salvo BLE001. line-length 100.
- Tests de integración con Postgres real: limpiar con `SET session_replication_role = replica` (superuser) y borrar explícitamente las filas hijas.

## Proceso obligatorio (policy del marco)

- **Journaling (E6 / Directive 002)**: entry por sesión en `journal/YYYY/YYYY-MM-DD.md` con el formato del marco (`# Journal — YYYY-MM-DD (Sprint 8 — ...)` + secciones `## Theme`, `## Today's Progress`, `## Discoveries`, `## Decisions`, `## Reflection`, `## Quote of the Day`). Listar archivos cambiados.

## Entregables

1. **Calibration Model — conectar `calibration_model.py`** (`libs/cognitive_core/calibration_model.py`, MODIFICAR):
   - Revisar la matemática existente contra el Calibration Model del concepto `confidence.md`. Verificar: `evidential_support` (log-odds + sigmoide), `brier_score`, `ece_score` (M bins, default M=10), `final_confidence` (C_final = [α·S + (1−α)·C]·(1−ECE)), `CalibrationParams` (α=0.5, M=10, L₀=0).
   - `explanatory_coherence()` es placeholder (retorna 0.5). En este sprint DEBE implementarse una versión REAL mínima y documentada: coherencia como satisfacción de constraints normalizada (Thagard 1989) sobre las hipótesis competidoras del mismo scope — p. ej. coherencia = fracción de evidencia que la hipótesis explica / consistencia con las demás hipótesis del scope. Definir el esquema en el docstring y testearlo con valores conocidos. Si el schema es demasiado grande para este sprint, documentar la simplificación y dejar la función con firma estable (MANTENER compatibilidad de firma: `hypothesis: str, evidence: list[str], constraints: dict -> float`).
   - Actualizar el docstring del módulo (ya NO es PLANNED en la parte cableada).
   - Mantener `QUALITY_CLASS_RANGES` y `quality_class_to_weight` (bandas canónicas); el confidence-service las usa para derivar pesos desde `evidence.weight`/`quality_class`.

2. **Modelo + persistencia de Confidence** (`libs/learning/confidence.py`, nuevo paquete `learning` — el directorio `libs/learning/` existe VACÍO):
   - `ConfidenceCreate` / `Confidence` (pydantic `frozen`, P1): campos espejo de la tabla `confidence_scores` (id, tenant_id, target_type, target_id, evidential_support, explanatory_coherence, historical_calibration, confidence_score, alpha, calibration_justification, calibration_error_estimate, computed_at). `build_confidence(create)`.
   - `confidence_id(tenant_id, target_type, target_id)` determinístico (uuid5, namespace propio) SIN `computed_at` → dedup idempotente (re-calibrar la misma hipótesis con los mismos inputs → misma fila). OJO: si los inputs cambian (nueva evidencia), el id NO cambia → usar `ON CONFLICT (id) DO NOTHING` y evaluar si una nueva calibración debe crear una nueva fila (id con hash del contenido de calibración, p. ej. incluyendo los inputs). Documentar y testear.
   - `ConfidenceStore`: INSERT append-only, `verify_connection`, `close`, reads `list_confidence(tenant_id)`, `get_confidence(target_type, target_id)`, `list_tenant_ids()`.

3. **Calibrator** (`apps/services/confidence-service/src/calibrator/`; funciones PURAS, sin I/O, testables):
   - `calibrate(hypothesis, evidence, coherence_inputs, params, historical) -> ConfidenceCreate`: computa S(H|E) desde los pesos de la evidencia (quality_class_to_weight) con signos (+1/-1 según apoye/contradiga la hipótesis — esquema documentado), C(H) desde `explanatory_coherence`, el factor (1−ECE) desde el historial de outcomes de la clase de juicio, y C_final con `final_confidence`. Parámetros α/M/L₀ desde `CalibrationParams` (fijos a priori, publicados en el justification).
   - `calibration_justification` SIEMPRE documenta: S, C, ECE, α, M, L₀ y cómo se derivó cada uno (para R6/explicación primera clase y trazabilidad).
   - Sin historial → `historical_calibration = 1.0` (ECE=0) documentado (primeros datos); con historial → ECE real.
   - Anti-tuning: el esquema es idéntico para inputs idénticos; los tests lo verifican (mismo input → mismo score).

4. **Orquestación en `confidence-service`** (`apps/services/confidence-service/` — el directorio existe VACÍO; crear completo):
   - Estructura: `src/main.py`, `src/service.py`, `src/health.py`, `src/calibrator/`, `tests/`, `pyproject.toml`, `Dockerfile`.
   - R1: `confidence-service` implementa EXACTAMENTE una capacidad (Calibrate). No genera hipótesis ni recomendaciones.
   - Ciclo: por tenant, `HypothesisStore.list_hypotheses` (input) + `EvidenceStore.list_evidence` (para evidential support) → calibrator → `ConfidenceStore` persistir (dedup idempotente). NUNCA escribe en artefactos previos (P1). NUNCA lee el observation bus.
   - Los targets hypothesis se calibran con su evidencia; recommendation/decision se calibran en Sprints 9/10 (el servicio debe dejar la API lista para target_type='recommendation'/'decision').
   - Métricas en `/metrics` (sin números de regla): `total_confidence_scores`, `total_confidence_duplicates`, `total_errors`, `confidence_by_target_type`, `mean_confidence_score`, `mean_calibration_error_estimate`.
   - Puerto: `CONFIDENCE_HEALTH_PORT` (default 8095). No produce acciones (R3; su output habilita el Action Layer).

5. **Schema**: tabla `confidence_scores` YA existe — usarla tal cual; NO regenerar. Evaluar y JUSTIFICAR trigger de inmutabilidad de contenido (contenido inmutable P1, DELETE bloqueado). Si se adopta, migración idempotente `infrastructure/db-migrations/sprint8-confidence-content-trigger.sql` + aplicar a la BD. Documentar en journal.

6. **Tests** (unit + integración PG):
   - Calibration Model: `evidential_support`, `ece_score`, `brier_score`, `final_confidence` con valores conocidos (verificar contra el formal del concepto `confidence.md`).
   - `explanatory_coherence` REAL: con hipótesis que explica la evidencia → score alto; que la contradice → score bajo; valores en [0,1].
   - Calibrator: mismo input → mismo score (anti-tuning); `calibration_justification` no vacío y con los parámetros (α, M, L₀); sin historial → historical_calibration=1.0.
   - Dedup: re-calibración sobre los mismos inputs no duplica filas.
   - Trazabilidad: `confidence.target_type='hypothesis'` + `target_id` referencia una hipótesis real; cadena confidence → hypothesis → anomaly → pattern → context → evidence → observations.
   - Integración PG: INSERT confidence, read-back, campos S/C/ECE/C_final/α persistidos.
   - Regresión: TODAS las suites previas verdes (128 + Sprints 6-7 + nuevas).

7. **Docs/env**: README (sección Sprint 8 + cómo correr), `.env.example` (agregar `CONFIDENCE_HEALTH_PORT=8095`, `CONFIDENCE_CYCLE_SECONDS`, `CALIBRATION_ALPHA=0.5`, `CALIBRATION_ECE_BINS=10` con defaults documentados). Journal al cierre. NO modificar prompts previos ni journal previo.

## Cumplimiento cognitivo a validar al cerrar

- R1: `confidence-service` implementa EXACTAMENTE una capacidad (Calibrate).
- R2: Contract (Input: Judgment + Evidence + Coherence + History → Transform: Calibration Model → Output: Confidence + justification + calibration error estimate) testeado.
- Concepto Confidence: "computed, not intuited"; score = medida de fiabilidad calibrada, nunca sensación; parámetros fijos publicados, sin tuning para justificar una confianza.
- Falsificabilidad del modelo: el factor de calibración se mide SOLO de outcomes; verificación post hoc posible.
- R4: todo juicio que influya acción lleva Confidence (esta capacidad es la habilitadora). R6: justification primera clase (explicaciones).
- P5: Confidence computada con parámetros publicados (α, M, L₀) nunca tunificados.
- P1: `confidence_scores` append-only (+ trigger si se decide); re-ejecución no duplica; trazabilidad verificada.
- Reasoning/Perception intactas: el servicio solo LEE artefactos previos (P1).
- No avanzar a Recommendation (Sprint 9), Decision (Sprint 10) ni Insight (Sprint 13).

## Criterios de aceptación verificables

- pytest verde: 128 + Sprints 6-7 + nuevos del confidence-service / calibration model.
- Corriendo `confidence-service` contra la PG real (con hypotheses sembradas): cada hypothesis calibrada con fila en `confidence_scores` completa (S, C, 1-ECE, C_final, α, justification, calibration_error_estimate); sin hypotheses → `total_confidence_scores=0`, sin errores.
- `explanatory_coherence` ya no retorna placeholder 0.5 (función real testeada).
- Re-calibración sin duplicados (dedup probado).
- `hypotheses`, `anomalies`, `patterns`, `contexts`, `evidence`, `observations` sin cambios tras el ciclo (P1 verificada).
- Métricas en `:8095/metrics` (confidence-service con `CONFIDENCE_HEALTH_PORT=8095`).
- (Gate para Sprint 9): la API del confidence-service permite calibrar target_type='recommendation'/'decision'.
