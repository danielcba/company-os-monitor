import { LogOut } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { useAuth } from '@/hooks/use-auth'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { formatRole } from '@/lib/utils'

export function UserMenu() {
  const { user, signOut } = useAuth()
  const navigate = useNavigate()

  const handleSignOut = () => {
    signOut()
    navigate('/login', { replace: true })
  }

  return (
    <div className="flex items-center gap-2">
      <div className="flex items-center gap-2 rounded-md border border-border bg-card px-2 py-1.5">
        <div className="flex h-6 w-6 items-center justify-center rounded-full bg-muted text-xs font-semibold">
          {user?.name ? user.name.charAt(0).toUpperCase() : user?.email.charAt(0).toUpperCase()}
        </div>
        <div className="hidden leading-tight md:block">
          <p className="max-w-[160px] truncate text-xs font-medium">
            {user?.name ?? user?.email ?? 'Not signed in'}
          </p>
          <p className="text-[11px] text-muted-foreground">{user?.email}</p>
        </div>
        {user ? <Badge variant="accent">{formatRole(user.role)}</Badge> : null}
      </div>
      <Button variant="ghost" size="icon" onClick={handleSignOut} aria-label="Sign out">
        <LogOut className="h-4 w-4" />
      </Button>
    </div>
  )
}