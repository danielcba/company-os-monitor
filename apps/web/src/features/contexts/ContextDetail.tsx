import { useQuery } from '@tanstack/react-query'
import { Radar, X } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchContextDetail } from '@/api/gateway'
import type { CognitiveContext } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { QualityClassBadge } from '@/components/cognitive/QualityClassBadge'
import { Field } from '@/components/ui/field'

export function ContextDetail({
  context,
  onClose,
}: {
  context: CognitiveContext | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['context-detail', tenantId, context?.id],
    queryFn: () => fetchContextDetail(tenantId!, context!.id),
    enabled: Boolean(tenantId && context),
  })

  if (!context) return null
  return (
    <div
      role="dialog"
      aria-label="Context detail"
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
            <h2 className="font-semibold">Context detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            Context is the interpretation selected by explanatory coherence — it does not create
            meaning (P2). The winner and its coherence score were assigned at activation and are
            immutable (P1); only the active lifecycle flag may change.
          </div>

          <dl className="grid grid-cols-2 gap-4">
            <Field label="Purpose" value={context.purpose} />
            <Field
              label="Status"
              value={
                context.is_active ? (
                  <Badge className="border-emerald-500/40 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200">
                    Active
                  </Badge>
                ) : (
                  <Badge variant="outline" className="text-muted-foreground">
                    Inactive
                  </Badge>
                )
              }
            />
            <Field
              label="Winner mental model"
              value={<span className="font-mono text-xs">{context.mental_model_id}</span>}
            />
            <Field
              label="Coherence score"
              value={<span className="tabular-nums">{context.coherence_score.toFixed(2)}</span>}
            />
            <Field
              label="Evidence organized"
              value={<span className="tabular-nums">{context.evidence_ids.length}</span>}
            />
            <Field label="Activated at" value={new Date(context.activated_at).toLocaleString()} />
          </dl>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Competing mental models
            </h3>
            {context.competing_models.length === 0 ? (
              <p className="rounded-md border border-border bg-muted/30 p-3 text-sm text-muted-foreground">
                No competing models were recorded for this activation.
              </p>
            ) : (
              <ul className="space-y-1.5">
                {context.competing_models.map((model) => {
                  const isWinner = model.mental_model_id === context.mental_model_id
                  return (
                    <li
                      key={model.mental_model_id}
                      className={`flex items-center justify-between gap-2 rounded-md border px-3 py-2 text-sm ${
                        isWinner
                          ? 'border-accent/50 bg-accent/10'
                          : 'border-border bg-muted/30'
                      }`}
                    >
                      <span className="font-mono text-xs">{model.mental_model_id}</span>
                      <span className="flex items-center gap-2">
                        {isWinner && (
                          <span className="text-[10px] uppercase tracking-wide text-muted-foreground">
                            winner
                          </span>
                        )}
                        <span className="tabular-nums text-muted-foreground">
                          {model.coherence_score.toFixed(2)}
                        </span>
                      </span>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Supporting evidence
            </h3>
            {isPending ? (
              <LoadingState label="Loading evidence…" />
            ) : isError ? (
              error instanceof Error && error instanceof ApiError && error.status === 403 ? (
                <ForbiddenState action="view this context" />
              ) : (
                <ErrorState message={error instanceof Error ? error.message : undefined} />
              )
            ) : !data || (data.evidence ?? []).length === 0 ? (
              <EmptyState
                title="No evidence resolved"
                description="The evidence that supported this activation is not available in this tenant."
              />
            ) : (
              <ul className="space-y-2">
                {data.evidence.map((evidence) => (
                  <li
                    key={evidence.id}
                    className="rounded-md border border-border bg-muted/30 p-3 text-sm"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono text-xs">{evidence.organization_type}</span>
                      <QualityClassBadge qualityClass={evidence.quality_class} />
                    </div>
                    <div className="mt-1.5 flex items-baseline justify-between gap-2">
                      <span className="text-xs text-muted-foreground">weight</span>
                      <span className="tabular-nums">{evidence.weight.toFixed(3)}</span>
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{evidence.description}</p>
                  </li>
                ))}
              </ul>
            )}
          </div>

          <dl className="grid grid-cols-1 gap-2">
            <Field label="Context id" value={<span className="font-mono text-xs">{context.id}</span>} />
            <Field label="Tenant id" value={<span className="font-mono text-xs">{context.tenant_id}</span>} />
          </dl>
        </div>
      </div>
    </div>
  )
}