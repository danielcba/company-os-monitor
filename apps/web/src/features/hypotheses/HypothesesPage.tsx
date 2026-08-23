import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Brain } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchHypotheses } from '@/api/gateway'
import type {
  CognitiveHypothesis,
  CognitiveHypothesisSort,
  CognitiveHypothesisStatus,
} from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { HypothesisDetail } from '@/features/hypotheses/HypothesisDetail'

const PAGE_SIZE = 50

export function StatusBadge({ status }: { status: CognitiveHypothesisStatus }) {
  if (status === 'confirmed') {
    return (
      <Badge className="border-emerald-500/40 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200">
        Confirmed
      </Badge>
    )
  }
  if (status === 'falsified') {
    return (
      <Badge className="border-red-500/40 bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200">
        Falsified
      </Badge>
    )
  }
  return <Badge variant="outline">Candidate</Badge>
}

export function HypothesesPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState<CognitiveHypothesisStatus | ''>('')
  const [sort, setSort] = useState<CognitiveHypothesisSort>('generated_at_desc')
  const [selected, setSelected] = useState<CognitiveHypothesis | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['hypotheses', tenantId, { offset, status, sort }],
    queryFn: () =>
      fetchHypotheses(tenantId!, {
        limit: PAGE_SIZE,
        offset,
        status: status || undefined,
        sort,
      }),
    enabled: Boolean(tenantId),
  })

  const applyFilter = () => {
    setOffset(0)
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1
  const hasFilters = Boolean(status)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Hypotheses</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Tentative, testable explanations of anomalies (Reasoning · Predict). A
            hypothesis pairs an explanation with observable predicted consequences and
            a falsification criterion — it is a commitment held tentatively until
            evidence decides. This is the first view where causal explanations appear
            (P4). Content is immutable once generated (P1); only the status lifecycle
            field may change (candidate → confirmed/falsified, decided by future
            evidence + Confidence).
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Status
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as CognitiveHypothesisStatus | '')
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.statuses ?? []).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Order
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as CognitiveHypothesisSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="generated_at_desc">Newest first</option>
              <option value="generated_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading hypotheses…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view hypotheses" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.hypotheses.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No hypotheses match the filters' : 'No hypotheses yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Hypotheses appear here as soon as the generator proposes testable explanations for this tenant’s detected anomalies.'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Generated at</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Coherence</th>
                  <th className="px-3 py-2 font-medium">Anomalies</th>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.hypotheses.map((hypothesis) => (
                  <tr
                    key={hypothesis.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(hypothesis)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(hypothesis.generated_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={hypothesis.status} />
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {hypothesis.coherence_score.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {hypothesis.anomaly_ids.length}
                    </td>
                    <td className="max-w-[360px] truncate px-3 py-2 text-muted-foreground">
                      {hypothesis.description}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Brain className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} hypotheses · page {page} of {totalPages.toLocaleString()}
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

      <HypothesisDetail hypothesis={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default HypothesesPage