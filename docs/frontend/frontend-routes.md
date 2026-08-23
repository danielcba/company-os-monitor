# Frontend Routes — COS-Monitor Web

> **Version:** 1.0 · **Status:** Official · **Owner:** COS-Monitor · **Date:** 2026-08-23

## Purpose

This document defines the complete route table of the COS-Monitor web application, including access control, lazy loading, and cognitive pipeline mapping.

## Route Table

All routes defined in `src/routes/index.tsx`. Protected routes are wrapped in `<ProtectedRoute>` (auth guard) then `<AppShell>` (layout).

### Public Routes

| Path | Component | Auth | Description |
|---|---|---|---|
| `/login` | `LoginPage` | Public | Email/password login form |

### Protected Routes — Overview

| Path | Component | Auth | Description |
|---|---|---|---|
| `/` | `Navigate → /dashboard` | JWT | Root redirect |
| `/dashboard` | `DashboardPage` | JWT | Cognitive pipeline health, summary counters |
| `/search` | `GlobalSearchPage` | JWT | Global search (Cmd+K) |

### Protected Routes — Cognition (Perception + Reasoning + Learning)

| Path | Component | Auth | Description |
|---|---|---|---|
| `/cognition/observations` | `ObservationsPage` | JWT | Raw immutable facts (Perception · Capture) |
| `/cognition/evidence` | `EvidencePage` | JWT | Organized facts (Perception · Organize) |
| `/cognition/contexts` | `ContextsPage` | JWT | Active interpretations (Perception · Interpret) |
| `/cognition/patterns` | `PatternsPage` | JWT | Detected regularities (Reasoning · Generalize) |
| `/cognition/anomalies` | `AnomaliesPage` | JWT | Quantified deviations (Reasoning · Detect) |
| `/cognition/hypotheses` | `HypothesesPage` | JWT | Tentative explanations (Reasoning · Predict) |
| `/cognition/insights` | `InsightsPage` | JWT | Restructured understanding (Reasoning · Restructure) |
| `/cognition/confidence` | `ConfidencePage` | JWT | Calibrated reliability (Learning · Calibrate) |
| `/cognition/audit` | `AuditPage` | JWT | Episodic memory / audit log |

### Protected Routes — Action

| Path | Component | Auth | Description |
|---|---|---|---|
| `/action/recommendations` | `RecommendationsPage` | JWT | Proposed actions (Action · Propose) |
| `/action/decisions` | `DecisionsPage` | JWT | Committed decisions (Action · Commit) |
| `/action/reports` | `ReportsPage` | JWT | Generated reports (Action · Report) |

### Protected Routes — Administration

| Path | Component | Auth | Description |
|---|---|---|---|
| `/administration/users` | `UsersPage` | JWT | User CRUD (admin+) |
| `/administration/roles` | `RolesPage` | JWT | Role definitions (viewer+) |
| `/administration/tenants` | `TenantsPage` | JWT | Tenant management (superadmin) |
| `/administration/system` | `SystemPage` | JWT | Infrastructure health |

### Catch-All

| Path | Behavior |
|---|---|
| `*` | Redirect → `/dashboard` |

## Access Control

### Authentication Guard (`ProtectedRoute`)

1. If `isLoading` → render `<LoadingState label="Verifying session…" />`
2. If `!isAuthenticated` → redirect to `/login` with `state.from` (return URL)
3. If `isAuthenticated` → render `<Outlet />` (child routes)

### Role-Based Access (UI Level)

The frontend renders navigation items and action buttons based on `user.role`:

| Role | Navigation | Actions |
|---|---|---|
| `viewer` | All read-only views | Read pipeline data |
| `operator` | All read-only views | + Acknowledge artifacts |
| `admin` | All views + Users admin | + User CRUD, propose, commit, define policy |
| `superadmin` | All views + Tenants admin | + Cross-tenant, execute, tenant management |

### Backend Enforcement (R3)

All access control is ultimately enforced by the API Gateway:
- JWT verification on every request
- RBAC check (role + permission + risk ceiling)
- Tenant isolation (query scoped by `tenant_id`)
- Cross-tenant only with `superadmin` authority

## Lazy Loading

All page components are lazy-loaded via `React.lazy()` + `<Suspense>`:

```tsx
const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage'))

<Route path="/dashboard" element={
  <LazySuspense><DashboardPage /></LazySuspense>
} />
```

Fallback: `<LoadingState label="Loading…" />`

## Breadcrumbs

Auto-generated from URL path segments by `Breadcrumbs.tsx`:
- `/cognition/observations` → Home > Cognition > Observations
- `/administration/users` → Home > Administration > Users

## Evolution Notes

- Add route-level RBAC guards (admin-only routes redirect viewers).
- Implement route preloading for critical paths.
- Add nested detail routes (`/cognition/observations/:id`).

## References

- `apps/web/src/routes/index.tsx` (route definitions)
- `apps/web/src/routes/ProtectedRoute.tsx` (auth guard)
- `apps/web/src/components/layout/Sidebar.tsx` (navigation groups)
- `apps/web/src/components/layout/Breadcrumbs.tsx` (auto-breadcrumbs)
