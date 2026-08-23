import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { EvidencePage } from '@/features/evidence/EvidencePage'
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

const evidencePage = {
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
    {
      id: 'ev2',
      tenant_id: tenantId,
      observation_ids: ['o2'],
      organization_type: 'service_degradation_evidence',
      description: 'Observations indicate a stopped auto-start service with error events.',
      quality_class: 'Q2',
      weight: 0.625,
      organized_at: '2026-08-19T14:06:00Z',
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    organization_types: ['resource_exhaustion_evidence', 'service_degradation_evidence'],
    quality_classes: ['Q1', 'Q2', 'Q3', 'Q4'],
  },
}

const evidenceDetail = {
  evidence: evidencePage.evidence[0],
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
      <EvidencePage />
    </QueryClientProvider>,
  )
}

function mockFetch(
  responses: { match: (url: string) => boolean; response: unknown }[],
  failFor?: string,
) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (input: string) => {
      const url = String(input)
      if (failFor && url.includes(failFor)) {
        return { ok: false, status: 500, json: async () => ({ error: 'boom' }) }
      }
      const hit = responses.find((r) => r.match(url))
      if (hit) return { ok: true, status: 200, json: async () => hit.response }
      return { ok: false, status: 404, json: async () => ({ error: 'not found' }) }
    }),
  )
}

describe('EvidencePage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders organized facts as a table with quality, weight and pagination', async () => {
    mockFetch([{ match: (u) => u.includes('/evidence'), response: evidencePage }])
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('resource_exhaustion_evidence')).toBeInTheDocument()
    expect(within(table).getByText('service_degradation_evidence')).toBeInTheDocument()
    expect(within(table).getByText('0.875')).toBeInTheDocument()
    expect(within(table).getByText('Q1')).toBeInTheDocument()
    expect(within(table).getByText('Q2')).toBeInTheDocument()
    expect(await screen.findByText('2 evidence · page 1 of 1')).toBeInTheDocument()
  })

  it('shows the canonical quality class legend', async () => {
    mockFetch([{ match: (u) => u.includes('/evidence'), response: evidencePage }])
    renderPage()
    expect(await screen.findByText('Q1 — Direct Measurement')).toBeInTheDocument()
    expect(screen.getByText('Q4 — Anecdotal / Single-Source')).toBeInTheDocument()
  })

  it('opens the detail drawer and resolves the observation desglose', async () => {
    const user = userEvent.setup()
    mockFetch([
      {
        match: (u) => u.includes('/evidence/'),
        response: evidenceDetail,
      },
      {
        match: (u) => u.includes('/evidence'),
        response: evidencePage,
      },
    ])
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByText('resource_exhaustion_evidence'))
    const dialog = await screen.findByRole('dialog', { name: 'Evidence detail' })
    expect(within(dialog).getByText('Organized observations')).toBeInTheDocument()
    expect(await within(dialog).findByText('cpu_utilization_percent')).toBeInTheDocument()
    expect(within(dialog).getByText('value=94 %')).toBeInTheDocument()
  })

  it('forwards filter selection to the gateway', async () => {
    const user = userEvent.setup()
    mockFetch([{ match: (u) => u.includes('/evidence'), response: evidencePage }])
    renderPage()
    const select = await screen.findByLabelText('Organization type')
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'service_degradation_evidence' })).toBeInTheDocument()
    })
    await user.selectOptions(select, 'service_degradation_evidence')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes('organization_type=service_degradation_evidence'))).toBe(true)
    })
  })

  it('shows an empty state when there is no evidence', async () => {
    mockFetch([{ match: (u) => u.includes('/evidence'), response: { ...evidencePage, evidence: [], total: 0 } }])
    renderPage()
    expect(await screen.findByText('No evidence yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (String(input).includes('/evidence')) {
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