import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { TimelinePage } from '@/features/timeline/TimelinePage'

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

const timelineResponse = {
  tenant_id: tenantId,
  events: [
    {
      tenant_id: tenantId,
      layer: 'perception',
      concept: 'observation',
      id: 'o1',
      timestamp: '2026-01-01T00:00:00Z',
      title: 'Observation: cpu',
      detail: '90 %',
      target_type: null,
      target_id: null,
      status: null,
    },
    {
      tenant_id: tenantId,
      layer: 'action',
      concept: 'decision',
      id: 'd1',
      timestamp: '2026-01-02T00:00:00Z',
      title: 'Decision (committed)',
      detail: 'risk=low',
      target_type: null,
      target_id: null,
      status: 'committed',
    },
  ],
  total: 2,
  per_layer_counts: { perception: 1, action: 1 },
  per_concept_counts: { observation: 1, decision: 1 },
  ascending: false,
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

function renderTimeline(initialEntry = '/investigation/timeline') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/investigation/timeline" element={<TimelinePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function mockFetch(body: unknown, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async () => ({
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    })),
  )
}

describe('TimelinePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the reconstructed timeline with layer badges', async () => {
    mockFetch(timelineResponse)
    renderTimeline()
    expect(await screen.findByText('Cognitive Timeline')).toBeInTheDocument()
    expect(await screen.findByText('Observation: cpu')).toBeInTheDocument()
    expect(screen.getByText('Decision (committed)')).toBeInTheDocument()
    expect(screen.getByText('perception: 1')).toBeInTheDocument()
    expect(screen.getByText('action: 1')).toBeInTheDocument()
  })

  it('renders empty state when there is no activity', async () => {
    mockFetch({ ...timelineResponse, events: [], total: 0, per_layer_counts: {}, per_concept_counts: {} })
    renderTimeline()
    expect(await screen.findByText('No activity')).toBeInTheDocument()
  })

  it('shows forbidden state when the gateway denies access (403)', async () => {
    mockFetch({ error: 'forbidden' }, 403)
    renderTimeline()
    expect((await screen.findAllByText('Access denied')).length).toBeGreaterThanOrEqual(1)
  })
})
