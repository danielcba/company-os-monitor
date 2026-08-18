# Company OS Monitor - FASE 4 y 5: Reasoning Layer - Pattern, Anomaly, Hypothesis, Insight, Confidence

## Principios Rectores

- **P3 — Stable Concepts, Transformative Intelligence**: Los conceptos (Pattern, Anomaly, Hypothesis, Insight, Confidence) son estables. La inteligencia vive en las transformaciones entre ellos.
- **P4 — Regularity and Law**: Patterns revelan regularidad. Laws explican regularidad. Hypothesis propone explicaciones testables.
- **P5 — Calibrated Confidence**: Todo juicio que influye en acción debe llevar Confidence calibrada (evidential support + coherence + historical calibration).
- **R1/R2**: Cada capacidad implementa **exactly one** concepto cognitivo con **Cognitive Contract definido**.
- **R4**: Ninguna conclusión influye en acción sin Confidence calibrada.
- **ADR-0002**: El flujo canónico (Perception → Reasoning → Confidence → Action) es el cerebro. LM Studio es herramienta externa no-canónica para Hypothesis Generation e Insight Restructuring.

---

# FASE 4: Reasoning Layer — Pattern, Anomaly, Hypothesis, Insight

## Cognitive Pipeline del Reasoning Layer

```
Active Context (desde Perception Layer)
        │
        ▼
┌───────────────────────┐
│  PATTERN DETECTION    │  Concept: Pattern | Family: Reasoning | Capability: Generalize
│  (Pattern Service)    │
│  Input: Active Context + Pattern Library (o open search)          │
│  Transform: Detect recurrent structures, correlations, sequences  │
│  Output: Pattern(s) + strength measure (support/frequency/p-val)  │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  ANOMALY DETECTION    │  Concept: Anomaly | Family: Reasoning | Capability: Detect Deviation
│  (Anomaly Service)    │
│  Input: Active Context + Expected Pattern(s) + Tolerance        │
│  Transform: Compare context vs pattern, measure deviation       │
│  Output: Anomaly + deviation score + violated pattern(s)        │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  HYPOTHESIS GENERATION│  Concept: Hypothesis | Family: Reasoning | Capability: Predict
│  (Hypothesis Service) │
│  Input: Active Context + Patterns + Anomalies + Mental Models   │
│  Transform: Generate testable explanations with falsification   │
│  Output: Hypothesis(es) + predicted consequences + falsification│
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  INSIGHT RESTRUCTURING│  Concept: Insight | Family: Reasoning | Capability: Restructure
│  (Insight Service)    │
│  Input: Active Context + Active Hypotheses + Knowledge          │
│  Transform: Restructure relationships between knowledge elements│
│  Output: Insight (novel understanding) + updated mental model   │
└───────────┬───────────┘
            │
            ▼
┌───────────────────────┐
│  CONFIDENCE CALIBRATION│ Concept: Confidence | Family: Learning | Capability: Calibrate
│  (Confidence Service)  │ (cross-cutting, applies to Hypothesis/Rec/Decision)
│  Input: Judgment + Evidence + Coherence + History                │
│  Transform: Calibration Model (S + C) · (1 - ECE)                │
│  Output: Confidence score + justification + calibration error    │
└───────────┬───────────┘
            │
            ▼
       ACTION LAYER
       (Recommendation → Decision)
```

---

## Pattern Detection (Pattern Service) — Concept: Pattern

### Cognitive Contract
- **Input**: Active Context + Pattern Library (known patterns) o Open Search Space
- **Transformation**: Detectar estructuras recurrentes, correlaciones, secuencias dentro del Active Context; comparar contra patrones conocidos
- **Output**: Candidate Pattern(s) + medida de fuerza (support, frequency, statistical significance)

### Pattern Types por Dominio de Infraestructura

| Pattern Type | Dominio | Descripción | Strength Measure | Mental Model Context |
|--------------|---------|-------------|------------------|---------------------|
| **Temporal Periodic** | Backup, Batch Jobs | "Backup fails every Friday 23:00" | Frequency + p-value (chi-square) | Operational schedules |
| **Resource Growth Trend** | Disk, Memory, DB | "Disk usage grows 2.3%/week linear" | R² + slope confidence interval | Capacity planning |
| **Correlation Cluster** | Multi-resource | "CPU↑ + Memory↑ + Disk Latency↑ together" | Mutual information / PCC | Resource contention |
| **Event Sequence** | Logs, Auth | "5 failed logins → 1 success → privilege escalation" | Sequence mining support/confidence | Attack patterns |
| **Threshold Approach** | Any metric | "Metric approaching threshold with accelerating rate" | Time-to-threshold distribution | Predictive maintenance |

