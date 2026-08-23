import { useQuery } from '@tanstack/react-query'
import { useAuth } from '@/hooks/use-auth'
import { fetchCognitiveSummary } from '@/api/gateway'
import type { CognitiveTotals } from '@/types/cognitive'
import { ServiceHealthPanel } from '@/components/infrastructure/ServiceHealthPanel'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingState, ErrorState, NotAvailable } from '@/components/ui/state'

const PIPELINE = [
  'Observation',
  'Evidence',
  'Context',
  'Pattern',
  'Anomaly',
  'Hypothesis',
  'Insight',
  'Confidence',
  'Recommendation',
  'Decision',
]

const FAMILY_LABELS: Record<string, string> = {
  Observation: 'Perception',
  Evidence: 'Perception',
  Context: 'Perception',
  Pattern: 'Reasoning',
  Anomaly: 'Reasoning',
  Hypothesis: 'Reasoning',
  Insight: 'Reasoning',
  Confidence: 'Learning',
  Recommendation: 'Action',
  Decision: 'Action',
}

const TOTALS_LABELS: { key: keyof CognitiveTotals; label: string; family: string }[] = [
  { key: 'observations', label: 'Observations', family: 'Perception' },
  { key: 'evidence', label: 'Evidence', family: 'Perception' },
  { key: 'contexts', label: 'Contexts', family: 'Perception' },
  { key: 'patterns', label: 'Patterns', family: 'Reasoning' },
  { key: 'anomalies', label: 'Anomalies', family: 'Reasoning' },
  { key: 'hypotheses', label: 'Hypotheses', family: 'Reasoning' },
  { key: 'confidence_scores', label: 'Confidence', family: 'Learning' },
  { key: 'recommendations', label: 'Recommendations', family: 'Action' },
  { key: 'decisions', label: 'Decisions', family: 'Action' },
  { key: 'reports', label: 'Reports', family: 'External' },
  { key: 'servers', label: 'Servers', family: 'Infrastructure' },
]

function StatusBadge({ statuses }: { statuses: Record<string, number> }) {
  const entries = Object.entries(statuses)
  if (entries.length === 0) return <NotAvailable />
  return (
    <div className="flex flex-wrap gap-1">
      {entries.map(([status, count]) => (
        <Badge key={status} variant="outline">
          {status} {count}
        </Badge>
      ))}
    </div>
  )
}

export function DashboardPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['cognitive', 'summary', tenantId],
    queryFn: () => fetchCognitiveSummary(tenantId!),
    enabled: Boolean(tenantId),
    refetchInterval: 30_000,
  })

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Welcome back{user?.name ? `, ${user.name}` : ''}. Pipeline state for your tenant.
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Cognitive Flow</CardTitle>
          <p className="text-sm text-muted-foreground">
            Reality → Observation → Evidence → Context → Pattern → Anomaly → Hypothesis → Insight →
            Confidence → Recommendation → Decision
          </p>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-center gap-1.5">
            {PIPELINE.map((concept, index) => (
              <span key={concept} className="flex items-center gap-1.5">
                <span className="flex flex-col rounded-md border border-border bg-card px-2 py-1 text-xs font-medium">
                  {concept}
                  <span className="text-[10px] font-normal text-muted-foreground">
                    {FAMILY_LABELS[concept]}
                  </span>
                </span>
                {index < PIPELINE.length - 1 ? (
                  <span className="text-muted-foreground">→</span>
                ) : null}
              </span>
            ))}
          </div>
        </CardContent>
      </Card>

      <div>
        <h2 className="mb-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
          Pipeline state
        </h2>
        {isPending ? (
          <LoadingState label="Loading pipeline state…" />
        ) : isError ? (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        ) : data ? (
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
            {TOTALS_LABELS.map(({ key, label, family }) => (
              <Card key={key}>
                <CardContent className="flex flex-col gap-1 p-4">
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">{family}</p>
                  <p className="text-2xl font-semibold tabular-nums">{data.totals[key]}</p>
                  <p className="text-sm text-muted-foreground">{label}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        ) : null}
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
        <Card>
          <CardHeader>
            <CardTitle>Hypotheses by status</CardTitle>
          </CardHeader>
          <CardContent>
            <StatusBadge statuses={data?.status.hypotheses ?? {}} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Recommendations by status</CardTitle>
          </CardHeader>
          <CardContent>
            <StatusBadge statuses={data?.status.recommendations ?? {}} />
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Decisions by status</CardTitle>
          </CardHeader>
          <CardContent>
            <StatusBadge statuses={data?.status.decisions ?? {}} />
          </CardContent>
        </Card>
      </div>

      <ServiceHealthPanel />
    </div>
  )
}

export default DashboardPage