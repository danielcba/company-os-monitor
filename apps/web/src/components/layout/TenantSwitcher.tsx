import { useState, useRef, useEffect, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { ChevronDown, Check } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { fetchTenants } from '@/api/gateway'
import { Badge } from '@/components/ui/badge'

export function TenantSwitcher() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id
  const isSuperadmin = user?.role === 'superadmin'

  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const { data } = useQuery({
    queryKey: ['tenants'],
    queryFn: fetchTenants,
    enabled: isSuperadmin,
  })

  const selectedTenant = useMemo(() => {
    if (data?.tenants && tenantId) {
      const current = data.tenants.find((t) => t.id === tenantId)
      if (current) return { id: current.id, name: current.name }
    }
    return null
  }, [data, tenantId])

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  if (!isSuperadmin) {
    return (
      <div className="hidden items-center gap-2 text-sm sm:flex">
        <Badge variant="outline" title="Tenant scope enforced by the API Gateway (R3)">
          {tenantId ? `Tenant ${tenantId.slice(0, 8)}` : 'No tenant'}
        </Badge>
      </div>
    )
  }

  const tenants = data?.tenants ?? []

  return (
    <div className="relative hidden text-sm sm:block" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 rounded border border-border px-2 py-1 text-sm hover:bg-muted/40"
        title="Switch tenant (superadmin)"
      >
        <span className="max-w-[120px] truncate">
          {selectedTenant?.name ?? `Tenant ${tenantId?.slice(0, 8) ?? '?'}`}
        </span>
        <ChevronDown className="h-3 w-3 text-muted-foreground" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 max-h-64 w-64 overflow-y-auto rounded-md border border-border bg-background shadow-lg">
          <div className="p-1">
            {tenants.length === 0 ? (
              <div className="px-2 py-1.5 text-xs text-muted-foreground">No tenants available</div>
            ) : (
              tenants.map((tenant) => (
                <button
                  key={tenant.id}
                  type="button"
                  onClick={() => {
                    setOpen(false)
                  }}
                  className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-left text-sm hover:bg-muted/40"
                >
                  <div className="flex min-w-0 flex-1 flex-col">
                    <span className="truncate font-medium">{tenant.name}</span>
                    <span className="truncate text-xs text-muted-foreground">{tenant.slug} · {tenant.plan}</span>
                  </div>
                  {tenant.id === tenantId && <Check className="h-4 w-4 shrink-0 text-accent" />}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  )
}
