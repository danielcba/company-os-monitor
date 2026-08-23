import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { ConfidencePage } from '@/features/confidence/ConfidencePage'
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

const confidencePage = {
  confidence: [
    {
      id: 'c1',
      tenant_id: tenantId,
      target_type: 'hypothesis',
      target_id: 'h1',
      evidential_support: 0.78,
      explanatory_coherence: 0.66,
      historical_calibration: 1.0,
      confidence_score: 0.72,
      alpha: 0.5,
      calibration_justification:
        'S=0.78 (2 evidence Q1), C=0.66, ECE=0.0 (no history yet); C_final = [0.5*S + 0.5*C] * (1 - ECE) = 0.72',
      calibration_error_estimate: 0.0,
      computed_at: '2026-08-19T16:00:00Z',
    },
  ],
  total: 1,
  limit: 50,
  offset: 0,
  facets: {
    target_types: ['hypothesis'],
  },
}

const confidenceDetail = {
  confidence: confidencePage.confidence[0],
  target: {
    hypothesis: {
      id: 'h1',
      tenant_id: tenantId,
      anomaly_ids: ['an1'],
      pattern_ids: [],
      description: 'Capacity pressure explains the deviation.',
      predicted_consequences: ['CPU utilization keeps exceeding the threshold.'],
      falsification_criterion: 'An observation of idle CPU for 24h would falsify it.',
      coherence_score: 0.66,
      status: 'candidate',
      generated_at: '2026-08-19T15:00:00Z',
    },
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
    ],
    patterns: [],
    contexts: {
      ctx1: {
        id: 'ctx1',
        tenant_id: tenantId,
        evidence_ids: ['ev1'],
        mental_model_id: 'capacity_risk',
        purpose: 'infrastructure_health',
        coherence_score: 0.33,
        competing_models: [],
        activated_at: '2026-08-19T14:10:00Z',
        is_active: true,
      },
    },
  },
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

