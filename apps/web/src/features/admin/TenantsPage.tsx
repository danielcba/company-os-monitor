import { useQuery } from '@tanstack/react-query'
import { Building2 } from 'lucide-react'
import { fetchTenants } from '@/api/gateway'
import { LoadingState, ErrorState, EmptyState } from '@/components/ui/state'
import { ApiError } from '@/types/cognitive'

export function TenantsPage() {
  const { data, isPending, isError, error } = useQuery({
    queryKey: ['tenants'],
    queryFn: fetchTenants,
  })

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <Building2 className="h-5 w-5 text-muted-foreground" />
          Tenants
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Multi-tenant isolation scopes all cognitive data. Each tenant has its own
          pipeline, users, and audit trail.
        </p>
      </div>

      {isPending ? (
        <LoadingState label="Loading tenants…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <EmptyState title="Access denied" description="Superadmin authority required to view tenants." />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.tenants.length === 0 ? (
        <EmptyState title="No tenants" description="No tenants found." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[600px] text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Slug</th>
                <th className="px-3 py-2 font-medium">Created</th>
                <th className="px-3 py-2 font-medium">ID</th>
              </tr>
            </thead>
            <tbody>
              {data.tenants.map((tenant) => (
                <tr key={tenant.id} className="border-b border-border/60 last:border-0">
                  <td className="px-3 py-2 font-medium">{tenant.name}</td>
                  <td className="px-3 py-2 text-muted-foreground">{tenant.slug}</td>
                  <td className="px-3 py-2 tabular-nums text-muted-foreground">
                    {new Date(tenant.created_at).toLocaleDateString()}
                  </td>
                  <td className="max-w-[120px] truncate px-3 py-2 font-mono text-xs text-muted-foreground">
                    {tenant.id}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export default TenantsPage
