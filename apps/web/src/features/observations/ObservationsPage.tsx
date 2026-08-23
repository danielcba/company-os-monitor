import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Eye } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchObservations } from '@/api/gateway'
import type { Observation, ObservationSort, QualityClass } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { QualityClassBadge, QualityClassLegend } from '@/components/cognitive/QualityClassBadge'
import { ObservationDetail } from '@/features/observations/ObservationDetail'
import { formatValue } from '@/features/observations/format'

const PAGE_SIZE = 50

export function ObservationsPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [factType, setFactType] = useState('')
  const [sourceType, setSourceType] = useState('')
  const [qualityClass, setQualityClass] = useState<QualityClass | ''>('')
  const [sort, setSort] = useState<ObservationSort>('captured_at_desc')
  const [selected, setSelected] = useState<Observation | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['observations', tenantId, { offset, factType, sourceType, qualityClass, sort }],
    queryFn: () =>
      fetchObservations(tenantId!, {
        limit: PAGE_SIZE,
        offset,
        fact_type: factType || undefined,
        source_type: sourceType || undefined,
        quality_class: qualityClass,
        sort,
      }),
    enabled: Boolean(tenantId),
  })

  const applyFilter = () => {
    setOffset(0)
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1
  const hasFilters = Boolean(factType || sourceType || qualityClass)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Observations</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Raw, immutable facts captured from the infrastructure (append-only, P1). Each row is a
            measurement — never an interpretation. Quality class (Q1–Q4) was assigned at capture
            time and is never retrofitted.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      <QualityClassLegend />

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Fact type
            <select
              value={factType}
              onChange={(e) => {
                setFactType(e.target.value)
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.fact_types ?? []).map((ft) => (
                <option key={ft} value={ft}>
                  {ft}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Source type
            <select
              value={sourceType}
              onChange={(e) => {
                setSourceType(e.target.value)
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.source_types ?? []).map((st) => (
                <option key={st} value={st}>
                  {st}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Quality class
            <select
              value={qualityClass}
              onChange={(e) => {
                setQualityClass(e.target.value as QualityClass | '')
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.quality_classes ?? []).map((qc) => (
                <option key={qc} value={qc}>
                  {qc}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Order
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as ObservationSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="captured_at_desc">Newest first</option>
              <option value="captured_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading observations…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view observations" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.observations.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No observations match the filters' : 'No observations yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Observations appear here as soon as an agent captures infrastructure facts for this tenant.'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Captured at</th>
                  <th className="px-3 py-2 font-medium">Quality</th>
                  <th className="px-3 py-2 font-medium">Fact type</th>
                  <th className="px-3 py-2 font-medium">Fact value</th>
                  <th className="px-3 py-2 font-medium">Unit</th>
                  <th className="px-3 py-2 font-medium">Source</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.observations.map((observation) => (
                  <tr
                    key={observation.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(observation)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(observation.captured_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <QualityClassBadge qualityClass={observation.quality_class} />
                    </td>
                    <td className="px-3 py-2 font-medium">{observation.fact_type}</td>
                    <td className="max-w-[240px] truncate px-3 py-2 font-mono text-xs text-muted-foreground">
                      {formatValue(observation.fact_value)}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">{observation.unit}</td>
                    <td className="px-3 py-2 text-muted-foreground">{observation.source_type}</td>
                    <td className="px-3 py-2 text-right">
                      <Eye className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} observations · page {page} of {totalPages.toLocaleString()}
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

      <ObservationDetail observation={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default ObservationsPage