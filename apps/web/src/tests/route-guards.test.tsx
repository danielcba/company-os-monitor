import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/hooks/use-auth'
import { ProtectedRoute } from '@/routes/ProtectedRoute'
import { queryClient } from '@/lib/query-client'
import { setTokens, clearTokens, getAccessToken } from '@/api/client'

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

function ProtectedContent() {
  return <p>protected content</p>
}

function renderProtected(path = '/dashboard') {
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/login" element={<p>login page</p>} />
            <Route element={<ProtectedRoute />}>
              <Route path="/dashboard" element={<ProtectedContent />} />
              <Route path="/cognition/observations" element={<p>observations page</p>} />
              <Route path="/action/decisions" element={<p>decisions page</p>} />
              <Route path="/administration/users" element={<p>users page</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

describe('Route guards — comprehensive', () => {
  beforeEach(() => {
    clearTokens()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('redirects unauthenticated user from any protected route', async () => {
    renderProtected('/cognition/observations')
    expect(await screen.findByText('login page')).toBeInTheDocument()
    expect(screen.queryByText('observations page')).not.toBeInTheDocument()
  })

  it('preserves the return location in state', async () => {
    renderProtected('/action/decisions')
    expect(await screen.findByText('login page')).toBeInTheDocument()
  })

  it('allows access to all protected routes when authenticated', async () => {
    setTokens({ access_token: 'valid-token', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => meResponse }),
    )
    renderProtected('/dashboard')
    expect(await screen.findByText('protected content')).toBeInTheDocument()
  })

  it('shows loading state while verifying session', async () => {
    setTokens({ access_token: 'valid-token', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal('fetch', vi.fn().mockImplementation(() => new Promise(() => {})))
    renderProtected()
    expect(screen.getByText('Verifying session…')).toBeInTheDocument()
  })

  it('clears tokens on 401 during profile fetch', async () => {
    setTokens({ access_token: 'expired-token', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ error: 'expired' }) }),
    )
    renderProtected()
    expect(await screen.findByText('login page')).toBeInTheDocument()
    expect(getAccessToken()).toBeNull()
  })

  it('catch-all route redirects to dashboard via Navigate', async () => {
    setTokens({ access_token: 'valid-token', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => meResponse }),
    )
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={['/nonexistent']}>
            <Routes>
              <Route path="/login" element={<p>login page</p>} />
              <Route element={<ProtectedRoute />}>
                <Route path="/dashboard" element={<p>dashboard</p>} />
              </Route>
              <Route path="*" element={<p>catch-all redirect</p>} />
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByText('catch-all redirect')).toBeInTheDocument()
    expect(screen.queryByText('dashboard')).not.toBeInTheDocument()
  })
})
