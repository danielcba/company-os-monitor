import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/use-auth'
import {
  fetchAnomalies,
  fetchDecisions,
  fetchHypotheses,
  fetchInsights,
  fetchRecommendations,
} from '@/api/gateway'

export interface CommandItem {
  id: string
  type: 'navigation' | 'action' | 'entity'
  label: string
  description?: string
  icon?: string
  href?: string
  action?: () => void
  category: string
}

interface CommandPaletteContextValue {
  isOpen: boolean
  query: string
  selectedIndex: number
  items: CommandItem[]
  isLoading: boolean
  open: () => void
  close: () => void
  toggle: () => void
  onHoverItem: (index: number) => void
  handleQueryChange: (value: string) => void
  handleKeyDown: (e: React.KeyboardEvent) => void
  executeItem: (item: CommandItem) => void
}

const CommandPaletteContext = createContext<CommandPaletteContextValue | undefined>(undefined)

const NAVIGATION_ITEMS: CommandItem[] = [
  { id: 'nav-dashboard', type: 'navigation', label: 'Dashboard', href: '/dashboard', category: 'Navigation', icon: 'layout-dashboard' },
  { id: 'nav-observations', type: 'navigation', label: 'Observations', href: '/cognition/observations', category: 'Cognition', icon: 'activity' },
  { id: 'nav-evidence', type: 'navigation', label: 'Evidence', href: '/cognition/evidence', category: 'Cognition', icon: 'activity' },
  { id: 'nav-contexts', type: 'navigation', label: 'Contexts', href: '/cognition/contexts', category: 'Cognition', icon: 'radar' },
  { id: 'nav-patterns', type: 'navigation', label: 'Patterns', href: '/cognition/patterns', category: 'Cognition', icon: 'repeat' },
  { id: 'nav-anomalies', type: 'navigation', label: 'Anomalies', href: '/cognition/anomalies', category: 'Cognition', icon: 'radar' },
  { id: 'nav-hypotheses', type: 'navigation', label: 'Hypotheses', href: '/cognition/hypotheses', category: 'Cognition', icon: 'brain' },
  { id: 'nav-insights', type: 'navigation', label: 'Insights', href: '/cognition/insights', category: 'Cognition', icon: 'lightbulb' },
  { id: 'nav-confidence', type: 'navigation', label: 'Confidence', href: '/cognition/confidence', category: 'Cognition', icon: 'gauge' },
  { id: 'nav-recommendations', type: 'navigation', label: 'Recommendations', href: '/action/recommendations', category: 'Action', icon: 'compass' },
  { id: 'nav-decisions', type: 'navigation', label: 'Decisions', href: '/action/decisions', category: 'Action', icon: 'brain' },
  { id: 'nav-reports', type: 'navigation', label: 'Reports', href: '/action/reports', category: 'Action', icon: 'file-text' },
  { id: 'nav-audit', type: 'navigation', label: 'Audit Log', href: '/cognition/audit', category: 'Cognition', icon: 'shield' },
  { id: 'nav-search', type: 'navigation', label: 'Global Search', href: '/search', category: 'Tools', icon: 'search' },
]

