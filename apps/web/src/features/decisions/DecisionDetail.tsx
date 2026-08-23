import { useQuery } from '@tanstack/react-query'
import { GitCommitHorizontal, X } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchDecisionDetail } from '@/api/gateway'
import type {
  CognitiveConfidenceDetail,
  CognitiveDecision,
  CognitiveDecisionStatus,
  CognitiveRecommendationDetail,
} from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { StatusBadge, RiskBadge } from '@/features/decisions/DecisionsPage'

function ConfidenceBlock({ confidence }: { confidence: CognitiveConfidenceDetail | null }) {
  if (!confidence) {
    return (
      <EmptyState
        title="Confidence not resolved"
        description="The calibrated confidence that supports this commitment is not available in this tenant."
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

function RecommendationBlock({
  recommendation,
}: {
  recommendation: CognitiveRecommendationDetail | null
}) {
  if (!recommendation) {
    return (
      <EmptyState
        title="Recommendation not resolved"
        description="The recommendation being committed is not available in this tenant."
      />
    )
  }
  return (
    <div className="space-y-2">
      <div className="rounded-md border border-border bg-muted/30 p-3 text-sm">
        <div className="mb-1 flex items-center gap-2">
          <Badge variant="outline">{recommendation.recommendation.status}</Badge>
          <span className="tabular-nums text-xs text-muted-foreground">
            confidence {recommendation.recommendation.confidence_score.toFixed(4)}
          </span>
        </div>
        <p>{recommendation.recommendation.action_description}</p>
      </div>
      <p className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
        {recommendation.recommendation.rationale}
      </p>
      {recommendation.hypothesis && (
        <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
          <p className="mb-1 font-semibold uppercase tracking-wide">Leading hypothesis</p>
          <div className="flex items-center gap-2">
            <Badge variant="outline">{recommendation.hypothesis.hypothesis.status}</Badge>
            <span className="tabular-nums">
              coherence {recommendation.hypothesis.hypothesis.coherence_score.toFixed(2)}
            </span>
          </div>
          <p className="mt-1">{recommendation.hypothesis.hypothesis.description}</p>
        </div>
      )}
    </div>
  )
}

function ChainVisualization({
  recommendation,
  confidence,
}: {
  recommendation: CognitiveRecommendationDetail | null
  confidence: CognitiveConfidenceDetail | null
}) {
  const hyp = recommendation?.hypothesis?.hypothesis
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        Cognitive Chain
      </h4>
      <div className="flex items-center gap-2 text-xs text-muted-foreground">
        {hyp && (
          <>
            <span className="rounded bg-amber-100 px-1.5 py-0.5 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
              Hypothesis
            </span>
            <span>→</span>
          </>
        )}
        <span className="rounded bg-orange-100 px-1.5 py-0.5 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200">
          Confidence {confidence?.confidence.confidence_score.toFixed(4) ?? 'n/a'}
        </span>
        <span>→</span>
        <span className="rounded bg-emerald-100 px-1.5 py-0.5 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200">
          Recommendation
        </span>
        <span>→</span>
        <span className="rounded bg-teal-100 px-1.5 py-0.5 text-teal-800 dark:bg-teal-900/40 dark:text-teal-200">
          Decision
        </span>
      </div>
    </div>
  )
}

export function DecisionDetail({
  decision,
  onClose,
}: {
  decision: CognitiveDecision | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['decision-detail', tenantId, decision?.id],
    queryFn: () => fetchDecisionDetail(tenantId!, decision!.id),
    enabled: Boolean(tenantId && decision),
  })

  if (!decision) return null
  const recommendation = data?.recommendation ?? null
  const confidence = data?.confidence ?? null
  return (
    <div
      role="dialog"
      aria-label="Decision detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <GitCommitHorizontal className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Decision detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            A decision is a commitment with an owner, a timeline and expected
            outcomes (P6): it ends deliberation, it does not end learning. Its
            expected outcomes are falsifiable predictions stated in observable,
            verifiable terms BEFORE execution — the comparison of expected vs
            actual outcomes is the primary learning signal of the system. This
            commitment is recorded, never executed in this MVP. Content is
            immutable (P1); only the status is lifecycle (committed →
            executing/completed/rolled_back, decided by the Learning loop). The
            confidence_score shown is the CALIBRATED score that supported the
            commitment (R4) — the decision never recalibrates.
          </div>

          <dl className="grid grid-cols-1 gap-3">
            <Field
              label="Status"
              value={<StatusBadge status={decision.status as CognitiveDecisionStatus} />}
            />
            <Field label="Commitment" value={decision.commitment} />
            <Field
              label="Risk tolerance"
              value={<RiskBadge risk={decision.risk_tolerance} />}
            />
            <Field
              label="Authority id"
              value={<span className="font-mono text-xs">{decision.authority_id}</span>}
            />
          </dl>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Expected outcomes (falsifiable)
            </h3>
            {decision.expected_outcomes.length === 0 ? (
              <EmptyState
                title="No expected outcomes recorded"
                description="This commitment was taken without falsifiable expected outcomes."
              />
            ) : (
              <ul className="space-y-1">
                {decision.expected_outcomes.map((outcome, index) => (
                  <li key={index} className="rounded-md border border-border bg-muted/30 p-2 text-sm">
                    <p className="font-medium">{outcome.prediction}</p>
                    <p className="mt-1 text-xs text-muted-foreground">
                      verifiable by: {outcome.verifiable_by} · deadline: {outcome.deadline}
                    </p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {!isPending && (
            <ChainVisualization
              recommendation={recommendation}
              confidence={confidence}
            />
          )}

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Committed recommendation
            </h3>
            {isPending ? (
              <LoadingState label="Loading recommendation…" />
            ) : isError ? (
              error instanceof Error && error instanceof ApiError && error.status === 403 ? (
                <ForbiddenState action="view this decision" />
              ) : (
                <ErrorState message={error instanceof Error ? error.message : undefined} />
              )
            ) : (
              <RecommendationBlock recommendation={recommendation} />
            )}
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Calibrated confidence (R4)
            </h3>
            {isPending ? (
              <LoadingState label="Loading confidence…" />
            ) : isError ? (
              <ErrorState message={error instanceof Error ? error.message : undefined} />
            ) : (
              <ConfidenceBlock confidence={confidence} />
            )}
          </div>

          <dl className="grid grid-cols-1 gap-2">
            <Field
              label="Decision id"
              value={<span className="font-mono text-xs">{decision.id}</span>}
            />
            <Field
              label="Tenant id"
              value={<span className="font-mono text-xs">{decision.tenant_id}</span>}
            />
            <Field
              label="Recommendation id"
              value={<span className="font-mono text-xs">{decision.recommendation_id}</span>}
            />
            <Field
              label="Confidence id"
              value={<span className="font-mono text-xs">{decision.confidence_id}</span>}
            />
          </dl>
        </div>
      </div>
    </div>
  )
}
