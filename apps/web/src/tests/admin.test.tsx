import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, within } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { UsersPage } from '@/features/admin/UsersPage'
import { RolesPage } from '@/features/admin/RolesPage'
import { TenantsPage } from '@/features/admin/TenantsPage'
import { SystemPage } from '@/features/admin/SystemPage'
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

const usersResponse = {
  users: [
    {
      id: 'u1',
      tenant_id: tenantId,
      email: 'admin@sandbox.local',
      name: 'Admin',
      role: 'superadmin',
      is_active: true,
      created_at: '2026-08-01T00:00:00Z',
      updated_at: '2026-08-01T00:00:00Z',
    },
    {
      id: 'u2',
      tenant_id: tenantId,
      email: 'viewer@sandbox.local',
      name: 'Viewer',
      role: 'viewer',
      is_active: true,
      created_at: '2026-08-02T00:00:00Z',
      updated_at: '2026-08-02T00:00:00Z',
    },
  ],
}

const tenantsResponse = {
  tenants: [
    {
      id: tenantId,
      name: 'Sandbox Tenant',
      slug: 'sandbox',
      plan: 'professional',
      settings: {},
      created_at: '2026-08-01T00:00:00Z',
      updated_at: '2026-08-01T00:00:00Z',
    },
  ],
}

const servicesHealth = {
  services: [
    { service: 'collector', url: 'http://localhost:8090/health', status: 200, healthy: true },
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

function renderComponent(Component: React.ComponentType) {
  return render(
    <QueryClientProvider client={queryClient}>
      <Component />
    </QueryClientProvider>,
  )
}

function mockFetch(handler: (input: string) => unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockImplementation(async (input: string) => {
      const result = handler(input)
      return { ok: true, status: 200, json: async () => result }
    }),
  )
}

describe('UsersPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders users in a table with roles and status', async () => {
    mockFetch((input) => {
      if (input.includes('/user/users')) return usersResponse
      return {}
    })
    renderComponent(UsersPage)
    const table = await screen.findByRole('table')
    expect(within(table).getByText('admin@sandbox.local')).toBeInTheDocument()
    expect(within(table).getByText('viewer@sandbox.local')).toBeInTheDocument()
    expect(within(table).getByText('superadmin')).toBeInTheDocument()
    expect(within(table).getByText('viewer')).toBeInTheDocument()
  })

  it('shows empty state when no users', async () => {
    mockFetch(() => ({ users: [] }))
    renderComponent(UsersPage)
    expect(await screen.findByText('No users')).toBeInTheDocument()
  })
})

describe('RolesPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders all four roles with their permissions', () => {
    renderComponent(RolesPage)
    expect(screen.getByText('viewer')).toBeInTheDocument()
    expect(screen.getByText('operator')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    expect(screen.getByText('superadmin')).toBeInTheDocument()
    expect(screen.getAllByText('Read pipeline data').length).toBeGreaterThan(0)
  })
})

describe('TenantsPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders tenants in a table', async () => {
    mockFetch((input) => {
      if (input.includes('/user/tenants')) return tenantsResponse
      return {}
    })
    renderComponent(TenantsPage)
    const table = await screen.findByRole('table')
    expect(within(table).getByText('Sandbox Tenant')).toBeInTheDocument()
    expect(within(table).getByText('sandbox')).toBeInTheDocument()
    expect(within(table).getByText('professional')).toBeInTheDocument()
  })
})

describe('SystemPage', () => {
  beforeEach(() => {
    queryClient.clear()
    vi.restoreAllMocks()
  })

  it('renders the system page heading', () => {
    mockFetch(() => servicesHealth)
    renderComponent(SystemPage)
    expect(screen.getByText('System')).toBeInTheDocument()
    expect(screen.getByText('Infrastructure health, gateway metrics, and user service metrics.')).toBeInTheDocument()
  })
})
