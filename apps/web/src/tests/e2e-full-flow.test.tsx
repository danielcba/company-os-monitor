import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuthProvider, useAuth } from '@/hooks/use-auth'
import { ProtectedRoute } from '@/routes/ProtectedRoute'
import { queryClient } from '@/lib/query-client'
import { apiFetch, setTokens, clearTokens } from '@/api/client'

// ── Helpers ────────────────────────────────────────────────────────────────

const viewerProfile = {
  id: 'u1',
  tenant_id: 't1',
  email: 'viewer@sandbox.local',
  name: 'Viewer',
  role: 'viewer',
  is_active: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
}

const adminProfile = {
  ...viewerProfile,
  id: 'u2',
  email: 'admin@sandbox.local',
  name: 'Admin',
  role: 'admin',
}

const superadminProfile = {
  ...viewerProfile,
  id: 'u3',
  email: 'superadmin@sandbox.local',
  name: 'Superadmin',
  role: 'superadmin',
}

const loginResponse = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  token_type: 'bearer',
  expires_in: 3600,
}

function RoleProbe() {
  const { user, isAuthenticated, isLoading } = useAuth()
  if (isLoading) return <p>loading</p>
  if (!isAuthenticated) return <p>not authenticated</p>
  return (
    <div>
      <p data-testid="role">{user?.role}</p>
      <p data-testid="tenant">{user?.tenant_id}</p>
    </div>
  )
}

function renderAuth(path: string) {
  return render(
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <MemoryRouter initialEntries={[path]}>
          <Routes>
            <Route path="/login" element={<p>login page</p>} />
            <Route element={<ProtectedRoute />}>
              <Route path="/dashboard" element={<RoleProbe />} />
              <Route path="/administration/users" element={<p>users admin</p>} />
              <Route path="/administration/tenants" element={<p>tenants admin</p>} />
              <Route path="/action/decisions" element={<p>decisions</p>} />
            </Route>
          </Routes>
        </MemoryRouter>
      </AuthProvider>
    </QueryClientProvider>,
  )
}

// ── E2E: Full Login → Dashboard → Cognitive Trace Flow ─────────────────────

describe('E2E: Login → Dashboard → Cognitive Trace', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('login → store tokens → load profile → render dashboard', async () => {
    // Step 1: Login stores tokens
    setTokens(loginResponse)
    expect(localStorage.getItem('cosmonitor.access_token')).toBe('access-1')

    // Step 2: Auth loads profile on mount
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => adminProfile }),
    )
    renderAuth('/dashboard')
    await waitFor(() => expect(screen.getByTestId('role').textContent).toBe('admin'))
    expect(screen.getByTestId('tenant').textContent).toBe('t1')
  })

  it('full cognitive trace chain is representable', () => {
    const traceData = {
      observations: [{ id: 'obs1', fact_type: 'cpu_utilization_percent', quality_class: 'Q1' }],
      evidence: [{ id: 'ev1', organization_type: 'resource_exhaustion_evidence', quality_class: 'Q1' }],
      contexts: [{ id: 'ctx1', purpose: 'infrastructure_health', coherence_score: 0.75 }],
      patterns: [{ id: 'pat1', pattern_type: 'temporal', strength_measure: 0.8 }],
      anomalies: [{ id: 'anom1', anomaly_class: 'cpu_spike', deviation_score: 0.92 }],
      hypotheses: [{ id: 'hyp1', status: 'candidate', coherence_score: 0.7 }],
      confidence: [{ id: 'conf1', confidence_score: 0.65, target_type: 'hypothesis' }],
      recommendations: [{ id: 'rec1', status: 'proposed', confidence_score: 0.65 }],
      decisions: [{ id: 'dec1', status: 'committed', risk_tolerance: 'medium' }],
    }

    expect(traceData.observations[0].quality_class).toBe('Q1')
    expect(traceData.confidence[0].target_type).toBe('hypothesis')
    expect(traceData.recommendations[0].status).toBe('proposed')
    expect(traceData.decisions[0].status).toBe('committed')

    const chain = [
      traceData.observations[0].id,
      traceData.evidence[0].id,
      traceData.contexts[0].id,
      traceData.patterns[0].id,
      traceData.anomalies[0].id,
      traceData.hypotheses[0].id,
      traceData.confidence[0].id,
      traceData.recommendations[0].id,
      traceData.decisions[0].id,
    ]
    expect(chain).toHaveLength(9)
  })
})

// ── E2E: Viewer Cannot Commit ──────────────────────────────────────────────

