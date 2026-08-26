import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClientProvider } from '@tanstack/react-query'
import { ReportsPage } from '@/features/reports/ReportsPage'
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

const reportPage = {
  reports: [
    {
      id: 'rep1',
      tenant_id: tenantId,
      report_type: 'executive',
      title: 'COS-Monitor Executive Summary',
      summary: 'Top critical decisions and future risks for the period.',
      ai_generated: false,
      model_used: null,
      period_start: '2026-08-10',
      period_end: '2026-08-11',
      generated_at: '2026-08-20T10:00:00Z',
      file_path: '/tmp/opencode/report-executive.pdf',
    },
    {
      id: 'rep2',
      tenant_id: tenantId,
      report_type: 'json',
      title: 'COS-Monitor JSON Report',
      summary: null,
      ai_generated: false,
      model_used: null,
      period_start: '2026-08-10',
      period_end: '2026-08-11',
      generated_at: '2026-08-20T10:05:00Z',
      file_path: '/tmp/opencode/report-json.json',
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    report_types: ['executive', 'json'],
  },
}

const reportDetail = {
  report: {
    ...reportPage.reports[0],
    content: {
      title: 'COS-Monitor Executive Summary',
      decision_count: 1,
      top_decisions: [
        {
          decision_id: 'd1',
          commitment: 'Expand the volume on day 8.',
          risk_tolerance: 'low',
          confidence: 0.72,
          expected_outcome_count: 1,
          action: 'Expand the backup volume before day 10.',
        },
      ],
      future_risks: [],
      pending_authority: [],
    },
  },
  tenant: { id: tenantId, name: 'ACME Corp', slug: 'acme' },
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
      <MemoryRouter>
        <ReportsPage />
      </MemoryRouter>
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

describe('ReportsPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders reports with type badge, period and generation source', async () => {
    mockFetch([{ match: (u) => u.includes('/reports'), response: reportPage }])
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('Executive')).toBeInTheDocument()
    expect(within(table).getByText('JSON')).toBeInTheDocument()
    expect(
      within(table).getByText('COS-Monitor Executive Summary'),
    ).toBeInTheDocument()
    expect(within(table).getAllByText('Local template').length).toBe(2)
    expect(await screen.findByText('2 reports · page 1 of 1')).toBeInTheDocument()
  })

  it('opens the detail drawer with the rendered content and tenant header', async () => {
    const user = userEvent.setup()
    mockFetch([
      { match: (u) => u.includes('/reports/'), response: reportDetail },
      { match: (u) => u.includes('/reports'), response: reportPage },
    ])
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByText('COS-Monitor Executive Summary'))
    const dialog = await screen.findByRole('dialog', { name: 'Report detail' })
    expect(within(dialog).getByText('ACME Corp (acme)')).toBeInTheDocument()
    expect(within(dialog).getByText('Rendered content')).toBeInTheDocument()
    expect(within(dialog).getByText('decision_count')).toBeInTheDocument()
    expect(
      within(dialog).getAllByText('1').length,
    ).toBeGreaterThanOrEqual(1)
    expect(
      within(dialog).getByText('Expand the volume on day 8.'),
    ).toBeInTheDocument()
  })

  it('forwards the report_type filter selection to the gateway', async () => {
    const user = userEvent.setup()
    mockFetch([{ match: (u) => u.includes('/reports'), response: reportPage }])
    renderPage()
    const select = await screen.findByLabelText('Report type')
    await waitFor(() => {
      expect(within(select).getByRole('option', { name: 'executive' })).toBeInTheDocument()
    })
    await user.selectOptions(select, 'executive')
    await waitFor(() => {
      const fetchMock = vi.mocked(fetch)
      const calls = fetchMock.mock.calls.map(([input]) => String(input))
      expect(calls.some((url) => url.includes('report_type=executive'))).toBe(true)
    })
  })

  it('shows an empty state when there are no reports', async () => {
    mockFetch([
      {
        match: (u) => u.includes('/reports'),
        response: { ...reportPage, reports: [], total: 0 },
      },
    ])
    renderPage()
    expect(await screen.findByText('No reports yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (String(input).includes('/reports')) {
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