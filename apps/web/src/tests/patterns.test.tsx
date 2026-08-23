import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { PatternsPage } from '@/features/patterns/PatternsPage'
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

const patternPage = {
  patterns: [
    {
      id: 'pat1',
      tenant_id: tenantId,
      context_id: 'ctx1',
      pattern_type: 'temporal',
      description:
        'El contexto capacity_risk se activó 3 veces en la ventana de 28 días (intervalo mediano ~7 días). Regularidad detectada.',
      strength_measure: 0.6,
      frequency: 'weekly',
      detected_at: '2026-08-19T14:20:00Z',
      is_active: true,
    },
    {
      id: 'pat2',
      tenant_id: tenantId,
      context_id: 'ctx2',
      pattern_type: 'correlation',
      description: 'El contexto service_failure se activó 3 veces en la ventana de 28 días. Regularidad detectada.',
      strength_measure: 0.6,
      frequency: 'event-driven',
      detected_at: '2026-08-19T14:21:00Z',
      is_active: true,
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    pattern_types: ['temporal', 'correlation'],
    is_active: ['true', 'false'],
  },
}

const patternDetail = {
  pattern: patternPage.patterns[0],
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
      <PatternsPage />
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

describe('PatternsPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders regularities with type, strength and facets', async () => {
    mockFetch([{ match: (u) => u.includes('/patterns'), response: patternPage }])
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getAllByText('0.6000').length).toBeGreaterThan(0)
    expect(within(table).getByText('temporal')).toBeInTheDocument()
    expect(within(table).getByText('correlation')).toBeInTheDocument()
    expect(within(table).getByText('weekly')).toBeInTheDocument()
    expect(within(table).getAllByText('Active').length).toBeGreaterThan(0)
    expect(await screen.findByText('2 patterns · page 1 of 1')).toBeInTheDocument()
  })

  it('opens the detail drawer with the source context', async () => {
    const user = userEvent.setup()
    mockFetch([
      {
        match: (u) => u.includes('/patterns/'),
        response: patternDetail,
      },
      {
        match: (u) => u.includes('/patterns'),
        response: patternPage,
      },
    ])
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByText('temporal'))
    const dialog = await screen.findByRole('dialog', { name: 'Pattern detail' })
    expect(within(dialog).getByText('Source context')).toBeInTheDocument()
    expect(await within(dialog).findByText('capacity_risk')).toBeInTheDocument()
    expect(within(dialog).getByText('infrastructure_health')).toBeInTheDocument()
    expect(within(dialog).getByText('Coherence')).toBeInTheDocument()
  })

  it('forwards filter selection to the gateway', async () => {
    const user = userEvent.setup()
    mockFetch([{ match: (u) => u.includes('/patterns'), response: patternPage }])
    renderPage()
    const select = await screen.findByLabelText('Pattern type')
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'correlation' })).toBeInTheDocument()
    })
    await user.selectOptions(select, 'correlation')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes('pattern_type=correlation'))).toBe(true)
    })
  })

  it('shows an empty state when there are no patterns', async () => {
    mockFetch([{ match: (u) => u.includes('/patterns'), response: { ...patternPage, patterns: [], total: 0 } }])
    renderPage()
    expect(await screen.findByText('No patterns yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (String(input).includes('/patterns')) {
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