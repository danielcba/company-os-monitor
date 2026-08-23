import { useQuery } from '@tanstack/react-query'
import { Radar, X } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchAnomalyDetail } from '@/api/gateway'
import type { CognitiveAnomaly } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { Field } from '@/components/ui/field'

export function AnomalyDetail({
  anomaly,
  onClose,
}: {
  anomaly: CognitiveAnomaly | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['anomaly-detail', tenantId, anomaly?.id],
    queryFn: () => fetchAnomalyDetail(tenantId!, anomaly!.id),
    enabled: Boolean(tenantId && anomaly),
  })

  if (!anomaly) return null
  const context = data?.context
  return (
    <div
      role="dialog"
      aria-label="Anomaly detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Radar className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Anomaly detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            An anomaly is a quantified deviation from a pattern: it occurs when the
            deviation_score exceeds the tolerance_threshold. It is shown with the measured
            deviation — causal explanations never appear here (they belong to Hypothesis,
            P4). The score and threshold were assigned at detection and are immutable (P1);
            an anomaly has no lifecycle flag.
          </div>

          <dl className="grid grid-cols-2 gap-4">
            <Field
              label="Anomaly class"
              value={<Badge variant="outline">{anomaly.anomaly_class}</Badge>}
            />
            <Field
              label="Deviation score"
              value={<span className="tabular-nums">{anomaly.deviation_score.toFixed(4)}</span>}
            />
            <Field
              label="Tolerance threshold"
              value={<span className="tabular-nums">{anomaly.tolerance_threshold.toFixed(4)}</span>}
            />
            <Field label="Detected at" value={new Date(anomaly.detected_at).toLocaleString()} />
            <Field
              label="Source pattern"
              value={
                anomaly.pattern_id ? (
                  <span className="font-mono text-xs">{anomaly.pattern_id}</span>
                ) : (
                  '—'
                )
              }
            />
          </dl>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Source context
            </h3>
            {isPending ? (
              <LoadingState label="Loading context…" />
            ) : isError ? (
              error instanceof Error && error instanceof ApiError && error.status === 403 ? (
                <ForbiddenState action="view this anomaly" />
              ) : (
                <ErrorState message={error instanceof Error ? error.message : undefined} />
              )
            ) : !context ? (
              <EmptyState
                title="No context resolved"
                description="The Active Context this deviation was detected over is not available in this tenant."
              />
            ) : (
              <div className="rounded-md border border-border bg-muted/30 p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs">{context.mental_model_id}</span>
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{context.purpose}</p>
                <dl className="mt-2 grid grid-cols-2 gap-2">
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      Coherence
                    </dt>
                    <dd className="tabular-nums">{context.coherence_score.toFixed(2)}</dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      Competing models
                    </dt>
                    <dd className="tabular-nums">{context.competing_models.length}</dd>
                  </div>
                </dl>
              </div>
            )}
          </div>

          <dl className="grid grid-cols-1 gap-2">
            <Field label="Anomaly id" value={<span className="font-mono text-xs">{anomaly.id}</span>} />
            <Field label="Tenant id" value={<span className="font-mono text-xs">{anomaly.tenant_id}</span>} />
            <Field label="Context id" value={<span className="font-mono text-xs">{anomaly.context_id}</span>} />
          </dl>
        </div>
      </div>
    </div>
  )
}