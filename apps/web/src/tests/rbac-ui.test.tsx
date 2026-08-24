import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from '@/hooks/use-auth'
import { queryClient } from '@/lib/query-client'
import { setTokens, clearTokens, getAccessToken } from '@/api/client'

const meResponse = {
  id: 'u1',
  tenant_id: 't1',
  email: 'viewer@sandbox.local',
  name: 'Viewer',
  role: 'viewer',
  is_active: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
}

const adminMeResponse = {
  ...meResponse,
  id: 'u2',
  email: 'admin@sandbox.local',
  name: 'Admin',
  role: 'admin',
}

function RoleProbe() {
  const { user } = useAuth()
  return <p data-testid="role">{user?.role ?? 'none'}</p>
}

function AdminOnlyContent() {
  return <p>admin content</p>
}

function ViewerContent() {
  return <p>viewer content</p>
}

describe('RBAC UI guards', () => {
  beforeEach(() => {
    clearTokens()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('viewer role is reflected in the auth context', async () => {
    setTokens({ access_token: 'token-viewer', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => meResponse }),
    )
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <RoleProbe />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByTestId('role')).toHaveTextContent('viewer')
  })

  it('admin role is reflected in the auth context', async () => {
    setTokens({ access_token: 'token-admin', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => adminMeResponse }),
    )
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <RoleProbe />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByTestId('role')).toHaveTextContent('admin')
  })

  it('unauthenticated user sees not authenticated', async () => {
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <RoleProbe />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    expect(screen.getByTestId('role')).toHaveTextContent('none')
  })

  it('authenticated viewer can access protected content', async () => {
    setTokens({ access_token: 'token-viewer', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => meResponse }),
    )
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <ViewerContent />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('viewer content')).toBeInTheDocument()
  })

  it('authenticated admin can access protected content', async () => {
    setTokens({ access_token: 'token-admin', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => adminMeResponse }),
    )
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <AdminOnlyContent />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('admin content')).toBeInTheDocument()
  })

  it('invalid token clears session and shows unauthenticated', async () => {
    setTokens({ access_token: 'expired-token', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ error: 'invalid' }) }),
    )
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <RoleProbe />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByTestId('role')).toHaveTextContent('none')
    expect(getAccessToken()).toBeNull()
  })

  it('expired token during profile fetch clears session', async () => {
    setTokens({ access_token: 'expired-token', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ error: 'token expired' }) }),
    )
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <RoleProbe />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByTestId('role')).toHaveTextContent('none')
    expect(getAccessToken()).toBeNull()
  })
})
