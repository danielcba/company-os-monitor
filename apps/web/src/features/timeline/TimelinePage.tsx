import { useState } from 'react'
import { useAuth } from '@/hooks/use-auth'
import { ApiError } from '@/types/cognitive'
import { useCognitiveTimeline } from '@/features/timeline/useCognitiveTimeline'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingState,
} from '@/components/ui/state'

function layerVariant(
  layer: string,
): 'outline' | 'accent' | 'warning' | 'success' | 'default' {
  switch (layer) {
    case 'perception':
      return 'outline'
    case 'reasoning':
      return 'accent'
    case 'action':
      return 'warning'
    case 'memory':
      return 'success'
    default:
      return 'default'
  }
}

function fmt(ts: string): string {
  const d = new Date(ts)
  return Number.isNaN(d.getTime()) ? ts : d.toLocaleString()
}

function SectionError({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.status === 403) {
    return <ForbiddenState action="view the cognitive timeline" />
  }
  if (error instanceof ApiError && error.status === 404) {
    return (
      <EmptyState
        title="No activity"
        description="This tenant has no recorded cognitive activity yet."
      />
    )
  }
  return <ErrorState message={error instanceof Error ? error.message : undefined} />
}

export function TimelinePage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id
  const [ascending, setAscending] = useState(false)
  const [limit, setLimit] = useState(40)

  const query = useCognitiveTimeline(tenantId, { limit, ascending })

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Cognitive Timeline</h1>
          <p className="text-sm text-muted-foreground">
            Chronological reconstruction of the tenant&apos;s cognitive activity
            (read-only, derived from canonical stores).
          </p>
        </div>
        <label className="flex items-center gap-2 text-sm text-muted-foreground">
          <input
            type="checkbox"
            checked={ascending}
            onChange={(e) => setAscending(e.target.checked)}
          />
          Oldest first
        </label>
        <select
          className="rounded border border-border bg-background px-2 py-1 text-sm"
          value={limit}
          onChange={(e) => setLimit(Number(e.target.value))}
          aria-label="Events per concept"
        >
          <option value={20}>20 / concept</option>
          <option value={40}>40 / concept</option>
          <option value={80}>80 / concept</option>
        </select>
      </div>

      {query.isLoading && <LoadingState label="Reconstructing timeline…" />}
      {query.isError && <SectionError error={query.error} />}
      {query.isSuccess && query.data.total === 0 && (
        <EmptyState
          title="No activity"
          description="This tenant has no recorded cognitive activity yet."
        />
      )}

      {query.isSuccess && query.data.total > 0 && (
        <div className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle className="text-sm">Activity by layer</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-wrap gap-2">
              {Object.entries(query.data.per_layer_counts).map(([layer, count]) => (
                <Badge key={layer} variant={layerVariant(layer)}>
                  {layer}: {count}
                </Badge>
              ))}
            </CardContent>
          </Card>

          <ol className="relative space-y-3 border-l border-border pl-4">
            {query.data.events.map((ev) => (
              <li key={`${ev.concept}-${ev.id}`} className="relative">
                <span className="absolute -left-[21px] top-2 h-2 w-2 rounded-full bg-primary" />
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs font-medium text-muted-foreground">
                    {fmt(ev.timestamp)}
                  </span>
                  <Badge variant={layerVariant(ev.layer)}>{ev.layer}</Badge>
                  <Badge variant="outline">{ev.concept}</Badge>
                  {ev.status && <Badge variant="outline">{ev.status}</Badge>}
                </div>
                <div className="mt-1 text-sm font-medium">{ev.title}</div>
                {ev.detail && (
                  <div className="text-xs text-muted-foreground">{ev.detail}</div>
                )}
              </li>
            ))}
          </ol>
        </div>
      )}
    </div>
  )
}

export default TimelinePage
