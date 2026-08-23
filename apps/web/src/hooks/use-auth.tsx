import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { fetchMe, login } from '@/api/auth'
import { clearTokens, getAccessToken, setTokens } from '@/api/client'
import type { LoginRequest, UserProfile } from '@/types/auth'

interface AuthContextValue {
  user: UserProfile | null
  accessToken: string | null
  isLoading: boolean
  isAuthenticated: boolean
  signIn: (credentials: LoginRequest) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthContextValue | undefined>(undefined)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserProfile | null>(null)
  const [accessToken, setAccessToken] = useState<string | null>(() => getAccessToken())
  const [isLoading, setIsLoading] = useState<boolean>(() => Boolean(getAccessToken()))

  useEffect(() => {
    if (!accessToken) {
      setUser(null)
      setIsLoading(false)
      return
    }
    let cancelled = false
    setIsLoading(true)
    fetchMe()
      .then((profile) => {
        if (!cancelled) setUser(profile)
      })
      .catch(() => {
        if (!cancelled) {
          clearTokens()
          setAccessToken(null)
          setUser(null)
        }
      })
      .finally(() => {
        if (!cancelled) setIsLoading(false)
      })
    return () => {
      cancelled = true
    }
  }, [accessToken])

  const signIn = useCallback(async (credentials: LoginRequest) => {
    const session = await login(credentials)
    setTokens(session)
    setAccessToken(session.access_token)
  }, [])

  const signOut = useCallback(() => {
    clearTokens()
    setAccessToken(null)
    setUser(null)
  }, [])

  const value = useMemo<AuthContextValue>(
    () => ({
      user,
      accessToken,
      isLoading,
      isAuthenticated: Boolean(accessToken),
      signIn,
      signOut,
    }),
    [user, accessToken, isLoading, signIn, signOut],
  )

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider')
  return ctx
}