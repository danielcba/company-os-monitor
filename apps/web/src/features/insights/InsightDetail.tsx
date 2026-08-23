import { useQuery } from '@tanstack/react-query'
import { Lightbulb, X } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchInsightDetail } from '@/api/gateway'
import type {
  CognitiveContext,
  CognitiveHypothesis,
  CognitiveInsight,
} from '@/types/cognitive'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Field } from '@/components/ui/field'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/state'
import { shortId } from '@/lib/utils'

function ContextBlock({ context }: { context: CognitiveContext | null }) {
  if (!context) {
    return (
      <EmptyState
        title="Context not resolved"
        description="The Active Context this insight operates on is not available in this tenant."
      />
    )
  }
  return (
    <div className="rounded-md border border-border bg-muted/30 p-3 text-sm">
      <div className="mb-1 flex items-center gap-2">
        <Badge variant="outline">{context.mental_model_id}</Badge>
        <span className="tabular-nums text-xs text-muted-foreground">
          coherence {context.coherence_score.toFixed(2)}
        </span>
      </div>
      <p className="text-muted-foreground">{context.purpose}</p>
    </div>
  )
}

function HypothesesBlock({ hypotheses }: { hypotheses: CognitiveHypothesis[] }) {
  if (hypotheses.length === 0) {
    return (
      <EmptyState
        title="No hypotheses resolved"
        description="The hypotheses this insight restructures are not available in this tenant."
      />
    )
  }
  return (
    <ul className="space-y-1">
      {hypotheses.map((hypothesis) => (
        <li
          key={hypothesis.id}
          className="rounded-md border border-border bg-muted/30 p-2 text-xs text-muted-foreground"
        >
          <div className="mb-1 flex items-center gap-2">
            <Badge variant="outline">{hypothesis.status}</Badge>
            <span className="font-mono">{shortId(hypothesis.id)}</span>
            <span className="tabular-nums">
              coherence {hypothesis.coherence_score.toFixed(2)}
            </span>
          </div>
          <p>{hypothesis.description}</p>
        </li>
      ))}
    </ul>
  )
}

export function InsightDetail({
  insight,
  onClose,
}: {
  insight: CognitiveInsight | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['insight-detail', tenantId, insight?.id],
    queryFn: () => fetchInsightDetail(tenantId!, insight!.id),
    enabled: Boolean(tenantId && insight),
  })

  if (!insight) return null
  const context = data?.context ?? null
  const hypotheses = data?.hypotheses ?? []
  return (
    <div
      role="dialog"
      aria-label="Insight detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Lightbulb className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Insight detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            An Insight is a novel understanding that results from RESTRUCTURING
            the relationship between existing knowledge elements — it is not new
            information, it is a new organization of information that was already
            available. Content is immutable (P1) and there is no lifecycle
            status: the row is a pure transformation journal, never updated and
            never deleted. "Insight cannot be forced or scheduled."
          </div>

          <dl className="grid grid-cols-1 gap-3">
            <Field
              label="Description"
              value={insight.description}
            />
            {insight.prior_understanding && (
              <Field
                label="Prior understanding"
                value={insight.prior_understanding}
              />
            )}
            {insight.mental_model_update && (
              <Field
                label="Mental model update"
                value={
                  <pre className="overflow-x-auto rounded bg-muted/30 p-2 text-xs">
                    {JSON.stringify(insight.mental_model_update, null, 2)}
                  </pre>
                }
              />
            )}
          </dl>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Active Context
            </h3>
            {isPending ? (
              <LoadingState label="Loading context…" />
            ) : isError ? (
              <ErrorState message={error instanceof Error ? error.message : undefined} />
            ) : (
              <ContextBlock context={context} />
            )}
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Restructured Hypotheses
            </h3>
            {isPending ? (
              <LoadingState label="Loading hypotheses…" />
            ) : isError ? (
              <ErrorState message={error instanceof Error ? error.message : undefined} />
            ) : (
              <HypothesesBlock hypotheses={hypotheses} />
            )}
          </div>

          <dl className="grid grid-cols-1 gap-2">
            <Field
              label="Insight id"
              value={<span className="font-mono text-xs">{insight.id}</span>}
            />
            <Field
              label="Tenant id"
              value={<span className="font-mono text-xs">{insight.tenant_id}</span>}
            />
            <Field
              label="Context id"
              value={<span className="font-mono text-xs">{insight.context_id}</span>}
            />
            <Field
              label="Generated at"
              value={new Date(insight.generated_at).toLocaleString()}
            />
          </dl>
        </div>
      </div>
    </div>
  )
}
