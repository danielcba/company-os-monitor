import { useEffect, useRef } from 'react'
import {
  Activity,
  Brain,
  Compass,
  FileText,
  Gauge,
  LayoutDashboard,
  Lightbulb,
  Radar,
  Repeat,
  Search,
  Shield,
} from 'lucide-react'
import { cn } from '@/lib/utils'
import { useCommandPalette, type CommandItem } from './CommandPaletteContext'

const ICON_MAP: Record<string, React.ComponentType<{ className?: string }>> = {
  'layout-dashboard': LayoutDashboard,
  activity: Activity,
  radar: Radar,
  repeat: Repeat,
  brain: Brain,
  lightbulb: Lightbulb,
  gauge: Gauge,
  compass: Compass,
  'file-text': FileText,
  shield: Shield,
  search: Search,
}

function CommandIcon({ icon }: { icon?: string }) {
  if (!icon) return null
  const Icon = ICON_MAP[icon]
  if (!Icon) return null
  return <Icon className="h-4 w-4 text-muted-foreground" />
}

export function CommandPalette() {
  const {
    isOpen,
    query,
    selectedIndex,
    items,
    isLoading,
    close,
    onHoverItem,
    handleQueryChange,
    handleKeyDown,
    executeItem,
  } = useCommandPalette()

  const inputRef = useRef<HTMLInputElement>(null)
  const listRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (isOpen) inputRef.current?.focus()
  }, [isOpen])

  useEffect(() => {
    const selected = listRef.current?.children[selectedIndex] as HTMLElement
    if (selected) selected.scrollIntoView({ block: 'nearest' })
  }, [selectedIndex])

  if (!isOpen) return null

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Command palette"
      className="fixed inset-0 z-50 flex items-start justify-center bg-black/50 pt-[15vh]"
      onClick={close}
    >
      <div
        className="w-full max-w-lg overflow-hidden rounded-lg border border-border bg-background shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center gap-3 border-b border-border px-4">
          <Search className="h-4 w-4 shrink-0 text-muted-foreground" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Search commands, entities, or navigate…"
            className="h-12 flex-1 bg-transparent text-sm text-foreground outline-none placeholder:text-muted-foreground"
          />
          {isLoading && (
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-muted-foreground border-t-transparent" />
          )}
        </div>

        <div ref={listRef} className="max-h-[360px] overflow-y-auto p-1" role="listbox">
          {items.length === 0 ? (
            <div className="px-4 py-8 text-center text-sm text-muted-foreground">
              No results found.
            </div>
          ) : (
            <>
              {query.length < 2 && (
                <div className="px-2 py-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Navigation
                </div>
              )}
              {items.map((item, index) => (
                <CommandItemRow
                  key={item.id}
                  item={item}
                  isSelected={index === selectedIndex}
                  onMouseEnter={() => onHoverItem(index)}
                  onClick={() => executeItem(item)}
                />
              ))}
            </>
          )}
        </div>

        <div className="flex items-center gap-4 border-t border-border px-4 py-2 text-xs text-muted-foreground">
          <span>
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">↑↓</kbd>{' '}
            navigate
          </span>
          <span>
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">↵</kbd>{' '}
            select
          </span>
          <span>
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">esc</kbd>{' '}
            close
          </span>
        </div>
      </div>
    </div>
  )
}

function CommandItemRow({
  item,
  isSelected,
  onMouseEnter,
  onClick,
}: {
  item: CommandItem
  isSelected: boolean
  onMouseEnter: () => void
  onClick: () => void
}) {
  return (
    <div
      role="option"
      aria-selected={isSelected}
      className={cn(
        'flex cursor-pointer items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors',
        isSelected ? 'bg-accent text-accent-foreground' : 'text-foreground hover:bg-muted',
      )}
      onMouseEnter={onMouseEnter}
      onClick={onClick}
    >
      <CommandIcon icon={item.icon} />
      <div className="flex-1 truncate">
        <span className="font-medium">{item.label}</span>
        {item.description && (
          <span className="ml-2 text-xs text-muted-foreground">{item.description}</span>
        )}
      </div>
      {item.category && (
        <span className="shrink-0 text-xs text-muted-foreground">{item.category}</span>
      )}
    </div>
  )
}