export function CommandPaletteProvider({ children }: { children: ReactNode }) {
  const [isOpen, setIsOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [selectedIndex, setSelectedIndex] = useState(0)
  const [entityResults, setEntityResults] = useState<CommandItem[]>([])
  const [isLoading, setIsLoading] = useState(false)
  const navigate = useNavigate()
  const { user } = useAuth()
  const tenantId = user?.tenant_id
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  const open = useCallback(() => {
    setIsOpen(true)
    setQuery('')
    setSelectedIndex(0)
    setEntityResults([])
  }, [])

  const close = useCallback(() => {
    setIsOpen(false)
    setQuery('')
    setSelectedIndex(0)
    setEntityResults([])
  }, [])

  const toggle = useCallback(() => {
    if (isOpen) close()
    else open()
  }, [isOpen, open, close])

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault()
        toggle()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [toggle])

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current)
    }
  }, [])

  const searchEntities = useCallback(
    async (searchQuery: string) => {
      if (!tenantId || searchQuery.length < 2) {
        setEntityResults([])
        return
      }
      setIsLoading(true)
      try {
        const results: CommandItem[] = []
        const q = searchQuery.toLowerCase()

        const fetches: Promise<void>[] = []

        fetches.push(
          fetchAnomalies(tenantId, { limit: 10 }).then((data) => {
            data.anomalies.forEach((a) => {
              if (a.anomaly_class.toLowerCase().includes(q) || a.id.toLowerCase().includes(q)) {
                results.push({
                  id: `anomaly-${a.id}`,
                  type: 'entity',
                  label: `Anomaly: ${a.anomaly_class}`,
                  description: `deviation ${a.deviation_score.toFixed(2)} · ${new Date(a.detected_at).toLocaleDateString()}`,
                  href: '/cognition/anomalies',
                  category: 'Anomalies',
                  icon: 'radar',
                })
              }
            })
          }),
        )

        fetches.push(
          fetchHypotheses(tenantId, { limit: 10 }).then((data) => {
            data.hypotheses.forEach((h) => {
              if (h.description.toLowerCase().includes(q) || h.id.toLowerCase().includes(q)) {
                results.push({
                  id: `hypothesis-${h.id}`,
                  type: 'entity',
                  label: `Hypothesis: ${h.description.slice(0, 60)}`,
                  description: `${h.status} · coherence ${h.coherence_score.toFixed(2)}`,
                  href: '/cognition/hypotheses',
                  category: 'Hypotheses',
                  icon: 'brain',
                })
              }
            })
          }),
        )

        fetches.push(
          fetchDecisions(tenantId, { limit: 10 }).then((data) => {
            data.decisions.forEach((d) => {
              if (d.commitment.toLowerCase().includes(q) || d.id.toLowerCase().includes(q)) {
                results.push({
                  id: `decision-${d.id}`,
                  type: 'entity',
                  label: `Decision: ${d.commitment.slice(0, 60)}`,
                  description: `${d.status} · ${new Date(d.committed_at).toLocaleDateString()}`,
                  href: '/action/decisions',
                  category: 'Decisions',
                  icon: 'brain',
                })
              }
            })
          }),
        )

        fetches.push(
          fetchInsights(tenantId, { limit: 10 }).then((data) => {
            data.insights.forEach((i) => {
              if (i.description.toLowerCase().includes(q) || i.id.toLowerCase().includes(q)) {
                results.push({
                  id: `insight-${i.id}`,
                  type: 'entity',
                  label: `Insight: ${i.description.slice(0, 60)}`,
                  description: `${i.hypothesis_ids.length} hypotheses · ${new Date(i.generated_at).toLocaleDateString()}`,
                  href: '/cognition/insights',
                  category: 'Insights',
                  icon: 'lightbulb',
                })
              }
            })
          }),
        )

        fetches.push(
          fetchRecommendations(tenantId, { limit: 10 }).then((data) => {
            data.recommendations.forEach((r) => {
              if (r.action_description.toLowerCase().includes(q) || r.id.toLowerCase().includes(q)) {
                results.push({
                  id: `recommendation-${r.id}`,
                  type: 'entity',
                  label: `Recommendation: ${r.action_description.slice(0, 60)}`,
                  description: `${r.status} · confidence ${r.confidence_score.toFixed(4)}`,
                  href: '/action/recommendations',
                  category: 'Recommendations',
                  icon: 'compass',
                })
              }
            })
          }),
        )

        await Promise.all(fetches)
        setEntityResults(results)
      } catch {
        setEntityResults([])
      } finally {
        setIsLoading(false)
      }
    },
    [tenantId],
  )

  const handleQueryChange = useCallback(
    (value: string) => {
      setQuery(value)
      setSelectedIndex(0)
      if (debounceRef.current) clearTimeout(debounceRef.current)
      debounceRef.current = setTimeout(() => {
        void searchEntities(value)
      }, 300)
    },
    [searchEntities],
  )

  const allItems = useMemo(() => {
    if (query.length < 2) return NAVIGATION_ITEMS
    const q = query.toLowerCase()
    const navFiltered = NAVIGATION_ITEMS.filter(
      (item) => item.label.toLowerCase().includes(q) || item.category.toLowerCase().includes(q),
    )
    return [...entityResults, ...navFiltered]
  }, [query, entityResults])

  const executeItem = useCallback(
    (item: CommandItem) => {
      if (item.action) item.action()
      else if (item.href) navigate(item.href)
      close()
    },
    [navigate, close],
  )

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'ArrowDown') {
        e.preventDefault()
        setSelectedIndex((prev) => Math.min(prev + 1, allItems.length - 1))
      } else if (e.key === 'ArrowUp') {
        e.preventDefault()
        setSelectedIndex((prev) => Math.max(prev - 1, 0))
      } else if (e.key === 'Enter') {
        e.preventDefault()
        const item = allItems[selectedIndex]
        if (item) executeItem(item)
      } else if (e.key === 'Escape') {
        close()
      }
    },
    [allItems, selectedIndex, executeItem, close],
  )

  const onHoverItem = useCallback((index: number) => {
    setSelectedIndex(index)
  }, [])

  const value = useMemo<CommandPaletteContextValue>(
    () => ({
      isOpen,
      query,
      selectedIndex,
      items: allItems,
      isLoading,
      open,
      close,
      toggle,
      onHoverItem,
      handleQueryChange,
      handleKeyDown,
      executeItem,
    }),
    [isOpen, query, selectedIndex, allItems, isLoading, open, close, toggle, onHoverItem, handleQueryChange, handleKeyDown, executeItem],
  )

  return (
    <CommandPaletteContext.Provider value={value}>
      {children}
    </CommandPaletteContext.Provider>
  )
}

export function useCommandPalette(): CommandPaletteContextValue {
  const ctx = useContext(CommandPaletteContext)
  if (!ctx) throw new Error('useCommandPalette must be used within a CommandPaletteProvider')
  return ctx
}
