import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
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
    vi.fn().mockImplementation(async (input: string) => {
      let body: unknown = {}
      if (String(input).includes('/patterns/refinement')) body = responses.patterns ?? {}
      else if (String(input).includes('/contexts/revision')) body = responses.contexts ?? {}
      else if (String(input).includes('/insights/transformations')) body = responses.insights ?? {}
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