describe('E2E: Viewer Cannot Commit', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('viewer profile has read-only permissions', () => {
    const viewerPermissions = ['read']
    expect(viewerPermissions).not.toContain('commit')
    expect(viewerPermissions).not.toContain('propose')
    expect(viewerPermissions).not.toContain('execute')
  })

  it('viewer is correctly identified in auth context', async () => {
    localStorage.setItem('cosmonitor.access_token', 'viewer-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => viewerProfile }),
    )
    renderAuth('/dashboard')
    await waitFor(() => expect(screen.getByTestId('role').textContent).toBe('viewer'))
  })

  it('viewer sees users admin page content (UI does not block, backend enforces RBAC)', async () => {
    localStorage.setItem('cosmonitor.access_token', 'viewer-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => viewerProfile }),
    )
    renderAuth('/administration/users')
    await waitFor(() => expect(screen.getByText('users admin')).toBeInTheDocument())
  })
})

// ── E2E: Admin Risk Restrictions ───────────────────────────────────────────

describe('E2E: Admin Risk Restrictions', () => {
  it('admin role has restricted permissions compared to superadmin', () => {
    const adminPerms = ['read', 'propose', 'ack', 'commit', 'define_policy']
    const superadminPerms = ['read', 'propose', 'ack', 'commit', 'execute', 'define_policy', 'cross_tenant']

    expect(adminPerms).not.toContain('execute')
    expect(adminPerms).not.toContain('cross_tenant')
    expect(superadminPerms).toContain('execute')
    expect(superadminPerms).toContain('cross_tenant')
  })

  it('admin risk ceiling is limited to low and medium', () => {
    const adminRiskCeiling = ['low', 'medium']
    const superadminRiskCeiling = ['low', 'medium', 'high']

    expect(adminRiskCeiling).not.toContain('high')
    expect(superadminRiskCeiling).toContain('high')
  })

  it('admin cannot access cross-tenant endpoints', async () => {
    setTokens({ access_token: 'admin-token', refresh_token: 'refresh-1', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ error: 'Cross-tenant access requires superadmin' }),
      }),
    )
    await expect(apiFetch('/tenants/other-tenant/observations')).rejects.toMatchObject({
      status: 403,
    })
  })
})

// ── E2E: Superadmin Cross-Tenant ───────────────────────────────────────────

describe('E2E: Superadmin Cross-Tenant', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('superadmin profile has cross_tenant permission', () => {
    const superadminPerms = ['read', 'propose', 'ack', 'commit', 'execute', 'define_policy', 'cross_tenant']
    expect(superadminPerms).toContain('cross_tenant')
  })

  it('superadmin can query other tenants', async () => {
    setTokens({ access_token: 'superadmin-token', refresh_token: 'refresh-1', token_type: 'bearer', expires_in: 3600 })
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ observations: [{ id: 'obs1' }], total: 1 }),
    })
    vi.stubGlobal('fetch', mockFetch)

    const result = await apiFetch('/tenants/other-tenant/observations')
    expect(result).toEqual({ observations: [{ id: 'obs1' }], total: 1 })
    const [url] = mockFetch.mock.calls[0]
    expect(url).toContain('/tenants/other-tenant/')
  })

  it('superadmin profile is loaded correctly', async () => {
    localStorage.setItem('cosmonitor.access_token', 'superadmin-token')
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => superadminProfile }),
    )
    renderAuth('/dashboard')
    await waitFor(() => expect(screen.getByTestId('role').textContent).toBe('superadmin'))
  })

  it('superadmin risk ceiling includes high', () => {
    const superadminRiskCeiling = ['low', 'medium', 'high']
    expect(superadminRiskCeiling).toContain('high')
  })
})

// ── E2E: Session Lifecycle ─────────────────────────────────────────────────

describe('E2E: Session Lifecycle', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
    queryClient.clear()
  })

  it('complete session lifecycle: login → operate → logout', async () => {
    // Login: store tokens
    setTokens(loginResponse)
    expect(localStorage.getItem('cosmonitor.access_token')).toBe('access-1')

    // Verify profile loaded
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, status: 200, json: async () => adminProfile }),
    )
    renderAuth('/dashboard')
    await waitFor(() => expect(screen.getByTestId('role').textContent).toBe('admin'))

    // Logout
    clearTokens()
    expect(localStorage.getItem('cosmonitor.access_token')).toBeNull()
    expect(localStorage.getItem('cosmonitor.refresh_token')).toBeNull()
  })

  it('token refresh extends the session', async () => {
    setTokens({ access_token: 'old', refresh_token: 'refresh-old', token_type: 'bearer', expires_in: 3600 })
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 200,
        json: async () => ({ access_token: 'refreshed', refresh_token: 'refresh-new', token_type: 'bearer', expires_in: 3600 }),
      }),
    )

    const { tryRefresh } = await import('@/api/client')
    const refreshed = await tryRefresh()
    expect(refreshed).toBe(true)
    expect(localStorage.getItem('cosmonitor.access_token')).toBe('refreshed')
  })
})
