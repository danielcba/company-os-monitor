import { ApiError } from '@/types/cognitive'
import type { AuthSession } from '@/types/auth'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8100/api/v1'
const USER_SERVICE_URL =
  (import.meta.env.VITE_USER_SERVICE_URL as string | undefined) ?? 'http://localhost:8099/api/v1'

const TOKEN_KEY = 'cosmonitor.access_token'
const REFRESH_KEY = 'cosmonitor.refresh_token'

export function getAccessToken(): string | null {
  return localStorage.getItem(TOKEN_KEY)
}

export function getRefreshToken(): string | null {
  return localStorage.getItem(REFRESH_KEY)
}

export function setTokens(session: AuthSession): void {
  localStorage.setItem(TOKEN_KEY, session.access_token)
  localStorage.setItem(REFRESH_KEY, session.refresh_token)
}

export function clearTokens(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
}

let refreshInFlight: Promise<boolean> | null = null

export async function tryRefresh(): Promise<boolean> {
  const refreshToken = getRefreshToken()
  if (!refreshToken) return false
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    try {
      const res = await fetch(`${USER_SERVICE_URL}/auth/refresh`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ refresh_token: refreshToken }),
      })
      if (!res.ok) {
        clearTokens()
        return false
      }
      const session = (await res.json()) as AuthSession
      setTokens(session)
      return true
    } catch {
      clearTokens()
      return false
    } finally {
      refreshInFlight = null
    }
  })()
  return refreshInFlight
}

export interface RequestOptions extends RequestInit {
  skipAuth?: boolean
  retryOn401?: boolean
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { skipAuth = false, retryOn401 = true, headers, ...rest } = options
  const base = path.startsWith('/user')
    ? USER_SERVICE_URL
    : API_URL
  const url = `${base}${path}`
  const finalHeaders: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(headers as Record<string, string> | undefined),
  }
  if (!skipAuth) {
    const token = getAccessToken()
    if (token) finalHeaders.Authorization = `Bearer ${token}`
  }

  const res = await fetch(url, { ...rest, headers: finalHeaders })

  if (res.status === 401 && retryOn401 && !skipAuth) {
    const refreshed = await tryRefresh()
    if (refreshed) return apiFetch<T>(path, { ...options, retryOn401: false })
    throw new ApiError(401, 'Session expired. Please sign in again.')
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const body = (await res.json()) as { error?: string }
      if (body.error) message = body.error
    } catch {
      // keep default message
    }
    throw new ApiError(res.status, message)
  }

  if (res.status === 204) return undefined as T
  return (await res.json()) as T
}