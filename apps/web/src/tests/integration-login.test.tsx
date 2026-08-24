import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from '@/hooks/use-auth'
import { queryClient } from '@/lib/query-client'
import userEvent from '@testing-library/user-event'
import { getAccessToken, clearTokens } from '@/api/client'

const loginResponse = {
  access_token: 'access-1',
  token_type: 'bearer',
  expires_in: 3600,
}

const meResponse = {
  id: 'u1',
  tenant_id: 't1',
  email: 'admin@sandbox.local',
  name: 'Admin',
  role: 'superadmin',
  is_active: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
}

function LoginForm() {
  const { signIn, isAuthenticated, user } = useAuth()
  if (isAuthenticated) return <p>logged in as {user?.email}</p>
  return (
    <div>
      <input aria-label="Email" defaultValue="admin@sandbox.local" />
      <input aria-label="Password" defaultValue="cosmonitor" />
      <button onClick={() => signIn({ email: 'admin@sandbox.local', password: 'cosmonitor' }).catch(() => {})}>
        sign in
      </button>
    </div>
  )
}

describe('Login flow — integration', () => {
  beforeEach(() => {
    clearTokens()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('successful login stores access token in memory and loads profile', async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => loginResponse })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => meResponse })
    vi.stubGlobal('fetch', mockFetch)
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <LoginForm />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    await user.click(screen.getByText('sign in'))
    await waitFor(() => expect(screen.getByText('logged in as admin@sandbox.local')).toBeInTheDocument())
    expect(getAccessToken()).toBe('access-1')
  })

  it('failed login does not store tokens', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: 'Invalid credentials' }),
    })
    vi.stubGlobal('fetch', mockFetch)
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <LoginForm />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    await user.click(screen.getByText('sign in'))
    await waitFor(() => expect(mockFetch).toHaveBeenCalled())
    expect(getAccessToken()).toBeNull()
    expect(screen.queryByText(/logged in/)).not.toBeInTheDocument()
  })

  it('network error during login does not store tokens', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockRejectedValue(new TypeError('Failed to fetch')),
    )
    const user = userEvent.setup()
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter>
            <LoginForm />
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    await user.click(screen.getByText('sign in'))
    await waitFor(() => expect(getAccessToken()).toBeNull())
  })
})
