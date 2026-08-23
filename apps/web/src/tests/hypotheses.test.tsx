import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { HypothesesPage } from '@/features/hypotheses/HypothesesPage'
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

const hypothesisPage = {
  hypotheses: [
    {
      id: 'h1',
      tenant_id: tenantId,
      anomaly_ids: ['an1'],
      pattern_ids: [],
      description: 'Capacity pressure explains the deviation.',
      predicted_consequences: [
        'CPU utilization keeps exceeding the threshold.',
        'Memory free bytes continue to drop.',
      ],
      falsification_criterion: 'An observation of idle CPU for 24h would falsify it.',
      coherence_score: 0.66,
      status: 'candidate',
      generated_at: '2026-08-19T15:00:00Z',
    },
    {
      id: 'h2',
      tenant_id: tenantId,
      anomaly_ids: ['an2'],
      pattern_ids: [],
      description: 'Auth compromise explains the burst.',
      predicted_consequences: ['Login failures keep repeating nightly.'],
      falsification_criterion: 'No failed logins for 7 days would falsify it.',
      coherence_score: 0.44,
      status: 'falsified',
      generated_at: '2026-08-19T15:05:00Z',
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    statuses: ['candidate', 'falsified'],
  },
}

const hypothesisDetail = {
  hypothesis: hypothesisPage.hypotheses[0],
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
      <HypothesesPage />
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

describe('HypothesesPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders tentative explanations with status badge, coherence and facets', async () => {
    mockFetch([{ match: (u) => u.includes('/hypotheses'), response: hypothesisPage }])
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('Candidate')).toBeInTheDocument()
    expect(within(table).getByText('Falsified')).toBeInTheDocument()
    expect(
      within(table).getByText('Capacity pressure explains the deviation.'),
    ).toBeInTheDocument()
    expect(within(table).getAllByText('0.66').length).toBeGreaterThan(0)
    expect(await screen.findByText('2 hypotheses · page 1 of 1')).toBeInTheDocument()
  })

  it('opens the detail drawer with consequences, falsification criterion and source anomaly', async () => {
    const user = userEvent.setup()
    mockFetch([
      {
        match: (u) => u.includes('/hypotheses/'),
        response: hypothesisDetail,
      },
      {
        match: (u) => u.includes('/hypotheses'),
        response: hypothesisPage,
      },
    ])
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByText('Capacity pressure explains the deviation.'))
    const dialog = await screen.findByRole('dialog', { name: 'Hypothesis detail' })
    expect(within(dialog).getByText('Predicted consequences')).toBeInTheDocument()
    expect(
      within(dialog).getByText('CPU utilization keeps exceeding the threshold.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByText('Falsification criterion')).toBeInTheDocument()
    expect(
      within(dialog).getByText('An observation of idle CPU for 24h would falsify it.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByText('capacity_risk')).toBeInTheDocument()
    expect(within(dialog).getByText('infrastructure_health')).toBeInTheDocument()
  })

  it('forwards status filter selection to the gateway', async () => {
    const user = userEvent.setup()
    mockFetch([{ match: (u) => u.includes('/hypotheses'), response: hypothesisPage }])
    renderPage()
    const select = await screen.findByLabelText('Status')
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'falsified' })).toBeInTheDocument()
    })
    await user.selectOptions(select, 'falsified')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes('status=falsified'))).toBe(true)
    })
  })

  it('shows an empty state when there are no hypotheses', async () => {
    mockFetch([
      {
        match: (u) => u.includes('/hypotheses'),
        response: { ...hypothesisPage, hypotheses: [], total: 0 },
      },
    ])
    renderPage()
    expect(await screen.findByText('No hypotheses yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (String(input).includes('/hypotheses')) {
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