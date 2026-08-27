import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { LearningPage } from '@/features/learning/LearningPage'

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

function makePatternRefinement() {
  return {
    tenant_id: tenantId,
    total_patterns: 1,
    patterns_with_outcomes: 1,
    results: [
      {
        pattern_id: '11111111-1111-1111-1111-111111111111',
        pattern_type: 'correlation',
        context_id: '22222222-2222-2222-2222-222222222222',
        tenant_id: tenantId,
        linked_decisions: 4,
        corroborated: 3,
        contradicted: 1,
        inconclusive: 0,
        contradiction_ratio: 0.25,
        current_strength: 1,
        recommended_strength: 0.75,
        recommended_action: 'degrade',
      },
    ],
  }
}

function makeContextRevision() {
  return {
    tenant_id: tenantId,
    total_contexts: 1,
    contexts_with_outcomes: 1,
    results: [
      {
        context_id: '22222222-2222-2222-2222-222222222222',
        tenant_id: tenantId,
        linked_decisions: 4,
        corroborated: 1,
        contradicted: 3,
        inconclusive: 0,
        contradiction_ratio: 0.75,
        has_competing_models: true,
        recommended_revision: 'consider_competitor',
        suggested_competitor: 'alt-9',
      },
    ],
  }
}

function makeInsightTransformations() {
  return {
    tenant_id: tenantId,
    total_insights: 1,
    results: [
      {
        insight_id: '33333333-3333-3333-3333-333333333333',
        tenant_id: tenantId,
        context_id: '22222222-2222-2222-2222-222222222222',
        description: 'Disk pressure is the dominant cause',
        prior_understanding: 'Memory pressure was the cause',
        mental_model_update: { cause: 'disk_pressure' },
        transformation_kind: 'revised',
        linked_recommendations: 1,
        linked_decisions_with_outcomes: 2,
        corroborated: 1,
        contradicted: 1,
        inconclusive: 0,
      },
    ],
  }
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

function renderLearning(initialEntry = '/learning') {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/learning" element={<LearningPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function mockFetch(responses: Record<string, unknown>, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (input: string, init?: { method?: string }) => {
      const url = String(input)
      let body: unknown = {}
      if (url.includes('/patterns/refinement')) body = responses.patterns ?? {}
      else if (url.includes('/contexts/revision')) body = responses.contexts ?? {}
      else if (url.includes('/insights/transformations')) body = responses.insights ?? {}
      else if (url.includes('/memory') && init?.method === 'POST')
        body = responses.memoryPost ?? {}
      else if (url.includes('/memory'))
        body = responses.memories ?? { memories: [], total: 0 }
      return { ok: status >= 200 && status < 300, status, json: async () => body }
    }),
  )
}

