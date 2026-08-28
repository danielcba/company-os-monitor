# 2026-08-28 — Phase 3A: Hypothesis Evaluation (Cerrar el Learning Loop)

## Objetivo
Implementar la capacidad **Evaluate** (Reasoning) para cerrar el bucle:
```
Hypothesis (candidate) → nueva Evidence → Evaluation Policy → confirmed / falsified / insufficient
```

## Cambios Implementados

### 1. Modelo de Evaluación (`libs/reasoning/evaluation.py`)
- `Evaluation` / `EvaluationCreate` / `EvaluationStore`
- UUID determinístico `evaluation_id` (tenant + hypothesis_id + evidence_ids + result)
- Append-only, inmutable (trigger P1), idempotent dedup
- Campos: hypothesis_id, evidence_ids, observed_outcomes, support_count, contradiction_count, confidence_id, result, rationale, evaluated_at
- Resultados válidos: `confirmed`, `falsified`, `insufficient`

### 2. Política de Evaluación Formal (`libs/reasoning/evaluation_policy.py`)
Reglas fijas a priori (nunca tunificadas):

| Regla | Condición | Resultado |
|-------|-----------|-----------|
| **FALSIFIED** | falsification_criterion met (>=1) AND confidence < 0.30 | falsified |
| **CONFIRMED** | >=2 predictions supported AND confidence >= 0.75 AND no falsification | confirmed |
| **INSUFFICIENT** | Default (ambigüedad) | insufficient |

**Principio conservador:** Confidence es señal necesaria, NO suficiente. Una sola predicción nunca confirma. Ambigüedad → candidate.

### 3. Evaluation Service (`apps/services/evaluation-service/`)
- Orquesta ciclo por tenant (paralelo con asyncio.gather)
- Lee candidate hypotheses + nuevas observations + confidence calibrada
- Aplica policy → persiste Evaluation → actualiza hypothesis.status (única mutación permitida)
- Métricas: total_evaluations, confirmed, falsified, insufficient, duplicates, errors
- Puerto 8097

### 4. Extensiones a Stores Existentes
- `HypothesisStore.get_hypothesis_by_id()` + `update_hypothesis_status()` (solo confirmed/falsified)
- `ObservationStore.list_observations_since()` para evidencia nueva

### 5. Migración DB (`sprint14-hypothesis-evaluation.sql`)
- Tabla `hypothesis_evaluations` con FK a hypotheses, confidence_scores
- Trigger inmutabilidad P1 (bloquea UPDATE/DELETE)
- Índices por tenant/hypothesis y tenant/result

### 6. Tests (36 total)
- **Unit**: model (deterministic ID, frozen, validation), policy (19 tests: support/contradiction, decision rules, conservative checks)
- **Integration**: store (insert/read, idempotent, immutability, by_hypothesis, append-only history, tenant isolation, re-evaluation new row)

## Validación
- `ruff check`: ✅ GREEN
- `mypy`: ✅ GREEN (strict)
- `pytest tests/`: 255/255 passed (root)
- `pytest apps/services/evaluation-service/tests/`: 36/36 passed
- `pytest apps/services/hypothesis-service/tests/`: 21/22 passed (1 pre-existing unrelated failure)

## Documentación
- `cognitive_contract.md`: Agregada capacidad "Hypothesis Evaluation" (servicio #7), actualizado pipeline Reasoning Layer, puertos (8097)

## Arquitectura
- **R1**: Evaluation Service = exactamente una capacidad (Evaluate)
- **R2**: Cognitive Contract definido (Input: candidate hypothesis + new evidence + confidence → Transform: policy → Output: evaluation + status change)
- **R3**: Cognitive Boundary respetado (no actions, no raw observations)
- **P1**: Append-only, inmutabilidad en BD
- **P7**: Learning loop habilitado (Evaluation → Outcome → Memory en fases siguientes)

## Próximos Pasos (Fase 3B+)
- Phase 3B: Outcome / Evaluation Contract (Decision → expected vs actual outcomes)
- Phase 3C: Memory Consolidation
- Phase 3D: Calibration Monitoring
- Phase 3E: Contextual + Collective Anomaly