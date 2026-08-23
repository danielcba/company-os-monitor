import { useQuery } from '@tanstack/react-query'
import { Repeat, X } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchPatternDetail } from '@/api/gateway'
import type { CognitivePattern } from '@/types/cognitive'
import { ApiError } from '@/types/cognitive'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'
import { Field } from '@/components/ui/field'

function StatusBadge({ isActive }: { isActive: boolean }) {
  return isActive ? (
    <Badge className="border-emerald-500/40 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200">
      Active
    </Badge>
  ) : (
    <Badge variant="outline" className="text-muted-foreground">
      Superseded
    </Badge>
  )
}

export function PatternDetail({
  pattern,
  onClose,
}: {
  pattern: CognitivePattern | null
  onClose: () => void
}) {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['pattern-detail', tenantId, pattern?.id],
    queryFn: () => fetchPatternDetail(tenantId!, pattern!.id),
    enabled: Boolean(tenantId && pattern),
  })

  if (!pattern) return null
  const context = data?.context
  return (
    <div
      role="dialog"
      aria-label="Pattern detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Repeat className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Pattern detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            A Pattern describes regular structure; a Hypothesis proposes its cause (P4).
            This is a working regularity — probabilistic and revisable, never a law. The
            description, strength measure and frequency were assigned at detection and are
            immutable (P1); only the active lifecycle flag may change.
          </div>

          <dl className="grid grid-cols-2 gap-4">
            <Field
              label="Pattern type"
              value={<Badge variant="outline">{pattern.pattern_type}</Badge>}
            />
            <Field label="Status" value={<StatusBadge isActive={pattern.is_active} />} />
            <Field
              label="Strength measure"
              value={<span className="tabular-nums">{pattern.strength_measure.toFixed(4)}</span>}
            />
            <Field label="Frequency" value={pattern.frequency ?? '—'} />
            <Field label="Detected at" value={new Date(pattern.detected_at).toLocaleString()} />
          </dl>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Description
            </h3>
            <p className="rounded-md border border-border bg-muted/30 p-3 text-sm">
              {pattern.description}
            </p>
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Source context
            </h3>
            {isPending ? (
              <LoadingState label="Loading context…" />
            ) : isError ? (
              error instanceof Error && error instanceof ApiError && error.status === 403 ? (
                <ForbiddenState action="view this pattern" />
              ) : (
                <ErrorState message={error instanceof Error ? error.message : undefined} />
              )
            ) : !context ? (
              <EmptyState
                title="No context resolved"
                description="The Active Context this regularity was detected over is not available in this tenant."
              />
            ) : (
              <div className="rounded-md border border-border bg-muted/30 p-3 text-sm">
                <div className="flex items-center justify-between gap-2">
                  <span className="font-mono text-xs">{context.mental_model_id}</span>
                  <StatusBadge isActive={context.is_active} />
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
                <dl className="mt-2 grid grid-cols-2 gap-2">
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      Activated at
                    </dt>
                    <dd className="tabular-nums text-xs text-muted-foreground">
                      {new Date(context.activated_at).toLocaleString()}
                    </dd>
                  </div>
                  <div>
                    <dt className="text-[10px] uppercase tracking-wide text-muted-foreground">
                      Evidence organized
                    </dt>
                    <dd className="tabular-nums">{context.evidence_ids.length}</dd>
                  </div>
                </dl>
              </div>
            )}
          </div>

          <dl className="grid grid-cols-1 gap-2">
            <Field label="Pattern id" value={<span className="font-mono text-xs">{pattern.id}</span>} />
            <Field label="Tenant id" value={<span className="font-mono text-xs">{pattern.tenant_id}</span>} />
          </dl>
        </div>
      </div>
    </div>
  )
}