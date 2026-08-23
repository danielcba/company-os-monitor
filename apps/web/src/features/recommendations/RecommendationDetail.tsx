import { useQuery } from '@tanstack/react-query'
import { Compass, X } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchRecommendationDetail } from '@/api/gateway'
import type {
  CognitiveConfidenceDetail,
  CognitiveHypothesisDetail,
  CognitiveRecommendation,
  CognitiveRecommendationStatus,
} from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { StatusBadge } from '@/features/recommendations/RecommendationsPage'

function shortId(id: string) {
  return id.slice(0, 8)
}

function ConfidenceBlock({ confidence }: { confidence: CognitiveConfidenceDetail | null }) {
  if (!confidence) {
    return (
      <EmptyState
        title="Confidence not resolved"
        description="The calibrated confidence that supports this offer is not available in this tenant."
      />
    )
  }
  const row = confidence.confidence
  return (
    <div className="space-y-2">
      <div className="rounded-md border border-border bg-muted/30 p-3 text-sm">
        <dl className="grid grid-cols-2 gap-3">
          <Field
            label="Confidence score"
            value={<span className="tabular-nums font-semibold">{row.confidence_score.toFixed(4)}</span>}
          />
          <Field
            label="Support S"
            value={<span className="tabular-nums">{row.evidential_support.toFixed(4)}</span>}
          />
          <Field
            label="Coherence C"
            value={<span className="tabular-nums">{row.explanatory_coherence.toFixed(4)}</span>}
          />
          <Field
            label="Calibration factor (1 − ECE)"
            value={<span className="tabular-nums">{row.historical_calibration.toFixed(4)}</span>}
          />
        </dl>
      </div>
      <p className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
        {row.calibration_justification}
      </p>
    </div>
  )
}

function HypothesisBlock({ hypothesis }: { hypothesis: CognitiveHypothesisDetail | null }) {
  if (!hypothesis) {
    return (
      <EmptyState
        title="Hypothesis not resolved"
        description="The leading hypothesis of this offer is not available in this tenant."
      />
    )
  }
  return (
    <div className="space-y-2">
      <div className="rounded-md border border-border bg-muted/30 p-3 text-sm">
        <div className="mb-1 flex items-center gap-2">
          <Badge variant="outline">{hypothesis.hypothesis.status}</Badge>
          <span className="tabular-nums text-xs text-muted-foreground">
            coherence {hypothesis.hypothesis.coherence_score.toFixed(2)}
          </span>
        </div>
        <p>{hypothesis.hypothesis.description}</p>
      </div>
      <ul className="space-y-1">
        {hypothesis.anomalies.map((anomaly) => {
          const context = hypothesis.contexts[anomaly.context_id]
          return (
            <li key={anomaly.id} className="rounded-md border border-border bg-muted/30 p-2 text-xs text-muted-foreground">
              anomaly <span className="font-mono">{anomaly.anomaly_class}</span> · deviation {anomaly.deviation_score.toFixed(4)}
              {context ? ` · ${context.mental_model_id}` : ''}
            </li>
          )
        })}
      </ul>
    </div>
  )
}

export function RecommendationDetail({
  recommendation,
  onClose,
}: {
  recommendation: CognitiveRecommendation | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['recommendation-detail', tenantId, recommendation?.id],
    queryFn: () => fetchRecommendationDetail(tenantId!, recommendation!.id),
    enabled: Boolean(tenantId && recommendation),
  })

  if (!recommendation) return null
  const hypothesis = data?.hypothesis ?? null
  const confidence = data?.confidence ?? null
  return (
    <div
      role="dialog"
      aria-label="Recommendation detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Compass className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Recommendation detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            A recommendation is an offer, never a commitment (P6): advisory and
            reversible — nothing is executed here. It states what to do, why, what is
            expected to happen, how confident the system is and what alternatives were
            considered. Content is immutable (P1); only the status is lifecycle
            (proposed → accepted/rejected/superseded, decided by the Decision layer).
            The confidence_score shown is the CALIBRATED score of the leading
            hypothesis (R4) — the recommendation never recalibrates.
          </div>

          <dl className="grid grid-cols-1 gap-3">
            <Field
              label="Status"
              value={<StatusBadge status={recommendation.status as CognitiveRecommendationStatus} />}
            />
            <Field label="Action" value={recommendation.action_description} />
            <Field label="Rationale" value={recommendation.rationale} />
          </dl>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Expected consequences
            </h3>
            {recommendation.expected_consequences.length === 0 ? (
              <EmptyState
                title="No expected consequences recorded"
                description="This offer was proposed without observable expected consequences."
              />
            ) : (
              <ul className="space-y-1">
                {recommendation.expected_consequences.map((consequence, index) => (
                  <li key={index} className="rounded-md border border-border bg-muted/30 p-2 text-sm">
                    {consequence}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Alternatives considered
            </h3>
            {recommendation.alternatives_considered.length === 0 ? (
              <EmptyState
                title="No alternatives recorded"
                description="This offer was proposed without documented alternatives."
              />
            ) : (
              <ul className="space-y-1">
                {recommendation.alternatives_considered.map((alternative, index) => (
                  <li key={index} className="rounded-md border border-border bg-muted/30 p-2 text-sm">
                    <span className="font-medium">{alternative.option ?? `Option ${index + 1}`}</span>
                    {alternative.not_chosen ? (
                      <span className="text-muted-foreground"> — not chosen: {alternative.not_chosen}</span>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Calibrated confidence (R4)
            </h3>
            {isPending ? (
              <LoadingState label="Loading confidence…" />
            ) : isError ? (
              error instanceof Error && error instanceof ApiError && error.status === 403 ? (
                <ForbiddenState action="view this recommendation" />
              ) : (
                <ErrorState message={error instanceof Error ? error.message : undefined} />
              )
            ) : (
              <ConfidenceBlock confidence={confidence} />
            )}
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Leading hypothesis
            </h3>
            {isPending ? (
              <LoadingState label="Loading hypothesis…" />
            ) : isError ? (
              <ErrorState message={error instanceof Error ? error.message : undefined} />
            ) : (
              <HypothesisBlock hypothesis={hypothesis} />
            )}
          </div>

          <dl className="grid grid-cols-1 gap-2">
            <Field
              label="Recommendation id"
              value={<span className="font-mono text-xs">{recommendation.id}</span>}
            />
            <Field
              label="Tenant id"
              value={<span className="font-mono text-xs">{recommendation.tenant_id}</span>}
            />
            <Field
              label="Hypothesis id"
              value={<span className="font-mono text-xs">{recommendation.hypothesis_id}</span>}
            />
            <Field
              label="Confidence id"
              value={<span className="font-mono text-xs">{recommendation.confidence_id}</span>}
            />
          </dl>

          {recommendation.insight_id && (
            <div className="rounded-md border border-border bg-muted/30 p-3">
              <p className="text-xs text-muted-foreground">
                This recommendation is linked to insight{' '}
                <span className="font-mono">{shortId(recommendation.insight_id)}</span>
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
