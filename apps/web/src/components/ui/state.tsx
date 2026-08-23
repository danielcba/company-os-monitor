import type { ReactNode } from 'react'

export function LoadingState({ label = 'Loading…' }: { label?: string }) {
  return (
    <div role="status" aria-live="polite" className="flex items-center gap-3 text-sm text-muted-foreground">
      <span className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-muted border-t-foreground" />
      {label}
    </div>
  )
}

export function EmptyState({ title, description }: { title: string; description?: string }) {
  return (
    <div className="flex flex-col items-center gap-1 rounded-lg border border-dashed border-border p-8 text-center">
      <p className="text-sm font-medium text-foreground">{title}</p>
      {description ? <p className="max-w-md text-sm text-muted-foreground">{description}</p> : null}
    </div>
  )
}

export function ErrorState({ title = 'Something went wrong', message }: { title?: string; message?: string }) {
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6">
      <p className="text-sm font-medium text-destructive">{title}</p>
      {message ? <p className="mt-1 text-sm text-muted-foreground">{message}</p> : null}
    </div>
  )
}

export function UnauthorizedState() {
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6">
      <p className="text-sm font-medium text-destructive">Unauthorized</p>
      <p className="mt-1 text-sm text-muted-foreground">
        Your session is no longer valid. Please sign in again.
      </p>
    </div>
  )
}

export function ForbiddenState({ action }: { action?: string }) {
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-6">
      <p className="text-sm font-medium text-destructive">Access denied</p>
      <p className="mt-1 text-sm text-muted-foreground">
        Your role does not grant permission to {action ?? 'this resource'}. Contact an administrator if you
        believe this is a mistake.
      </p>
    </div>
  )
}

export function NotAvailable({ label = 'Not available' }: { label?: string }) {
  return <span className="text-sm italic text-muted-foreground">{label}</span>
}

export function StateSwitch({ children }: { children: ReactNode }) {
  return <>{children}</>
}