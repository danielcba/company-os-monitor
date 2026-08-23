import { useQuery } from '@tanstack/react-query'
import { Gauge, X } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchConfidenceDetail } from '@/api/gateway'
import type {
  CognitiveConfidence,
  CognitiveDecision,
  CognitiveHypothesisDetail,
  CognitiveRecommendation,
} from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { Field } from '@/components/ui/field'

function TargetHypothesis({ target }: { target: CognitiveHypothesisDetail }) {
  const hypothesis = target.hypothesis
  return (
    <div className="space-y-3">
      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Judgment under evaluation
        </h4>
        <p className="rounded-md border border-border bg-muted/30 p-3 text-sm">
          {hypothesis.description}
        </p>
      </div>
      <div>
        <h4 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Source anomalies
        </h4>
        {target.anomalies.length === 0 ? (
          <EmptyState
            title="No anomalies resolved"
            description="The anomalies this judgment accounts for are not available in this tenant."
          />
        ) : (
          <ul className="space-y-2">
            {target.anomalies.map((anomaly) => {
              const context = target.contexts[anomaly.context_id]
              return (
                <li key={anomaly.id} className="rounded-md border border-border bg-muted/30 p-3 text-sm">
                  <div className="flex items-center justify-between gap-2">
                    <Badge variant="outline">{anomaly.anomaly_class}</Badge>
                    <span className="tabular-nums text-muted-foreground">
                      deviation {anomaly.deviation_score.toFixed(4)}
                    </span>
                  </div>
                  {context ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      context <span className="font-mono">{context.mental_model_id}</span> · {context.purpose}
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
    </div>
  )
}

function TargetDecision({ target }: { target: CognitiveDecision }) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 text-sm">
      <dl className="grid grid-cols-1 gap-2">
        <Field label="Commitment" value={target.commitment} />
        <Field label="Status" value={target.status} />
        <Field label="Risk tolerance" value={target.risk_tolerance} />
        <Field
          label="Authority id"
          value={<span className="font-mono text-xs">{target.authority_id}</span>}
        />
      </dl>
    </div>
  )
}

function TargetRecommendation({ target }: { target: CognitiveRecommendation }) {
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 text-sm">
      <dl className="grid grid-cols-1 gap-2">
        <Field label="Action" value={target.action_description} />
        <Field label="Rationale" value={target.rationale} />
        <Field label="Status" value={target.status} />
      </dl>
    </div>
  )
}

export function ConfidenceDetail({
  confidence,
  onClose,
}: {
  confidence: CognitiveConfidence | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['confidence-detail', tenantId, confidence?.id],
    queryFn: () => fetchConfidenceDetail(tenantId!, confidence!.id),
    enabled: Boolean(tenantId && confidence),
  })

  if (!confidence) return null
  const target = data?.target
  return (
    <div
      role="dialog"
      aria-label="Confidence detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Gauge className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Confidence detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            Confidence is a calibrated reliability estimate — computed, not intuited. It is
            an estimate of how much weight a judgment can carry, not &quot;the probability
            that the hypothesis is true&quot;. Every field was assigned at computation and
            is immutable (P1); a re-calibration with different inputs is a new row, never
            an update.
          </div>

          <dl className="grid grid-cols-2 gap-4">
            <Field
              label="Confidence score"
              value={<span className="tabular-nums text-base font-semibold">{confidence.confidence_score.toFixed(4)}</span>}
            />
            <Field
              label="Target type"
              value={<Badge variant="outline">{confidence.target_type}</Badge>}
            />
            <Field
              label="Evidential support S"
              value={<span className="tabular-nums">{confidence.evidential_support.toFixed(4)}</span>}
            />
            <Field
              label="Explanatory coherence C"
              value={<span className="tabular-nums">{confidence.explanatory_coherence.toFixed(4)}</span>}
            />
            <Field
              label="Calibration factor (1 − ECE)"
              value={<span className="tabular-nums">{confidence.historical_calibration.toFixed(4)}</span>}
            />
            <Field
              label="Calibration error estimate (ECE)"
              value={<span className="tabular-nums">{confidence.calibration_error_estimate.toFixed(4)}</span>}
            />
            <Field label="Mixing coefficient α" value={<span className="tabular-nums">{confidence.alpha.toFixed(2)}</span>} />
            <Field label="Computed at" value={new Date(confidence.computed_at).toLocaleString()} />
          </dl>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Calibration justification
            </h3>
            <p className="rounded-md border border-border bg-muted/30 p-3 text-sm">
              {confidence.calibration_justification}
            </p>
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Target judgment
            </h3>
            {isPending ? (
              <LoadingState label="Loading target…" />
            ) : isError ? (
              error instanceof Error && error instanceof ApiError && error.status === 403 ? (
                <ForbiddenState action="view this confidence" />
              ) : (
                <ErrorState message={error instanceof Error ? error.message : undefined} />
              )
            ) : !target ? (
              <EmptyState
                title="Target not resolved"
                description="The judgment this confidence evaluates is not available in this tenant."
              />
            ) : confidence.target_type === 'hypothesis' ? (
              <TargetHypothesis target={target as CognitiveHypothesisDetail} />
            ) : confidence.target_type === 'decision' ? (
              <TargetDecision target={target as CognitiveDecision} />
            ) : (
              <TargetRecommendation target={target as CognitiveRecommendation} />
            )}
          </div>

          <dl className="grid grid-cols-1 gap-2">
            <Field
              label="Confidence id"
              value={<span className="font-mono text-xs">{confidence.id}</span>}
            />
            <Field
              label="Tenant id"
              value={<span className="font-mono text-xs">{confidence.tenant_id}</span>}
            />
            <Field
              label="Target id"
              value={<span className="font-mono text-xs">{confidence.target_id}</span>}
            />
          </dl>
        </div>
      </div>
    </div>
  )
}