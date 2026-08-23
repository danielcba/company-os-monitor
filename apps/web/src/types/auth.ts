export type Role = 'viewer' | 'operator' | 'admin' | 'superadmin'

export interface UserProfile {
  id: string
  tenant_id: string
  email: string
  name: string | null
  role: Role
  is_active: boolean
  created_at: string
  updated_at: string
}

export interface AuthSession {
  access_token: string
  refresh_token: string
  token_type: string
  expires_in: number
}

export interface TokenClaims {
  sub: string
  tenant_id: string
  email: string
  role: Role
  token_type: 'access' | 'refresh'
  exp: number
  iat: number
}

export interface LoginRequest {
  email: string
  password: string
  tenant_id?: string
}

export interface RefreshRequest {
  refresh_token: string
}