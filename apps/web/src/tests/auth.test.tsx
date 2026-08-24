import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from '@/hooks/use-auth'
import { queryClient } from '@/lib/query-client'
import { getAccessToken, clearTokens } from '@/api/client'

function Probe() {
  const { isAuthenticated, user, signIn, signOut } = useAuth()
  return (
    <div>
      <p data-testid="auth">{String(isAuthenticated)}</p>
      <p data-testid="email">{user?.email ?? 'none'}</p>
      <button onClick={() => signIn({ email: 'admin@sandbox.local', password: 'cosmonitor' })}>
        signin
      </button>
      <button onClick={signOut}>signout</button>
    </div>
  )
}

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

function renderWithProviders() {
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter>
          <Routes>
            <Route path="/" element={<Probe />} />
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

describe('auth provider', () => {
  beforeEach(() => {
    clearTokens()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('starts unauthenticated', () => {
    renderWithProviders()
    expect(screen.getByTestId('auth').textContent).toBe('false')
  })

  it('signs in and loads the profile', async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => loginResponse })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => meResponse })
    vi.stubGlobal('fetch', mockFetch)
    const user = userEvent.setup()
    renderWithProviders()
    await user.click(screen.getByText('signin'))
    await waitFor(() => expect(screen.getByTestId('auth').textContent).toBe('true'))
    expect(screen.getByTestId('email').textContent).toBe('admin@sandbox.local')
  })

  it('signs out and clears the session', async () => {
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => loginResponse })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => meResponse })
    vi.stubGlobal('fetch', mockFetch)
    const user = userEvent.setup()
    renderWithProviders()
    await user.click(screen.getByText('signin'))
    await waitFor(() => expect(screen.getByTestId('auth').textContent).toBe('true'))
    await user.click(screen.getByText('signout'))
    await waitFor(() => expect(screen.getByTestId('auth').textContent).toBe('false'))
    expect(getAccessToken()).toBeNull()
  })
})
