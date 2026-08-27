import { useAuth } from '@/hooks/use-auth'
import { ApiError } from '@/types/cognitive'
import {
  useContextRevision,
  useInsightTransformations,
  usePatternRefinement,
} from '@/features/learning/useLearning'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  EmptyState,
  ErrorState,
  ForbiddenState,
  LoadingState,
} from '@/components/ui/state'

const short = (id: string) => id.slice(0, 8)

function patternActionVariant(action: string): 'success' | 'warning' | 'destructive' {
  if (action === 'keep') return 'success'
  if (action === 'degrade') return 'warning'
  return 'destructive'
}

function revisionVariant(action: string): 'success' | 'outline' | 'warning' | 'accent' {
  if (action === 'keep') return 'success'
  if (action === 'consider_competitor') return 'accent'
  return 'warning'
}

function kindVariant(kind: string): 'accent' | 'outline' | 'default' {
  if (kind === 'revised') return 'accent'
  if (kind === 'stable') return 'outline'
  return 'default'
}

function SectionError({ error }: { error: unknown }) {
  if (error instanceof ApiError && error.status === 403) {
    return <ForbiddenState action="view learning signals" />
  }
  if (error instanceof ApiError && error.status === 404) {
    return <EmptyState title="No data" description="This tenant has no recorded artifacts yet." />
  }
  return (
    <ErrorState message={error instanceof Error ? error.message : undefined} />
  )
}

