import { isAxiosError } from 'axios'
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from 'react'

import { authApi } from '../services/auth-api'
import { getAuthToken, setAuthToken } from '../services/api'
import type { User } from '../types'

const PUBLIC_AUTH_PATHS = new Set([
  '/login',
  '/register',
  '/reset-password',
  '/auth/callback',
  '/dev/auth',
])

interface AuthState {
  user: User | null
  token: string | null
  isLoading: boolean
}

interface AuthContextValue extends AuthState {
  login: (email: string, password: string) => Promise<void>
  logout: () => void
  /** Step 1: sends OTP. Returns the email address (confirmation). */
  register: (email: string, password: string, displayName: string) => Promise<{ email: string }>
  /** Step 2: verifies OTP, creates account, logs in. */
  verifyRegister: (email: string, code: string) => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

async function resolveUser(data: { access_token: string; user: User | null }): Promise<User> {
  if (data.user) return data.user
  return authApi.getMe()
}

function clearAuthSession(setToken: (v: string | null) => void, setUser: (v: User | null) => void) {
  setAuthToken(null)
  setToken(null)
  setUser(null)
}

function redirectToLoginIfProtected() {
  const path = window.location.pathname
  if (PUBLIC_AUTH_PATHS.has(path)) return
  window.location.replace('/login')
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [token, setToken] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    let cancelled = false

    async function bootstrap() {
      const stored = getAuthToken()
      if (!stored) {
        if (!cancelled) setIsLoading(false)
        return
      }

      setToken(stored)
      try {
        const me = await authApi.getMe(stored)
        if (!cancelled && getAuthToken() === stored) setUser(me)
      } catch {
        if (cancelled || getAuthToken() !== stored) return
        clearAuthSession(setToken, setUser)
        redirectToLoginIfProtected()
      } finally {
        if (!cancelled) setIsLoading(false)
      }
    }

    void bootstrap()
    return () => {
      cancelled = true
    }
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const data = await authApi.login(email, password)
    setAuthToken(data.access_token)
    setToken(data.access_token)
    setUser(await resolveUser(data))
    setIsLoading(false)
  }, [])

  const register = useCallback(async (email: string, password: string, displayName: string) => {
    const data = await authApi.register(email, password, displayName)
    // OTP sent — user not created yet; return email for the verification step
    return { email: data.email }
  }, [])

  const verifyRegister = useCallback(async (email: string, code: string) => {
    const data = await authApi.verifyRegister(email, code)
    setAuthToken(data.access_token)
    setToken(data.access_token)
    setUser(await resolveUser(data))
    setIsLoading(false)
  }, [])

  const logout = useCallback(() => {
    setAuthToken(null)
    setToken(null)
    setUser(null)
  }, [])

  return (
    <AuthContext.Provider value={{ user, token, isLoading, login, logout, register, verifyRegister }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return ctx
}