### Implementation Tools (Subordinados a Cognitive Contract)

| Pattern Type | Primary Library | Fallback | Data Minimum |
|--------------|----------------|----------|--------------|
| Temporal Periodic | `statsmodels` (STL, seasonal_decompose) | `prophet` | 30 días (3+ cycles) |
| Resource Growth Trend | `pmdarima` (auto_arima) → ARIMA/SARIMA | Holt-Winters | 30 días |
| Correlation Cluster | `scikit-learn` (mutual_info, PCA) | `numpy` corr | 60 días |
| Event Sequence | `scikit-learn` (PrefixSpan) / `mlxtend` | Custom | 90 días eventos |
| Threshold Approach | `statsmodels` (survival analysis) | Linear extrapolation | 7+ días |

### Pattern Library (Procedural Memory)
Patrones conocidos versionados en Git, deployed via CI/CD:
```yaml
# patterns/disk_growth_weekly.yaml
pattern_id: disk_growth_weekly_v1
type: temporal_periodic
domain: storage
description: "Weekly periodicity in disk growth (batch jobs, logs)"
min_observations: 21  # 3 weeks
strength_threshold: 0.7  # R²
falsification: "No weekly periodicity detected in 4 consecutive weeks"
```

---

## Anomaly Detection (Anomaly Service) — Concept: Anomaly

### Cognitive Contract
- **Input**: Active Context + Expected Pattern(s) + Tolerance Thresholds (explícitos, auditable, purpose-dependent)
- **Transformation**: Comparar Active Context contra patrón esperado, medir magnitud de desviación
- **Output**: Anomaly + deviation score + patrón(es) violado(s)

### Anomaly Classes (per Anomaly Spec)

| Class | Definition | Example | Tolerance Definition |
|-------|------------|---------|---------------------|
| **Point Anomaly** | Single observation deviates | Backup fails Tuesday (expected: Friday only) | `deviation > 3σ` from pattern |
| **Contextual Anomaly** | Observation anomalous in specific context | 200 login failures in 40 sec during business hours | `rate > baseline_rate * 10` in context |
| **Collective Anomaly** | Set of observations deviates together | Disk growth rate changes from 2% to 8%/week sustained | `CUSUM > threshold` on rate change |

### Tolerance Thresholds (Explícitos, Auditable)
```yaml
# anomalies/tolerances.yaml
disk_growth_rate_change:
  type: collective
  metric: disk_growth_percent_per_week
  baseline_pattern: disk_growth_weekly_v1
  tolerance: "CUSUM(h=5, k=0.5) on weekly growth rate delta"
  purpose: "early capacity exhaustion warning"
  
backup_schedule_deviation:
  type: point
  metric: backup_completion_day_of_week
  baseline_pattern: backup_friday_only_v1
  tolerance: "day_of_week != 5 (Friday)"
  purpose: "operational schedule compliance"
```

### Relationship to Hypothesis (Anomaly → Hypothesis)
- Anomaly **Contradicts** Context (debilita coherencia explicativa)
- Anomaly **Leads To** Hypothesis (anomalías motivan nuevas explicaciones)
- Anomaly **Refines** Pattern (anomalías persistentes fuerzan revisión de patrón)

---

## Hypothesis Generation (Hypothesis Service) — Concept: Hypothesis

### Cognitive Contract
- **Input**: Active Context + Patterns + Anomalies + Mental Model Library
- **Transformation**: Generar explicaciones testables que expliquen la situación actual y sean consistentes con el modelo mental más coherente
- **Output**: 
  - One or more candidate Hypotheses
  - Predicted consequences of each hypothesis (observable, falsifiable)
  - Falsification criterion: concrete observable outcome that would demonstrate hypothesis false

### Hypothesis Templates por Dominio

