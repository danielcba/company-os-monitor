# Learning Layer (P7) — Status and Pipeline

## Current Status: PARTIAL

P7 (Learning Through Outcome) is partially implemented:
- ** IMPLEMENTED **: Expected vs actual outcomes comparison (Brier score, ECE)
- ** IMPLEMENTED **: Confidence calibration with historical calibration factor
- ** PLANNED **: Automatic calibration update from outcome comparison
- ** PLANNED **: Memory persistence of learning signals
- ** NOT IMPLEMENTED **: Automated feedback loop

## Learning Pipeline

```
Decision
    ↓
Expected Outcomes (declared before execution)
    ↓
Actual Outcomes (observed after execution)
    ↓
Outcome Error (Brier score, ECE)
    ↓
Calibration Update (historical_calibration = 1 - ECE)
    ↓
Memory (future: persist learning signals)
```

## Key Functions

### compare_expected_actual_outcomes (IMPLEMENTED)

Located in `libs/action/decision.py`.

Compares expected vs actual outcomes and computes:
- `brier_score`: Mean squared error between predicted probabilities and actual outcomes
- `ece`: Expected Calibration Error
- `historical_calibration`: 1 - ECE
- `confidence_adjustment`: Change in the (1-ECE) factor

### build_confidence (IMPLEMENTED)

Located in `libs/learning/confidence.py`.

Builds a calibrated confidence from:
- `evidential_support`: S(H|E)
- `explanatory_coherence`: C(H)
- `historical_calibration`: 1 - ECE
- `alpha`: mixing coefficient

## What's Missing

1. **Automatic calibration update**: The comparison results are not automatically fed back to update confidence scores
2. **Memory persistence**: Learning signals are not stored in a dedicated memory table
3. **Feedback loop**: No automated mechanism to trigger re-calibration based on outcomes

## Falsifiability

P7 is designed to be falsifiable:
- Expected outcomes must be declared BEFORE execution
- Actual outcomes are observed AFTER execution
- The comparison is objective (Brier score, ECE)
- No synthetic data is used to fake learning

## Future Work

- Sprint 10+: Implement automatic calibration update
- Sprint 12+: Implement memory persistence
- Sprint 14+: Implement feedback loop
