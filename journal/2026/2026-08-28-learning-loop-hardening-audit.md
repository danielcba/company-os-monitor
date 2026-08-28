# 2026-08-28 — Learning-Loop Hardening Audit (PR #15)

Audit + repair of the Hypothesis Evaluation / Learning Loop Hardening PR on
`feature/learning-loop-hardening`. Objective: AUDITAR + CORREGIR + VALIDAR (no new
features). Outcome: architecturally correct, semantically correct, operationally
runnable, traceable, tenant-safe, reproducible.

## Blockers corregidos

- **#1/#2 — ObservationStore removido de Evaluation.** `EvaluationService` y
  `evaluation_policy` ahora consumen **Evidence** (artefacto canónico de
  Perception) vía `EvidenceStore`. La cadena de datos es Hypothesis + Evidence +
  Confidence → Evaluation. Ya no se construye descripción textual desde Observation.
- **#3 — Matcher explícito y acotado.** `_evidence_supports_prediction` /
  `_evidence_meets_falsification` son deterministas y están etiquetados
  `MATCHER_RELIABILITY = "heuristic"`. El servicio MVP **no auto-promueve** una
  Hypothesis a estado terminal sobre señal heurística: registra `insufficient` y
  preserva el candidato. Las reglas formales confirmed/falsified se ejercen sobre
  base de evidencia confiable (futuro matcher estructurado).
- **#4 — Falsificación formalizada.** `falsified` es por evidencia; Confidence NO
  lo bloquea (se corrigió la regla "criterion met pero confidence high ⇒ no
  falsified", que no tenía fundamento en el Framework). `confirmed` requiere
  corroboración de evidencia + Confidence como gating (necesario-no-suficiente), no
  sustituto. Confidence tampoco reemplaza Evidence.
- **#7/#8 — Evaluation inmutable + idempotente + provenance.** `evaluation_id`
  content-addressed (tenant + hypothesis + evidence_ids + result, sin timestamp).
  `EvaluationCreate` lleva hypothesis_id, evidence_ids, observed_outcomes,
  support_count, contradiction_count, confidence_id, result, rationale,
  evaluated_at. Se agregó `evidence_basis_reliable` al input.
- **#9 — Tenant discovery.** Ya usaba `hypotheses` (fuente canónica); un tenant con
  candidatas y cero evaluaciones previas SÍ es descubierto (test L).
- **#10/#11 — Runtime + puerto.** Evaluation Service agregado a `start.sh` /
  `stop.sh` (`SERVICE_SPECS`, puerto `8102` / `EVALUATION_HEALTH_PORT`). `main.py`
  usa 8102 (antes 8097, colisión con decision-service).
- **#12 — Health.** `/health` ahora hace `verify_connection()` y responde
  `unhealthy`/503 si la DB está caída (antes decía ok siempre).
- **#13 — Metrics.** `metrics()` extendido: `evaluation_cycles`,
  `last_successful_cycle_at`, `evaluations_by_result`, confirmed/falsified/
  insufficient/duplicates/errors.
- **#14 — Error semantics.** Se eliminó doble conteo de errores; una falla de BD
  es distinguishable de "zero hypotheses evaluated".
- **#15 — Concurrency.** `asyncio.gather` sobre tenants ahora acotado por
  `asyncio.Semaphore(MAX_CONCURRENT_TENANTS)` (default 8, `EVALUATION_MAX_TENANTS`).
  Evidencia cargada una vez por batch de tenant (sin N+1).
- **#16 — Migración.** `hypothesis_evaluations`: `evidence_ids` es `UUID[]` (no FK,
  así borrar Evidence no rompe el audit trail); `confidence_id … ON DELETE SET
  NULL` preserva la Evaluation. Hypotheses son inmutables (trigger), así que el
  `ON DELETE CASCADE` sobre `hypothesis_id` es inocuo. Verificado, no requirió
  cambio destructivo de la migración.
- **#17/#18 — Docker + CI.** Dockerfile ahora copia `libs/` y usa puerto 8102;
  build context = repo root. CI: `docker-build` ahora corre en PR/feature branches
  y builda explícitamente la imagen del Evaluation Service (antes SKIPPED en el PR).
- **#19 — Architecture tests.** `test_architecture_boundary.py` falla el build si
  Evaluation vuelve a importar `ObservationStore` / `libs.perception.store`, y
  verifica consumo de Evidence, ausencia de colisión de puerto, y Perception ↛ Action.

## Test matrix (A–S)

Cubierto en `tests/`: A,B,C,D (reliable), E,F,G,H (idempotente), I (heurístico no
promueve), J (append-only), K/L (aislamiento + discovery), M (tenant B no consume
evidencia de A), N/O (start/stop vía SERVICE_SPECS), P/Q (health/metrics), R
(sin colisión de puerto), S (imagen Docker build verificada localmente). E2E
(Observation→Evidence→Hypothesis→Evaluation) en `test_e2e_observation_to_evaluation_provenance`.

## Riesgos remanentes

- El matcher MVP es heurístico: en producción las Hypotheses candidatas no se
  promueven a confirmed/falsified hasta que exista un matcher de evidencia
  estructurada/confiable (decisión arquitectónica explícita, no un gap oculto).
- `README_EN.md` / `README_ES.md` son espejos del índice `README.md`; se actualizó
  el índice y `cognitive_contract.md`; la expansión exhaustiva de los READMEs largos
  queda fuera de este PR (no cambia comportamiento).
