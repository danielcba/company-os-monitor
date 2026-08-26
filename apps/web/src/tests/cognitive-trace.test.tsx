import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { CognitiveTracePage } from '@/features/cognitive-trace/CognitiveTracePage'

const tenantId = '00000000-0000-0000-0000-000000000001'
const reportId = 'rep1'

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

function makeTrace(overrides: Record<string, unknown> = {}) {
  return {
    root: { type: 'report', id: reportId, tenant_id: tenantId },
    nodes: [
      { type: 'report', id: 'r1', tenant_id: tenantId, timestamp: null, data: { title: 'Exec report' } },
      { type: 'decision', id: 'd1', tenant_id: tenantId, timestamp: null, data: { commitment: 'Expand volume' } },
      { type: 'recommendation', id: 'rec1', tenant_id: tenantId, timestamp: null, data: { action_description: 'Add disk' } },
      { type: 'confidence', id: 'c1', tenant_id: tenantId, timestamp: null, data: { confidence_score: 0.85 } },
      { type: 'hypothesis', id: 'h1', tenant_id: tenantId, timestamp: null, data: { description: 'Disk pressure' } },
      { type: 'anomaly', id: 'a1', tenant_id: tenantId, timestamp: null, data: { anomaly_class: 'capacity', deviation_score: 1.2 } },
      { type: 'pattern', id: 'p1', tenant_id: tenantId, timestamp: null, data: { pattern_type: 'resource_pressure' } },
      { type: 'context', id: 'ctx1', tenant_id: tenantId, timestamp: null, data: { purpose: 'diagnose' } },
      { type: 'evidence', id: 'e1', tenant_id: tenantId, timestamp: null, data: { quality_class: 'Q1' } },
      { type: 'observation', id: 'o1', tenant_id: tenantId, timestamp: null, data: { fact_type: 'cpu', fact_value: 92 } },
    ],
    edges: [
      { from: 'r1', to: 'd1', relation: 'documents' },
      { from: 'd1', to: 'rec1', relation: 'commits' },
    ],
    completeness: 'complete',
    warnings: [],
    ...overrides,
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

function renderTrace(initialEntry = `/action/reports/${reportId}/trace`) {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[initialEntry]}>
        <Routes>
          <Route path="/action/reports/:reportId/trace" element={<CognitiveTracePage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

function mockFetch(response: unknown, status = 200) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (input: string) => {
      if (String(input).includes('/cognitive-trace/report/')) {
        return { ok: status >= 200 && status < 300, status, json: async () => response }
      }
      return { ok: false, status: 404, json: async () => ({ error: 'not found' }) }
    }),
  )
}

describe('CognitiveTracePage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders the full provenance chain for a complete trace', async () => {
    mockFetch(makeTrace())
    renderTrace()
    expect(await screen.findByText('Cognitive Trace')).toBeInTheDocument()
    expect(await screen.findByText('complete')).toBeInTheDocument()
    // Each canonical node type is labeled.
    for (const label of ['Report', 'Decision', 'Recommendation', 'Confidence', 'Hypothesis', 'Anomaly', 'Pattern', 'Context', 'Evidence', 'Observation']) {
      expect(screen.getAllByText(label).length).toBeGreaterThanOrEqual(1)
    }
    // Summary text derived from node data shows up.
    expect(screen.getAllByText('Expand volume').length).toBeGreaterThanOrEqual(1)
    // Relationship rows render.
    expect(screen.getByText('documents')).toBeInTheDocument()
  })

  it('surfaces broken provenance as a partial trace with warnings', async () => {
    mockFetch(
      makeTrace({
        completeness: 'partial',
        warnings: ['decision d1 referenced by report not found'],
        nodes: [
          { type: 'report', id: 'r1', tenant_id: tenantId, timestamp: null, data: { title: 'Exec report' } },
        ],
        edges: [],
      }),
    )
    renderTrace()
    expect(await screen.findByText('partial')).toBeInTheDocument()
    expect(await screen.findByText('Provenance is partial')).toBeInTheDocument()
    expect(
      screen.getByText('decision d1 referenced by report not found'),
    ).toBeInTheDocument()
  })

  it('shows a tenant-scoped not-found state when the report is missing (404)', async () => {
    mockFetch({ error: 'not found' }, 404)
    renderTrace()
    expect(
      await screen.findByText('Report not found in this tenant'),
    ).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    mockFetch({ error: 'forbidden' }, 403)
    renderTrace()
    expect(await screen.findByText('Access denied')).toBeInTheDocument()
  })
})
