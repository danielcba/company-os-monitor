# Frontend Architecture — COS-Monitor Web

> **Version:** 1.0 · **Status:** Official · **Owner:** COS-Monitor · **Date:** 2026-08-23

## Purpose

This document describes the architecture of the COS-Monitor web application (`apps/web`), an external product capability (ADR-0002) that represents cognitive concepts from the Company OS pipeline — it never redefines or executes them.

## Stack

| Layer | Choice | Purpose |
|---|---|---|
| Framework | React 19 + TypeScript | SPA with strict typing |
| Build | Vite 8 | Lazy routes, code-splitting |
| Styling | Tailwind CSS v4 + CSS-variable tokens | Design system, light/dark |
| Data | TanStack React Query 5 | Server state (loading/error/refetch) |
| Routing | React Router 7 | Protected routes, breadcrumbs |
| Tests | Vitest 4 + React Testing Library | Unit / component / integration |
| Icons | lucide-react | Minimal, non-decorative |
| Lint | oxlint | Fast, Rust-based |

## Directory Structure

```
apps/web/src/
├── app/providers.tsx              # QueryClientProvider + ThemeProvider + AuthProvider
├── main.tsx                       # React root entry
├── routes/
│   ├── index.tsx                  # Route table (BrowserRouter, lazy pages)
│   └── ProtectedRoute.tsx         # Auth guard (redirect → /login)
├── api/
│   ├── client.ts                  # apiFetch: JWT, refresh, 401 retry
│   ├── auth.ts                    # login(), fetchMe()
│   ├── admin.ts                   # createUser(), updateUser(), deactivateUser()
│   └── gateway.ts                 # ~30 cognitive data fetching functions
├── types/
│   ├── auth.ts                    # Role, UserProfile, AuthSession, TokenClaims
│   └── cognitive.ts               # All cognitive domain types (571 lines)
├── hooks/
│   ├── use-auth.tsx               # AuthContext + useAuth
│   └── use-theme.tsx              # ThemeProvider + useTheme (light/dark)
├── lib/
│   ├── utils.ts                   # cn(), formatDateTime(), formatRole(), shortId()
│   ├── quality-class.ts           # QUALITY_CLASS_LABELS (Q1-Q4)
│   └── query-client.ts            # React Query client config
├── components/
│   ├── ui/                        # button, badge, card, input, field, skeleton, state
│   ├── layout/                    # AppShell, Sidebar, Header, Breadcrumbs, TenantSwitcher, UserMenu
│   ├── cognitive/                 # QualityClassBadge, QualityClassLegend
│   └── infrastructure/           # ServiceHealthPanel
├── features/
│   ├── auth/LoginPage.tsx
│   ├── dashboard/DashboardPage.tsx
│   ├── observations/              # ObservationsPage, ObservationDetail, format.ts
│   ├── evidence/                  # EvidencePage, EvidenceDetail
│   ├── contexts/                  # ContextsPage, ContextDetail
│   ├── patterns/                  # PatternsPage, PatternDetail
│   ├── anomalies/                 # AnomaliesPage, AnomalyDetail
│   ├── hypotheses/                # HypothesesPage, HypothesisDetail
│   ├── insights/                  # InsightsPage, InsightDetail
│   ├── confidence/                # ConfidencePage, ConfidenceDetail
│   ├── recommendations/           # RecommendationsPage, RecommendationDetail
│   ├── decisions/                 # DecisionsPage, DecisionDetail
│   ├── reports/                   # ReportsPage, ReportDetail
│   ├── audit/                     # AuditPage, AuditDetail
│   ├── search/                    # GlobalSearchPage
│   ├── admin/                     # UsersPage, RolesPage, TenantsPage, SystemPage
│   ├── notifications/             # NotificationsCenter
│   └── command-palette/           # CommandPalette, CommandPaletteContext, useCommandPalette
├── styles/globals.css             # Tailwind + CSS variable tokens
└── tests/                         # 18 test files (Vitest + RTL)
```

## Provider Tree

```tsx
<QueryClientProvider>    // TanStack React Query
  <ThemeProvider>        // light/dark via CSS class on <html>
    <AuthProvider>       // JWT session, signIn/signOut
      <BrowserRouter>    // React Router
        <AppShell>       // Sidebar + Header + Outlet
```

## Data Flow

1. **Authentication**: `AuthProvider` checks localStorage for `cosmonitor.access_token`. If present, calls `GET /api/v1/user/me` to load the profile.
2. **API Gateway**: All cognitive data fetched via `apiFetch()` → `http://localhost:8100/api/v1/...` with Bearer JWT.
3. **User Service**: Auth endpoints via `http://localhost:8099/api/v1/...`.
4. **Token Refresh**: On 401, `apiFetch` calls `POST /auth/refresh` with the refresh token, then retries once.
5. **Tenant Scoping**: `user.tenant_id` from the JWT claims drives all API calls. Superadmin can switch tenants via `TenantSwitcher`.

## Cognitive Compliance

- Views map 1:1 to cognitive capabilities (external capability, ADR-0002).
- R3: all reads through the Gateway; auth via user-service only.
- P1: append-only data shown as-is; never fabricated.
- P2: context shown as active model + competing models; never generated directly.
- P4: patterns = regularity, hypotheses = causal explanation; never mixed.
- P5: confidence = calibrated reliability estimate; never a probability of truth.
- P6: recommendation ≠ decision; recommendation is advisory, decision is commitment.
- Frontend never creates cognitive concepts; never touches DB/Redis.

## Evolution Notes

- Add OpenAPI code generation when the platform exposes an OpenAPI spec.
- Implement service-worker caching for offline read of latest snapshot.
- Add WebSocket subscriptions for real-time cognitive updates.

## References

- ADR-0002: COS-Monitor Is the Product
- `docs/frontend/architecture.md` (detailed feature-level architecture)
- `cognitive_contract.md` (product cognitive contract)