| Domain | Anomaly Trigger | Candidate Hypotheses (H1, H2, H3...) | Falsification Criteria |
|--------|-----------------|--------------------------------------|------------------------|
| **Disk Saturation** | Growth rate anomaly (2% → 8%/week) | H1: New logging verbosity enabled<br>H2: Backup retention policy changed<br>H3: Database auto-growth misconfigured | H1 falsified if log verbosity unchanged<br>H2 falsified if retention policy unchanged<br>H3 falsified if DB growth settings normal |
| **Backup Failure** | Backup fails on Tuesday (not Friday) | H1: Maintenance job schedule changed<br>H2: Disk target reached capacity<br>H3: New antivirus scan conflicts window | H1 falsified if job schedule unchanged<br>H2 falsified if disk > 20% free<br>H3 falsified if AV schedule unchanged |
| **Auth Burst** | 200 failed logins/40sec business hours | H1: Compromised account probing<br>H2: Misconfigured app retry loop<br>H3: External monitoring tool testing | H1 falsified if single source IP<br>H2 falsified if app logs show no retries<br>H3 falsified if no monitoring tool configured |

### Multiple Competing Hypotheses (per Hypothesis Design Implications)
- **Mantener múltiples hipótesis simultáneamente** — convergencia prematura = fallo cognitivo
- Representar con: evidential support, predicted consequences, falsification criteria
- **Explanatory Coherence (P2)**: Aceptar hipótesis que maximice coherencia con evidencia total

### LM Studio Integration para Hypothesis Generation (External Capability)

LM Studio es una **herramienta externa no-canónica** (ADR-0002) usada por Hypothesis Service para:
1. Generar candidate hypotheses desde Anomaly + Context + Mental Models
2. Producir predicted consequences en términos observables
3. Sugerir falsification criteria

**Cognitive Contract para LM Studio en Hypothesis Generation:**
- **Input**: Structured prompt = Active Context (Evidence summary) + Anomaly description + Mental Model descriptions + Few-shot examples
- **Transformation**: LLM reasoning sobre explicaciones plausibles
- **Output**: Structured JSON = Hypothesis[] {description, predicted_consequences[], falsification_criterion, coherence_estimate}

```python
# hypothesis_service/lm_studio_client.py
from openai import OpenAI
from pydantic import BaseModel
from typing import List

class HypothesisCandidate(BaseModel):
    description: str
    predicted_consequences: List[str]  # observable, falsifiable
    falsification_criterion: str
    coherence_estimate: float  # 0-1, LLM self-assessment

lm_client = OpenAI(base_url="http://localhost:1234/v1", api_key="not-needed")

HYPOTHESIS_GENERATION_PROMPT = """
You are an expert infrastructure analyst. Given an Active Context and Anomaly, 
generate 3-5 competing testable hypotheses. Each must have:
1. Description (explanation)
2. Predicted consequences (observable, verifiable)
3. Falsification criterion (concrete outcome that would prove it wrong)
4. Coherence estimate (0-1)

Active Context: {context_summary}
Anomaly: {anomaly_description}
Available Mental Models: {mental_models}
Evidence: {evidence_summary}

Output JSON array of HypothesisCandidate.
"""

async def generate_hypotheses(context, anomaly, mental_models, evidence) -> List[HypothesisCandidate]:
    response = await lm_client.chat.completions.create(
        model="local-model",
        messages=[
            {"role": "system", "content": HYPOTHESIS_GENERATION_PROMPT},
            {"role": "user", "content": f"Context: {context}\nAnomaly: {anomaly}\nModels: {mental_models}\nEvidence: {evidence}"}
        ],
        temperature=0.3,  # diversity for competing hypotheses
        max_tokens=3000,
        response_format={"type": "json_object"}
    )
    return parse_hypotheses(response.choices[0].message.content)
```

---

## Insight Restructuring (Insight Service) — Concept: Insight

### Cognitive Contract
- **Input**: Active Context + Active Hypotheses + Existing Knowledge Structures
- **Transformation**: Reestructurar relaciones entre elementos de conocimiento existentes para producir comprensión más coherente o general
- **Output**: Insight (novel understanding) + updated mental model

### Insight Triggers (Metacognitive)

| Trigger | Detection | Action |
|---------|-----------|--------|
| **Repeated Falsification** | >3 hypotheses falsified for same anomaly cluster | Trigger restructuring: current frame fails |
| **Cross-Domain Pattern** | Pattern detected linking previously unrelated domains (e.g., backup failure + auth anomaly = compromised backup account) | Restructure: unify mental models |
| **Confidence Impasse** | Confidence calibration fails (ECE > threshold) repeatedly | Trigger metacognitive restructuring |
| **Novel Anomaly Class** | Anomaly type not in Pattern Library | Create new pattern category, restructure library |

### Insight Examples (per Insight Spec)

