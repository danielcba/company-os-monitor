import { useCallback, useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  Search,
  Activity,
  Brain,
  Compass,
  Gauge,
  Lightbulb,
  Radar,
  Repeat,
} from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import {
  fetchAnomalies,
  fetchDecisions,
  fetchHypotheses,
  fetchInsights,
  fetchObservations,
  fetchRecommendations,
} from '@/api/gateway'
import { cn } from '@/lib/utils'
import { shortId } from '@/lib/utils'
import { Card } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/ui/state'

type EntityType =
  | 'observation'
  | 'evidence'
  | 'context'
  | 'pattern'
  | 'anomaly'
  | 'hypothesis'
  | 'insight'
  | 'confidence'
  | 'recommendation'
  | 'decision'

interface SearchResult {
  id: string
  type: EntityType
  title: string
  description: string
  timestamp: string
  href: string
  metadata?: Record<string, string>
}

const ENTITY_ICONS: Record<EntityType, React.ComponentType<{ className?: string }>> = {
  observation: Activity,
  evidence: Activity,
  context: Radar,
  pattern: Repeat,
  anomaly: Radar,
  hypothesis: Brain,
  insight: Lightbulb,
  confidence: Gauge,
  recommendation: Compass,
  decision: Brain,
}

const ENTITY_LABELS: Record<EntityType, string> = {
  observation: 'Observation',
  evidence: 'Evidence',
  context: 'Context',
  pattern: 'Pattern',
  anomaly: 'Anomaly',
  hypothesis: 'Hypothesis',
  insight: 'Insight',
  confidence: 'Confidence',
  recommendation: 'Recommendation',
  decision: 'Decision',
}

const ENTITY_COLORS: Record<EntityType, string> = {
  observation: 'bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200',
  evidence: 'bg-indigo-100 text-indigo-800 dark:bg-indigo-900/40 dark:text-indigo-200',
  context: 'bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200',
  pattern: 'bg-purple-100 text-purple-800 dark:bg-purple-900/40 dark:text-purple-200',
  anomaly: 'bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200',
  hypothesis: 'bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200',
  insight: 'bg-yellow-100 text-yellow-800 dark:bg-yellow-900/40 dark:text-yellow-200',
  confidence: 'bg-orange-100 text-orange-800 dark:bg-orange-900/40 dark:text-orange-200',
  recommendation: 'bg-emerald-100 text-emerald-800 dark:bg-emerald-900/40 dark:text-emerald-200',
  decision: 'bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-200',
}

