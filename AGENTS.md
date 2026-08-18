# AGENTS.md — Company OS Monitor

Guía para sesiones de agente sobre este repositorio. El producto implementa el
framework de arquitectura cognitiva Company OS: cada componente implementa
exactamente una capacidad cognitiva (R1) con un Cognitive Contract definido
(R2); el framework guía el código, nunca lo contrario (R7).

## Marco de referencia (solo lectura)

- Framework (SOLO LECTURA, NO modificar): `/home/dcordoba/Documents/Default Project/company/company-os-main/`
- Producto (este repo): `/home/dcordoba/Documents/Default Project/company-os-monitor/`
- El framework es read-only; la arquitectura guía el código, nunca al revés.

## Política de citación canónica (NO escribir nada fuera de la policy)

Toda referencia al marco usa exclusivamente el set canónico:

- **Principios**: P1–P7 — `docs/cognitive-lexicon/cognitive-principles.md`
- **Design rules**: R1–R7 — `docs/cognitive-architecture/cognitive-architecture.md`
- **Conceptos**: nombres de `docs/cognitive-lexicon/core-concepts/*.md`
- **ADR**: ADR-0001 (Company OS es el cerebro), ADR-0002 (COS-Monitor es el producto)

Reglas:

1. **Nada fuera de la policy se escribe.** Toda cita/referencia al marco debe
   mapear a un elemento canónico existente y verificable en el checkout.
2. **No se inventan números de regla** (p. ej. "R8/R9/R10" con significados
   propios): colisionan con las canónicas. Quien necesite una referencia que
   no existe, la describe de forma factual sin número de regla.
3. **NO usar la numeración R1–R10 de `ontology.md`**: sus significados difieren
   de R1–R7 de `cognitive-architecture.md` (p. ej. la R5 de ontology =
   "observación/interpretación nunca se mezclan", que en el producto es P1; la
   R9 de ontology = "la arquitectura guía el código", que en el producto es R7).
4. La trazabilidad, objetividad y provenance se describen de forma factual,
   **sin número de regla**.
5. No citar paths, specs o campos que no existan en el checkout del marco
   (p. ej. `specifications/` no existe; los conceptos viven en
   `docs/cognitive-lexicon/core-concepts/*.md`).
6. Ante una afirmación sin respaldo canónico: se omite o se describe factual,
   nunca se le inventa una regla ni un spec.

## Conformidad por capa (recordatorio)

- Observations / Evidence / Context / Pattern: append-only e inmutables (P1);
  `quality_class`/`weight`/`coherence_score` asignados en la creación, sin retrofitting.
- Context se activa por competencia de coherencia entre modelos compatibles,
  nunca se genera directamente (P2).
- Patterns describen regularidad con apoyo suficiente; las explicaciones de
  causa son de Hypothesis (P4).
- Ninguna conclusión influye acción sin Confidence calibrada (R4) — la
  calibración y el Action Layer (Recommendation → Decision) son fases futuras.
- Confianza/calibración y LM Studio: herramientas/capacidades externas
  no-canónicas (ADR-0002), nunca bypassan el flujo cognitivo canónico.
