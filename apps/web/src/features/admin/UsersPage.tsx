import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Users, UserPlus, Pencil, XCircle } from 'lucide-react'
import { useAuth } from '@/hooks/use-auth'
import { apiFetch } from '@/api/client'
import type { UserProfile } from '@/types/auth'
import { ApiError } from '@/types/cognitive'
import { Button } from '@/components/ui/button'
import { Badge } from '@/components/ui/badge'
import { Input } from '@/components/ui/input'
import { LoadingState, ErrorState, ForbiddenState, EmptyState } from '@/components/ui/state'

interface UsersResponse {
  users: UserProfile[]
}

const ROLE_BADGES: Record<string, string> = {
  superadmin: 'bg-purple-100 text-purple-800 dark:bg-purple-900 dark:text-purple-300',
  admin: 'bg-blue-100 text-blue-800 dark:bg-blue-900 dark:text-blue-300',
  operator: 'bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300',
  viewer: 'bg-gray-100 text-gray-800 dark:bg-gray-800 dark:text-gray-300',
}

export function UsersPage() {
  const { user } = useAuth()
  const tenantId = user?.tenant_id
  const canManage = user?.role === 'admin' || user?.role === 'superadmin'

  const [showCreate, setShowCreate] = useState(false)
  const [editingUser, setEditingUser] = useState<UserProfile | null>(null)
  const [createEmail, setCreateEmail] = useState('')
  const [createPassword, setCreatePassword] = useState('')
  const [createName, setCreateName] = useState('')
  const [createRole, setCreateRole] = useState('viewer')
  const [editName, setEditName] = useState('')
  const [editRole, setEditRole] = useState('')

  const { data, isPending, isError, error, refetch } = useQuery({
    queryKey: ['users', tenantId],
    queryFn: () => apiFetch<UsersResponse>('/user/users'),
    enabled: Boolean(tenantId),
  })

  const handleCreate = async () => {
    try {
      await apiFetch<UserProfile>('/user/users', {
        method: 'POST',
        body: JSON.stringify({ email: createEmail, password: createPassword, name: createName, role: createRole }),
      })
      setShowCreate(false)
      setCreateEmail('')
      setCreatePassword('')
      setCreateName('')
      setCreateRole('viewer')
      void refetch()
    } catch {
      // error handled by UI
    }
  }

  const handleUpdate = async () => {
    if (!editingUser) return
    try {
      await apiFetch<UserProfile>(`/user/users/${editingUser.id}`, {
        method: 'PUT',
        body: JSON.stringify({ name: editName, role: editRole }),
      })
      setEditingUser(null)
      void refetch()
    } catch {
      // error handled by UI
    }
  }

  const handleDeactivate = async (userId: string) => {
    try {
      await apiFetch<UserProfile>(`/user/users/${userId}`, { method: 'DELETE' })
      void refetch()
    } catch {
      // error handled by UI
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold flex items-center gap-2">
            <Users className="h-5 w-5 text-muted-foreground" />
            Users
          </h1>
          <p className="max-w-2xl text-sm text-muted-foreground">
            Manage users and their Decision Authority roles within this tenant.
          </p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" onClick={() => void refetch()}>
            Refresh
          </Button>
          {canManage && (
            <Button size="sm" onClick={() => setShowCreate(true)}>
              <UserPlus className="mr-1 h-4 w-4" /> Create User
            </Button>
          )}
        </div>
      </div>

      {isPending ? (
        <LoadingState label="Loading users…" />
      ) : isError ? (
        error instanceof Error && error instanceof ApiError && error.status === 403 ? (
          <ForbiddenState action="view users" />
        ) : (
          <ErrorState message={error instanceof Error ? error.message : undefined} />
        )
      ) : !data || data.users.length === 0 ? (
        <EmptyState title="No users" description="No users exist for this tenant." />
      ) : (
        <div className="overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[700px] text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/40 text-left text-xs uppercase tracking-wide text-muted-foreground">
                <th className="px-3 py-2 font-medium">Name</th>
                <th className="px-3 py-2 font-medium">Email</th>
                <th className="px-3 py-2 font-medium">Role</th>
                <th className="px-3 py-2 font-medium">Status</th>
                <th className="px-3 py-2 font-medium">Created</th>
                {canManage && <th className="px-3 py-2 font-medium">Actions</th>}
              </tr>
            </thead>
            <tbody>
              {data.users.map((u) => (
                <tr key={u.id} className="border-b border-border/60 last:border-0">
                  <td className="px-3 py-2 font-medium">{u.name ?? '—'}</td>
                  <td className="px-3 py-2 text-muted-foreground">{u.email}</td>
                  <td className="px-3 py-2">
                    <span className={`inline-flex items-center rounded px-1.5 py-0.5 text-xs font-medium ${ROLE_BADGES[u.role] ?? ''}`}>
                      {u.role}
                    </span>
                  </td>
                  <td className="px-3 py-2">
                    <Badge variant={u.is_active ? 'success' : 'destructive'}>
                      {u.is_active ? 'active' : 'inactive'}
                    </Badge>
                  </td>
                  <td className="px-3 py-2 tabular-nums text-muted-foreground">
                    {new Date(u.created_at).toLocaleDateString()}
                  </td>
                  {canManage && (
                    <td className="px-3 py-2">
                      <div className="flex gap-1">
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7"
                          onClick={() => {
                            setEditingUser(u)
                            setEditName(u.name ?? '')
                            setEditRole(u.role)
                          }}
                        >
                          <Pencil className="h-3.5 w-3.5" />
                        </Button>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="h-7 w-7 text-destructive"
                          onClick={() => void handleDeactivate(u.id)}
                        >
                          <XCircle className="h-3.5 w-3.5" />
                        </Button>
                      </div>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {showCreate && (
        <div role="dialog" className="fixed inset-0 z-40 flex items-center justify-center bg-black/40" onClick={() => setShowCreate(false)}>
          <div className="w-full max-w-md rounded-lg border border-border bg-background p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">Create User</h2>
            <div className="space-y-3">
              <Input placeholder="Email" value={createEmail} onChange={(e) => setCreateEmail(e.target.value)} />
              <Input placeholder="Password" type="password" value={createPassword} onChange={(e) => setCreatePassword(e.target.value)} />
              <Input placeholder="Name (optional)" value={createName} onChange={(e) => setCreateName(e.target.value)} />
              <select value={createRole} onChange={(e) => setCreateRole(e.target.value)} className="w-full rounded border border-border bg-background px-2 py-1.5 text-sm">
                <option value="viewer">viewer</option>
                <option value="operator">operator</option>
                <option value="admin">admin</option>
                <option value="superadmin">superadmin</option>
              </select>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setShowCreate(false)}>Cancel</Button>
                <Button size="sm" onClick={() => void handleCreate()}>Create</Button>
              </div>
            </div>
          </div>
        </div>
      )}

      {editingUser && (
        <div role="dialog" className="fixed inset-0 z-40 flex items-center justify-center bg-black/40" onClick={() => setEditingUser(null)}>
          <div className="w-full max-w-md rounded-lg border border-border bg-background p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h2 className="mb-4 text-lg font-semibold">Edit User</h2>
            <div className="space-y-3">
              <Input placeholder="Name" value={editName} onChange={(e) => setEditName(e.target.value)} />
              <select value={editRole} onChange={(e) => setEditRole(e.target.value)} className="w-full rounded border border-border bg-background px-2 py-1.5 text-sm">
                <option value="viewer">viewer</option>
                <option value="operator">operator</option>
                <option value="admin">admin</option>
                <option value="superadmin">superadmin</option>
              </select>
              <div className="flex justify-end gap-2">
                <Button variant="outline" size="sm" onClick={() => setEditingUser(null)}>Cancel</Button>
                <Button size="sm" onClick={() => void handleUpdate()}>Save</Button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default UsersPage