| Situation | Insight | Restructuring |
|-----------|---------|---------------|
| Backup failures, disk pressure, slow response treated separately | "All three symptoms are consequences of a single constraint: the storage controller is saturated" | Evidence reorganized from 3 problems → 1 root cause |
| Two anomaly streams monitored independently | "Both streams generated by same compromised service account" | Mental model updated: threat model spans domains |

### LM Studio Integration para Insight Restructuring

```python
# insight_service/lm_studio_client.py
INSIGHT_RESTRUCTURING_PROMPT = """
You are an expert infrastructure analyst. Given multiple hypotheses, anomalies, and evidence
that have not been resolved by current mental models, restructure the understanding.

Current Frame: {current_mental_model}
Active Hypotheses: {hypotheses}
Anomalies: {anomalies}
Evidence: {evidence}
Failed Falsifications: {failed_falsifications}

Produce:
1. Novel understanding (insight) - new organization of existing knowledge
2. Updated mental model description
3. New predicted consequences from restructured model
4. Confidence in restructuring (0-1)
"""
```

---

## Confidence Calibration (Confidence Service) — Concept: Confidence | Family: Learning | Cross-cutting

### Cognitive Contract
- **Input**: Judgment (Hypothesis / Recommendation / Decision) + Evidence + Explanatory Coherence + Historical Performance
- **Transformation**: Calibration Model computation
- **Output**: Confidence score + justification + calibration error estimate

### Calibration Model (Per Confidence Spec — Formal Specification)

```
1. EVIDENTIAL SUPPORT: S(H|E) = 1 / (1 + e⁻ᴸ)
   L = L₀ + Σᵢ wᵢ·eᵢ
   - wᵢ ∈ [0,1] from Evidence Quality Class (Q1: 0.75-1.0, Q2: 0.50-0.75, Q3: 0.25-0.50, Q4: 0.00-0.25)
   - eᵢ ∈ {+1, -1} (supports/contradicts)
   - L₀ = 0 (uniform prior) unless documented base rate

2. EXPLANATORY COHERENCE: C(H) ∈ [0,1]
   Normalized constraint satisfaction (Thagard 1989)
   Positive: H explains evidence; hypotheses that jointly explain are coherent
   Negative: contradiction constraints

3. HISTORICAL CALIBRATION: (1 - ECE)
   Brier Score: B = (1/N) Σᵢ (pᵢ - oᵢ)²
   ECE = Σₘ (|Bₘ|/N) · |accₘ - confₘ| over M bins (default M=10)

4. FINAL CONFIDENCE: C_final = [α·S + (1-α)·C] · (1 - ECE)
   - α ∈ [0,1] fixed a priori, documented (default α=0.5)
   - Never tuned to match desired confidence

5. PARAMETERS (fixed a priori, published with every report):
   - α = 0.5 (mixing coefficient)
   - M = 10 (ECE bins)
   - L₀ = 0 (uniform prior)
```

### Confidence Application (Confidence ↦ Hypothesis, Recommendation, Decision)

| Judgment Type | Confidence Required | Threshold for Action |
|---------------|---------------------|---------------------|
| **Hypothesis** | Always computed | > 0.7 to lead to Insight/Recommendation |
| **Recommendation** | Always computed (Confidence ↦ Recommendation) | > 0.6 to propose; > 0.8 for high-risk |
| **Decision** | Always computed (Confidence ↦ Decision) | > 0.75 to commit; > 0.9 for irreversible |

### Confidence Affects (Confidence ⇝)
- **Recommendation strength**: Higher confidence → stronger recommendation language, fewer alternatives
- **Decision threshold**: Higher confidence → lower evidence threshold for commitment

### Historical Calibration Feedback (Confidence ← Memory/ Learning)
- Every Decision produces outcome → compares expected vs actual → updates Brier/ECE
- Continuous monitoring: if ECE > 0.15 for any judgment class → metacognitive alert → trigger restructuring

---

# FASE 5: LM Studio — External Capability para Reasoning Layer

## Posición Arquitectónica (ADR-0002)

LM Studio es una **capacidad externa no-canónica**. Se usa como herramienta por:
- **Hypothesis Service**: Generar candidate hypotheses (abductive reasoning)
- **Insight Service**: Restructuring cuando frame falla (metacognitive trigger)
- **Context Service** (futuro): Coherence evaluation entre mental models competidores

