import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Layers } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchEvidence } from '@/api/gateway'
import type { Evidence, EvidenceSort, QualityClass } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { QualityClassBadge, QualityClassLegend } from '@/components/cognitive/QualityClassBadge'
import { EvidenceDetail } from '@/features/evidence/EvidenceDetail'

const PAGE_SIZE = 50

export function EvidencePage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [organizationType, setOrganizationType] = useState('')
  const [qualityClass, setQualityClass] = useState<QualityClass | ''>('')
  const [sort, setSort] = useState<EvidenceSort>('organized_at_desc')
  const [selected, setSelected] = useState<Evidence | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['evidence', tenantId, { offset, organizationType, qualityClass, sort }],
    queryFn: () =>
      fetchEvidence(tenantId!, {
        limit: PAGE_SIZE,
        offset,
        organization_type: organizationType || undefined,
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
  const hasFilters = Boolean(organizationType || qualityClass)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Evidence</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Coherent organizations of observations (append-only, P1). Each row groups the facts
            that support a possible understanding — the description is objective, never an
            interpretation. Quality class and weight (wᵢ) were assigned at creation and are never
            retrofitted.
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
            Organization type
            <select
              value={organizationType}
              onChange={(e) => {
                setOrganizationType(e.target.value)
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.organization_types ?? []).map((ot) => (
                <option key={ot} value={ot}>
                  {ot}
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
              onChange={(e) => setSort(e.target.value as EvidenceSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="organized_at_desc">Newest first</option>
              <option value="organized_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading evidence…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view evidence" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.evidence.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No evidence matches the filters' : 'No evidence yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Evidence appears here as soon as the collector organizes observations for this tenant.'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Organized at</th>
                  <th className="px-3 py-2 font-medium">Quality</th>
                  <th className="px-3 py-2 font-medium">Organization type</th>
                  <th className="px-3 py-2 font-medium">Weight</th>
                  <th className="px-3 py-2 font-medium">Observations</th>
                  <th className="px-3 py-2 font-medium">Description</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.evidence.map((evidence) => (
                  <tr
                    key={evidence.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(evidence)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(evidence.organized_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <QualityClassBadge qualityClass={evidence.quality_class} />
                    </td>
                    <td className="px-3 py-2 font-medium">{evidence.organization_type}</td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {evidence.weight.toFixed(3)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {evidence.observation_ids.length}
                    </td>
                    <td className="max-w-[320px] truncate px-3 py-2 text-muted-foreground">
                      {evidence.description}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Layers className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} evidence · page {page} of {totalPages.toLocaleString()}
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

      <EvidenceDetail evidence={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default EvidencePage