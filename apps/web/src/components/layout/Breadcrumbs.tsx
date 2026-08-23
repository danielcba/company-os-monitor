import { useMemo } from 'react'
import { Link, useLocation } from 'react-router-dom'
import { cn } from '@/lib/utils'
import { useAuth } from '@/hooks/use-auth'

const SEGMENT_LABELS: Record<string, string> = {
  dashboard: 'Dashboard',
  cognition: 'Cognition',
  observations: 'Observations',
  evidence: 'Evidence',
  contexts: 'Contexts',
  patterns: 'Patterns',
  anomalies: 'Anomalies',
  hypotheses: 'Hypotheses',
  insights: 'Insights',
  confidence: 'Confidence',
  audit: 'Audit Log',
  action: 'Action',
  recommendations: 'Recommendations',
  decisions: 'Decisions',
  investigation: 'Investigation',
  reports: 'Reports',
  infrastructure: 'Infrastructure',
  administration: 'Administration',
  users: 'Users',
  roles: 'Roles',
  tenants: 'Tenants',
  system: 'System',
  search: 'Search',
}

export function Breadcrumbs() {
  const { pathname } = useLocation()
  const { user } = useAuth()
  const segments = useMemo(() => pathname.split('/').filter(Boolean), [pathname])
  const tenantId = user?.tenant_id

  const crumbs = segments.map((segment, index) => {
    const path = `/${segments.slice(0, index + 1).join('/')}`
    const label = SEGMENT_LABELS[segment] ?? segment
    const isLast = index === segments.length - 1
    return { path, label, isLast }
  })

  return (
    <nav aria-label="Breadcrumb" className="flex items-center gap-1.5 text-sm text-muted-foreground">
      <Link to="/dashboard" className="hover:text-foreground">
        Home
      </Link>
      {crumbs.map((crumb) => (
        <span key={crumb.path} className="flex items-center gap-1.5">
          <span className="text-muted-foreground/50">/</span>
          {crumb.isLast ? (
            <span aria-current="page" className="font-medium text-foreground">
              {crumb.label}
            </span>
          ) : (
            <Link to={crumb.path} className="hover:text-foreground">
              {crumb.label}
            </Link>
          )}
        </span>
      ))}
      {tenantId ? (
        <span
          className={cn('ml-2 hidden items-center rounded px-1.5 py-0.5 text-xs sm:inline-flex')}
        >
          tenant {tenantId.slice(0, 8)}
        </span>
      ) : null}
    </nav>
  )
}