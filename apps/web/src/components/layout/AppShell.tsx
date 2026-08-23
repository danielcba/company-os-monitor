import { Outlet } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { Header } from '@/components/layout/Header'
import { Breadcrumbs } from '@/components/layout/Breadcrumbs'
import { CommandPalette } from '@/features/command-palette/CommandPalette'
import { CommandPaletteProvider } from '@/features/command-palette/CommandPaletteContext'

export function AppShell() {
  return (
    <CommandPaletteProvider>
      <div className="flex min-h-screen bg-background">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <Header />
          <div className="px-4 pt-3">
            <Breadcrumbs />
          </div>
          <main className="flex-1 p-4">
            <Outlet />
          </main>
          <footer className="border-t border-border px-4 py-3 text-xs text-muted-foreground">
            COS-Monitor · Cognitive OS Monitor · All cognitive state originates from the Company OS pipeline
            and is served exclusively through the API Gateway.
          </footer>
        </div>
        <CommandPalette />
      </div>
    </CommandPaletteProvider>
  )
}