describe('LearningPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders all three P7 sections with data', async () => {
    mockFetch({
      patterns: makePatternRefinement(),
      contexts: makeContextRevision(),
      insights: makeInsightTransformations(),
    })
    renderLearning()
    expect(await screen.findByText('Learning (P7)')).toBeInTheDocument()

    // Pattern Refinement section
    expect(await screen.findByText('Pattern Refinement')).toBeInTheDocument()
    expect(screen.getByText('degrade')).toBeInTheDocument()
    expect(screen.getByText('1.00 → 0.75')).toBeInTheDocument()

    // Context Revision section
    expect(await screen.findByText('Context Revision')).toBeInTheDocument()
    expect(screen.getByText('consider_competitor')).toBeInTheDocument()
    expect(screen.getByText('alt-9')).toBeInTheDocument()

    // Insight Transformations section
    expect(await screen.findByText('Insight Transformations')).toBeInTheDocument()
    expect(screen.getByText('revised')).toBeInTheDocument()
    expect(screen.getByText('Disk pressure is the dominant cause')).toBeInTheDocument()
    // prior -> updated journaling is shown
    expect(screen.getByText(/prior:/)).toBeInTheDocument()

    // Persisted Memory section renders (empty in this scenario)
    expect(await screen.findByText('Persisted Memory')).toBeInTheDocument()
    expect(screen.getByText('No persisted memory yet')).toBeInTheDocument()
  })

  it('renders persisted memory records when present', async () => {
    mockFetch({
      patterns: { tenant_id: tenantId, total_patterns: 0, patterns_with_outcomes: 0, results: [] },
      contexts: { tenant_id: tenantId, total_contexts: 0, contexts_with_outcomes: 0, results: [] },
      insights: { tenant_id: tenantId, total_insights: 0, results: [] },
      memories: {
        memories: [
          {
            id: 'm1',
            tenant_id: tenantId,
            target_type: 'pattern',
            target_id: '11111111-1111-1111-1111-111111111111',
            signal: { recommended_action: 'degrade' },
            provenance: { corroborated: 3, contradicted: 1 },
            signal_hash: 'h',
            created_at: '2026-01-01T00:00:00Z',
          },
        ],
        total: 1,
      },
    })
    renderLearning()
    expect(await screen.findByText('Persisted Memory')).toBeInTheDocument()
    expect(await screen.findByText(/recommended_action/)).toBeInTheDocument()
  })

  it('persists a learning signal via the Save to Memory button', async () => {
    const fetchMock = vi.fn().mockImplementation(
      async (input: string, init?: { method?: string; body?: string }) => {
        const url = String(input)
        if (url.includes('/patterns/refinement'))
          return { ok: true, status: 200, json: async () => makePatternRefinement() }
        if (url.includes('/contexts/revision'))
          return { ok: true, status: 200, json: async () => ({ tenant_id: tenantId, total_contexts: 0, contexts_with_outcomes: 0, results: [] }) }
        if (url.includes('/insights/transformations'))
          return { ok: true, status: 200, json: async () => ({ tenant_id: tenantId, total_insights: 0, results: [] }) }
        if (url.includes('/memory') && init?.method === 'POST') {
          const parsed = JSON.parse(init.body ?? '{}')
          return {
            ok: true,
            status: 200,
            json: async () => ({
              id: 'm1',
              tenant_id: tenantId,
              target_type: parsed.target_type,
              target_id: parsed.target_id,
              signal: parsed.signal,
              provenance: parsed.provenance,
              signal_hash: 'h',
              created_at: '2026-01-01T00:00:00Z',
            }),
          }
        }
        if (url.includes('/memory'))
          return { ok: true, status: 200, json: async () => ({ memories: [], total: 0 }) }
        return { ok: true, status: 200, json: async () => ({}) }
      },
    )
    vi.stubGlobal('fetch', fetchMock)
    renderLearning()

    const saveBtn = await screen.findByRole('button', { name: 'Save to Memory' })
    fireEvent.click(saveBtn)

    // Button reflects the saved state (implies the POST succeeded)
    expect(await screen.findByRole('button', { name: 'Saved' })).toBeInTheDocument()

    // POST was issued to /memory with the pattern signal
    const postCall = (fetchMock.mock.calls as Array<[string, { method?: string; body?: string }]>)
      .find(([u, o]) => String(u).includes('/memory') && o?.method === 'POST')
    expect(postCall).toBeTruthy()
    const payload = JSON.parse(postCall![1].body ?? '{}')
    expect(payload.target_type).toBe('pattern')
    expect(payload.signal.recommended_action).toBe('degrade')
  })

  it('shows forbidden state when the gateway denies access (403)', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async () => ({
        ok: false,
        status: 403,
        json: async () => ({ error: 'forbidden' }),
      })),
    )
    renderLearning()
    expect((await screen.findAllByText('Access denied')).length).toBeGreaterThanOrEqual(1)
  })

  it('renders empty states when there are no outcomes yet', async () => {
    mockFetch({ patterns: { tenant_id: tenantId, total_patterns: 0, patterns_with_outcomes: 0, results: [] },
      contexts: { tenant_id: tenantId, total_contexts: 0, contexts_with_outcomes: 0, results: [] },
      insights: { tenant_id: tenantId, total_insights: 0, results: [] } })
    renderLearning()
    expect(await screen.findByText('No patterns with outcomes')).toBeInTheDocument()
    expect(screen.getByText('No contexts with outcomes')).toBeInTheDocument()
    expect(screen.getByText('No insights yet')).toBeInTheDocument()
  })
})
