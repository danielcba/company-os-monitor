import { FileJson, X } from 'lucide-react'
import type { Observation } from '@/types/cognitive'
import { Button } from '@/components/ui/button'
import { QualityClassBadge } from '@/components/cognitive/QualityClassBadge'
import { formatJson } from '@/features/observations/format'
import { Field } from '@/components/ui/field'

export function ObservationDetail({
  observation,
  onClose,
}: {
  observation: Observation | null
  onClose: () => void
}) {
  if (!observation) return null
  return (
    <div
      role="dialog"
      aria-label="Observation detail"
      className="fixed inset-0 z-40 flex justify-end bg-black/40"
      onClick={onClose}
    >
      <div
        className="flex h-full w-full max-w-lg flex-col overflow-y-auto bg-background shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-border p-4">
          <div className="flex items-center gap-2">
            <FileJson className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">Observation detail</h2>
          </div>
          <Button variant="ghost" size="sm" aria-label="Close" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        <div className="space-y-4 p-4">
          <div className="rounded-md border border-border bg-muted/30 p-3 text-xs text-muted-foreground">
            This is a raw fact captured from the infrastructure — never an interpretation. The
            pipeline may later organize it into Evidence; the UI never reinterprets it.
          </div>

          <dl className="grid grid-cols-2 gap-4">
            <Field label="Fact type" value={observation.fact_type} />
            <Field label="Unit" value={observation.unit || <span className="italic text-muted-foreground">—</span>} />
            <Field label="Captured at" value={new Date(observation.captured_at).toLocaleString()} />
            <Field label="Quality class" value={<QualityClassBadge qualityClass={observation.quality_class} />} />
            <Field label="Source type" value={observation.source_type} />
            <Field label="Source id" value={<span className="font-mono text-xs">{observation.source_id}</span>} />
          </dl>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Fact value
            </h3>
            <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs">
              {formatJson(observation.fact_value)}
            </pre>
          </div>

          <div>
            <h3 className="mb-1 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
              Raw payload
            </h3>
            <pre className="overflow-x-auto rounded-md border border-border bg-muted/30 p-3 font-mono text-xs">
              {formatJson(observation.raw_payload)}
            </pre>
          </div>

          <dl className="grid grid-cols-1 gap-2">
            <Field label="Observation id" value={<span className="font-mono text-xs">{observation.id}</span>} />
            <Field label="Tenant id" value={<span className="font-mono text-xs">{observation.tenant_id}</span>} />
          </dl>
        </div>
      </div>
    </div>
  )
}