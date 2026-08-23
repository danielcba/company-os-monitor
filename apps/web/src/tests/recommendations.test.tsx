import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { RecommendationsPage } from '@/features/recommendations/RecommendationsPage'
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

const recommendationPage = {
  recommendations: [
    {
      id: 'r1',
      tenant_id: tenantId,
      hypothesis_id: 'h1',
      confidence_id: 'c1',
      action_description: 'Expand the backup volume before day 10.',
      rationale: 'Backup disk reaches capacity in 12 days.',
      expected_consequences: [
        'Backup jobs stop failing with disk full.',
        'Retention stays at 30 days.',
      ],
      alternatives_considered: [
        { option: 'Compress older backups', not_chosen: 'higher restore risk' },
        { option: 'Reduce retention window', not_chosen: 'shorter audit trail' },
      ],
      confidence_score: 0.72,
      status: 'proposed',
      proposed_at: '2026-08-19T17:00:00Z',
    },
    {
      id: 'r2',
      tenant_id: tenantId,
      hypothesis_id: 'h2',
      confidence_id: 'c2',
      action_description: 'Reset the affected account credentials.',
      rationale: 'Login bursts are consistent with a compromised account.',
      expected_consequences: ['Login failures stop repeating.'],
      alternatives_considered: [],
      confidence_score: 0.44,
      status: 'accepted',
      proposed_at: '2026-08-19T17:10:00Z',
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    statuses: ['accepted', 'proposed'],
  },
}

const recommendationDetail = {
  recommendation: recommendationPage.recommendations[0],
  hypothesis: {
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
  confidence: {
    confidence: {
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
    target: null,
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
      <RecommendationsPage />
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

describe('RecommendationsPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders proposed offers with status badge, confidence and facets', async () => {
    mockFetch([{ match: (u) => u.includes('/recommendations'), response: recommendationPage }])
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('Proposed')).toBeInTheDocument()
    expect(within(table).getByText('Accepted')).toBeInTheDocument()
    expect(
      within(table).getByText('Expand the backup volume before day 10.'),
    ).toBeInTheDocument()
    expect(within(table).getByText('0.7200')).toBeInTheDocument()
    expect(await screen.findByText('2 recommendations · page 1 of 1')).toBeInTheDocument()
  })

  it('opens the detail drawer with consequences, alternatives, confidence and hypothesis', async () => {
    const user = userEvent.setup()
    mockFetch([
      { match: (u) => u.includes('/recommendations/'), response: recommendationDetail },
      { match: (u) => u.includes('/recommendations'), response: recommendationPage },
    ])
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByText('Expand the backup volume before day 10.'))
    const dialog = await screen.findByRole('dialog', { name: 'Recommendation detail' })
    expect(within(dialog).getByText('Expected consequences')).toBeInTheDocument()
    expect(
      within(dialog).getByText('Backup jobs stop failing with disk full.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByText('Alternatives considered')).toBeInTheDocument()
    expect(
      within(dialog).getByText(/Compress older backups/),
    ).toBeInTheDocument()
    expect(within(dialog).getByText('Calibrated confidence (R4)')).toBeInTheDocument()
    expect(within(dialog).getByText('0.7200')).toBeInTheDocument()
    expect(within(dialog).getByText('Leading hypothesis')).toBeInTheDocument()
    expect(
      within(dialog).getByText('Capacity pressure explains the deviation.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByText(/capacity_risk/)).toBeInTheDocument()
  })

  it('forwards the status filter selection to the gateway', async () => {
    const user = userEvent.setup()
    mockFetch([{ match: (u) => u.includes('/recommendations'), response: recommendationPage }])
    renderPage()
    const select = await screen.findByLabelText('Status')
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'proposed' })).toBeInTheDocument()
    })
    await user.selectOptions(select, 'proposed')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes('status=proposed'))).toBe(true)
    })
  })

  it('shows an empty state when there are no recommendations', async () => {
    mockFetch([
      {
        match: (u) => u.includes('/recommendations'),
        response: { ...recommendationPage, recommendations: [], total: 0 },
      },
    ])
    renderPage()
    expect(await screen.findByText('No recommendations yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (String(input).includes('/recommendations')) {
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