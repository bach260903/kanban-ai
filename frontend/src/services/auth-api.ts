import { api, type ApiRequestConfig } from './api'
import type { User } from '../types'

export interface AuthTokenResponse {
  access_token: string
  token_type: string
  user: User | null
}

export const authApi = {
  async register(
    email: string,
    password: string,
    display_name: string,
  ): Promise<AuthTokenResponse> {
    const res = await api.post<AuthTokenResponse>('/api/v1/auth/register', {
      email,
      password,
      display_name,
    })
    return res.data
  },

  async login(email: string, password: string): Promise<AuthTokenResponse> {
    const res = await api.post<AuthTokenResponse>('/api/v1/auth/login', { email, password })
    return res.data
  },

  async getMe(token?: string): Promise<User> {
    if (token) {
      const res = await api.get<User>('/api/v1/auth/me', {
        headers: { Authorization: `Bearer ${token}` },
        skipAuthRedirect: true,
      } as ApiRequestConfig)
      return res.data
    }
    const res = await api.get<User>('/api/v1/auth/me')
    return res.data
  },
}

/** Dev-only token from ``POST /api/v1/dev/token`` (requires ``DEV_AUTH_ENABLED=true``). */
export async function fetchDevToken(): Promise<{ access_token: string }> {
  const res = await api.post<{ access_token: string; token_type?: string }>('/api/v1/dev/token')
  return { access_token: res.data.access_token }
}
