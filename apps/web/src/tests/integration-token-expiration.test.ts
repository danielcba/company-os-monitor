import { describe, it, expect, vi, beforeEach } from 'vitest'
import { apiFetch, setTokens, clearTokens, tryRefresh, getAccessToken } from '@/api/client'
import type { AuthSession } from '@/types/auth'

const session: AuthSession = {
  access_token: 'access-old',
  token_type: 'bearer',
  expires_in: 3600,
}

const newSession: AuthSession = {
  access_token: 'access-new',
  token_type: 'bearer',
  expires_in: 3600,
}

describe('Token expiration — integration', () => {
  beforeEach(() => {
    clearTokens()
    vi.restoreAllMocks()
  })

  it('refreshes token on 401 and retries the request', async () => {
    setTokens(session)
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => newSession })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({ data: 'ok' }) })
    vi.stubGlobal('fetch', mockFetch)

    const result = await apiFetch('/services/health')
    expect(result).toEqual({ data: 'ok' })
    expect(mockFetch).toHaveBeenCalledTimes(3)
    expect(getAccessToken()).toBe('access-new')
  })

  it('clears tokens and throws when refresh fails', async () => {
    setTokens(session)
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
    vi.stubGlobal('fetch', mockFetch)

    await expect(apiFetch('/services/health')).rejects.toMatchObject({ status: 401 })
    expect(getAccessToken()).toBeNull()
  })

  it('clears tokens when refresh endpoint is unreachable', async () => {
    setTokens(session)
    const mockFetch = vi
      .fn()
      .mockResolvedValueOnce({ ok: false, status: 401, json: async () => ({}) })
      .mockRejectedValueOnce(new TypeError('Failed to fetch'))
    vi.stubGlobal('fetch', mockFetch)

    await expect(apiFetch('/services/health')).rejects.toMatchObject({ status: 401 })
    expect(getAccessToken()).toBeNull()
  })

  it('deduplicates concurrent refresh requests', async () => {
    setTokens(session)
    const mockFetch = vi
      .fn()
      .mockResolvedValue({ ok: false, status: 401, json: async () => ({}) })
    vi.stubGlobal('fetch', mockFetch)

    const p1 = apiFetch('/services/health').catch(() => {})
    const p2 = apiFetch('/services/health').catch(() => {})
    await Promise.all([p1, p2])

    const refreshCalls = mockFetch.mock.calls.filter(
      (call: unknown[]) => {
        const init = call[1] as RequestInit | undefined
        return init?.method === 'POST' && typeof init?.body === 'undefined'
      },
    )
    expect(refreshCalls).toHaveLength(1)
  })

  it('tryRefresh returns false when no refresh token exists', async () => {
    clearTokens()
    const result = await tryRefresh()
    expect(result).toBe(false)
  })

  it('tryRefresh clears tokens on network error', async () => {
    setTokens(session)
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const result = await tryRefresh()
    expect(result).toBe(false)
    expect(getAccessToken()).toBeNull()
  })
})
