import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { TrustValuePanel } from '@/components/trust/TrustValuePanel'
import { queryClient } from '@/lib/query-client'

const tenantId = '00000000-0000-0000-0000-000000000001'

const meResponse = {
  id: 'u1',
  tenant_id: tenantId,
  email: 'admin@sandbox.local',
  name: 'Admin',
  role: 'superadmin',
  is_active: true,
  created_at: '2026-08-01T00:00:00Z',
  updated_at: '2026-08-01T00:00:00Z',
}

const confidenceSummary = {
  total: 2,
  by_target_type: { hypothesis: 2 },
  averages: {
    confidence: 0.58,
    support: 0.78,
    coherence: 0.66,
    historical_calibration: 1.0,
    ece: 0.0,
    alpha: 0.5,
  },
  range: { min_confidence: 0.44, max_confidence: 0.81 },
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

function mockFetch(
  responses: { match: (url: string) => boolean; response: unknown }[],
) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (input: string) => {
      const url = String(input)
      const hit = responses.find((r) => r.match(url))
      if (hit) return { ok: true, status: 200, json: async () => hit.response }
      return { ok: false, status: 404, json: async () => ({ error: 'not found' }) }
    }),
  )
}

function renderPanel() {
  return render(
    <QueryClientProvider client={queryClient}>
      <TrustValuePanel />
    </QueryClientProvider>,
  )
}

describe('TrustValuePanel', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders the aggregated trust value with its metrics', async () => {
    mockFetch([
      { match: (u) => u.includes('/confidence/summary'), response: confidenceSummary },
    ])
    renderPanel()

    expect(await screen.findByText('Valor de Confianza')).toBeInTheDocument()
    // Promedio C_final 0.58 -> nivel "Medio"
    expect(await screen.findByText('Medio')).toBeInTheDocument()
    expect(screen.getByText('0.58')).toBeInTheDocument()
    expect(screen.getByText('Soporte S')).toBeInTheDocument()
    expect(screen.getByText('0.780')).toBeInTheDocument()
    expect(screen.getByText('Coherencia C')).toBeInTheDocument()
    expect(screen.getByText('0.660')).toBeInTheDocument()
    expect(screen.getByText('Calibración 1−ECE')).toBeInTheDocument()
    expect(screen.getByText('Error ECE')).toBeInTheDocument()
  })

  it('shows "No disponible" when there is no calibration yet', async () => {
    mockFetch([
      {
        match: (u) => u.includes('/confidence/summary'),
        response: { ...confidenceSummary, total: 0, by_target_type: {} },
      },
    ])
    renderPanel()

    expect(
      await screen.findByText('Aún no hay calibración calculada para este tenant.'),
    ).toBeInTheDocument()
  })

  it('labels the trust level by the C_final value', async () => {
    mockFetch([
      {
        match: (u) => u.includes('/confidence/summary'),
        response: {
          ...confidenceSummary,
          averages: { ...confidenceSummary.averages, confidence: 0.88 },
        },
      },
    ])
    renderPanel()

    expect(await screen.findByText('Alto')).toBeInTheDocument()
    expect(screen.getByText('0.88')).toBeInTheDocument()
  })
})