export function LearningPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const patterns = usePatternRefinement(tenantId)
  const contexts = useContextRevision(tenantId)
  const insights = useInsightTransformations(tenantId)

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Learning (P7)</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Read/compute signals (external capability, ADR-0002) derived from Decision
          outcomes. They surface how Patterns, Contexts and Insights should be
          reconsidered — they never mutate canonical entities, and Memory
          persistence remains planned. Source of truth for every outcome verdict is
          Outcome Consolidation (no fabrication of failures).
        </p>
      </div>

      {/* Pattern Refinement */}
      <Card>
        <CardHeader>
          <CardTitle>Pattern Refinement</CardTitle>
          <p className="text-sm text-muted-foreground">
            Each Pattern’s support reconsidered from the Decisions that used it.
          </p>
        </CardHeader>
        <CardContent>
          {patterns.isPending ? (
            <LoadingState label="Loading pattern refinement…" />
          ) : patterns.isError ? (
            <SectionError error={patterns.error} />
          ) : patterns.data && patterns.data.results.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3">Pattern</th>
                    <th className="py-2 pr-3">Type</th>
                    <th className="py-2 pr-3">Linked</th>
                    <th className="py-2 pr-3">Corr.</th>
                    <th className="py-2 pr-3">Contr.</th>
                    <th className="py-2 pr-3">Ratio</th>
                    <th className="py-2 pr-3">Strength (cur→rec)</th>
                    <th className="py-2 pr-3">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {patterns.data.results.map((r) => (
                    <tr key={r.pattern_id} className="border-t border-border">
                      <td className="py-2 pr-3 font-mono text-xs">{short(r.pattern_id)}</td>
                      <td className="py-2 pr-3">{r.pattern_type}</td>
                      <td className="py-2 pr-3">{r.linked_decisions}</td>
                      <td className="py-2 pr-3 text-emerald-700 dark:text-emerald-400">{r.corroborated}</td>
                      <td className="py-2 pr-3 text-red-700 dark:text-red-400">{r.contradicted}</td>
                      <td className="py-2 pr-3">{r.contradiction_ratio.toFixed(2)}</td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {r.current_strength.toFixed(2)} → {r.recommended_strength.toFixed(2)}
                      </td>
                      <td className="py-2 pr-3">
                        <Badge variant={patternActionVariant(r.recommended_action)}>
                          {r.recommended_action}
                        </Badge>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No patterns with outcomes"
              description="Patterns appear here once Decisions based on them record actual outcomes."
            />
          )}
        </CardContent>
      </Card>

      {/* Context Revision */}
      <Card>
        <CardHeader>
          <CardTitle>Context Revision</CardTitle>
          <p className="text-sm text-muted-foreground">
            Contexts reconsidered from the outcomes of the Patterns they framed. A
            competing model is only suggested, never auto-activated (P2).
          </p>
        </CardHeader>
        <CardContent>
          {contexts.isPending ? (
            <LoadingState label="Loading context revision…" />
          ) : contexts.isError ? (
            <SectionError error={contexts.error} />
          ) : contexts.data && contexts.data.results.length > 0 ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs uppercase text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-3">Context</th>
                    <th className="py-2 pr-3">Linked</th>
                    <th className="py-2 pr-3">Corr.</th>
                    <th className="py-2 pr-3">Contr.</th>
                    <th className="py-2 pr-3">Ratio</th>
                    <th className="py-2 pr-3">Revision</th>
                    <th className="py-2 pr-3">Suggested competitor</th>
                  </tr>
                </thead>
                <tbody>
                  {contexts.data.results.map((r) => (
                    <tr key={r.context_id} className="border-t border-border">
                      <td className="py-2 pr-3 font-mono text-xs">{short(r.context_id)}</td>
                      <td className="py-2 pr-3">{r.linked_decisions}</td>
                      <td className="py-2 pr-3 text-emerald-700 dark:text-emerald-400">{r.corroborated}</td>
                      <td className="py-2 pr-3 text-red-700 dark:text-red-400">{r.contradicted}</td>
                      <td className="py-2 pr-3">{r.contradiction_ratio.toFixed(2)}</td>
                      <td className="py-2 pr-3">
                        <Badge variant={revisionVariant(r.recommended_revision)}>
                          {r.recommended_revision}
                        </Badge>
                      </td>
                      <td className="py-2 pr-3 font-mono text-xs">
                        {r.suggested_competitor ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState
              title="No contexts with outcomes"
              description="Contexts appear here once Decisions framed by their Patterns record actual outcomes."
            />
          )}
        </CardContent>
      </Card>

      {/* Insight Transformations */}
      <Card>
        <CardHeader>
          <CardTitle>Insight Transformations</CardTitle>
          <p className="text-sm text-muted-foreground">
            Each Insight journals its knowledge restructuring (R6): prior
            understanding → mental-model update. Outcome attribution, when present,
            links back to the Insight that informed the Recommendation.
          </p>
        </CardHeader>
        <CardContent>
          {insights.isPending ? (
            <LoadingState label="Loading insight transformations…" />
          ) : insights.isError ? (
            <SectionError error={insights.error} />
          ) : insights.data && insights.data.results.length > 0 ? (
            <ul className="space-y-3">
              {insights.data.results.map((r) => (
                <li key={r.insight_id} className="rounded-md border border-border bg-muted/30 p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={kindVariant(r.transformation_kind)}>
                      {r.transformation_kind}
                    </Badge>
                    <span className="font-mono text-xs text-muted-foreground">
                      insight {short(r.insight_id)}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      {r.linked_recommendations} linked · {r.linked_decisions_with_outcomes} outcomes ·
                      corr {r.corroborated} / contr {r.contradicted}
                    </span>
                  </div>
                  <p className="mt-2 text-sm">{r.description}</p>
                  {r.transformation_kind !== 'unchanged' ? (
                    <p className="mt-1 text-xs text-muted-foreground">
                      <span className="font-medium">prior:</span>{' '}
                      {r.prior_understanding ?? '—'} →{' '}
                      <span className="font-medium">updated:</span>{' '}
                      {r.mental_model_update ? JSON.stringify(r.mental_model_update) : '—'}
                    </p>
                  ) : null}
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No insights yet"
              description="Insights journaled by the reasoning layer appear here."
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default LearningPage
