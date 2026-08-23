import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuditPage } from '@/features/audit/AuditPage'
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

const auditPage = {
  entries: [
    {
      id: 'a1',
      tenant_id: tenantId,
      user_id: 'u1',
      policy_id: null,
      cognitive_layer: 'perception',
      cognitive_concept: 'observation',
      action: 'captured',
      resource_type: 'observation',
      resource_id: 'o1',
      details: { source: 'linux-agent' },
      ip_address: '127.0.0.1',
      user_agent: 'test-agent',
      timestamp: '2026-08-20T10:00:00Z',
    },
    {
      id: 'a2',
      tenant_id: tenantId,
      user_id: null,
      policy_id: 'p1',
      cognitive_layer: 'reasoning',
      cognitive_concept: 'pattern',
      action: 'detected',
      resource_type: 'pattern',
      resource_id: 'pat1',
      details: { strength: 0.9 },
      ip_address: null,
      user_agent: null,
      timestamp: '2026-08-20T10:05:00Z',
    },
  ],
  total: 2,
  limit: 50,
  offset: 0,
  facets: {
    cognitive_layers: ['perception', 'reasoning'],
    cognitive_concepts: ['observation', 'pattern'],
    actions: ['captured', 'detected'],
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
      <AuditPage />
    </QueryClientProvider>,
  )
}

function mockAudit(response: typeof auditPage) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (input: string) => {
      if (input.includes('/audit')) {
        return { ok: true, status: 200, json: async () => response }
      }
      return { ok: false, status: 404, json: async () => ({ error: 'not found' }) }
    }),
  )
}

describe('AuditPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders audit entries as a table with layers and actions', async () => {
    mockAudit(auditPage)
    renderPage()
    const table = await screen.findByRole('table')
    expect(within(table).getByText('perception')).toBeInTheDocument()
    expect(within(table).getByText('reasoning')).toBeInTheDocument()
    expect(within(table).getByText('observation')).toBeInTheDocument()
    expect(within(table).getByText('pattern')).toBeInTheDocument()
    expect(within(table).getByText('captured')).toBeInTheDocument()
    expect(within(table).getByText('detected')).toBeInTheDocument()
    expect(await screen.findByText('2 entries · page 1 of 1')).toBeInTheDocument()
  })

  it('opens the detail drawer on row click', async () => {
    const user = userEvent.setup()
    mockAudit(auditPage)
    renderPage()
    const table = await screen.findByRole('table')
    await user.click(within(table).getByText('perception'))
    const dialog = await screen.findByRole('dialog', { name: 'Audit entry detail' })
    expect(within(dialog).getByText('Details')).toBeInTheDocument()
    expect(within(dialog).getByText(/View source/)).toBeInTheDocument()
  })

  it('shows an empty state when there are no audit entries', async () => {
    mockAudit({ ...auditPage, entries: [], total: 0 })
    renderPage()
    expect(await screen.findByText('No audit entries yet')).toBeInTheDocument()
  })

  it('shows a forbidden state on 403', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockImplementation(async (input: string) => {
        if (input.includes('/audit')) {
          return { ok: false, status: 403, json: async () => ({ error: 'forbidden' }) }
        }
        return { ok: false, status: 404, json: async () => ({ error: 'not found' }) }
      }),
    )
    renderPage()
    expect(await screen.findByText('Access denied', undefined, { timeout: 5000 })).toBeInTheDocument()
  })
})
