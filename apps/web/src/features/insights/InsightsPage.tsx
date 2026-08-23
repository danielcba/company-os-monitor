import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Lightbulb } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchInsights } from '@/api/gateway'
import { shortId } from '@/lib/utils'
import type {
  CognitiveInsight,
  CognitiveInsightSort,
} from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { InsightDetail } from '@/features/insights/InsightDetail'

const PAGE_SIZE = 50

export function InsightsPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [sort, setSort] = useState<CognitiveInsightSort>('generated_at_desc')
  const [selected, setSelected] = useState<CognitiveInsight | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['insights', tenantId, { offset, sort }],
    queryFn: () =>
      fetchInsights(tenantId!, {
        limit: PAGE_SIZE,
        offset,
        sort,
      }),
    enabled: Boolean(tenantId),
  })

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Insights</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Novel understandings that result from RESTRUCTURING the relationship
            between existing knowledge elements (Reasoning · Restructure). An
            Insight is not new information — it is a new organization of
            information that was already available. Content is immutable (P1) and
            there is no lifecycle status: an Insight is a journaled
            transformation, never updated and never deleted. "Insight cannot be
            forced or scheduled" — the Restructure capability only fires when a
            declarative rule detects that the current frame is competitive.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Order
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as CognitiveInsightSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="generated_at_desc">Newest first</option>
              <option value="generated_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading insights…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view insights" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.insights.length === 0 ? (
        <EmptyState
          title="No insights yet"
          description="Insights appear here as soon as the Restructure capability detects a competitive frame and journals a novel understanding over the existing hypotheses."
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Generated at</th>
                  <th className="px-3 py-2 font-medium">Context</th>
                  <th className="px-3 py-2 font-medium">Hypotheses</th>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.insights.map((insight) => (
                  <tr
                    key={insight.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(insight)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(insight.generated_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {shortId(insight.context_id)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {insight.hypothesis_ids.length}
                    </td>
                    <td className="max-w-[360px] truncate px-3 py-2 text-muted-foreground">
                      {insight.description}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Lightbulb className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} insight{data.total === 1 ? '' : 's'} · page {page} of {totalPages.toLocaleString()}
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

      <InsightDetail insight={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default InsightsPage
