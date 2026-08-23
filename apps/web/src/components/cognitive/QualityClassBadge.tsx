import { Badge } from '@/components/ui/badge'
import type { QualityClass } from '@/types/cognitive'
import { QUALITY_CLASS_LABELS, QUALITY_CLASS_ORDER } from '@/lib/quality-class'

const variantClasses: Record<QualityClass, string> = {
  Q1: 'border-emerald-500/40 bg-emerald-100 text-emerald-900 dark:bg-emerald-900/40 dark:text-emerald-200',
  Q2: 'border-sky-500/40 bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-200',
  Q3: 'border-amber-500/40 bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200',
  Q4: 'border-red-500/40 bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200',
}

export function QualityClassBadge({ qualityClass }: { qualityClass: QualityClass }) {
  const label = QUALITY_CLASS_LABELS[qualityClass]
  return (
    <Badge
      variant="outline"
      className={variantClasses[qualityClass]}
      title={`${qualityClass} — ${label}`}
    >
      {qualityClass}
    </Badge>
  )
}

export function QualityClassLegend() {
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
      {QUALITY_CLASS_ORDER.map((qc) => (
        <span key={qc} className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full border border-border" />
          <span>
            {qc} — {QUALITY_CLASS_LABELS[qc]}
          </span>
        </span>
      ))}
    </div>
  )
}