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

// Phase 20.1: AuthSession no longer contains refresh_token.
// The refresh token is in HttpOnly cookie (JS-inaccessible).
export interface AuthSession {
  access_token: string
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

// Phase 20.1: RefreshRequest no longer needed (cookie-based).
// Kept for backward compatibility in deprecated body path.
export interface RefreshRequest {
  refresh_token: string
}