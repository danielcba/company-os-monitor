import { NavLink } from 'react-router-dom'
import { cn } from '@/lib/utils'
import {
  Activity,
  BookOpen,
  Brain,
  Compass,
  FileText,
  Gauge,
  History,
  LayoutDashboard,
  Lightbulb,
  Radar,
  Repeat,
  Search,
  Settings,
  Shield,
  Users,
  Building2,
  Server,
  ShieldCheck,
} from 'lucide-react'

interface NavItem {
  to: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  active?: boolean
  planned?: boolean
}

const cognitionItems: NavItem[] = [
  { to: '/cognition/observations', label: 'Observations', icon: Activity },
  { to: '/cognition/evidence', label: 'Evidence', icon: Activity },
  { to: '/cognition/contexts', label: 'Contexts', icon: Radar },
  { to: '/cognition/patterns', label: 'Patterns', icon: Repeat },
  { to: '/cognition/anomalies', label: 'Anomalies', icon: Radar },
  { to: '/cognition/hypotheses', label: 'Hypotheses', icon: Brain },
  { to: '/cognition/insights', label: 'Insights', icon: Lightbulb },
  { to: '/cognition/confidence', label: 'Confidence', icon: Gauge },
  { to: '/cognition/audit', label: 'Audit Log', icon: Shield },
]

const actionItems: NavItem[] = [
  { to: '/action/recommendations', label: 'Recommendations', icon: Compass },
  { to: '/action/decisions', label: 'Decisions', icon: Brain },
  { to: '/action/reports', label: 'Reports', icon: FileText },
]

const adminItems: NavItem[] = [
  { to: '/administration/users', label: 'Users', icon: Users },
  { to: '/administration/roles', label: 'Roles', icon: ShieldCheck },
  { to: '/administration/tenants', label: 'Tenants', icon: Building2 },
  { to: '/administration/system', label: 'System', icon: Server },
]

const learningItems: NavItem[] = [
  { to: '/learning', label: 'Learning (P7)', icon: BookOpen },
]

const investigationItems: NavItem[] = [
  { to: '/investigation/timeline', label: 'Cognitive Timeline', icon: History },
]

function NavItemLink({ item }: { item: NavItem }) {
  if (item.planned) {
    return (
      <span
        title="Planned — endpoint not available yet"
        className={cn(
          'flex items-center gap-2 rounded px-2 py-1.5 text-sm text-muted-foreground',
          'opacity-60 cursor-not-allowed select-none',
        )}
      >
        <item.icon className="h-4 w-4" />
        {item.label}
        <span className="ml-auto text-[10px] uppercase tracking-wide opacity-70">planned</span>
      </span>
    )
  }
  return (
    <NavLink
      to={item.to}
      className={({ isActive }) =>
        cn(
          'flex items-center gap-2 rounded px-2 py-1.5 text-sm transition-colors',
          isActive ? 'bg-accent text-accent-foreground' : 'text-sidebar-foreground hover:bg-white/10',
        )
      }
    >
      <item.icon className="h-4 w-4" />
      {item.label}
    </NavLink>
  )
}

function NavGroup({ title, items }: { title: string; items: NavItem[] }) {
  return (
    <div className="space-y-1">
      <p className="px-2 text-xs font-semibold uppercase tracking-wider text-sidebar-foreground/60">
        {title}
      </p>
      {items.map((item) => (
        <NavItemLink key={item.to} item={item} />
      ))}
    </div>
  )
}

export function Sidebar() {
  return (
    <aside className="hidden w-64 shrink-0 flex-col bg-sidebar text-sidebar-foreground md:flex">
      <div className="flex items-center gap-2 border-b border-sidebar px-4 py-4">
        <div className="flex h-8 w-8 items-center justify-center rounded bg-accent">
          <Brain className="h-5 w-5 text-accent-foreground" />
        </div>
        <div className="leading-tight">
          <p className="text-sm font-semibold">COS-Monitor</p>
          <p className="text-xs text-sidebar-foreground/60">Cognitive OS Monitor</p>
        </div>
      </div>
      <nav className="flex-1 space-y-6 overflow-y-auto p-3">
        <NavGroup
          title="Overview"
          items={[
            { to: '/dashboard', label: 'Dashboard', icon: LayoutDashboard },
            { to: '/search', label: 'Search', icon: Search },
          ]}
        />
        <NavGroup title="Cognition" items={cognitionItems} />
        <NavGroup title="Action" items={actionItems} />
        <NavGroup title="Learning" items={learningItems} />
        <NavGroup title="Investigation" items={investigationItems} />
        <NavGroup title="Administration" items={adminItems} />
      </nav>
      <div className="border-t border-sidebar p-3">
        <div className="flex items-center gap-2 px-2 text-xs text-sidebar-foreground/60">
          <Settings className="h-4 w-4" />
          Settings
          <span className="ml-auto text-[10px] uppercase tracking-wide opacity-70">planned</span>
        </div>
      </div>
    </aside>
  )
}