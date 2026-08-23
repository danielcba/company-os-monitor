import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Repeat } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchPatterns } from '@/api/gateway'
import type { CognitivePattern, CognitivePatternSort } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { PatternDetail } from '@/features/patterns/PatternDetail'

const PAGE_SIZE = 50

function StatusBadge({ isActive }: { isActive: boolean }) {
  return isActive ? (
    <Badge className="border-emerald-500/40 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200">
      Active
    </Badge>
  ) : (
    <Badge variant="outline" className="text-muted-foreground">
      Superseded
    </Badge>
  )
}

function shortId(id: string) {
  return id.slice(0, 8)
}

export function PatternsPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [patternType, setPatternType] = useState('')
  const [isActive, setIsActive] = useState('')
  const [sort, setSort] = useState<CognitivePatternSort>('detected_at_desc')
  const [selected, setSelected] = useState<CognitivePattern | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['patterns', tenantId, { offset, patternType, isActive, sort }],
    queryFn: () =>
      fetchPatterns(tenantId!, {
        limit: PAGE_SIZE,
        offset,
        pattern_type: patternType || undefined,
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
  const hasFilters = Boolean(patternType || isActive)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Patterns</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Recurring structures detected within Active Contexts (Reasoning · Generalize).
            A Pattern describes regular structure — a Hypothesis proposes its cause (P4).
            Regularity is shown here with the support measured at detection; causal
            explanations never appear on this view. Content is immutable once detected
            (P1); only the active lifecycle flag may change.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Pattern type
            <select
              value={patternType}
              onChange={(e) => {
                setPatternType(e.target.value)
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.pattern_types ?? []).map((t) => (
                <option key={t} value={t}>
                  {t}
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
              <option value="false">Superseded</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Order
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as CognitivePatternSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="detected_at_desc">Newest first</option>
              <option value="detected_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading patterns…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view patterns" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.patterns.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No patterns match the filters' : 'No patterns yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Patterns appear here as soon as the detector measures sufficient support for a recurring structure over this tenant’s context stream.'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Detected at</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="px-3 py-2 font-medium">Pattern type</th>
                  <th className="px-3 py-2 font-medium">Frequency</th>
                  <th className="px-3 py-2 font-medium">Strength</th>
                  <th className="px-3 py-2 font-medium">Context</th>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.patterns.map((pattern) => (
                  <tr
                    key={pattern.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(pattern)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(pattern.detected_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <StatusBadge isActive={pattern.is_active} />
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant="outline">{pattern.pattern_type}</Badge>
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{pattern.frequency ?? '—'}</td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {pattern.strength_measure.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {shortId(pattern.context_id)}
                    </td>
                    <td className="max-w-[320px] truncate px-3 py-2 text-muted-foreground">
                      {pattern.description}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Repeat className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} patterns · page {page} of {totalPages.toLocaleString()}
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

      <PatternDetail pattern={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default PatternsPage