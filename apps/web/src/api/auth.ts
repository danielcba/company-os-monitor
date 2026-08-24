import { apiFetch } from '@/api/client'
import type { AuthSession, LoginRequest, UserProfile } from '@/types/auth'

export async function login(credentials: LoginRequest): Promise<AuthSession> {
  return apiFetch<AuthSession>('/auth/login', {
    method: 'POST',
    body: JSON.stringify(credentials),
    skipAuth: true,
    credentials: 'include',
  })
}

export async function fetchMe(): Promise<UserProfile> {
  return apiFetch<UserProfile>('/user/me')
}