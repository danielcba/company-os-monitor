import { apiFetch } from '@/api/client'
import type { UserProfile } from '@/types/auth'

export interface UpdateUserRequest {
  name?: string
  role?: string
}

export async function updateUser(userId: string, data: UpdateUserRequest): Promise<UserProfile> {
  return apiFetch<UserProfile>(`/user/users/${userId}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  })
}

export async function deactivateUser(userId: string): Promise<UserProfile> {
  return apiFetch<UserProfile>(`/user/users/${userId}`, {
    method: 'DELETE',
  })
}

export interface CreateUserRequest {
  email: string
  password: string
  name?: string
  role?: string
}

export async function createUser(data: CreateUserRequest): Promise<UserProfile> {
  return apiFetch<UserProfile>('/user/users', {
    method: 'POST',
    body: JSON.stringify(data),
  })
}
