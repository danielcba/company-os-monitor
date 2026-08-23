import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, Gauge, Target, TrendingUp } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchConfidence, fetchConfidenceSummary } from '@/api/gateway'
import type {
  CognitiveConfidence,
  CognitiveConfidenceSort,
  CognitiveConfidenceSummary,
  CognitiveConfidenceTargetType,
} from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { ConfidenceDetail } from '@/features/confidence/ConfidenceDetail'

const PAGE_SIZE = 50

function shortId(id: string) {
  return id.slice(0, 8)
}

function SummaryStat({
  label,
  value,
  icon,
}: {
  label: string
  value: string
  icon: React.ReactNode
}) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3">
      <div className="flex items-center gap-1.5 text-xs uppercase tracking-wide text-muted-foreground">
        {icon}
        {label}
      </div>
      <p className="mt-1 tabular-nums text-lg font-semibold">{value}</p>
    </div>
  )
}

function ConfidenceSummaryBlock({
  summary,
}: {
  summary: CognitiveConfidenceSummary
}) {
  const a = summary.averages
  return (
    <div className="space-y-3">
      <div className="grid grid-cols-2 gap-3 md:grid-cols-5">
        <SummaryStat
          label="Calibrated rows"
          value={summary.total.toLocaleString()}
          icon={<Gauge className="h-3.5 w-3.5" />}
        />
        <SummaryStat
          label="Avg C_final"
          value={a.confidence.toFixed(4)}
          icon={<TrendingUp className="h-3.5 w-3.5" />}
        />
        <SummaryStat
          label="Avg support S"
          value={a.support.toFixed(4)}
          icon={<Target className="h-3.5 w-3.5" />}
        />
        <SummaryStat
          label="Avg coherence C"
          value={a.coherence.toFixed(4)}
          icon={<Target className="h-3.5 w-3.5" />}
        />
        <SummaryStat
          label="Avg 1 − ECE"
          value={a.historical_calibration.toFixed(4)}
          icon={<TrendingUp className="h-3.5 w-3.5" />}
        />
      </div>
      <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
        <span className="font-semibold uppercase tracking-wide">Target types</span>
        {Object.entries(summary.by_target_type).map(([type, n]) => (
          <span
            key={type}
            className="rounded-full border border-border bg-background px-2 py-0.5 tabular-nums"
          >
            {type}: {n}
          </span>
        ))}
        <span className="ml-auto tabular-nums">
          range C_final {summary.range.min_confidence.toFixed(4)} –{' '}
          {summary.range.max_confidence.toFixed(4)} · avg ECE {a.ece.toFixed(4)} ·
          alpha {a.alpha.toFixed(2)}
        </span>
      </div>
    </div>
  )
}

export function ConfidencePage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [targetType, setTargetType] = useState<CognitiveConfidenceTargetType | ''>('')
  const [sort, setSort] = useState<CognitiveConfidenceSort>('computed_at_desc')
  const [selected, setSelected] = useState<CognitiveConfidence | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['confidence', tenantId, { offset, targetType, sort }],
    queryFn: () =>
      fetchConfidence(tenantId!, {
        limit: PAGE_SIZE,
        offset,
        target_type: targetType || undefined,
        sort,
      }),
    enabled: Boolean(tenantId),
  })

  const summaryQuery = useQuery({
    queryKey: ['confidence-summary', tenantId],
    queryFn: () => fetchConfidenceSummary(tenantId!),
    enabled: Boolean(tenantId),
  })

  const applyFilter = () => {
    setOffset(0)
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1
  const hasFilters = Boolean(targetType)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Confidence</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Calibrated reliability estimates of the pipeline&apos;s judgments (Learning ·
            Calibrate). Confidence is computed, not intuited: each row records C_final
            with its first-class justification — evidential support S(H|E), explanatory
            coherence C(H), the calibration factor (1 − ECE), α and M. A confidence score
            is a calibrated estimate of reliability, not &quot;the probability that the
            hypothesis is true&quot;. Content is immutable once computed (P1); a
            re-calibration with different inputs is a new row, never an update.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Target type
            <select
              value={targetType}
              onChange={(e) => {
                setTargetType(e.target.value as CognitiveConfidenceTargetType | '')
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.target_types ?? []).map((t) => (
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
              onChange={(e) => setSort(e.target.value as CognitiveConfidenceSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="computed_at_desc">Newest first</option>
              <option value="computed_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {summaryQuery.isPending ? (
        <p className="text-xs text-muted-foreground">
          Computing calibration summary…
        </p>
      ) : summaryQuery.isError ? (
        <p className="text-xs text-muted-foreground">
          Calibration summary unavailable ({summaryQuery.error instanceof Error ? summaryQuery.error.message : 'error'}).
        </p>
      ) : summaryQuery.data && summaryQuery.data.total > 0 ? (
        <Card className="p-4">
          <h2 className="mb-3 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
            Calibration state
          </h2>
          <ConfidenceSummaryBlock summary={summaryQuery.data} />
        </Card>
      ) : null}

      {isPending ? (
        <LoadingState label="Loading confidence…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view confidence" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.confidence.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No confidence rows match the filters' : 'No confidence yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Confidence rows appear here as soon as the calibrator computes C_final for this tenant’s judgments (hypotheses first).'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Computed at</th>
                  <th className="px-3 py-2 font-medium">Target type</th>
                  <th className="px-3 py-2 font-medium">Confidence</th>
                  <th className="px-3 py-2 font-medium">Support S</th>
                  <th className="px-3 py-2 font-medium">Coherence C</th>
                  <th className="px-3 py-2 font-medium">ECE</th>
                  <th className="px-3 py-2 font-medium">Target</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.confidence.map((confidence) => (
                  <tr
                    key={confidence.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(confidence)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(confidence.computed_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <Badge variant="outline">{confidence.target_type}</Badge>
                    </td>
                    <td className="px-3 py-2 tabular-nums">
                      {confidence.confidence_score.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {confidence.evidential_support.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {confidence.explanatory_coherence.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 tabular-nums text-muted-foreground">
                      {confidence.calibration_error_estimate.toFixed(4)}
                    </td>
                    <td className="px-3 py-2 font-mono text-xs text-muted-foreground">
                      {shortId(confidence.target_id)}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <Gauge className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} confidence {data.total === 1 ? 'row' : 'rows'} · page {page} of {totalPages.toLocaleString()}
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

      <ConfidenceDetail confidence={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default ConfidencePage