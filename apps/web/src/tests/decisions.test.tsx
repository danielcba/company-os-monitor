import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { DecisionsPage } from '@/features/decisions/DecisionsPage'
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

const decisionPage = {
  decisions: [
    {
      id: 'd1',
      tenant_id: tenantId,
      recommendation_id: 'r1',
      confidence_id: 'c1',
      authority_id: 'a1',
      commitment: 'Expand the volume on day 8 and raise the alert threshold to 90%.',
      expected_outcomes: [
        {
          prediction: 'Backup capacity stays above 20% for 6 months.',
          verifiable_by: 'disk usage query',
          deadline: '2027-02-20',
        },
      ],
      risk_tolerance: 'medium',
      status: 'committed',
      committed_at: '2026-08-19T18:00:00Z',
      executed_at: null,
      actual_outcomes: null,
    },
    {
      id: 'd2',
      tenant_id: tenantId,
      recommendation_id: 'r2',
      confidence_id: 'c2',
      authority_id: 'a1',
      commitment: 'Reset credentials and revoke all sessions.',
      expected_outcomes: [],
      risk_tolerance: 'high',
      status: 'completed',
      committed_at: '2026-08-19T18:30:00Z',
      executed_at: null,
      actual_outcomes: null,
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    statuses: ['committed', 'completed'],
  },
}

const decisionDetail = {
  decision: decisionPage.decisions[0],
  recommendation: {
    recommendation: {
      id: 'r1',
      tenant_id: tenantId,
      hypothesis_id: 'h1',
      confidence_id: 'c1',
      action_description: 'Expand the backup volume before day 10.',
      rationale: 'Backup disk reaches capacity in 12 days.',
      expected_consequences: ['Backup jobs stop failing with disk full.'],
      alternatives_considered: [],
      confidence_score: 0.72,
      status: 'accepted',
      proposed_at: '2026-08-19T17:00:00Z',
    },
    hypothesis: null,
    confidence: null,
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
      <DecisionsPage />
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

describe('DecisionsPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders committed decisions with status badge, risk and outcome counts', async () => {
    mockFetch([{ match: (u) => u.includes('/decisions'), response: decisionPage }])
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('Committed')).toBeInTheDocument()
    expect(within(table).getByText('Completed')).toBeInTheDocument()
    expect(
      within(table).getByText('Expand the volume on day 8 and raise the alert threshold to 90%.'),
    ).toBeInTheDocument()
    expect(within(table).getByText('Medium')).toBeInTheDocument()
    expect(within(table).getByText('High')).toBeInTheDocument()
    expect(await screen.findByText('2 decisions · page 1 of 1')).toBeInTheDocument()
  })

  it('opens the detail drawer with commitment, expected outcomes, recommendation and confidence', async () => {
    const user = userEvent.setup()
    mockFetch([
      { match: (u) => u.includes('/decisions/'), response: decisionDetail },
      { match: (u) => u.includes('/decisions'), response: decisionPage },
    ])
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(
      within(table).getByText('Expand the volume on day 8 and raise the alert threshold to 90%.'),
    )
    const dialog = await screen.findByRole('dialog', { name: 'Decision detail' })
    expect(
      within(dialog).getByText('Expand the volume on day 8 and raise the alert threshold to 90%.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByText('Expected outcomes (falsifiable)')).toBeInTheDocument()
    expect(
      within(dialog).getByText('Backup capacity stays above 20% for 6 months.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByText(/verifiable by: disk usage query/)).toBeInTheDocument()
    expect(within(dialog).getByText('Committed recommendation')).toBeInTheDocument()
    expect(
      within(dialog).getByText('Expand the backup volume before day 10.'),
    ).toBeInTheDocument()
    expect(within(dialog).getByText('Calibrated confidence (R4)')).toBeInTheDocument()
    expect(within(dialog).getByText('0.7200')).toBeInTheDocument()
  })

  it('forwards the status filter selection to the gateway', async () => {
    const user = userEvent.setup()
    mockFetch([{ match: (u) => u.includes('/decisions'), response: decisionPage }])
    renderPage()
    const select = await screen.findByLabelText('Status')
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'committed' })).toBeInTheDocument()
    })
    await user.selectOptions(select, 'committed')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes('status=committed'))).toBe(true)
    })
  })

  it('shows an empty state when there are no decisions', async () => {
    mockFetch([
      {
        match: (u) => u.includes('/decisions'),
        response: { ...decisionPage, decisions: [], total: 0 },
      },
    ])
    renderPage()
    expect(await screen.findByText('No decisions yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (String(input).includes('/decisions')) {
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