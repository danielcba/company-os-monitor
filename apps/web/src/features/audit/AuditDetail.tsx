import { Shield, X } from 'lucide-react'
import type { AuditLogEntry } from '@/types/cognitive'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Field } from '@/components/ui/field'

function formatJson(obj: unknown): string {
  if (obj === null || obj === undefined) return '—'
  return JSON.stringify(obj, null, 2)
}

const COGNITIVE_TRACE_ROUTES: Record<string, string> = {
  observation: '/cognition/observations',
  evidence: '/cognition/evidence',
  context: '/cognition/contexts',
  pattern: '/cognition/patterns',
  anomaly: '/cognition/anomalies',
  hypothesis: '/cognition/hypotheses',
  confidence: '/cognition/confidence',
  recommendation: '/action/recommendations',
  decision: '/action/decisions',
}

export function AuditDetail({
  entry,
  onClose,
}: {
  entry: AuditLogEntry | null
  onClose: () => void
}) {
  if (!entry) return null

  const tracePath = COGNITIVE_TRACE_ROUTES[entry.cognitive_concept]

  return (
    <div
      role="dialog"
      aria-label="Audit entry detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <Shield className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Audit entry detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            This is an immutable episodic memory record. It captures what happened, when, and in
            which cognitive layer — never an interpretation.
          </div>

          <dl className="grid grid-cols-2 gap-4">
            <Field label="Timestamp" value={new Date(entry.timestamp).toLocaleString()} />
            <Field
              label="Cognitive layer"
              value={<Badge variant="outline">{entry.cognitive_layer}</Badge>}
            />
            <Field label="Concept" value={entry.cognitive_concept} />
            <Field label="Action" value={<Badge variant="outline">{entry.action}</Badge>} />
            <Field
              label="User"
              value={entry.user_id ? (
                <span className="font-mono text-xs">{entry.user_id}</span>
              ) : (
                <span className="italic text-muted-foreground">automated</span>
              )}
            />
            <Field
              label="Policy"
              value={entry.policy_id ? (
                <span className="font-mono text-xs">{entry.policy_id}</span>
              ) : (
                <span className="italic text-muted-foreground">—</span>
              )}
            />
          </dl>

          <dl className="grid grid-cols-1 gap-2">
            <Field label="Resource type" value={entry.resource_type} />
            <Field label="Resource id" value={<span className="font-mono text-xs">{entry.resource_id}</span>} />
          </dl>

          {entry.details && (
            <div>
              <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                Details
              </h3>
              <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs">
                {formatJson(entry.details)}
              </pre>
            </div>
          )}

          <dl className="grid grid-cols-1 gap-2">
            <Field
              label="IP address"
              value={entry.ip_address ?? <span className="italic text-muted-foreground">—</span>}
            />
            <Field
              label="User agent"
              value={entry.user_agent ?? <span className="italic text-muted-foreground">—</span>}
            />
          </dl>

          {tracePath && (
            <div>
              <a
                href={tracePath}
                className="inline-flex items-center gap-1 text-sm text-accent hover:underline"
              >
                View source {entry.cognitive_concept} →
              </a>
            </div>
          )}

          <dl className="grid grid-cols-1 gap-2">
            <Field label="Audit id" value={<span className="font-mono text-xs">{entry.id}</span>} />
            <Field label="Tenant id" value={<span className="font-mono text-xs">{entry.tenant_id}</span>} />
          </dl>
        </div>
      </div>
    </div>
  )
}
