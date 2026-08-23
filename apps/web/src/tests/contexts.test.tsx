import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { ContextsPage } from '@/features/contexts/ContextsPage'
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

const contextPage = {
  contexts: [
    {
      id: 'ctx1',
      tenant_id: tenantId,
      evidence_ids: ['ev1'],
      mental_model_id: 'capacity_risk',
      purpose: 'infrastructure_health',
      coherence_score: 0.33,
      competing_models: [
        { mental_model_id: 'capacity_risk', coherence_score: 0.33 },
        { mental_model_id: 'resource_pressure', coherence_score: 0.33 },
        { mental_model_id: 'service_failure', coherence_score: 0.33 },
        { mental_model_id: 'connectivity_degradation', coherence_score: 0 },
      ],
      activated_at: '2026-08-19T14:10:00Z',
      is_active: true,
    },
    {
      id: 'ctx2',
      tenant_id: tenantId,
      evidence_ids: ['ev2'],
      mental_model_id: 'service_failure',
      purpose: 'security_posture',
      coherence_score: 0.33,
      competing_models: [
        { mental_model_id: 'service_failure', coherence_score: 0.33 },
        { mental_model_id: 'auth_compromise', coherence_score: 0 },
      ],
      activated_at: '2026-08-19T14:11:00Z',
      is_active: true,
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    purposes: ['infrastructure_health', 'security_posture'],
    mental_model_ids: ['capacity_risk', 'service_failure'],
    is_active: ['true', 'false'],
  },
}

const contextDetail = {
  context: contextPage.contexts[0],
  evidence: [
    {
      id: 'ev1',
      tenant_id: tenantId,
      observation_ids: ['o1'],
      organization_type: 'resource_exhaustion_evidence',
      description: 'Observations indicate sustained resource usage across cpu/mem/disk.',
      quality_class: 'Q1',
      weight: 0.875,
      organized_at: '2026-08-19T14:05:00Z',
    },
  ],
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
      <ContextsPage />
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

describe('ContextsPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders activations with winner model, coherence and competing models', async () => {
    mockFetch([{ match: (u) => u.includes('/contexts'), response: contextPage }])
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('capacity_risk')).toBeInTheDocument()
    expect(within(table).getByText('service_failure')).toBeInTheDocument()
    expect(within(table).getByText('infrastructure_health')).toBeInTheDocument()
    expect(within(table).getAllByText('0.33').length).toBeGreaterThan(0)
    expect(within(table).getAllByText('Active').length).toBeGreaterThan(0)
    expect(await screen.findByText('2 contexts · page 1 of 1')).toBeInTheDocument()
  })

  it('opens the detail drawer with competing models and evidence desglose', async () => {
    const user = userEvent.setup()
    mockFetch([
      {
        match: (u) => u.includes('/contexts/'),
        response: contextDetail,
      },
      {
        match: (u) => u.includes('/contexts'),
        response: contextPage,
      },
    ])
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByText('capacity_risk'))
    const dialog = await screen.findByRole('dialog', { name: 'Context detail' })
    expect(within(dialog).getByText('Competing mental models')).toBeInTheDocument()
    expect(within(dialog).getByText('resource_pressure')).toBeInTheDocument()
    expect(within(dialog).getByText('winner')).toBeInTheDocument()
    expect(within(dialog).getByText('Supporting evidence')).toBeInTheDocument()
    expect(await within(dialog).findByText('resource_exhaustion_evidence')).toBeInTheDocument()
    expect(within(dialog).getByText('Q1')).toBeInTheDocument()
  })

  it('forwards filter selection to the gateway', async () => {
    const user = userEvent.setup()
    mockFetch([{ match: (u) => u.includes('/contexts'), response: contextPage }])
    renderPage()
    const select = await screen.findByLabelText('Purpose')
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'security_posture' })).toBeInTheDocument()
    })
    await user.selectOptions(select, 'security_posture')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes('purpose=security_posture'))).toBe(true)
    })
  })

  it('shows an empty state when there are no contexts', async () => {
    mockFetch([{ match: (u) => u.includes('/contexts'), response: { ...contextPage, contexts: [], total: 0 } }])
    renderPage()
    expect(await screen.findByText('No contexts yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (String(input).includes('/contexts')) {
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