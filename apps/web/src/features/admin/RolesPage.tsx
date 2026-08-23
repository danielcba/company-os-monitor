import { Shield } from 'lucide-react'
import { Badge } from '@/components/ui/badge'

const ROLES = [
  {
    name: 'viewer',
    description: 'Read-only access to cognitive pipeline data',
    permissions: ['read'],
  },
  {
    name: 'operator',
    description: 'Read + acknowledge pipeline artifacts',
    permissions: ['read', 'ack'],
  },
  {
    name: 'admin',
    description: 'Full pipeline access + user management within tenant',
    permissions: ['read', 'propose', 'ack', 'commit', 'define_policy'],
    riskCeiling: 'low, medium',
  },
  {
    name: 'superadmin',
    description: 'Cross-tenant authority + all permissions + user/tenant management',
    permissions: ['read', 'propose', 'ack', 'commit', 'execute', 'define_policy', 'cross_tenant'],
    riskCeiling: 'low, medium, high',
  },
]

const PERMISSION_LABELS: Record<string, string> = {
  read: 'Read pipeline data',
  ack: 'Acknowledge artifacts',
  propose: 'Propose actions',
  commit: 'Commit decisions',
  execute: 'Execute decisions',
  define_policy: 'Define policies',
  cross_tenant: 'Cross-tenant access',
}

export function RolesPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-xl font-semibold flex items-center gap-2">
          <Shield className="h-5 w-5 text-muted-foreground" />
          Roles &amp; Permissions
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Decision Authority roles define what actions each identity can take in the cognitive pipeline.
          RBAC is enforced by the API Gateway (R3).
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {ROLES.map((role) => (
          <div key={role.name} className="rounded-lg border border-border bg-card p-4">
            <div className="mb-2 flex items-center gap-2">
              <Badge variant="outline" className="text-sm font-semibold">
                {role.name}
              </Badge>
            </div>
            <p className="mb-3 text-sm text-muted-foreground">{role.description}</p>
            <div className="space-y-1">
              {role.permissions.map((perm) => (
                <div key={perm} className="flex items-center gap-2 text-sm">
                  <span className="h-1.5 w-1.5 rounded-full bg-green-500" />
                  {PERMISSION_LABELS[perm] ?? perm}
                </div>
              ))}
            </div>
            {role.riskCeiling && (
              <div className="mt-3 border-t border-border pt-2">
                <span className="text-xs text-muted-foreground">Risk ceiling for COMMIT: </span>
                <span className="text-xs font-medium">{role.riskCeiling}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}

export default RolesPage
