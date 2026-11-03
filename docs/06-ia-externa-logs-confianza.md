# Propuesta de Diseño — IA Externa para Análisis de Logs y Estimación de Confianza

**Estado:** Propuesto (draft, sin implementar)
**Aplica a:** `company-os-monitor` (el producto)
**Origen:** decisión de diseño del dueño; alineada al Framework de Arquitectura Cognitiva (`company-os`).
**Relaciones:** ADR-0001, ADR-0002 (capacidades externas no-canónicas), ADR-0003 (Memory/Learning layer), P1–P7, R1–R7.

---

## 1. Contexto y motivación

El pipeline canónico de COS-Monitor (Perception → Reasoning → Confidence → Action) ya
produce juicios con **Confianza calibrada** (C_final = [α·S + (1−α)·C]·(1−ECE)), sin usar IA
para ese cálculo.

El dueño plantea dos extensiones con IA local/remota (ollama, LM Studio, ChatGPT, Gemini,
DeepSeek, Claude):

1. **Estimación de confianza de un activo** (server, router, switch, etc.) asistida por IA.
2. **Análisis en tiempo real de logs** de los dispositivos monitoreados por un modelo de IA.

Este documento define cómo integrar ambas capacidades **sin romper los invariantes del
framework** (P1–P7, R1–R7, R3 Cognitive Boundary, R4 No Action Without Confidence).

---

## 2. Principios rectores (alineación a full)

- **ADR-0002**: Toda capacidad externa (IA) es **no-canónica**. Su salida **debe re-entrar
  al flujo canónico** como un artefacto estructurado y validado; nunca bypassa el pipeline.
- **P1 (Primacía de la Observación)**: Las Observaciones son **inmutables y nunca
  interpretadas** por el agente. La interpretación (significado) surge **después**, en
  Reasoning. La IA que "lee logs" debe producir **Observaciones/Evidence** estructuradas,
  no juicios finales.
- **P4 (Regularidad y Ley)**: Los patrones describen regularidad; las Hipótesis la
  explican. La IA puede **proponer hipótesis**, nunca decidir causalidad como hecho.
- **P5 (Confianza Calibrada)**: La confianza se **computa, no se intuye**. La IA **nunca**
  produce el número C_final como "opinión"; sólo puede aportar **evidencia / hipótesis /
  interpretación** que entran al modelo de calibración.
- **R3 (Cognitive Boundary)**: La IA externa se invoca sólo como **tool** dentro del flujo
  canónico; su salida pasa por parsing estructurado (Pydantic) y validación de contrato.
- **R4 (No Action Without Confidence)**: Ninguna acción/recomendación/decisión se libera
  sin confidence calibrada proveniente del calibrador canónico.
- **ADR-0003**: El aprendizaje (P7) persiste append-only y tenant-scoped; la IA puede
  alimentar el señal de aprendizaje, pero nunca escribir directamente en el Memory Ledger
  sin pasar por el Learning Loop.

---

## 3. Decisiones de diseño (propuestas)

### 3.1 Abstracción `LlmProvider` (local/remoto)

Hoy existe `LMStudioHypothesisTool` (sólo LM Studio, sólo hipótesis). Se propone una
abstracción general que permita **cualquier proveedor** (local o remoto) con el mismo
contrato `CognitiveTool` (invoke → validate_output → available):

```
[LlmProvider] (abstracto)
 ├── LmStudioProvider      (local: LM Studio / ollama, compatible OpenAI)
 ├── OpenAiCompatibleProvider (remoto: ChatGPT, Gemini, DeepSeek, Claude vía API)
```

Cada provider expone:
- `available() -> bool` — probe de salud (nunca bloquea el flujo).
- `invoke(input: dict) -> T` — prompt estructurado → salida estructurada.
- `validate_output(output: T) -> bool` — valida el contrato cognitivo.

**Regla de fallback:** si ningún provider está disponible, el flujo canónico continúa con
plantillas internas. La IA es **aditiva**, nunca un punto único de falla.

### 3.2 Análisis de logs en tiempo real (Observación asistida por IA)

**Dónde entra:** en la capa de **Perception** (agentes: linux-agent, windows-agent,
vmware-agent), como capacidad externa que ayuda a **estructurar** observaciones a partir de
logs crudos — **no** a emitir juicios.

**Contrato propuesto:**

- **Input**: log(s) crudos de un dispositivo (syslog, application log, event).
- **Transform**: el agente (o un servicio de enriching) pide al LLM extraer **hechos
  observables** (fact_type, fact_value, calidad) y mapearlos a `Observation` canónicas.
