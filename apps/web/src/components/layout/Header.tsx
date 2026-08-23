import { Moon, Sun, Search } from 'lucide-react'
import { useTheme } from '@/hooks/use-theme'
import { TenantSwitcher } from '@/components/layout/TenantSwitcher'
import { UserMenu } from '@/components/layout/UserMenu'
import { NotificationsCenter } from '@/features/notifications/NotificationsCenter'
import { Button } from '@/components/ui/button'
import { useCommandPalette } from '@/features/command-palette/CommandPaletteContext'

export function Header() {
  const { theme, toggleTheme } = useTheme()
  const { open } = useCommandPalette()
  return (
    <header className="sticky top-0 z-10 flex h-14 items-center gap-3 border-b border-border bg-background/95 px-4 backdrop-blur">
      <div className="relative hidden max-w-xs flex-1 md:block">
        <Search className="pointer-events-none absolute left-2.5 top-2.5 h-4 w-4 text-muted-foreground" />
        <button
          onClick={open}
          className="flex h-9 w-full cursor-pointer items-center rounded-md border border-border bg-card pl-8 pr-3 text-sm text-muted-foreground transition-colors hover:bg-muted"
          aria-label="Open command palette"
        >
          Search…
          <span className="ml-auto text-xs text-muted-foreground/60">
            <kbd className="rounded border border-border bg-muted px-1.5 py-0.5 font-mono text-[10px]">⌘K</kbd>
          </span>
        </button>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <TenantSwitcher />
        <NotificationsCenter />
        <Button
          variant="ghost"
          size="icon"
          onClick={toggleTheme}
          aria-label={theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}
        >
          {theme === 'light' ? <Moon className="h-4 w-4" /> : <Sun className="h-4 w-4" />}
        </Button>
        <UserMenu />
      </div>
    </header>
  )
}
