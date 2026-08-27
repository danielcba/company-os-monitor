import { useState } from 'react'
import { useAuth } from '@/hooks/use-auth'
import { ApiError } from '@/types/cognitive'
import {
  useContextRevision,
  useInsightTransformations,
  useLearningMemories,
  usePatternRefinement,
  usePersistLearningMemory,
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
  const memories = useLearningMemories(tenantId)
  const persist = usePersistLearningMemory(tenantId)
  const [savedIds, setSavedIds] = useState<Set<string>>(new Set())

  function handleSave(
    targetType: 'pattern' | 'context' | 'insight',
    targetId: string,
    signal: Record<string, unknown>,
    provenance: Record<string, unknown>,
  ) {
    if (!tenantId) return
    persist.mutate(
      { target_type: targetType, target_id: targetId, signal, provenance },
      {
        onSuccess: () =>
          setSavedIds((prev) => new Set(prev).add(targetId)),
      },
    )
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Learning (P7)</h1>
        <p className="max-w-3xl text-sm text-muted-foreground">
          Read/compute signals (external capability, ADR-0002) derived from Decision
          outcomes. They surface how Patterns, Contexts and Insights should be
          reconsidered — they never mutate canonical entities. When authorized, a
          signal can be persisted into the Learning Memory ledger (append-only, P1);
          the Persisted Memory section below shows what has been recorded. Source of
          truth for every outcome verdict is Outcome Consolidation (no fabrication
          of failures).
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
                    <th className="py-2 pr-3">Memory</th>
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
                      <td className="py-2 pr-3">
                        <button
                          type="button"
                          disabled={persist.isPending}
                          onClick={() =>
                            handleSave(
                              'pattern',
                              r.pattern_id,
                              {
                                recommended_action: r.recommended_action,
                                current_strength: r.current_strength,
                                recommended_strength: r.recommended_strength,
                                contradiction_ratio: r.contradiction_ratio,
                              },
                              {
                                linked_decisions: r.linked_decisions,
                                corroborated: r.corroborated,
                                contradicted: r.contradicted,
                                inconclusive: r.inconclusive,
                              },
                            )
                          }
                          className="rounded border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
                        >
                          {savedIds.has(r.pattern_id) ? 'Saved' : 'Save to Memory'}
                        </button>
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
                    <th className="py-2 pr-3">Memory</th>
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
                      <td className="py-2 pr-3">
                        <button
                          type="button"
                          disabled={persist.isPending}
                          onClick={() =>
                            handleSave(
                              'context',
                              r.context_id,
                              {
                                recommended_revision: r.recommended_revision,
                                contradiction_ratio: r.contradiction_ratio,
                                has_competing_models: r.has_competing_models,
                                suggested_competitor: r.suggested_competitor,
                              },
                              {
                                linked_decisions: r.linked_decisions,
                                corroborated: r.corroborated,
                                contradicted: r.contradicted,
                                inconclusive: r.inconclusive,
                              },
                            )
                          }
                          className="rounded border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
                        >
                          {savedIds.has(r.context_id) ? 'Saved' : 'Save to Memory'}
                        </button>
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
                        <button
                          type="button"
                          disabled={persist.isPending}
                          onClick={() =>
                            handleSave(
                              'insight',
                              r.insight_id,
                              {
                                transformation_kind: r.transformation_kind,
                                prior_understanding: r.prior_understanding,
                                mental_model_update: r.mental_model_update,
                              },
                              {
                                linked_recommendations: r.linked_recommendations,
                                linked_decisions_with_outcomes: r.linked_decisions_with_outcomes,
                                corroborated: r.corroborated,
                                contradicted: r.contradicted,
                                inconclusive: r.inconclusive,
                              },
                            )
                          }
                          className="ml-auto rounded border border-border px-2 py-1 text-xs hover:bg-muted disabled:opacity-50"
                        >
                          {savedIds.has(r.insight_id) ? 'Saved' : 'Save to Memory'}
                        </button>
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

      {/* Persisted Learning Memory */}
      <Card>
        <CardHeader>
          <CardTitle>Persisted Memory</CardTitle>
          <p className="text-sm text-muted-foreground">
            Learning signals saved into the append-only ledger (P7 persistence,
            authorized). Each row is immutable once recorded.
          </p>
        </CardHeader>
        <CardContent>
          {memories.isPending ? (
            <LoadingState label="Loading persisted memory…" />
          ) : memories.isError ? (
            <SectionError error={memories.error} />
          ) : memories.data && (memories.data.memories?.length ?? 0) > 0 ? (
            <ul className="space-y-2">
              {memories.data.memories.map((m) => (
                <li
                  key={m.id}
                  className="flex flex-wrap items-center gap-2 rounded-md border border-border bg-muted/30 p-3 text-sm"
                >
                  <Badge variant="outline">{m.target_type}</Badge>
                  <span className="font-mono text-xs text-muted-foreground">
                    {short(m.target_id)}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {JSON.stringify(m.signal)}
                  </span>
                  <span className="ml-auto text-xs text-muted-foreground">
                    {new Date(m.created_at).toLocaleString()}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <EmptyState
              title="No persisted memory yet"
              description="Use “Save to Memory” on any signal above to record it in the ledger."
            />
          )}
        </CardContent>
      </Card>
    </div>
  )
}

export default LearningPage
