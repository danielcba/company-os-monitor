import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from '@/hooks/use-auth'
import { ProtectedRoute } from '@/routes/ProtectedRoute'
import { queryClient } from '@/lib/query-client'
import { UnauthorizedState, ForbiddenState } from '@/components/ui/state'
import { apiFetch, setTokens } from '@/api/client'

function Probe() {
  const { isAuthenticated, isLoading } = useAuth()
  if (isLoading) return <p>loading</p>
  if (isAuthenticated) return <p>authenticated</p>
  return <p>not authenticated</p>
}

describe('Unauthorized state — integration', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('UnauthorizedState renders the session expired message', () => {
    render(<UnauthorizedState />)
    expect(screen.getByText('Unauthorized')).toBeInTheDocument()
    expect(screen.getByText(/session is no longer valid/)).toBeInTheDocument()
  })

  it('401 from API causes redirect to login', async () => {
    setTokens({ access_token: 'expired', refresh_token: 'refresh-1', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({ error: 'invalid token' }) }),
    )
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={['/dashboard']}>
            <Routes>
              <Route path="/login" element={<p>login page</p>} />
              <Route element={<ProtectedRoute />}>
                <Route path="/dashboard" element={<Probe />} />
              </Route>
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    await waitFor(() => expect(screen.getByText('login page')).toBeInTheDocument())
    expect(localStorage.getItem('cosmonitor.access_token')).toBeNull()
  })

  it('clears both access and refresh tokens on 401', async () => {
    setTokens({ access_token: 'expired', refresh_token: 'refresh-1', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 401, json: async () => ({}) }),
    )
    render(
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <MemoryRouter initialEntries={['/']}>
            <Routes>
              <Route path="/login" element={<p>login</p>} />
              <Route element={<ProtectedRoute />}>
                <Route path="/" element={<Probe />} />
              </Route>
            </Routes>
          </MemoryRouter>
        </AuthProvider>
      </QueryClientProvider>,
    )
    await waitFor(() => {
      expect(localStorage.getItem('cosmonitor.access_token')).toBeNull()
      expect(localStorage.getItem('cosmonitor.refresh_token')).toBeNull()
    })
  })
})

describe('Forbidden state — integration', () => {
  it('ForbiddenState renders the access denied message', () => {
    render(<ForbiddenState />)
    expect(screen.getByText('Access denied')).toBeInTheDocument()
    expect(screen.getByText(/does not grant permission/)).toBeInTheDocument()
  })

  it('ForbiddenState renders custom action message', () => {
    render(<ForbiddenState action="commit decisions" />)
    expect(screen.getByText(/does not grant permission to commit decisions/)).toBeInTheDocument()
  })

  it('403 from API throws ApiError with status 403', async () => {
    setTokens({ access_token: 'token', refresh_token: 'refresh-1', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: false, status: 403, json: async () => ({ error: 'forbidden' }) }),
    )
    await expect(apiFetch('/tenants/t1/decisions')).rejects.toMatchObject({
      status: 403,
      code: 'forbidden',
    })
  })
})

describe('Tenant isolation — integration', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('cross-tenant query by non-superadmin returns 403', async () => {
    setTokens({ access_token: 'admin-token', refresh_token: 'refresh-1', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ error: 'Cross-tenant access denied' }),
      }),
    )
    await expect(apiFetch('/tenants/other-tenant-id/observations')).rejects.toMatchObject({
      status: 403,
      code: 'forbidden',
    })
  })

  it('tenant-scoped query uses the correct tenant_id in the URL', async () => {
    setTokens({ access_token: 'token', refresh_token: 'refresh-1', token_type: 'bearer', expires_in: 3600 })
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ observations: [], total: 0, limit: 20, offset: 0, facets: {} }),
    })
    vi.stubGlobal('fetch', mockFetch)

    await apiFetch('/tenants/my-tenant-id/observations')
    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('/tenants/my-tenant-id/observations')
  })

  it('superadmin cross-tenant query succeeds', async () => {
    setTokens({ access_token: 'superadmin-token', refresh_token: 'refresh-1', token_type: 'bearer', expires_in: 3600 })
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ observations: [], total: 0, limit: 20, offset: 0, facets: {} }),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await apiFetch('/tenants/other-tenant/observations')
    expect(result).toEqual({ observations: [], total: 0, limit: 20, offset: 0, facets: {} })
  })
})
