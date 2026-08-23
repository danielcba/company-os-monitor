import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronLeft, ChevronRight, FileText } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchReports } from '@/api/gateway'
import type {
  CognitiveReport,
  CognitiveReportSort,
  CognitiveReportType,
} from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { ReportDetail } from '@/features/reports/ReportDetail'

const PAGE_SIZE = 50

export function ReportTypeBadge({ reportType }: { reportType: CognitiveReportType }) {
  if (reportType === 'technical') {
    return (
      <Badge className="border-blue-500/40 bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-200">
        Technical
      </Badge>
    )
  }
  if (reportType === 'json') {
    return (
      <Badge className="border-purple-500/40 bg-purple-100 text-purple-900 dark:bg-purple-900/40 dark:text-purple-200">
        JSON
      </Badge>
    )
  }
  if (reportType === 'compliance') {
    return (
      <Badge className="border-slate-500/40 bg-slate-100 text-slate-900 dark:bg-slate-900/40 dark:text-slate-200">
        Compliance
      </Badge>
    )
  }
  return <Badge variant="outline">Executive</Badge>
}

function periodLabel(report: CognitiveReport) {
  if (!report.period_start && !report.period_end) return '—'
  return `${report.period_start ?? '?'} → ${report.period_end ?? '?'}`
}

export function ReportsPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const [offset, setOffset] = useState(0)
  const [reportType, setReportType] = useState<CognitiveReportType | ''>('')
  const [sort, setSort] = useState<CognitiveReportSort>('generated_at_desc')
  const [selected, setSelected] = useState<CognitiveReport | null>(null)

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['reports', tenantId, { offset, reportType, sort }],
    queryFn: () =>
      fetchReports(tenantId!, {
        limit: PAGE_SIZE,
        offset,
        report_type: reportType || undefined,
        sort,
      }),
    enabled: Boolean(tenantId),
  })

  const applyFilter = () => {
    setOffset(0)
  }

  const totalPages = data ? Math.max(1, Math.ceil(data.total / data.limit)) : 1
  const page = data ? Math.floor(data.offset / data.limit) + 1 : 1
  const hasFilters = Boolean(reportType)

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Reports</h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Formatted output documents (Action · Output, external non-canonical,
            ADR-0002). The Report Generator only FORMATS what the canonical flow
            already committed — Decision(s), Recommendation(s), Confidence
            scores and the supporting trace — it never generates judgments. Each
            report is an append-only, immutable output artifact (its content
            trigger blocks any modification): a served report stays auditable.
            In this MVP reports are rendered by local templates
            (ai_generated = false, model_used = null); LM Studio arrives in a
            future sprint.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void refetch()}>
          Refresh
        </Button>
      </div>

      <Card className="p-3">
        <div className="flex flex-wrap items-end gap-3">
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Report type
            <select
              value={reportType}
              onChange={(e) => {
                setReportType(e.target.value as CognitiveReportType | '')
                applyFilter()
              }}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="">All</option>
              {(data?.facets.report_types ?? []).map((rt) => (
                <option key={rt} value={rt}>
                  {rt}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-xs text-muted-foreground">
            Order
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as CognitiveReportSort)}
              className="rounded border border-border bg-background px-2 py-1.5 text-sm text-foreground"
            >
              <option value="generated_at_desc">Newest first</option>
              <option value="generated_at_asc">Oldest first</option>
            </select>
          </label>
        </div>
      </Card>

      {isPending ? (
        <LoadingState label="Loading reports…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view reports" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.reports.length === 0 ? (
        <EmptyState
          title={hasFilters ? 'No reports match the filters' : 'No reports yet'}
          description={
            hasFilters
              ? 'Try clearing or changing the filters.'
              : 'Formatted documents appear here as soon as the Report Generator formats the tenant’s committed decisions and recommendations.'
          }
        />
      ) : (
        <>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[820px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">Generated at</th>
                  <th className="px-3 py-2 font-medium">Type</th>
                  <th className="px-3 py-2 font-medium">Title</th>
                  <th className="px-3 py-2 font-medium">Period</th>
                  <th className="px-3 py-2 font-medium">Generated</th>
                  <th className="px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {data.reports.map((report) => (
                  <tr
                    key={report.id}
                    className="cursor-pointer border-b border-border/60 last:border-0 hover:bg-muted/40"
                    onClick={() => setSelected(report)}
                  >
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {new Date(report.generated_at).toLocaleString()}
                    </td>
                    <td className="px-3 py-2">
                      <ReportTypeBadge reportType={report.report_type} />
                    </td>
                    <td className="max-w-xs px-3 py-2">{report.title}</td>
                    <td className="px-3 py-2 tabular-nums whitespace-nowrap text-muted-foreground">
                      {periodLabel(report)}
                    </td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {report.ai_generated ? 'LM Studio' : 'Local template'}
                    </td>
                    <td className="px-3 py-2 text-right">
                      <FileText className="ml-auto h-4 w-4 text-muted-foreground" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="flex flex-wrap items-center justify-between gap-3 text-sm text-muted-foreground">
            <p className="tabular-nums">
              {data.total.toLocaleString()} report{data.total === 1 ? '' : 's'} · page {page} of {totalPages.toLocaleString()}
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

      <ReportDetail report={selected} onClose={() => setSelected(null)} />
    </div>
  )
}

export default ReportsPage