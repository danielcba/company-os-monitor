import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Compass } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchRecommendations } from '@/api/gateway'
import type {
  CognitiveRecommendation,
  CognitiveRecommendationSort,
  CognitiveRecommendationStatus,
} from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { RecommendationDetail } from '@/features/recommendations/RecommendationDetail'

const PAGE_SIZE = 50

function shortId(id: string) {
  return id.slice(0, 8)
}

export function StatusBadge({ status }: { status: CognitiveRecommendationStatus }) {
  if (status === 'accepted') {
    return (
      <Badge className="border-emerald-500/40 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200">
        Accepted
      </Badge>
    )
  }
  if (status === 'rejected') {
    return (
      <Badge className="border-red-500/40 bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200">
        Rejected
      </Badge>
    )
  }
  if (status === 'superseded') {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        Superseded
      </Badge>
    )
  }
  return <Badge variant="outline">Proposed</Badge>
}

export function RecommendationsPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState<CognitiveRecommendationStatus | ''>('')
  const [sort, setSort] = useState<CognitiveRecommendationSort>('proposed_at_desc')
  const [selected, setSelected] = useState<CognitiveRecommendation | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['recommendations', tenantId, { offset, status, sort }],
    queryFn: () =>
      fetchRecommendations(tenantId!, {
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
          <h1 className="text-xl font-semibold">Recommendations</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Proposed courses of action (Action · Propose). A recommendation is an
            offer, never a commitment: it states what to do, why, what is expected to
            happen, how confident the system is and what alternatives were considered —
            all advisory and reversible (P6: nothing is executed here). Each offer
            carries the calibrated confidence_score of its leading hypothesis (R4) and
            is fully traceable: hypothesis → confidence → evidence. Content is
            immutable (P1); only the status is lifecycle (proposed →
            accepted/rejected/superseded, decided by the Decision layer).
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
                setStatus(e.target.value as CognitiveRecommendationStatus | '')
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
              onChange={(e) => setSort(e.target.value as CognitiveRecommendationSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="proposed_at_desc">Newest first</option>
              <option value="proposed_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading recommendations…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view recommendations" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.recommendations.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No recommendations match the filters' : 'No recommendations yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Proposed offers appear here as soon as the formulator proposes actions over the tenant’s hypotheses and their calibrated confidence.'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Proposed at</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Action</th>
                  <th className="px-3 py-2 font-medium">Confidence</th>
                  <th className="px-3 py-2 font-medium">Consequences</th>
                  <th className="px-3 py-2 font-medium">Hypothesis</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.recommendations.map((recommendation) => (
                  <tr
                    key={recommendation.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(recommendation)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(recommendation.proposed_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={recommendation.status as CognitiveRecommendationStatus} />
                    </td>
                    <td className="max-w-xs px-3 py-2">{recommendation.action_description}</td>
                    <td className="px-3 py-2 tabular-nums">
                      {recommendation.confidence_score.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {recommendation.expected_consequences.length}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {shortId(recommendation.hypothesis_id)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Compass className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} recommendation{data.total === 1 ? '' : 's'} · page {page} of {totalPages.toLocaleString()}
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

      <RecommendationDetail recommendation={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default RecommendationsPage