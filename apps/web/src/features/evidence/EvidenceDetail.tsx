import { useQuery } from '@tanstack/react-query'
import { Layers, X } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchEvidenceDetail } from '@/api/gateway'
import type { Evidence } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { QualityClassBadge } from '@/components/cognitive/QualityClassBadge'
import { formatValue, formatJson } from '@/features/observations/format'
import { Field } from '@/components/ui/field'

export function EvidenceDetail({
  evidence,
  onClose,
}: {
  evidence: Evidence | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['evidence-detail', tenantId, evidence?.id],
    queryFn: () => fetchEvidenceDetail(tenantId!, evidence!.id),
    enabled: Boolean(tenantId && evidence),
  })

  if (!evidence) return null
  return (
    <div
      role="dialog"
      aria-label="Evidence detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Layers className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Evidence detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            Evidence organizes facts — it does not explain them. The description is objective and
            the weight (wᵢ) was assigned at creation from the quality class, never retrofitted. The
            rows below are the observations this evidence organized (P1).
          </div>

          <dl className="grid grid-cols-2 gap-4">
            <Field label="Organization type" value={evidence.organization_type} />
            <Field
              label="Quality class"
              value={<QualityClassBadge qualityClass={evidence.quality_class} />}
            />
            <Field label="Weight (wᵢ)" value={<span className="tabular-nums">{evidence.weight.toFixed(3)}</span>} />
            <Field label="Organized at" value={new Date(evidence.organized_at).toLocaleString()} />
            <Field
              label="Observations organized"
              value={<span className="tabular-nums">{evidence.observation_ids.length}</span>}
            />
          </dl>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Description
            </h3>
            <p className="rounded-md border border-border bg-muted/30 p-3 text-sm">
              {evidence.description}
            </p>
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Organized observations
            </h3>
            {isPending ? (
              <LoadingState label="Loading observations…" />
            ) : isError ? (
              error instanceof Error && error instanceof ApiError && error.status === 403 ? (
                <ForbiddenState action="view this evidence" />
              ) : (
                <ErrorState message={error instanceof Error ? error.message : undefined} />
              )
            ) : !data || (data.observations ?? []).length === 0 ? (
              <EmptyState
                title="No observations resolved"
                description="The observations this evidence organizes are not available in this tenant."
              />
            ) : (
              <ul className="space-y-2">
                {data.observations.map((observation) => (
                  <li
                    key={observation.id}
                    className="rounded-md border border-border bg-muted/30 p-3 text-sm"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs text-muted-foreground">
                        {new Date(observation.captured_at).toLocaleString()}
                      </span>
                      <QualityClassBadge qualityClass={observation.quality_class} />
                    </div>
                    <div className="mt-1.5 flex items-baseline justify-between gap-2">
                      <span className="font-medium">{observation.fact_type}</span>
                      <span className="font-mono text-xs text-muted-foreground">
                        {formatValue(observation.fact_value)}
                        {observation.unit ? ` ${observation.unit}` : ''}
                      </span>
                    </div>
                    <p className="mt-1 truncate font-mono text-xs text-muted-foreground">
                      {formatJson(observation.raw_payload)}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <dl className="grid grid-cols-1 gap-2">
            <Field label="Evidence id" value={<span className="font-mono text-xs">{evidence.id}</span>} />
            <Field label="Tenant id" value={<span className="font-mono text-xs">{evidence.tenant_id}</span>} />
          </dl>
        </div>
      </div>
    </div>
  )
}