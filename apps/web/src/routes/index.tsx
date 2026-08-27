import { lazy, Suspense } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'
import { ProtectedRoute } from '@/routes/ProtectedRoute'
import { LoadingState } from '@/components/ui/state'

const LoginPage = lazy(() => import('@/features/auth/LoginPage'))
const DashboardPage = lazy(() => import('@/features/dashboard/DashboardPage'))
const ObservationsPage = lazy(() => import('@/features/observations/ObservationsPage'))
const EvidencePage = lazy(() => import('@/features/evidence/EvidencePage'))
const ContextsPage = lazy(() => import('@/features/contexts/ContextsPage'))
const PatternsPage = lazy(() => import('@/features/patterns/PatternsPage'))
const AnomaliesPage = lazy(() => import('@/features/anomalies/AnomaliesPage'))
const HypothesesPage = lazy(() => import('@/features/hypotheses/HypothesesPage'))
const InsightsPage = lazy(() => import('@/features/insights/InsightsPage'))
const ConfidencePage = lazy(() => import('@/features/confidence/ConfidencePage'))
const RecommendationsPage = lazy(() => import('@/features/recommendations/RecommendationsPage'))
const DecisionsPage = lazy(() => import('@/features/decisions/DecisionsPage'))
const ReportsPage = lazy(() => import('@/features/reports/ReportsPage'))
const CognitiveTracePage = lazy(() => import('@/features/cognitive-trace/CognitiveTracePage'))
const LearningPage = lazy(() => import('@/features/learning/LearningPage'))
const TimelinePage = lazy(() => import('@/features/timeline/TimelinePage'))
const AuditPage = lazy(() => import('@/features/audit/AuditPage'))
const GlobalSearchPage = lazy(() => import('@/features/search/GlobalSearchPage'))
const UsersPage = lazy(() => import('@/features/admin/UsersPage'))
const RolesPage = lazy(() => import('@/features/admin/RolesPage'))
const TenantsPage = lazy(() => import('@/features/admin/TenantsPage'))
const SystemPage = lazy(() => import('@/features/admin/SystemPage'))

function LazySuspense({ children }: { children: React.ReactNode }) {
  return <Suspense fallback={<LoadingState label="Loading…" />}>{children}</Suspense>
}

export function AppRoutes() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LazySuspense><LoginPage /></LazySuspense>} />
        <Route element={<ProtectedRoute />}>
          <Route element={<AppShell />}>
            <Route path="/" element={<Navigate to="/dashboard" replace />} />
            <Route path="/dashboard" element={<LazySuspense><DashboardPage /></LazySuspense>} />
            <Route path="/cognition/observations" element={<LazySuspense><ObservationsPage /></LazySuspense>} />
            <Route path="/cognition/evidence" element={<LazySuspense><EvidencePage /></LazySuspense>} />
            <Route path="/cognition/contexts" element={<LazySuspense><ContextsPage /></LazySuspense>} />
            <Route path="/cognition/patterns" element={<LazySuspense><PatternsPage /></LazySuspense>} />
            <Route path="/cognition/anomalies" element={<LazySuspense><AnomaliesPage /></LazySuspense>} />
            <Route path="/cognition/hypotheses" element={<LazySuspense><HypothesesPage /></LazySuspense>} />
            <Route path="/cognition/insights" element={<LazySuspense><InsightsPage /></LazySuspense>} />
            <Route path="/cognition/confidence" element={<LazySuspense><ConfidencePage /></LazySuspense>} />
            <Route path="/cognition/audit" element={<LazySuspense><AuditPage /></LazySuspense>} />
            <Route path="/action/recommendations" element={<LazySuspense><RecommendationsPage /></LazySuspense>} />
            <Route path="/action/decisions" element={<LazySuspense><DecisionsPage /></LazySuspense>} />
            <Route path="/action/reports" element={<LazySuspense><ReportsPage /></LazySuspense>} />
            <Route path="/action/reports/:reportId/trace" element={<LazySuspense><CognitiveTracePage /></LazySuspense>} />
            <Route path="/learning" element={<LazySuspense><LearningPage /></LazySuspense>} />
            <Route path="/investigation/timeline" element={<LazySuspense><TimelinePage /></LazySuspense>} />
            <Route path="/search" element={<LazySuspense><GlobalSearchPage /></LazySuspense>} />
            <Route path="/administration/users" element={<LazySuspense><UsersPage /></LazySuspense>} />
            <Route path="/administration/roles" element={<LazySuspense><RolesPage /></LazySuspense>} />
            <Route path="/administration/tenants" element={<LazySuspense><TenantsPage /></LazySuspense>} />
            <Route path="/administration/system" element={<LazySuspense><SystemPage /></LazySuspense>} />
          </Route>
        </Route>
        <Route path="*" element={<Navigate to="/dashboard" replace />} />
      </Routes>
    </BrowserRouter>
  )
}