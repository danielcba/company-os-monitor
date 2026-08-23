import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { AnomaliesPage } from '@/features/anomalies/AnomaliesPage'
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

const anomalyPage = {
  anomalies: [
    {
      id: 'an1',
      tenant_id: tenantId,
      context_id: 'ctx1',
      pattern_id: null,
      anomaly_class: 'point',
      deviation_score: 1.204,
      tolerance_threshold: 1.0,
      detected_at: '2026-08-19T14:20:00Z',
    },
    {
      id: 'an2',
      tenant_id: tenantId,
      context_id: 'ctx2',
      pattern_id: 'pat1',
      anomaly_class: 'contextual',
      deviation_score: 1.35,
      tolerance_threshold: 1.0,
      detected_at: '2026-08-19T14:21:00Z',
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    anomaly_classes: ['point', 'contextual'],
  },
}

const anomalyDetail = {
  anomaly: anomalyPage.anomalies[0],
  context: {
    id: 'ctx1',
    tenant_id: tenantId,
    evidence_ids: ['ev1'],
    mental_model_id: 'capacity_risk',
    purpose: 'infrastructure_health',
    coherence_score: 0.33,
    competing_models: [
      { mental_model_id: 'capacity_risk', coherence_score: 0.33 },
      { mental_model_id: 'resource_pressure', coherence_score: 0.33 },
    ],
    activated_at: '2026-08-19T14:10:00Z',
    is_active: true,
  },
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

function renderPage() {
  return render(
    <QueryClientProvider client={queryClient}>
      <AnomaliesPage />
    </QueryClientProvider>,
  )
}

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

describe('AnomaliesPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders deviations with class, score, threshold and facets', async () => {
    mockFetch([{ match: (u) => u.includes('/anomalies'), response: anomalyPage }])
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('point')).toBeInTheDocument()
    expect(within(table).getByText('contextual')).toBeInTheDocument()
    expect(within(table).getAllByText('1.2040').length).toBeGreaterThan(0)
    expect(within(table).getAllByText('1.0000').length).toBeGreaterThan(0)
    expect(await screen.findByText('2 anomalies · page 1 of 1')).toBeInTheDocument()
  })

  it('opens the detail drawer with the source context', async () => {
    const user = userEvent.setup()
    mockFetch([
      {
        match: (u) => u.includes('/anomalies/'),
        response: anomalyDetail,
      },
      {
        match: (u) => u.includes('/anomalies'),
        response: anomalyPage,
      },
    ])
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByText('point'))
    const dialog = await screen.findByRole('dialog', { name: 'Anomaly detail' })
    expect(within(dialog).getByText('Source context')).toBeInTheDocument()
    expect(await within(dialog).findByText('capacity_risk')).toBeInTheDocument()
    expect(within(dialog).getByText('infrastructure_health')).toBeInTheDocument()
    expect(within(dialog).getByText('Coherence')).toBeInTheDocument()
  })

  it('forwards filter selection to the gateway', async () => {
    const user = userEvent.setup()
    mockFetch([{ match: (u) => u.includes('/anomalies'), response: anomalyPage }])
    renderPage()
    const select = await screen.findByLabelText('Anomaly class')
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'contextual' })).toBeInTheDocument()
    })
    await user.selectOptions(select, 'contextual')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes('anomaly_class=contextual'))).toBe(true)
    })
  })

  it('shows an empty state when there are no anomalies', async () => {
    mockFetch([{ match: (u) => u.includes('/anomalies'), response: { ...anomalyPage, anomalies: [], total: 0 } }])
    renderPage()
    expect(await screen.findByText('No anomalies yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (String(input).includes('/anomalies')) {
          return { ok: false, status: 403, json: async () => ({ error: 'forbidden' }) }
        }
        return { ok: false, status: 404, json: async () => ({ error: 'not found' }) }
      }),
    )
    renderPage()
    expect(await screen.findByText('Access denied', undefined, { timeout: 5000 })).toBeInTheDocument()
  })

  it('shows an error state when the request fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async () => {
        return { ok: false, status: 500, json: async () => ({ error: 'boom' }) }
      }),
    )
    renderPage()
    expect(await screen.findByText(/Something went wrong/i, undefined, { timeout: 5000 })).toBeInTheDocument()
  })
})