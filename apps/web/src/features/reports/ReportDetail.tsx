import { useQuery } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { FileText, X, GitBranch } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchReportDetail } from '@/api/gateway'
import type { CognitiveReport, CognitiveReportDetail } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { ReportTypeBadge } from '@/features/reports/ReportsPage'
import { Field } from '@/components/ui/field'

function formatValue(value: unknown): string {
  if (typeof value === 'number') return value.toLocaleString()
  if (typeof value === 'boolean') return String(value)
  if (value === null || value === undefined) return 'null'
  return String(value)
}

function ContentTree({ value }: { value: unknown }) {
  if (Array.isArray(value)) {
    return (
      <ul className="space-y-1">
        {value.length === 0 ? (
          <li className="text-xs text-muted-foreground">empty</li>
        ) : (
          value.map((item, index) => (
            <li key={index} className="rounded-md border border-border bg-muted/30 p-2">
              <ContentTree value={item} />
            </li>
          ))
        )}
      </ul>
    )
  }
  if (typeof value === 'object' && value !== null) {
    const entries = Object.entries(value as Record<string, unknown>)
    return (
      <dl className="space-y-1">
        {entries.map(([key, val]) => (
          <div key={key} className="rounded-md border border-border/60 bg-background/40 p-2">
            <dt className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              {key}
            </dt>
            <dd className="mt-0.5 text-sm">
              {typeof val === 'object' && val !== null ? (
                <ContentTree value={val} />
              ) : (
                <span className="tabular-nums">{formatValue(val)}</span>
              )}
            </dd>
          </div>
        ))}
      </dl>
    )
  }
  return <span className="tabular-nums">{formatValue(value)}</span>
}

function ContentBlock({ detail }: { detail: CognitiveReportDetail | null }) {
  if (!detail) {
    return (
      <EmptyState
        title="Report not resolved"
        description="The rendered report content is not available in this tenant."
      />
    )
  }
  const report = detail.report
  const decisionCount = (report.content as Record<string, unknown>)['decision_count']
  return (
    <div className="space-y-3">
      <dl className="grid grid-cols-2 gap-3">
        <Field
          label="Report type"
          value={<ReportTypeBadge reportType={report.report_type} />}
        />
        <Field
          label="Generated"
          value={
            <span className="tabular-nums text-muted-foreground">
              {new Date(report.generated_at).toLocaleString()}
            </span>
          }
        />
        <Field label="Period" value={periodLabel(report)} />
        <Field label="File" value={<span className="break-all font-mono text-xs">{report.file_path ?? '—'}</span>} />
      </dl>
      <Field label="Summary" value={report.summary ?? '—'} />
      {typeof decisionCount === 'number' ? (
        <Field
          label="Decision count"
          value={<span className="tabular-nums font-semibold">{decisionCount}</span>}
        />
      ) : null}
      <h3 className="pt-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Rendered content
      </h3>
      <ContentTree value={report.content} />
    </div>
  )
}

function periodLabel(report: CognitiveReport) {
  if (!report.period_start && !report.period_end) return '—'
  return `${report.period_start ?? '?'} → ${report.period_end ?? '?'}`
}

export function ReportDetail({
  report,
  onClose,
}: {
  report: CognitiveReport | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const tenantId = user?.tenant_id
  const navigate = useNavigate()

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['report-detail', tenantId, report?.id],
    queryFn: () => fetchReportDetail(tenantId!, report!.id),
    enabled: Boolean(tenantId && report),
  })

  if (!report) return null
  return (
    <div
      role="dialog"
      aria-label="Report detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-xl flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <FileText className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Report detail</h2>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              onClose()
              navigate(`/action/reports/${report.id}/trace`)
            }}
          >
            <GitBranch className="h-4 w-4" /> Cognitive trace
          </Button>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            A report is a formatted output document (external non-canonical,
            ADR-0002): it only FORMATS what the canonical flow already committed
            — it never generates judgments. This document is append-only and
            immutable (its content trigger blocks any modification): a served
            report stays auditable and is never retroactively changed. In this
            MVP it was rendered by local templates (ai_generated = false);
            LM Studio arrives in a future sprint.
          </div>

          <div className="flex items-center gap-2">
            <span className="font-semibold">{report.title}</span>
            <ReportTypeBadge reportType={report.report_type} />
          </div>

          {data?.tenant ? (
            <Field
              label="Tenant"
              value={`${data.tenant.name} (${data.tenant.slug})`}
            />
          ) : null}

          {isPending ? (
            <LoadingState label="Loading report…" />
          ) : isError ? (
            error instanceof Error && error instanceof ApiError && error.status === 403 ? (
              <ForbiddenState action="view this report" />
            ) : (
              <ErrorState message={error instanceof Error ? error.message : undefined} />
            )
          ) : (
            <ContentBlock detail={data ?? null} />
          )}

          <dl className="grid grid-cols-1 gap-2">
            <Field
              label="Report id"
              value={<span className="font-mono text-xs">{report.id}</span>}
            />
            <Field
              label="Tenant id"
              value={<span className="font-mono text-xs">{report.tenant_id}</span>}
            />
            <Field
              label="AI generated"
              value={report.ai_generated ? 'yes' : 'no'}
            />
            <Field label="Model used" value={report.model_used ?? '—'} />
          </dl>
        </div>
      </div>
    </div>
  )
}