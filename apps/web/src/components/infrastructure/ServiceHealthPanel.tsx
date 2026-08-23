import { useQuery } from '@tanstack/react-query'
import { fetchServicesHealth } from '@/api/gateway'
import type { ServiceHealth } from '@/types/cognitive'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { LoadingState, ErrorState } from '@/components/ui/state'

const FAMILIES: Record<string, string> = {
  'linux-agent': 'Perception',
  collector: 'Perception',
  context: 'Perception',
  pattern: 'Reasoning',
  anomaly: 'Reasoning',
  hypothesis: 'Reasoning',
  confidence: 'Learning',
  recommendation: 'Action',
  decision: 'Action',
  report: 'External (ADR-0002)',
  user: 'External (ADR-0002)',
  gateway: 'Cognitive Boundary (R3)',
}

function statusVariant(healthy: boolean): 'success' | 'warning' | 'destructive' | 'default' {
  if (healthy) return 'success'
  return 'destructive'
}

function ServiceRow({ service }: { service: ServiceHealth }) {
  return (
    <li className="flex items-center justify-between gap-2 rounded-md border border-border px-3 py-2">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium">{service.service}</p>
        <p className="text-xs text-muted-foreground">
          {FAMILIES[service.service] ?? 'Service'}
        </p>
      </div>
      <Badge variant={statusVariant(service.healthy)}>
        {service.healthy ? 'healthy' : service.error ?? `unreachable (${service.status})`}
      </Badge>
    </li>
  )
}

export function ServiceHealthPanel() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['services', 'health'],
    queryFn: fetchServicesHealth,
    refetchInterval: 30_000,
  })

  if (isPending) return <LoadingState label="Checking service health…" />
  if (isError) return <ErrorState message={error instanceof Error ? error.message : undefined} />
  if (!data || data.services.length === 0) {
    return <p className="text-sm text-muted-foreground">No service health data available.</p>
  }

  const total = data.services.length
  const healthy = data.services.filter((s) => s.healthy).length

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cognitive Pipeline Health</CardTitle>
        <p className="text-sm text-muted-foreground">
          {healthy} of {total} services healthy · reported by the API Gateway
        </p>
      </CardHeader>
      <CardContent>
        <ul className="space-y-1.5">
          {data.services.map((service) => (
            <ServiceRow key={service.service} service={service} />
          ))}
        </ul>
      </CardContent>
    </Card>
  )
}