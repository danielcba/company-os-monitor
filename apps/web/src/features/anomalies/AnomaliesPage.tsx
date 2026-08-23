import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Radar } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchAnomalies } from '@/api/gateway'
import type { CognitiveAnomaly, CognitiveAnomalySort } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { AnomalyDetail } from '@/features/anomalies/AnomalyDetail'

const PAGE_SIZE = 50

function shortId(id: string) {
  return id.slice(0, 8)
}

export function AnomaliesPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [anomalyClass, setAnomalyClass] = useState('')
  const [sort, setSort] = useState<CognitiveAnomalySort>('detected_at_desc')
  const [selected, setSelected] = useState<CognitiveAnomaly | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['anomalies', tenantId, { offset, anomalyClass, sort }],
    queryFn: () =>
      fetchAnomalies(tenantId!, {
        limit: PAGE_SIZE,
        offset,
        anomaly_class: anomalyClass || undefined,
        sort,
      }),
    enabled: Boolean(tenantId),
  })

  const applyFilter = () => {
    setOffset(0)
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1
  const hasFilters = Boolean(anomalyClass)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Anomalies</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Detected deviations from patterns (Reasoning · Detect Deviation): an anomaly
            occurs when the deviation_score exceeds the tolerance_threshold. Anomaly is
            shown with the quantified deviation — causal explanations never appear on
            this view (explanation belongs to Hypothesis, P4). Content is immutable once
            detected (P1); it has no lifecycle flag.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Anomaly class
            <select
              value={anomalyClass}
              onChange={(e) => {
                setAnomalyClass(e.target.value)
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.anomaly_classes ?? []).map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Order
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as CognitiveAnomalySort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="detected_at_desc">Newest first</option>
              <option value="detected_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading anomalies…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view anomalies" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.anomalies.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No anomalies match the filters' : 'No anomalies yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Anomalies appear here as soon as the detector measures deviation exceeding the tolerance threshold over this tenant’s context stream.'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Detected at</th>
                  <th className="px-3 py-2 font-medium">Anomaly class</th>
                  <th className="px-3 py-2 font-medium">Deviation</th>
                  <th className="px-3 py-2 font-medium">Threshold</th>
                  <th className="px-3 py-2 font-medium">Context</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.anomalies.map((anomaly) => (
                  <tr
                    key={anomaly.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(anomaly)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(anomaly.detected_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant="outline">{anomaly.anomaly_class}</Badge>
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {anomaly.deviation_score.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {anomaly.tolerance_threshold.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {shortId(anomaly.context_id)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Radar className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} anomalies · page {page} of {totalPages.toLocaleString()}
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset(Math.max(0, offset - data.limit))}
              >
                <ChevronLeft className="h-4 w-4" /> Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + data.limit >= data.total}
                onClick={() => setOffset(offset + data.limit)}
              >
                Next <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </div>
        </>
      )}

      <AnomalyDetail anomaly={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default AnomaliesPage