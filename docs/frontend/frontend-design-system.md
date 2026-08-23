# Frontend Design System — COS-Monitor Web

> **Version:** 1.0 · **Status:** Official · **Owner:** COS-Monitor · **Date:** 2026-08-23

## Purpose

This document defines the visual design system of the COS-Monitor web application: color tokens, typography, component variants, and the quality-class visual language.

## Color Tokens (CSS Variables)

All colors are defined as CSS custom properties in `src/styles/globals.css` and toggle between light/dark mode via the `dark` class on `<html>`.

| Token | Light | Dark | Purpose |
|---|---|---|---|
| `--background` | white | neutral-950 | Page background |
| `--foreground` | neutral-950 | neutral-50 | Primary text |
| `--card` | white | neutral-900 | Card surfaces |
| `--accent` | neutral-100 | neutral-800 | Active state highlight |
| `--muted` | neutral-100 | neutral-800 | Muted backgrounds |
| `--border` | neutral-200 | neutral-800 | Borders |
| `--sidebar` | neutral-950 | neutral-950 | Sidebar background |
| `--destructive` | red-600 | red-400 | Errors, danger |

## Typography

- **Headings**: `text-xl font-semibold` (h1), `text-sm font-semibold uppercase tracking-wide` (section labels)
- **Body**: `text-sm text-muted-foreground`
- **Data**: `text-2xl font-semibold tabular-nums` (counters), `text-xs font-mono` (IDs)
- **Badges**: `text-xs font-medium` inside `<Badge variant="outline">`

## Component Library

### Primitives (`components/ui/`)

| Component | Variants | Usage |
|---|---|---|
| `Button` | default, ghost, destructive, outline; sm, md, lg, icon | Actions |
| `Badge` | default, secondary, destructive, outline | Status labels |
| `Card` + `CardHeader` + `CardContent` + `CardTitle` | — | Content containers |
| `Input` | default | Form fields |
| `Field` | — | Label + value display |
| `Skeleton` | — | Loading placeholders |

### State Primitives (`components/ui/state.tsx`)

| Component | Props | Purpose |
|---|---|---|
| `LoadingState` | `label?` | Spinner + text (role="status", aria-live="polite") |
| `EmptyState` | `title`, `description?` | No-data message |
| `ErrorState` | `title?`, `message?` | Error display |
| `UnauthorizedState` | — | 401 message |
| `ForbiddenState` | `action?` | 403 message |
| `NotAvailable` | `label?` | Inline "Not available" text |

### Cognitive Components

| Component | Purpose |
|---|---|
| `QualityClassBadge` | Q1-Q4 colored badges (emerald/sky/amber/red) |
| `QualityClassLegend` | Full legend of quality classes |

## Quality Class Visual Language

| Class | Label | Color (light) | Color (dark) |
|---|---|---|---|
| Q1 | Direct Measurement | emerald-100/emerald-900 | emerald-900/40/emerald-200 |
| Q2 | Corroborated Inference | sky-100/sky-900 | sky-900/40/sky-200 |
| Q3 | Statistical Regularity | amber-100/amber-900 | amber-900/40/amber-200 |
| Q4 | Anecdotal / Single-Source | red-100/red-900 | red-900/40/red-200 |

All quality class data is immutable (P1) — badges reflect the class assigned at creation, never retrofitted.

## Layout

- **AppShell**: fixed sidebar (w-64, hidden on mobile) + sticky header (h-14) + breadcrumbs + scrollable outlet
- **Sidebar**: dark background (`bg-sidebar`), 4 navigation groups (Overview, Cognition, Action, Administration)
- **Header**: search bar (Cmd+K), tenant switcher, notifications bell, theme toggle, user menu
- **Responsive**: sidebar collapses on `< md`; pages use `grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4`

## Icons

All icons from `lucide-react`. Minimal, functional, non-decorative. Consistent sizing: `h-4 w-4` (inline), `h-5 w-5` (headings).

## Dark Mode

- Persisted in `localStorage` under `cosmonitor.theme`
- Applied via `dark` class on `<html>` element
- All CSS variables update automatically
- Quality class badges maintain contrast in both modes

## Evolution Notes

- Add CSS variables for success/warning/info states beyond destructive.
- Define spacing scale tokens (currently Tailwind defaults).
- Add animation tokens for transitions between states.

## References

- `apps/web/src/styles/globals.css` (CSS variable definitions)
- `apps/web/src/hooks/use-theme.tsx` (theme provider)
- `apps/web/src/components/ui/` (component library)
