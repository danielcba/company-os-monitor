import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Radar } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchContexts } from '@/api/gateway'
import type { CognitiveContext, CognitiveContextSort } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { ContextDetail } from '@/features/contexts/ContextDetail'

const PAGE_SIZE = 50

function StatusBadge({ isActive }: { isActive: boolean }) {
  return isActive ? (
    <Badge className="border-emerald-500/40 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200">
      Active
    </Badge>
  ) : (
    <Badge variant="outline" className="text-muted-foreground">
      Inactive
    </Badge>
  )
}

export function ContextsPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [purpose, setPurpose] = useState('')
  const [mentalModelId, setMentalModelId] = useState('')
  const [isActive, setIsActive] = useState('')
  const [sort, setSort] = useState<CognitiveContextSort>('activated_at_desc')
  const [selected, setSelected] = useState<CognitiveContext | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['contexts', tenantId, { offset, purpose, mentalModelId, isActive, sort }],
    queryFn: () =>
      fetchContexts(tenantId!, {
        limit: PAGE_SIZE,
        offset,
        purpose: purpose || undefined,
        mental_model_id: mentalModelId || undefined,
        is_active: isActive || undefined,
        sort,
      }),
    enabled: Boolean(tenantId),
  })

  const applyFilter = () => {
    setOffset(0)
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1
  const hasFilters = Boolean(purpose || mentalModelId || isActive)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Contexts</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Active interpretations selected by explanatory coherence among competing mental
            models (P2). Each row is an activation: the winning model, its coherence score and
            the alternatives it competed against. Content is immutable once activated (P1); only
            the active lifecycle flag may change.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Purpose
            <select
              value={purpose}
              onChange={(e) => {
                setPurpose(e.target.value)
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.purposes ?? []).map((p) => (
                <option key={p} value={p}>
                  {p}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Mental model
            <select
              value={mentalModelId}
              onChange={(e) => {
                setMentalModelId(e.target.value)
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.mental_model_ids ?? []).map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Status
            <select
              value={isActive}
              onChange={(e) => {
                setIsActive(e.target.value)
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              <option value="true">Active</option>
              <option value="false">Inactive</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Order
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as CognitiveContextSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="activated_at_desc">Newest first</option>
              <option value="activated_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading contexts…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view contexts" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.contexts.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No contexts match the filters' : 'No contexts yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Contexts appear here as soon as an activation selects the most coherent mental model for this tenant.'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Activated at</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Purpose</th>
                  <th className="px-3 py-2 font-medium">Mental model</th>
                  <th className="px-3 py-2 font-medium">Coherence</th>
                  <th className="px-3 py-2 font-medium">Evidence</th>
                  <th className="px-3 py-2 font-medium">Models</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.contexts.map((context) => (
                  <tr
                    key={context.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(context)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(context.activated_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge isActive={context.is_active} />
                    </td>
                    <td className="px-3 py-2 font-medium">{context.purpose}</td>
                    <td className="px-3 py-2 font-mono text-xs">{context.mental_model_id}</td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {context.coherence_score.toFixed(2)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {context.evidence_ids.length}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {context.competing_models.length}
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
              {data.total.toLocaleString()} contexts · page {page} of {totalPages.toLocaleString()}
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

      <ContextDetail context={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default ContextsPage