import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { DashboardPage } from '@/features/dashboard/DashboardPage'
import { queryClient } from '@/lib/query-client'

const meResponse = {
  id: 'u1',
  tenant_id: '00000000-0000-0000-0000-000000000001',
  email: 'admin@sandbox.local',
  name: 'Admin',
  role: 'superadmin',
  is_active: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
}

const summaryResponse = {
  tenant_id: '00000000-0000-0000-0000-000000000001',
  totals: {
    observations: 1505,
    evidence: 3,
    contexts: 3,
    active_contexts: 2,
    patterns: 0,
    anomalies: 0,
    hypotheses: 0,
    confidence_scores: 0,
    recommendations: 0,
    decisions: 0,
    reports: 2,
    servers: 0,
  },
  status: {
    hypotheses: {},
    recommendations: {},
    decisions: {},
  },
}

const healthResponse = {
  services: [
    { service: 'collector', url: 'http://x', status: 200, healthy: true },
    { service: 'gateway', url: 'http://x', status: 200, healthy: true },
  ],
}

function mockApi() {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (input: string) => {
      if (input.includes('/cognitive/summary')) {
        return { ok: true, status: 200, json: async () => summaryResponse }
      }
      return { ok: true, status: 200, json: async () => healthResponse }
    }),
  )
}

vi.mock('@/hooks/use-auth', () => ({
  useAuth: () => ({
    user: meResponse,
    accessToken: 't',
    isLoading: false,
    isAuthenticated: true,
    signIn: vi.fn(),
    signOut: vi.fn(),
  }),
}))

function renderDashboard() {
  return render(
    <QueryClientProvider client={queryClient}>
      <DashboardPage />
    </QueryClientProvider>,
  )
}

describe('DashboardPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
    vi.stubGlobal('fetch', vi.fn())
  })

  it('renders the cognitive flow and the summary labels', async () => {
    mockApi()
    renderDashboard()
    expect(screen.getByText('Cognitive Flow')).toBeInTheDocument()
    expect((await screen.findAllByText('Observations')).length).toBeGreaterThan(0)
    expect((await screen.findAllByText('Confidence')).length).toBeGreaterThan(0)
    expect(screen.getByText('Pipeline state')).toBeInTheDocument()
  })

  it('shows the real counts served by the gateway', async () => {
    mockApi()
    renderDashboard()
    expect(await screen.findByText('1505')).toBeInTheDocument()
    expect((await screen.findAllByText('3')).length).toBeGreaterThan(0)
  })

  it('shows an error state when the summary request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (input.includes('/cognitive/summary')) {
          return { ok: false, status: 403, json: async () => ({ error: 'forbidden' }) }
        }
        return { ok: true, status: 200, json: async () => healthResponse }
      }),
    )
    renderDashboard()
    expect(await screen.findByText(/Something went wrong/i, undefined, { timeout: 5000 })).toBeInTheDocument()
    expect(screen.getByText('forbidden')).toBeInTheDocument()
  })
})