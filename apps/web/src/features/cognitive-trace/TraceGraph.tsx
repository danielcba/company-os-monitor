import { GitBranch, AlertTriangle } from 'lucide-react'
import { Badge } from '@/components/ui/badge'
import type {
  CognitiveTraceNode,
  CognitiveTraceNodeType,
} from '@/types/cognitive'

// Canonical pipeline order used for the layered (left-to-right) view.
const NODE_ORDER: CognitiveTraceNodeType[] = [
  'report',
  'decision',
  'recommendation',
  'confidence',
  'hypothesis',
  'anomaly',
  'pattern',
  'context',
  'evidence',
  'observation',
]

const NODE_META: Record<
  CognitiveTraceNodeType,
  { label: string; family: string; classes: string }
> = {
  report: {
    label: 'Report',
    family: 'Action',
    classes: 'border-slate-500/40 bg-slate-100 text-slate-900 dark:bg-slate-900/40 dark:text-slate-200',
  },
  decision: {
    label: 'Decision',
    family: 'Action',
    classes: 'border-emerald-500/40 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
  },
  recommendation: {
    label: 'Recommendation',
    family: 'Action',
    classes: 'border-teal-500/40 bg-teal-100 text-teal-900 dark:bg-teal-900/40 dark:text-teal-200',
  },
  confidence: {
    label: 'Confidence',
    family: 'Learning',
    classes: 'border-violet-500/40 bg-violet-100 text-violet-900 dark:bg-violet-900/40 dark:text-violet-200',
  },
  hypothesis: {
    label: 'Hypothesis',
    family: 'Reasoning',
    classes: 'border-amber-500/40 bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  },
  anomaly: {
    label: 'Anomaly',
    family: 'Reasoning',
    classes: 'border-orange-500/40 bg-orange-100 text-orange-900 dark:bg-orange-900/40 dark:text-orange-200',
  },
  pattern: {
    label: 'Pattern',
    family: 'Reasoning',
    classes: 'border-yellow-500/40 bg-yellow-100 text-yellow-900 dark:bg-yellow-900/40 dark:text-yellow-200',
  },
  context: {
    label: 'Context',
    family: 'Perception',
    classes: 'border-sky-500/40 bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200',
  },
  evidence: {
    label: 'Evidence',
    family: 'Perception',
    classes: 'border-blue-500/40 bg-blue-100 text-blue-900 dark:bg-blue-900/40 dark:text-blue-200',
  },
  observation: {
    label: 'Observation',
    family: 'Perception',
    classes: 'border-cyan-500/40 bg-cyan-100 text-cyan-900 dark:bg-cyan-900/40 dark:text-cyan-200',
  },
}

function formatValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (typeof value === 'number') return String(value)
  if (value === null || value === undefined) return '—'
  return JSON.stringify(value)
}

function nodeSummary(node: CognitiveTraceNode): string {
  const d = (node.data ?? {}) as Record<string, unknown>
  switch (node.type) {
    case 'report':
      return formatValue(d['title'])
    case 'decision':
      return formatValue(d['commitment'])
    case 'recommendation':
      return formatValue(d['action_description'])
    case 'confidence':
      return `score ${formatValue(d['confidence_score'])}`
    case 'hypothesis':
      return formatValue(d['description'])
    case 'anomaly':
      return `${formatValue(d['anomaly_class'])} · dev ${formatValue(d['deviation_score'])}`
    case 'pattern':
      return formatValue(d['pattern_type'])
    case 'context':
      return formatValue(d['purpose'])
    case 'evidence':
      return `quality ${formatValue(d['quality_class'])}`
    case 'observation':
      return `${formatValue(d['fact_type'])} = ${formatValue(d['fact_value'])}`
    default:
      return node.id
  }
}

function shortId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 8)}…` : id
}

export function TraceGraph({
  nodes,
  edges,
}: {
  nodes: CognitiveTraceNode[]
  edges: { from: string; to: string; relation: string }[]
}) {
  const byType = new Map<CognitiveTraceNodeType, CognitiveTraceNode[]>()
  for (const node of nodes) {
    const list = byType.get(node.type) ?? []
    list.push(node)
    byType.set(node.type, list)
  }

  const layers = NODE_ORDER.filter((type) => byType.has(type))

  return (
    <div className="space-y-6">
      <div>
        <h3 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          <GitBranch className="h-4 w-4" /> Provenance chain
        </h3>
        <div className="flex flex-wrap items-stretch gap-2 overflow-x-auto pb-2">
          {layers.map((type, index) => {
            const meta = NODE_META[type]
            const layerNodes = byType.get(type) ?? []
            return (
              <div key={type} className="flex items-stretch gap-2">
                <div className="flex min-w-[180px] flex-col gap-2">
                  <div className="flex items-center justify-between">
                    <Badge className={meta.classes}>{meta.label}</Badge>
                    <span className="text-xs text-muted-foreground">{meta.family}</span>
                  </div>
                  {layerNodes.map((node) => (
                    <div
                      key={node.id}
                      className="rounded-md border border-border bg-background p-2"
                      title={node.id}
                    >
                      <p className="text-sm leading-snug">{nodeSummary(node)}</p>
                      <p className="mt-1 font-mono text-[10px] text-muted-foreground">
                        {shortId(node.id)}
                      </p>
                    </div>
                  ))}
                </div>
                {index < layers.length - 1 ? (
                  <div className="flex items-center text-muted-foreground" aria-hidden>
                    →
                  </div>
                ) : null}
              </div>
            )
          })}
        </div>
      </div>

      <div>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
          Relationships ({edges.length})
        </h3>
        {edges.length === 0 ? (
          <p className="text-sm text-muted-foreground">No relationships reconstructed.</p>
        ) : (
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full min-w-[520px] text-sm">
              <thead>
                <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                  <th className="px-3 py-2 font-medium">From</th>
                  <th className="px-3 py-2 font-medium">Relation</th>
                  <th className="px-3 py-2 font-medium">To</th>
                </tr>
              </thead>
              <tbody>
                {edges.map((edge, i) => (
                  <tr key={i} className="border-b border-border/60 last:border-0">
                    <td className="px-3 py-2 font-mono text-xs">{shortId(edge.from)}</td>
                    <td className="px-3 py-2">
                      <span className="rounded bg-muted px-1.5 py-0.5 font-mono text-xs">
                        {edge.relation}
                      </span>
                    </td>
                    <td className="px-3 py-2 font-mono text-xs">{shortId(edge.to)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  )
}

export function TraceWarnings({ warnings }: { warnings: string[] }) {
  if (warnings.length === 0) return null
  return (
    <div className="rounded-lg border border-amber-500/40 bg-amber-50 p-3 dark:bg-amber-950/30">
      <p className="flex items-center gap-2 text-sm font-medium text-amber-800 dark:text-amber-200">
        <AlertTriangle className="h-4 w-4" /> Provenance is partial
      </p>
      <ul className="mt-1 list-disc space-y-0.5 pl-6 text-xs text-amber-800 dark:text-amber-200">
        {warnings.map((w, i) => (
          <li key={i} className="font-mono">{w}</li>
        ))}
      </ul>
    </div>
  )
}
