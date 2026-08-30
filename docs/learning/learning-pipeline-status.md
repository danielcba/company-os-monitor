# Learning Layer (P7) — Status and Pipeline

## Current Status: OPERATIONAL

P7 (Learning Through Outcome) is fully implemented since PR #14 (learning loop) and PR #10 (learning memory ledger):

- **IMPLEMENTED**: Expected vs actual outcomes comparison (Brier score, ECE)
- **IMPLEMENTED**: Confidence calibration with historical calibration factor
- **IMPLEMENTED**: Automatic calibration update from outcome comparison
- **IMPLEMENTED**: Memory persistence of learning signals (append-only ledger)
- **IMPLEMENTED**: Automated feedback loop (Decision → Outcome → Consolidation → Memory)

## Learning Pipeline

```
Decision
    ↓
Expected Outcomes (declared before execution)
    ↓
Actual Outcomes (observed after execution)
    ↓
Outcome Consolidation (corroborated/contradicted/inconclusive)
    ↓
Pattern Refinement (keep/degrade/deactivate signals)
    ↓
Context Revision (keep/review/consider_competitor signals)
    ↓
Insight Transformation (revised/stable/unchanged classification)
    ↓
Learning Memory Ledger (append-only, idempotent by signal_hash)
```

## Key Components

### Consolidation (`libs/memory/consolidation.py`)

Compares expected vs actual outcomes and computes:
- `calibration_feedback`: (corroborated - contradicted) / (corroborated + contradicted)
- `brier_score`: Mean squared error between predicted probabilities and actual outcomes
- `ece`: Expected Calibration Error
- Classification: corroborated, contradicted, inconclusive per outcome

### Pattern Refinement (`libs/memory/pattern_refinement.py`)

Attributes outcomes to Patterns via traceability chain:
- Decision → Recommendation → Hypothesis → Pattern
- Computes `contradiction_ratio` per pattern
- Signals: keep (< 2 samples), degrade (> 0 contradictions), deactivate (>= 50% contradiction)

### Context Revision (`libs/memory/context_revision.py`)

Attributes outcomes to Contexts via traceability chain:
- Decision → Recommendation → Hypothesis → Pattern → Context
- Signals: keep, review, consider_competitor
- Never auto-activates Context (P2 compliant)

### Insight Transformation (`libs/memory/insight_transformation.py`)

Journals transformation of Insights:
- Classification: revised, stable, unchanged (descriptive, P4 compliant)
- Attributes outcomes via recommendation.insight_id

### Learning Memory Ledger (`libs/memory/memory_ledger.py`)

Persists learning signals as append-only ledger:
- Idempotency by UNIQUE index (tenant_id, target_type, target_id, signal_hash)
- 4 signal types: consolidation, pattern_refinement, context_revision, insight_transformation
- Deterministic IDs via uuid5

## What Was Implemented

1. **Consolidation** (libs/memory/consolidation.py): Expected vs actual comparison with cross-tenant validation
2. **Pattern Refinement** (libs/memory/pattern_refinement.py): Outcome attribution to patterns
3. **Context Revision** (libs/memory/context_revision.py): Outcome attribution to contexts
4. **Insight Transformation** (libs/memory/insight_transformation.py): Transformation journaling
5. **Learning Loop** (libs/memory/learning_loop.py): Orchestration of all refinement signals
6. **Memory Ledger** (libs/memory/memory_ledger.py): Append-only persistence with dedup
7. **Learning Memory Table** (infrastructure/db-migrations/learning-memory-ledger.sql): DB schema

## Falsifiability

P7 is designed to be falsifiable:
- Expected outcomes must be declared BEFORE execution
- Actual outcomes are observed AFTER execution
- The comparison is objective (Brier score, ECE)
- No synthetic data is used to fake learning

## Future Work

- Calibration Dashboard: Visualize calibration metrics over time
- Historical ECE computation: Accumulate outcome history for accurate ECE
- Automated re-calibration triggers: Re-calibrate confidence when new outcomes arrive
