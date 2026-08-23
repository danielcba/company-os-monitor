# Frontend Cognitive UX — COS-Monitor Web

> **Version:** 1.0 · **Status:** Official · **Owner:** COS-Monitor · **Date:** 2026-08-23

## Purpose

This document defines the UX principles that ensure the frontend faithfully represents cognitive concepts without distortion, fabrication, or misrepresentation. Every visual decision maps to a cognitive principle.

## Core UX Principles

### 1. Truthfulness (P1 — Immutability)

- **What the user sees is what the pipeline produced.** No fabrication, no approximation, no "close enough."
- When data is absent: show `Not available` or `No [concept] yet` — never invented values.
- When data is immutable: the UI never exposes edit controls for cognitive artifacts (observations, evidence, contexts, patterns, anomalies, hypotheses, insights, confidence).
- Lifecycle fields (`is_active`, `status`, `executed_at`) are the only mutable state — and they reflect backend decisions, not user edits.

### 2. Honest State Representation

Every page renders exactly one of these states:

| State | Visual | When |
|---|---|---|
| Loading | Spinner + "Loading…" | Request in flight |
| Empty | Dashed border + "No [concept] yet" | Valid query, zero results |
| Error | Red border + title + message | Request failed |
| Unauthorized | Red border + "Session expired" | 401 after refresh failure |
| Forbidden | Red border + "Access denied" | 403 from backend |
| Data | Table/detail view | Successful response |

States are **never combined** — a page shows one state at a time. The `StateSwitch` component ensures this invariant.

### 3. Cognitive Flow Visualization

The Dashboard renders the canonical cognitive pipeline:

```
Reality → Observation → Evidence → Context → Pattern → Anomaly →
Hypothesis → Insight → Confidence → Recommendation → Decision
```

Each concept is labeled with its cognitive family (Perception, Reasoning, Learning, Action). The flow is visual-only — it does not imply execution order or data flow speed.

### 4. Quality Class Language (P5 — Evidence Quality)

Quality classes are the visual language for evidence quality:

| Class | Visual | Meaning |
|---|---|---|
| Q1 | Emerald badge | Direct Measurement — highest reliability |
| Q2 | Sky badge | Corroborated Inference — supported by multiple sources |
| Q3 | Amber badge | Statistical Regularity — pattern-based, not direct |
| Q4 | Red badge | Anecdotal / Single-Source — lowest reliability |

Quality class badges appear on:
- Observations (in the `quality_class` column)
- Evidence (in the `quality_class` column)
- Contexts (via the supporting evidence's quality classes)
- Confidence detail (in the evidential support breakdown)

The legend (`QualityClassLegend`) is always available on pages that display quality classes.

### 5. Confidence as Calibrated Estimate (P5)

Confidence is shown as a **calibrated reliability estimate**, never as "the probability that the hypothesis is true."

- **Confidence detail** shows: C_final, S (evidential support), C (explanatory coherence), 1 − ECE (calibration factor), α (mixing coefficient), ECE (calibration error estimate), and the justification verbatim.
- **Recommendations** carry the calibrated confidence score of their leading hypothesis — they never recompute or recalibrate.
- **Missing confidence** shows `Not available` — the system never fabricates a confidence score.

### 6. Separation of Concerns (P4 — Explanation vs. Regularity)

- **Patterns** show regularity (structure, frequency, strength) — never causal claims.
- **Hypotheses** show causal explanations (tentative, with falsification criteria) — the first place causes appear.
- **Anomalies** show quantified deviation (deviation_score vs. tolerance_threshold) — never causal claims.
- The UI enforces this separation: a Pattern page never says "because"; a Hypothesis page never says "this pattern exists."

### 7. Recommendation ≠ Decision (P6)

- **Recommendations** are advisory offers: "this is what we suggest, with confidence C, rationale R, and alternatives considered." They carry `status: proposed | accepted | rejected | superseded`.
- **Decisions** are commitments: "this is what we will do, with authority A, expected outcomes, and risk tolerance." They carry `status: committed | executing | completed | rolled_back`.
- The UI clearly distinguishes these states — a recommendation is never shown as "done" and a decision is never shown as "suggested."

### 8. Traceability

Every detail view shows the **provenance chain**:
- An Evidence detail shows its source Observations.
- A Context detail shows its supporting Evidence and competing mental models.
- A Pattern detail shows its source Context.
- An Anomaly detail shows its source Context.
- A Hypothesis detail shows its source Anomalies, Patterns, and Contexts.
- A Confidence detail shows its target (Hypothesis/Recommendation/Decision) with full breakdown.
- A Recommendation detail shows its leading Hypothesis and calibrated Confidence.
- A Decision detail shows its Recommendation and Confidence.

Missing links in the chain show `No trace available` — never fabricated connections.

### 9. Multi-Tenant Awareness

- The **TenantSwitcher** (header) is only visible to superadmins.
- All data is scoped to the current tenant — the user sees only their tenant's data.
- Cross-tenant queries by non-superadmins result in a 403 `ForbiddenState`.
- The current tenant name and slug appear in the sidebar and user menu.

### 10. Accessibility

- All interactive elements have `aria-label` or visible text.
- Loading states use `role="status"` and `aria-live="polite"`.
- Color is never the sole indicator of meaning — quality class badges include text labels (Q1, Q2, Q3, Q4).
- Keyboard navigation works for all interactive elements (sidebar links, table rows, buttons).

## Page-Specific UX Patterns

### Dashboard
- Cognitive flow visualization (static, informational).
- Pipeline counters in a responsive grid (tabular-nums for alignment).
- Status breakdowns as badges (hypotheses/recommendations/decisions lifecycle).
- Service health panel (real-time pipeline health).

### List Pages (Observations, Evidence, etc.)
- Paginated table with filterable columns.
- Facets (distinct values from real data) drive filter options — never invented.
- Sort by timestamp (desc/asc).
- Click row → detail drawer (slide-in panel).
- Loading → skeleton rows. Empty → dashed border + honest message.

### Detail Pages
- Full provenance chain (from raw facts to the current concept).
- Immutable content shown as read-only.
- Lifecycle fields (status, is_active) shown with their current value.
- Related concepts shown as linked cards with their own quality class badges.

### Administration
- Users: full CRUD (admin+) with role assignment.
- Roles: read-only reference card showing the 4 roles and their permissions.
- Tenants: read-only table (superadmin only).
- System: infrastructure health panel.

## Evolution Notes

- Add cognitive trace visualization (full pipeline trace for a decision).
- Add timeline view for concept evolution over time.
- Add comparison view for two hypotheses or recommendations.
- Add export/share functionality for cognitive traces.

## References

- `cognitive_contract.md` (product cognitive contract)
- `docs/cognitive-lexicon/cognitive-principles.md` (P1-P7)
- `docs/cognitive-architecture/cognitive-architecture.md` (R1-R7)
- `apps/web/src/components/ui/state.tsx` (state primitives)
- `apps/web/src/components/cognitive/QualityClassBadge.tsx` (quality class visual)
