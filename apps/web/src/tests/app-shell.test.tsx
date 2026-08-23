import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { AppShell } from '@/components/layout/AppShell'

vi.mock('@/hooks/use-auth', () => ({
  useAuth: () => ({
    user: { tenant_id: 'tenant-1234', email: 'admin@sandbox.local', name: 'Admin', role: 'superadmin' },
    accessToken: 't',
    isLoading: false,
    isAuthenticated: true,
    signIn: vi.fn(),
    signOut: vi.fn(),
  }),
}))

vi.mock('@/hooks/use-theme', () => ({
  useTheme: () => ({ theme: 'light', toggleTheme: vi.fn() }),
}))

vi.mock('@tanstack/react-query', () => ({
  useQuery: () => ({ data: undefined, isPending: true, isError: false, error: null }),
}))

describe('AppShell', () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it('renders the sidebar, header and a footer describing the cognitive boundary', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard']}>
        <AppShell />
      </MemoryRouter>,
    )
    expect(screen.getByText('COS-Monitor')).toBeInTheDocument()
    expect(screen.getByText('Cognitive OS Monitor')).toBeInTheDocument()
    expect(screen.getByText(/API Gateway/)).toBeInTheDocument()
    expect(screen.getByText('Observations')).toBeInTheDocument()
    expect(screen.getByText('Confidence')).toBeInTheDocument()
    expect(screen.getByText('Decisions')).toBeInTheDocument()
  })
})