- **Output**: una o más `Observation` válidas (P1: inmutables, no interpretadas como
  "conclusión").

**Restricción clave (P1):** la salida del LLM se **valida contra el esquema `Observation`**
(Q1–Q4, fact_type conocido). El LLM **no** decide "esto es una anomalía"; sólo estructura
lo que observó. La anomalía la detecta el motor canónico (Pattern/Anomaly service).

**¿En tiempo real?** Sí, mediante un **servicio de enrichment de observaciones** que corre
junto al agente, con:
- cola (Redis) de logs por procesar,
- límite de latencia (ej. ventana de 5–15s),
- `available()` como gate: si la IA no responde, los logs se encolan o se descartan
  **sin** afectar el flujo canónico (se conserva la observación mínima del agente).

### 3.3 Estimación de confianza de un activo

**Punto crítico de alineación:** la IA **NUNCA** debe producir el número C_final como
"opinión". Eso viola P5 y R4.

**Rol propuesto para la IA:** aportar **interpretación contextual** y **evidencia adicional**
que el calibrador canónico consume. Concretamente:

- La IA puede generar una **`Hypothesis`** (explicación candidata, con criterio de
  falsificación) sobre el estado de un activo — reutilizando `LMStudioHypothesisTool` /
  `LlmProvider`.
- Esa hipótesis **entra al flujo canónico** (Hypothesis service) y pasa por:
  1. parsing estructurado,
  2. validación de contrato (falsification_criterion obligatorio),
  3. **Confidence Calibration** (el calibrador canónico calcula S, C, ECE y C_final).
- La **confianza del activo** que se muestra en el dashboard es la **C_final canónica**,
  nunca un score "crudo" del LLM.

**Resultado:** la IA *asiste* la estimación (aporta hipótesis/contexto), pero el **valor
de confianza** sigue siendo un **medición calibrada** del pipeline, preservando P5/R4.

---

## 4. Contratos de integración (boceto)

```python
# libs/cognitive_core/llm_provider.py (nuevo)
from typing import Generic, TypeVar
from libs.cognitive_core.cognitive_tool import CognitiveTool

T = TypeVar("T")

class LlmProvider(CognitiveTool[T]):
    """Abstracción para cualquier proveedor LLM (local/remoto)."""
    # hereda: invoke(input) -> T ; validate_output(output) -> bool ; available() -> bool

class OpenAiCompatibleProvider(LlmProvider[T]):
    """Provider genérico compatible OpenAI (LM Studio, ollama, ChatGPT, Gemini,
    DeepSeek, Claude vía endpoint compatible)."""
    def __init__(self, base_url: str, api_key: str, model: str, ...): ...
```

```python
# libs/perception/observation_enricher.py (nuevo)
class ObservationEnricher:
    """Estructura logs crudos -> Observaciones canónicas (P1) usando un LlmProvider."""
    async def enrich(self, raw_log: str) -> list[Observation]: ...
    # validate: cada Observation cumple esquema (fact_type, quality_class Q1-Q4)
```

---

## 5. Riesgos y mitigaciones

| Riesgo | Mitigación |
|---|---|
| La IA "alucina" hechos | Salida validada contra esquema `Observation`; calidad Q1–Q4; el LLM nunca decide causalidad |
| Latencia en tiempo real | Cola Redis + timeout + `available()` gate; fallback a observación mínima |
| Costo (remoto) | Provedores remotos opcionales; local por defecto; límite de requests |
| Romper P5/R4 (IA "da" la confianza) | La confianza **siempre** la calcula el calibrador canónico; la IA sólo aporta hipótesis/evidencia |
| Proveedor caído | Fallback a plantillas internas; la IA es aditiva, no bloqueante |
| Seguridad (logs sensibles) | Tenant-scoped, sin exponer credenciales al prompt; sanitización |

---

## 6. Orden de implementación sugerido (cuando haya hardware)

1. **Abstracción `LlmProvider`** + adaptadores local (LM Studio/ollama) y remoto (OpenAI-compatible).
2. **`ObservationEnricher`** en el linux-agent (logs → Observaciones) — respetando P1.
3. **Reutilizar `LlmProvider`** en Hypothesis service (ya hay LM Studio; generalizar a multi-provider).
4. **Nunca** tocar el Confidence service para "dejar pasar" scores de IA.

---

## 7. Fuera de alcance (por ahora)

- Que la IA decida autónomamente acciones.
- Que la IA modifique el calibrador o el Memory Ledger.
- Que la IA reemplace el pipeline canónico.
