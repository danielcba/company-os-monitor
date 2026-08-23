import { useQuery } from '@tanstack/react-query'
import { Server, Activity } from 'lucide-react'
import { apiFetch } from '@/api/client'
import { ServiceHealthPanel } from '@/components/infrastructure/ServiceHealthPanel'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { LoadingState, ErrorState } from '@/components/ui/state'

interface GatewayMetrics {
  total_requests: number
  total_rejected_401: number
  total_rejected_403: number
  total_boundary_violations: number
  total_forwarded: number
  total_errors: number
  requests_by_action: Record<string, number>
  last_request_at: string | null
}

interface UserMetrics {
  total_logins: number
  total_login_failures: number
  total_tokens_issued: number
  total_errors: number
  total_users_created: number
  users_by_role: Record<string, number>
  last_login_at: string | null
}

export function SystemPage() {
  const { data: gatewayMetrics, isPending: gwPending, isError: gwError, error: gwErr } = useQuery({
    queryKey: ['gateway-metrics'],
    queryFn: () => apiFetch<GatewayMetrics>('/services/health'),
    refetchInterval: 30_000,
  })

  const { data: userMetrics, isPending: uPending, isError: uError, error: uErr } = useQuery({
    queryKey: ['user-metrics'],
    queryFn: () => apiFetch<UserMetrics>('/user/metrics'),
    refetchInterval: 30_000,
  })

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <Server className="h-5 w-5 text-muted-foreground" />
          System
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Infrastructure health, gateway metrics, and user service metrics.
        </p>
      </div>

      <ServiceHealthPanel />

      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Activity className="h-4 w-4" />
              API Gateway
            </CardTitle>
          </CardHeader>
          <CardContent>
            {gwPending ? (
              <LoadingState label="Loading…" />
            ) : gwError ? (
              <ErrorState message={gwErr instanceof Error ? gwErr.message : undefined} />
            ) : gatewayMetrics ? (
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <div><dt className="text-muted-foreground">Requests</dt><dd className="font-medium">{gatewayMetrics.total_requests.toLocaleString()}</dd></div>
                <div><dt className="text-muted-foreground">Forwarded</dt><dd className="font-medium">{gatewayMetrics.total_forwarded.toLocaleString()}</dd></div>
                <div><dt className="text-muted-foreground">Rejected (401)</dt><dd className="font-medium">{gatewayMetrics.total_rejected_401.toLocaleString()}</dd></div>
                <div><dt className="text-muted-foreground">Rejected (403)</dt><dd className="font-medium">{gatewayMetrics.total_rejected_403.toLocaleString()}</dd></div>
                <div><dt className="text-muted-foreground">Boundary violations</dt><dd className="font-medium">{gatewayMetrics.total_boundary_violations.toLocaleString()}</dd></div>
                <div><dt className="text-muted-foreground">Errors</dt><dd className="font-medium">{gatewayMetrics.total_errors.toLocaleString()}</dd></div>
              </dl>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-sm">
              <Activity className="h-4 w-4" />
              User Service
            </CardTitle>
          </CardHeader>
          <CardContent>
            {uPending ? (
              <LoadingState label="Loading…" />
            ) : uError ? (
              <ErrorState message={uErr instanceof Error ? uErr.message : undefined} />
            ) : userMetrics ? (
              <dl className="grid grid-cols-2 gap-2 text-sm">
                <div><dt className="text-muted-foreground">Logins</dt><dd className="font-medium">{userMetrics.total_logins.toLocaleString()}</dd></div>
                <div><dt className="text-muted-foreground">Login failures</dt><dd className="font-medium">{userMetrics.total_login_failures.toLocaleString()}</dd></div>
                <div><dt className="text-muted-foreground">Tokens issued</dt><dd className="font-medium">{userMetrics.total_tokens_issued.toLocaleString()}</dd></div>
                <div><dt className="text-muted-foreground">Users created</dt><dd className="font-medium">{userMetrics.total_users_created.toLocaleString()}</dd></div>
                <div className="col-span-2">
                  <dt className="text-muted-foreground">Users by role</dt>
                  <dd className="flex flex-wrap gap-1 pt-1">
                    {Object.entries(userMetrics.users_by_role).map(([role, count]) => (
                      <Badge key={role} variant="outline">{role}: {count}</Badge>
                    ))}
                  </dd>
                </div>
              </dl>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

export default SystemPage
