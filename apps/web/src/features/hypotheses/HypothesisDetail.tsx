import { useQuery } from '@tanstack/react-query'
import { Brain, X } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchHypothesisDetail } from '@/api/gateway'
import type { CognitiveHypothesis } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { StatusBadge } from '@/features/hypotheses/HypothesesPage'
import { Field } from '@/components/ui/field'

export function HypothesisDetail({
  hypothesis,
  onClose,
}: {
  hypothesis: CognitiveHypothesis | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['hypothesis-detail', tenantId, hypothesis?.id],
    queryFn: () => fetchHypothesisDetail(tenantId!, hypothesis!.id),
    enabled: Boolean(tenantId && hypothesis),
  })

  if (!hypothesis) return null
  const anomalies = data?.anomalies ?? []
  const contexts = data?.contexts ?? {}
  return (
    <div
      role="dialog"
      aria-label="Hypothesis detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Brain className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Hypothesis detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            A hypothesis is a tentative, testable explanation of an anomaly (Reasoning ·
            Predict). It pairs an explanation with observable predicted consequences and
            a concrete falsification criterion. Content is immutable once generated (P1);
            only the status lifecycle field may change — confirmation or falsification
            requires future evidence + Confidence.
          </div>

          <dl className="grid grid-cols-2 gap-4">
            <Field
              label="Status"
              value={<StatusBadge status={hypothesis.status} />}
            />
            <Field
              label="Coherence score"
              value={<span className="tabular-nums">{hypothesis.coherence_score.toFixed(2)}</span>}
            />
            <Field label="Generated at" value={new Date(hypothesis.generated_at).toLocaleString()} />
            <Field
              label="Source anomalies"
              value={<span className="tabular-nums">{hypothesis.anomaly_ids.length}</span>}
            />
          </dl>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Explanation
            </h3>
            <p className="rounded-md border border-border bg-muted/30 p-3 text-sm">
              {hypothesis.description}
            </p>
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Predicted consequences
            </h3>
            <ul className="space-y-1">
              {hypothesis.predicted_consequences.length === 0 ? (
                <li className="text-sm text-muted-foreground">—</li>
              ) : (
                hypothesis.predicted_consequences.map((c, i) => (
                  <li key={i} className="flex gap-2 text-sm">
                    <span className="text-muted-foreground">·</span>
                    {c}
                  </li>
                ))
              )}
            </ul>
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Falsification criterion
            </h3>
            <p className="rounded-md border border-border bg-muted/30 p-3 text-sm">
              {hypothesis.falsification_criterion}
            </p>
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Source anomalies
            </h3>
            {isPending ? (
              <LoadingState label="Loading anomalies…" />
            ) : isError ? (
              error instanceof Error && error instanceof ApiError && error.status === 403 ? (
                <ForbiddenState action="view this hypothesis" />
              ) : (
                <ErrorState message={error instanceof Error ? error.message : undefined} />
              )
            ) : anomalies.length === 0 ? (
              <EmptyState
                title="No anomalies resolved"
                description="The anomalies this hypothesis accounts for are not available in this tenant."
              />
            ) : (
              <ul className="space-y-2">
                {anomalies.map((anomaly) => {
                  const context = contexts[anomaly.context_id]
                  return (
                    <li key={anomaly.id} className="rounded-md border border-border bg-muted/30 p-3 text-sm">
                      <div className="flex items-center justify-between gap-2">
                        <Badge variant="outline">{anomaly.anomaly_class}</Badge>
                        <span className="tabular-nums text-muted-foreground">
                          deviation {anomaly.deviation_score.toFixed(4)}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        detected {new Date(anomaly.detected_at).toLocaleString()}
                      </p>
                      {context ? (
                        <p className="mt-1 flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
                          <span>context</span>
                          <span className="font-mono">{context.mental_model_id}</span>
                          <span>·</span>
                          <span>{context.purpose}</span>
                        </p>
                      ) : (
                        <p className="mt-1 text-xs text-muted-foreground">context not resolved</p>
                      )}
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          <dl className="grid grid-cols-1 gap-2">
            <Field
              label="Hypothesis id"
              value={<span className="font-mono text-xs">{hypothesis.id}</span>}
            />
            <Field
              label="Tenant id"
              value={<span className="font-mono text-xs">{hypothesis.tenant_id}</span>}
            />
            <Field
              label="Anomaly ids"
              value={
                hypothesis.anomaly_ids.length ? (
                  <span className="font-mono text-xs">{hypothesis.anomaly_ids.join(', ')}</span>
                ) : (
                  '—'
                )
              }
            />
          </dl>
        </div>
      </div>
    </div>
  )
}