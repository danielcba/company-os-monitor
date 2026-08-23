import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, GitCommitHorizontal } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchDecisions } from '@/api/gateway'
import type {
  CognitiveDecision,
  CognitiveDecisionSort,
  CognitiveDecisionStatus,
} from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { DecisionDetail } from '@/features/decisions/DecisionDetail'

const PAGE_SIZE = 50

function shortId(id: string) {
  return id.slice(0, 8)
}

export function StatusBadge({ status }: { status: CognitiveDecisionStatus }) {
  if (status === 'completed') {
    return (
      <Badge className="border-emerald-500/40 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200">
        Completed
      </Badge>
    )
  }
  if (status === 'executing') {
    return (
      <Badge className="border-amber-500/40 bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
        Executing
      </Badge>
    )
  }
  if (status === 'rolled_back') {
    return (
      <Badge variant="outline" className="text-muted-foreground">
        Rolled back
      </Badge>
    )
  }
  return <Badge variant="outline">Committed</Badge>
}

export function RiskBadge({ risk }: { risk: string }) {
  if (risk === 'high') {
    return (
      <Badge className="border-red-500/40 bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200">
        High
      </Badge>
    )
  }
  if (risk === 'medium') {
    return (
      <Badge className="border-amber-500/40 bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200">
        Medium
      </Badge>
    )
  }
  return <Badge variant="outline">Low</Badge>
}

export function DecisionsPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [status, setStatus] = useState<CognitiveDecisionStatus | ''>('')
  const [sort, setSort] = useState<CognitiveDecisionSort>('committed_at_desc')
  const [selected, setSelected] = useState<CognitiveDecision | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['decisions', tenantId, { offset, status, sort }],
    queryFn: () =>
      fetchDecisions(tenantId!, {
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
          <h1 className="text-xl font-semibold">Decisions</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Committed courses of action (Action · Commit). A decision is a
            commitment with an owner, a timeline and expected outcomes — it
            ends deliberation, it does not end learning. Each commitment
            records the definitive course of action, its falsifiable expected
            outcomes (prediction + verifiable_by + deadline, stated BEFORE
            execution), the authority under which it was taken, the declared
            risk tolerance and the calibrated Confidence that supported it
            (R4). Content is immutable (P1); only the status is lifecycle
            (committed → executing/completed/rolled_back, decided by the
            Learning loop). In this MVP decisions are recorded, never executed
            (P6).
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
                setStatus(e.target.value as CognitiveDecisionStatus | '')
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
              onChange={(e) => setSort(e.target.value as CognitiveDecisionSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="committed_at_desc">Newest first</option>
              <option value="committed_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading decisions…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view decisions" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.decisions.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No decisions match the filters' : 'No decisions yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Committed decisions appear here as soon as the Decision layer commits a recommendation over the tenant’s calibrated confidence.'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Committed at</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Commitment</th>
                  <th className="px-3 py-2 font-medium">Risk</th>
                  <th className="px-3 py-2 font-medium">Outcomes</th>
                  <th className="px-3 py-2 font-medium">Recommendation</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.decisions.map((decision) => (
                  <tr
                    key={decision.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(decision)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(decision.committed_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge status={decision.status as CognitiveDecisionStatus} />
                    </td>
                    <td className="max-w-xs px-3 py-2">{decision.commitment}</td>
                    <td className="px-3 py-2">
                      <RiskBadge risk={decision.risk_tolerance} />
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {decision.expected_outcomes.length}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {shortId(decision.recommendation_id)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <GitCommitHorizontal className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} decision{data.total === 1 ? '' : 's'} · page {page} of {totalPages.toLocaleString()}
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

      <DecisionDetail decision={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default DecisionsPage