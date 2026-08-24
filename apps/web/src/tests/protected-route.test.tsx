import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider } from '@/hooks/use-auth'
import { ThemeProvider } from '@/hooks/use-theme'
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
      <ThemeProvider>
        <AuthProvider>
          <MemoryRouter initialEntries={[path]}>
            <Routes>
              <Route path="/login" element={<p>login page</p>} />
              <Route element={<ProtectedRoute />}>
                <Route path="/dashboard" element={<ProtectedContent />} />
              </Route>
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </ThemeProvider>
    </QueryClientProvider>,
  )
}

describe('ProtectedRoute', () => {
  beforeEach(() => {
    clearTokens()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('redirects to /login when unauthenticated', async () => {
    renderProtected()
    expect(await screen.findByText('login page')).toBeInTheDocument()
    expect(screen.queryByText('protected content')).not.toBeInTheDocument()
  })

  it('renders protected content when a valid session exists', async () => {
    setTokens({ access_token: 'access-1', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => meResponse }),
    )
    renderProtected()
    expect(await screen.findByText('protected content')).toBeInTheDocument()
  })

  it('redirects to /login when the token is invalid', async () => {
    setTokens({ access_token: 'expired', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ error: 'invalid' }) }),
    )
    renderProtected()
    expect(await screen.findByText('login page')).toBeInTheDocument()
    expect(getAccessToken()).toBeNull()
  })
})
