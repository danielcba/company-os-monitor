import { useState, useRef, useEffect } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Bell, AlertTriangle, Info, XCircle } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { apiFetch } from '@/api/client'
import type { CognitiveAnomalyPage, CognitiveDecisionPage, ServicesHealthResponse, Notification, NotificationSeverity } from '@/types/cognitive'

function SeverityIcon({ severity }: { severity: NotificationSeverity }) {
  switch (severity) {
    case 'critical':
      return <XCircle className="h-4 w-4 text-red-500" />
    case 'warning':
      return <AlertTriangle className="h-4 w-4 text-amber-500" />
    case 'info':
      return <Info className="h-4 w-4 text-blue-500" />
  }
}

function buildNotifications(
  anomalies: CognitiveAnomalyPage | null,
  decisions: CognitiveDecisionPage | null,
  health: ServicesHealthResponse | null,
): Notification[] {
  const notifications: Notification[] = []

  if (anomalies) {
    for (const a of anomalies.anomalies) {
      if (a.deviation_score > 0.8) {
        notifications.push({
          id: `anomaly-${a.id}`,
          type: 'anomaly',
          severity: 'critical',
          title: `Critical anomaly: ${a.anomaly_class}`,
          message: `Deviation score: ${a.deviation_score.toFixed(2)} (threshold: ${a.tolerance_threshold})`,
          timestamp: a.detected_at,
          read: false,
          link: '/cognition/anomalies',
        })
      }
    }
  }

  if (decisions) {
    for (const d of decisions.decisions) {
      if (d.status === 'committed' && !d.executed_at) {
        notifications.push({
          id: `decision-${d.id}`,
          type: 'decision',
          severity: 'warning',
          title: 'Decision pending execution',
          message: d.commitment.slice(0, 80),
          timestamp: d.committed_at,
          read: false,
          link: '/action/decisions',
        })
      }
    }
  }

  if (health) {
    for (const s of health.services) {
      if (!s.healthy) {
        notifications.push({
          id: `health-${s.service}`,
          type: 'system',
          severity: 'critical',
          title: `Service down: ${s.service}`,
          message: s.error ?? `HTTP ${s.status}`,
          timestamp: new Date().toISOString(),
          read: false,
          link: '/dashboard',
        })
      }
    }
  }

  return notifications.sort((a, b) => {
    const sevOrder = { critical: 0, warning: 1, info: 2 }
    return (sevOrder[a.severity] ?? 3) - (sevOrder[b.severity] ?? 3)
  })
}

export function NotificationsCenter() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id
  const [open, setOpen] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  const { data: anomalies } = useQuery({
    queryKey: ['anomalies-for-notifications', tenantId],
    queryFn: () =>
      apiFetch<CognitiveAnomalyPage>(`/tenants/${tenantId}/anomalies?limit=50&sort=detected_at_desc`),
    enabled: Boolean(tenantId),
    refetchInterval: 60_000,
  })

  const { data: decisions } = useQuery({
    queryKey: ['decisions-for-notifications', tenantId],
    queryFn: () =>
      apiFetch<CognitiveDecisionPage>(`/tenants/${tenantId}/decisions?limit=50&sort=committed_at_desc`),
    enabled: Boolean(tenantId),
    refetchInterval: 60_000,
  })

  const { data: health } = useQuery({
    queryKey: ['services-health-notifications'],
    queryFn: () => apiFetch<ServicesHealthResponse>('/services/health'),
    refetchInterval: 30_000,
  })

  const notifications = buildNotifications(anomalies ?? null, decisions ?? null, health ?? null)
  const unreadCount = notifications.filter((n) => !n.read).length

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    if (open) document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [open])

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="relative rounded p-1.5 hover:bg-muted/40"
        aria-label={`Notifications${unreadCount > 0 ? ` (${unreadCount} unread)` : ''}`}
      >
        <Bell className="h-4 w-4 text-muted-foreground" />
        {unreadCount > 0 && (
          <span className="absolute -right-0.5 -top-0.5 flex h-4 min-w-4 items-center justify-center rounded-full bg-red-500 px-1 text-[10px] font-bold text-white">
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-1 w-80 max-h-96 overflow-y-auto rounded-md border border-border bg-background shadow-lg">
          <div className="border-b border-border px-3 py-2">
            <h3 className="text-sm font-semibold">Notifications</h3>
          </div>
          {notifications.length === 0 ? (
            <div className="px-3 py-4 text-center text-xs text-muted-foreground">
              No notifications
            </div>
          ) : (
            <div className="divide-y divide-border">
              {notifications.slice(0, 20).map((n) => (
                <a
                  key={n.id}
                  href={n.link}
                  onClick={() => setOpen(false)}
                  className="flex gap-2 px-3 py-2 hover:bg-muted/40"
                >
                  <SeverityIcon severity={n.severity} />
                  <div className="min-w-0 flex-1">
                    <p className="text-xs font-medium leading-tight">{n.title}</p>
                    <p className="truncate text-xs text-muted-foreground">{n.message}</p>
                    <p className="mt-0.5 text-[10px] text-muted-foreground">
                      {new Date(n.timestamp).toLocaleString()}
                    </p>
                  </div>
                </a>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
