import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiFetch, getAccessToken, setTokens, clearTokens, tryRefresh } from '@/api/client'
import type { AuthSession } from '@/types/auth'

const session: AuthSession = {
  access_token: 'access-1',
  refresh_token: 'refresh-1',
  token_type: 'bearer',
  expires_in: 3600,
}

describe('api client', () => {
  beforeEach(() => {
    localStorage.clear()
    vi.restoreAllMocks()
  })

  it('sets and clears tokens from storage', () => {
    expect(getAccessToken()).toBeNull()
    setTokens(session)
    expect(getAccessToken()).toBe('access-1')
    clearTokens()
    expect(getAccessToken()).toBeNull()
  })

  it('adds the bearer token to authenticated requests', async () => {
    setTokens(session)
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    })
    vi.stubGlobal('fetch', mockFetch)
    await apiFetch('/services/health')
    const [, init] = mockFetch.mock.calls[0]
    expect(init.headers.Authorization).toBe('Bearer access-1')
  })

  it('does not attach a token when skipAuth is true', async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ ok: true }),
    })
    vi.stubGlobal('fetch', mockFetch)
    await apiFetch('/auth/login', { method: 'POST', skipAuth: true })
    const [, init] = mockFetch.mock.calls[0]
    expect(init.headers.Authorization).toBeUndefined()
  })

  it('refreshes and retries once on 401', async () => {
    setTokens(session)
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ access_token: 'access-2', refresh_token: 'refresh-2' }),
      })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ refreshed: true }) })
    vi.stubGlobal('fetch', mockFetch)
    const result = await apiFetch('/services/health')
    expect(result).toEqual({ refreshed: true })
    expect(mockFetch).toHaveBeenCalledTimes(3)
    expect(getAccessToken()).toBe('access-2')
  })

  it('throws ApiError with status 403 for forbidden', async () => {
    setTokens(session)
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: false,
        status: 403,
        json: async () => ({ error: 'forbidden' }),
      }),
    )
    await expect(apiFetch('/services/health')).rejects.toMatchObject({ status: 403 })
  })

  it('tryRefresh returns false when no refresh token exists', async () => {
    clearTokens()
    const ok = await tryRefresh()
    expect(ok).toBe(false)
  })
})