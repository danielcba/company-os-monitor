import { useQuery } from '@tanstack/react-query'
import { Gauge, ShieldCheck, Target, TrendingUp, AlertTriangle } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchConfidenceSummary } from '@/api/gateway'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingState, ErrorState, NotAvailable } from '@/components/ui/state'

function confidenceLevel(value: number): { label: string; tone: string } {
  if (value >= 0.75) return { label: 'Alto', tone: 'bg-emerald-500/15 text-emerald-700' }
  if (value >= 0.5) return { label: 'Medio', tone: 'bg-amber-500/15 text-amber-700' }
  return { label: 'Bajo', tone: 'bg-red-500/15 text-red-700' }
}

function RowMetric({
  label,
  value,
  icon,
}: {
  label: string
  value: string
  icon: React.ReactNode
}) {
  return (
    <div className="flex items-center gap-2 rounded-md border border-border bg-muted/30 px-3 py-2">
      <span className="text-muted-foreground">{icon}</span>
      <div className="min-w-0">
        <p className="text-[10px] uppercase tracking-wide text-muted-foreground">{label}</p>
        <p className="truncate text-sm font-semibold tabular-nums">{value}</p>
      </div>
    </div>
  )
}

/**
 * TrustValuePanel — la pieza central de la visión COS-Monitor:
 * un único valor de confianza agregado, fundamentado en el resumen de
 * calibración del pipeline (confidence/summary). No inventa métricas:
 * usa los promedios que ya calcula el calibrator.
 */
export function TrustValuePanel() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id

  const { data, isPending, isError, error } = useQuery({
    queryKey: ['trust-value', 'confidence-summary', tenantId],
    queryFn: () => fetchConfidenceSummary(tenantId!),
    enabled: Boolean(tenantId),
  })

  if (isPending) return <LoadingState label="Computing trust value…" />
  if (isError)
    return <ErrorState message={error instanceof Error ? error.message : undefined} />

  if (!data || data.total === 0) {
    return (
      <Card>
        <CardContent className="p-5">
          <NotAvailable label="Aún no hay calibración calculada para este tenant." />
        </CardContent>
      </Card>
    )
  }

  const a = data.averages
  const trust = a.confidence
  const level = confidenceLevel(trust)

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between gap-3">
        <CardTitle className="flex items-center gap-2 text-sm">
          <ShieldCheck className="h-4 w-4 text-muted-foreground" />
          Valor de Confianza
        </CardTitle>
        <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${level.tone}`}>
          {level.label}
        </span>
      </CardHeader>

      <CardContent className="space-y-4">
        <div className="flex items-center gap-4">
          <div className="flex h-20 w-20 shrink-0 items-center justify-center rounded-full border-4 border-emerald-500/40 bg-muted/40">
            <span className="text-2xl font-bold tabular-nums">{trust.toFixed(2)}</span>
          </div>
          <div className="min-w-0 space-y-0.5">
            <p className="text-xs text-muted-foreground">
              Confianza promedio (C_final) de los juicios calibrados del pipeline.
            </p>
            <p className="text-xs text-muted-foreground">
              {data.total.toLocaleString()} juicio{data.total === 1 ? '' : 's'} calibrado
              {data.total === 1 ? '' : 's'}.
            </p>
          </div>
        </div>

        <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
          <RowMetric label="Soporte S" value={a.support.toFixed(3)} icon={<Target className="h-3.5 w-3.5" />} />
          <RowMetric label="Coherencia C" value={a.coherence.toFixed(3)} icon={<Gauge className="h-3.5 w-3.5" />} />
          <RowMetric
            label="Calibración 1−ECE"
            value={a.historical_calibration.toFixed(3)}
            icon={<TrendingUp className="h-3.5 w-3.5" />}
          />
          <RowMetric label="Error ECE" value={a.ece.toFixed(3)} icon={<AlertTriangle className="h-3.5 w-3.5" />} />
        </div>

        <p className="text-[11px] leading-relaxed text-muted-foreground">
          La confianza se computa, no se intuye: cada fila registra C_final con su
          justificación (soporte, coherencia, calibración, α). Es una estimación
          calibrada de fiabilidad, no «probabilidad de que la hipótesis sea cierta».
          {data.range ? ` Rango C_final: ${data.range.min_confidence.toFixed(3)}–${data.range.max_confidence.toFixed(3)}.` : ''}
        </p>
      </CardContent>
    </Card>
  )
}

export default TrustValuePanel
