import { ApiError } from '@/types/cognitive'
import type { AuthSession } from '@/types/auth'

const API_URL = (import.meta.env.VITE_API_URL as string | undefined) ?? 'http://localhost:8100/api/v1'
const USER_SERVICE_URL =
  (import.meta.env.VITE_USER_SERVICE_URL as string | undefined) ?? 'http://localhost:8099/api/v1'

// Phase 20.1: Access token in memory only (never in localStorage).
// Refresh token is in HttpOnly cookie (server-managed, JS-inaccessible).
let accessToken: string | null = null

export function getAccessToken(): string | null {
  return accessToken
}

export function setAccessToken(token: string | null): void {
  accessToken = token
}

// Phase 20.1: setTokens now only stores access token in memory.
// The refresh token is set as HttpOnly cookie by the backend.
export function setTokens(session: AuthSession): void {
  accessToken = session.access_token
  // refresh_token is NOT stored in JS — it's in HttpOnly cookie set by backend.
}

export function clearTokens(): void {
  accessToken = null
}

let refreshInFlight: Promise<boolean> | null = null

export async function tryRefresh(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight
  refreshInFlight = (async () => {
    try {
      // Phase 20.1: Refresh uses HttpOnly cookie (credentials: "include").
      // The browser sends the refresh_token cookie automatically.
      // No body.refresh_token — the cookie is the source of truth.
      const res = await fetch(`${USER_SERVICE_URL}/auth/refresh`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
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

  // Phase 20.1: Always include credentials so HttpOnly cookies are sent.
  const res = await fetch(url, { ...rest, headers: finalHeaders, credentials: 'include' })

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