export function GlobalSearchPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id
  const navigate = useNavigate()
  const [query, setQuery] = useState('')
  const [results, setResults] = useState<SearchResult[]>([])
  const [isSearching, setIsSearching] = useState(false)
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)
  const searchIdRef = useRef(0)

  const search = useCallback(
    async (q: string, searchId: number) => {
      if (!tenantId || q.length < 2) {
        setResults([])
        return
      }
      setIsSearching(true)
      try {
        const allResults: SearchResult[] = []
        const lower = q.toLowerCase()

        const [
          observations,
          anomalies,
          hypotheses,
          insights,
          recommendations,
          decisions,
        ] = await Promise.all([
          fetchObservations(tenantId, { limit: 15 }),
          fetchAnomalies(tenantId, { limit: 15 }),
          fetchHypotheses(tenantId, { limit: 15 }),
          fetchInsights(tenantId, { limit: 15 }),
          fetchRecommendations(tenantId, { limit: 15 }),
          fetchDecisions(tenantId, { limit: 15 }),
        ])

        if (searchId !== searchIdRef.current) return

        observations.observations.forEach((o) => {
          const match =
            o.id.toLowerCase().includes(lower) ||
            o.fact_type.toLowerCase().includes(lower) ||
            o.source_type.toLowerCase().includes(lower) ||
            JSON.stringify(o.fact_value).toLowerCase().includes(lower)
          if (match) {
            allResults.push({
              id: o.id,
              type: 'observation',
              title: `${o.fact_type} (${o.source_type})`,
              description: JSON.stringify(o.fact_value).slice(0, 120),
              timestamp: o.captured_at,
              href: '/cognition/observations',
              metadata: { quality: o.quality_class },
            })
          }
        })

        anomalies.anomalies.forEach((a) => {
          const match =
            a.id.toLowerCase().includes(lower) ||
            a.anomaly_class.toLowerCase().includes(lower)
          if (match) {
            allResults.push({
              id: a.id,
              type: 'anomaly',
              title: `Anomaly: ${a.anomaly_class}`,
              description: `deviation ${a.deviation_score.toFixed(2)} · threshold ${a.tolerance_threshold.toFixed(2)}`,
              timestamp: a.detected_at,
              href: '/cognition/anomalies',
            })
          }
        })

        hypotheses.hypotheses.forEach((h) => {
          const match =
            h.id.toLowerCase().includes(lower) ||
            h.description.toLowerCase().includes(lower)
          if (match) {
            allResults.push({
              id: h.id,
              type: 'hypothesis',
              title: h.description.slice(0, 80),
              description: `${h.status} · coherence ${h.coherence_score.toFixed(2)} · ${h.anomaly_ids.length} anomalies`,
              timestamp: h.generated_at,
              href: '/cognition/hypotheses',
            })
          }
        })

        insights.insights.forEach((i) => {
          const match =
            i.id.toLowerCase().includes(lower) ||
            i.description.toLowerCase().includes(lower)
          if (match) {
            allResults.push({
              id: i.id,
              type: 'insight',
              title: i.description.slice(0, 80),
              description: `${i.hypothesis_ids.length} hypotheses restructured`,
              timestamp: i.generated_at,
              href: '/cognition/insights',
            })
          }
        })

        recommendations.recommendations.forEach((r) => {
          const match =
            r.id.toLowerCase().includes(lower) ||
            r.action_description.toLowerCase().includes(lower) ||
            r.rationale.toLowerCase().includes(lower)
          if (match) {
            allResults.push({
              id: r.id,
              type: 'recommendation',
              title: r.action_description.slice(0, 80),
              description: `${r.status} · confidence ${r.confidence_score.toFixed(4)}`,
              timestamp: r.proposed_at,
              href: '/action/recommendations',
            })
          }
        })

        decisions.decisions.forEach((d) => {
          const match =
            d.id.toLowerCase().includes(lower) ||
            d.commitment.toLowerCase().includes(lower)
          if (match) {
            allResults.push({
              id: d.id,
              type: 'decision',
              title: d.commitment.slice(0, 80),
              description: `${d.status} · risk ${d.risk_tolerance}`,
              timestamp: d.committed_at,
              href: '/action/decisions',
            })
          }
        })

        allResults.sort(
          (a, b) => new Date(b.timestamp).getTime() - new Date(a.timestamp).getTime(),
        )
        setResults(allResults)
      } catch {
        setResults([])
      } finally {
        setIsSearching(false)
      }
    },
    [tenantId],
  )

  const handleQueryChange = useCallback(
    (value: string) => {
      setQuery(value)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      searchIdRef.current += 1
      const currentSearchId = searchIdRef.current
      debounceRef.current = setTimeout(() => {
        void search(value, currentSearchId)
      }, 400)
    },
    [search],
  )

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  const grouped = results.reduce<Record<EntityType, SearchResult[]>>(
    (acc, r) => {
      if (!acc[r.type]) acc[r.type] = []
      acc[r.type].push(r)
      return acc
    },
    {} as Record<EntityType, SearchResult[]>,
  )

  const totalResults = results.length

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold">Global Search</h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Search across all cognitive concepts: observations, evidence, contexts,
          patterns, anomalies, hypotheses, insights, confidence scores,
          recommendations, and decisions. Results are grouped by entity type
          and sorted by recency.
        </p>
      </div>

      <Card className="p-4">
        <div className="relative">
          <Search className="pointer-events-none absolute left-3 top-3 h-4 w-4 text-muted-foreground" />
          <input
            type="text"
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            placeholder="Search by ID, description, type, or content…"
            className="h-10 w-full rounded-md border border-border bg-background pl-10 pr-4 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring"
            autoFocus
          />
          {isSearching && (
            <div className="absolute right-3 top-3 h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
          )}
        </div>
      </Card>

      {query.length < 2 ? (
        <EmptyState
          title="Enter a search query"
          description="Type at least 2 characters to search across all cognitive concepts."
        />
      ) : totalResults === 0 && !isSearching ? (
        <EmptyState
          title="No results found"
          description={`No entities match "${query}". Try a different search term.`}
        />
      ) : (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            {totalResults} result{totalResults === 1 ? '' : 's'} found
          </p>
          {(Object.keys(grouped) as EntityType[]).map((type) => {
            const items = grouped[type]
            if (!items || items.length === 0) return null
            const Icon = ENTITY_ICONS[type]
            return (
              <div key={type}>
                <h2 className="mb-2 flex items-center gap-2 text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                  <Icon className="h-4 w-4" />
                  {ENTITY_LABELS[type]}
                  <Badge variant="outline" className="ml-1 text-xs">
                    {items.length}
                  </Badge>
                </h2>
                <div className="space-y-1">
                  {items.map((item) => (
                    <div
                      key={item.id}
                      className="flex cursor-pointer items-center gap-3 rounded-md border border-border bg-card p-3 text-sm transition-colors hover:bg-muted"
                      onClick={() => navigate(item.href)}
                    >
                      <Badge
                        className={cn(
                          'shrink-0 border-0 text-xs',
                          ENTITY_COLORS[item.type],
                        )}
                      >
                        {ENTITY_LABELS[item.type]}
                      </Badge>
                      <div className="min-w-0 flex-1">
                        <p className="truncate font-medium">{item.title}</p>
                        <p className="truncate text-xs text-muted-foreground">
                          {item.description}
                        </p>
                      </div>
                      <span className="shrink-0 font-mono text-xs text-muted-foreground">
                        {shortId(item.id)}
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">
                        {new Date(item.timestamp).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default GlobalSearchPage