**NUNCA** bypassa el flujo cognitivo. Todo output de LM Studio pasa por:
1. Parsing estructurado (Pydantic validation)
2. Confidence Calibration (evidential support from Evidence, coherence, historical)
3. Hypothesis/Insight representation con falsification criteria
4. Solo entonces → Recommendation → Decision

## Model Selection por Cognitive Capability

| Cognitive Capability | Model Recommended | Justificación (Cognitive) |
|---------------------|-------------------|---------------------------|
| **Hypothesis Generation** (abductive, diverse) | Qwen 3 14B / DeepSeek V3 | Good divergence, structured output, falsification criteria |
| **Insight Restructuring** (analogical, frame-switching) | DeepSeek R1 32B | Superior reasoning for restructuring, causal chains |
| **Coherence Evaluation** (Context competition) | Qwen 3 32B | Better structured comparison, coherence scoring |
| **MVP / Budget** | Llama 4 8B / Mistral 7B | Minimum viable for structured JSON output |

## Hardware Requirements (para Cognitive Throughput)

| Tier | Cognitive Throughput Target | CPU | GPU | RAM | Model |
|------|----------------------------|-----|-----|-----|-------|
| **MVP** (3-5 tenants) | 10 hypotheses/min, 1 insight/hr | 8 cores AVX2 | Optional | 16 GB | Llama 4 8B / Mistral 7B |
| **Production** (20+ tenants) | 50 hypotheses/min, 5 insights/hr | 16 cores | RTX 3090 24GB | 32 GB | Qwen 3 14B / DeepSeek V3 |
| **Enterprise** (100+ tenants) | 200 hypotheses/min, 20 insights/hr | Dual EPYC | 2x A4000 48GB | 128 GB | DeepSeek R1 32B / Llama 4 70B |

**Critical**: CPU inference (~3-5 tok/s) sufficient for **batch hypothesis generation** (scheduled, not real-time). Real-time Context activation requires GPU for <500ms latency.

## Integration Contract (Cognitive Boundary Enforcement)

```python
# reasoning/lm_studio_contract.py
from abc import ABC, abstractmethod
from typing import Generic, TypeVar

T = TypeVar('T')

class CognitiveTool(ABC, Generic[T]):
    """Abstract contract for external cognitive tools (LM Studio, etc.)"""
    
    @abstractmethod
    async def invoke(self, input: dict) -> T:
        """Invoke tool with structured input, return structured output"""
        pass
    
    @abstractmethod
    def validate_output(self, output: T) -> bool:
        """Validate output conforms to cognitive contract (e.g., Hypothesis has falsification)"""
        pass

class LMStudioHypothesisTool(CognitiveTool[List[HypothesisCandidate]]):
    """LM Studio as hypothesis generation tool"""
    
    async def invoke(self, input: dict) -> List[HypothesisCandidate]:
        # ... LM Studio call with structured prompt
        return parsed_hypotheses
    
    def validate_output(self, hypotheses: List[HypothesisCandidate]) -> bool:
        # Every hypothesis MUST have falsification_criterion
        return all(h.falsification_criterion for h in hypotheses)

# Usage in Hypothesis Service (canonical flow)
async def generate_hypotheses_canonical(context, anomaly, evidence):
    # 1. Internal pattern-based hypotheses (always)
    internal_hypotheses = pattern_based_hypotheses(context, anomaly)
    
    # 2. LM Studio hypotheses (external tool, optional)
    lm_tool = LMStudioHypothesisTool()
    if lm_tool.available():
        lm_hypotheses = await lm_tool.invoke(build_prompt(context, anomaly, evidence))
        if lm_tool.validate_output(lm_hypotheses):
            all_hypotheses = internal_hypotheses + lm_hypotheses
        else:
            all_hypotheses = internal_hypotheses  # fallback
    else:
        all_hypotheses = internal_hypotheses
    
    # 3. ALL hypotheses go through Confidence Calibration
    for h in all_hypotheses:
        h.confidence = await confidence_service.calibrate(h, evidence, context)
    
    # 4. Explanatory coherence competition (P2)
    active_hypotheses = coherence_competition(all_hypotheses, context)
    
    return active_hypotheses
```

## Model Management (Procedural Memory)

- Model versions, prompts, parameters versionados en Git (`models/`, `prompts/`)
- Deployed via CI/CD como Procedural Memory artifacts
- A/B testing de modelos via Confidence calibration comparison (historical ECE)
- Rollback automático si nuevo modelo degrada calibración (ECE increase > 0.05)