function renderPage() {
  return render(
    <QueryClientProvider client={queryClient}>
      <ConfidencePage />
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

describe('ConfidencePage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders calibrated confidence rows with components and facets', async () => {
    mockFetch([
      { match: (u) => u.includes('/confidence/summary'), response: confidenceSummary },
      { match: (u) => u.includes('/confidence'), response: confidencePage },
    ])
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('hypothesis')).toBeInTheDocument()
    expect(within(table).getByText('0.7200')).toBeInTheDocument()
    expect(within(table).getByText('0.7800')).toBeInTheDocument()
    expect(within(table).getByText('0.6600')).toBeInTheDocument()
    expect(await screen.findByText('1 confidence row · page 1 of 1')).toBeInTheDocument()
  })

  it('opens the detail drawer with the judgment desglose and calibration semantics', async () => {
    const user = userEvent.setup()
    mockFetch([
      { match: (u) => u.includes('/confidence/summary'), response: confidenceSummary },
      { match: (u) => u.includes('/confidence/'), response: confidenceDetail },
      { match: (u) => u.includes('/confidence'), response: confidencePage },
    ])
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByText('0.7200'))
    const dialog = await screen.findByRole('dialog', { name: 'Confidence detail' })
    expect(within(dialog).getByText('Calibration justification')).toBeInTheDocument()
    expect(
      within(dialog).getByText('S=0.78 (2 evidence Q1), C=0.66, ECE=0.0 (no history yet); C_final = [0.5*S + 0.5*C] * (1 - ECE) = 0.72'),
    ).toBeInTheDocument()
    expect(
      within(dialog).getByText('Capacity pressure explains the deviation.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByText('capacity_risk')).toBeInTheDocument()
  })

  it('forwards the target_type filter to the gateway', async () => {
    const user = userEvent.setup()
    mockFetch([
      { match: (u) => u.includes('/confidence/summary'), response: confidenceSummary },
      { match: (u) => u.includes('/confidence'), response: confidencePage },
    ])
    renderPage()
    const select = await screen.findByLabelText('Target type')
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'hypothesis' })).toBeInTheDocument()
    })
    await user.selectOptions(select, 'hypothesis')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes('target_type=hypothesis'))).toBe(true)
    })
  })

  it('shows an empty state when there are no confidence rows', async () => {
    mockFetch([
      {
        match: (u) => u.includes('/confidence/summary'),
        response: { ...confidenceSummary, total: 0, by_target_type: {} },
      },
      {
        match: (u) => u.includes('/confidence'),
        response: { ...confidencePage, confidence: [], total: 0 },
      },
    ])
    renderPage()
    expect(await screen.findByText('No confidence yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (String(input).includes('/confidence')) {
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

  it('renders the calibration state summary with aggregated values', async () => {
    mockFetch([
      { match: (u) => u.includes('/confidence/summary'), response: confidenceSummary },
      { match: (u) => u.includes('/confidence'), response: confidencePage },
    ])
    renderPage()
    expect(await screen.findByText('Calibration state')).toBeInTheDocument()
    expect(screen.getByText('Calibrated rows')).toBeInTheDocument()
    expect(screen.getByText('2')).toBeInTheDocument()
    expect(screen.getByText('Avg C_final')).toBeInTheDocument()
    expect(screen.getByText('0.5800')).toBeInTheDocument()
    expect(screen.getByText('Avg support S')).toBeInTheDocument()
    expect(screen.getAllByText('0.7800').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Avg coherence C')).toBeInTheDocument()
    expect(screen.getAllByText('0.6600').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('Avg 1 − ECE')).toBeInTheDocument()
    expect(screen.getByText('1.0000')).toBeInTheDocument()
  })

  it('renders the target-type breakdown and C_final range from the summary', async () => {
    mockFetch([
      { match: (u) => u.includes('/confidence/summary'), response: confidenceSummary },
      { match: (u) => u.includes('/confidence'), response: confidencePage },
    ])
    renderPage()
    await screen.findByText('Calibration state')
    expect(screen.getByText('hypothesis: 2')).toBeInTheDocument()
    expect(
      screen.getByText('range C_final 0.4400 – 0.8100 · avg ECE 0.0000 · alpha 0.50'),
    ).toBeInTheDocument()
  })

  it('requests the calibration summary from the gateway', async () => {
    mockFetch([
      { match: (u) => u.includes('/confidence/summary'), response: confidenceSummary },
      { match: (u) => u.includes('/confidence'), response: confidencePage },
    ])
    renderPage()
    await screen.findByText('Calibration state')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes(`/tenants/${tenantId}/confidence/summary`))).toBe(true)
    })
  })

  it('hides the summary block when nothing is calibrated yet', async () => {
    mockFetch([
      {
        match: (u) => u.includes('/confidence/summary'),
        response: { ...confidenceSummary, total: 0, by_target_type: {} },
      },
      { match: (u) => u.includes('/confidence'), response: confidencePage },
    ])
    renderPage()
    await screen.findByRole('table')
    expect(screen.queryByText('Calibration state')).not.toBeInTheDocument()
    expect(screen.getByText('1 confidence row · page 1 of 1')).toBeInTheDocument()
  })

  it('shows a pending placeholder while the summary loads', async () => {
    const never = new Promise<Response>(() => {})
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        const url = String(input)
        if (url.includes('/confidence/summary')) return never
        return { ok: true, status: 200, json: async () => confidencePage }
      }),
    )
    renderPage()
    await screen.findByRole('table')
    expect(screen.getByText('Computing calibration summary…')).toBeInTheDocument()
  })

  it('shows an inline note when the summary fails without breaking the table', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        const url = String(input)
        if (url.includes('/confidence/summary')) {
          return { ok: false, status: 500, json: async () => ({ error: 'boom' }) }
        }
        return { ok: true, status: 200, json: async () => confidencePage }
      }),
    )
    renderPage()
    await screen.findByRole('table')
    expect(await screen.findByText(/Calibration summary unavailable/)).toBeInTheDocument()
    expect(screen.getByText('1 confidence row · page 1 of 1')).toBeInTheDocument()
  })
})