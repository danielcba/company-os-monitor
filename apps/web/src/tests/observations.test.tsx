import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { ObservationsPage } from '@/features/observations/ObservationsPage'
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

const observationsPage = {
  observations: [
    {
      id: 'o1',
      tenant_id: tenantId,
      source_id: 's1',
      source_type: 'linux_agent',
      fact_type: 'cpu_utilization_percent',
      fact_value: { value: 94 },
      unit: '%',
      captured_at: '2026-08-19T14:02:00Z',
      quality_class: 'Q1',
      raw_payload: { agent: 'linux-agent-1' },
    },
    {
      id: 'o2',
      tenant_id: tenantId,
      source_id: 's2',
      source_type: 'linux_agent',
      fact_type: 'memory_free_bytes',
      fact_value: { value: 1073741824 },
      unit: 'bytes',
      captured_at: '2026-08-19T14:03:00Z',
      quality_class: 'Q2',
      raw_payload: { agent: 'linux-agent-1' },
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    fact_types: ['cpu_utilization_percent', 'memory_free_bytes'],
    source_types: ['linux_agent'],
    quality_classes: ['Q1', 'Q2', 'Q3', 'Q4'],
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
      <ObservationsPage />
    </QueryClientProvider>,
  )
}

function mockObservations(response: typeof observationsPage) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (input: string) => {
      if (input.includes('/observations')) {
        return { ok: true, status: 200, json: async () => response }
      }
      return { ok: false, status: 404, json: async () => ({ error: 'not found' }) }
    }),
  )
}

describe('ObservationsPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders raw facts as a table with quality classes and pagination', async () => {
    mockObservations(observationsPage)
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('cpu_utilization_percent')).toBeInTheDocument()
    expect(within(table).getByText('memory_free_bytes')).toBeInTheDocument()
    expect(within(table).getByText('value=94')).toBeInTheDocument()
    expect(within(table).getByText('%')).toBeInTheDocument()
    expect(within(table).getAllByText('linux_agent').length).toBeGreaterThan(0)
    expect(within(table).getByText('Q1')).toBeInTheDocument()
    expect(within(table).getByText('Q2')).toBeInTheDocument()
    expect(await screen.findByText('2 observations · page 1 of 1')).toBeInTheDocument()
  })

  it('shows the canonical quality class legend', async () => {
    mockObservations(observationsPage)
    renderPage()
    expect(await screen.findByText('Q1 — Direct Measurement')).toBeInTheDocument()
    expect(screen.getByText('Q2 — Corroborated Inference')).toBeInTheDocument()
    expect(screen.getByText('Q3 — Statistical Regularity')).toBeInTheDocument()
    expect(screen.getByText('Q4 — Anecdotal / Single-Source')).toBeInTheDocument()
  })

  it('opens the detail drawer with provenance fields on row click', async () => {
    const user = userEvent.setup()
    mockObservations(observationsPage)
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByText('cpu_utilization_percent'))
    const dialog = await screen.findByRole('dialog', { name: 'Observation detail' })
    expect(within(dialog).getByText('Fact value')).toBeInTheDocument()
    expect(within(dialog).getByText('Raw payload')).toBeInTheDocument()
    expect(within(dialog).getByText(/linux-agent-1/)).toBeInTheDocument()
  })

  it('forwards filter selection to the gateway', async () => {
    const user = userEvent.setup()
    mockObservations(observationsPage)
    renderPage()
    const select = await screen.findByLabelText('Quality class')
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'Q2' })).toBeInTheDocument()
    })
    await user.selectOptions(select, 'Q2')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes('quality_class=Q2'))).toBe(true)
    })
  })

  it('shows an empty state when there are no observations', async () => {
    mockObservations({ ...observationsPage, observations: [], total: 0 })
    renderPage()
    expect(await screen.findByText('No observations yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (input.includes('/observations')) {
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