import { api, type ApiRequestConfig } from './api'
import type { User } from '../types'

export interface AuthTokenResponse {
  access_token: string
  token_type: string
  user: User | null
}

export interface VerificationSentResponse {
  message: string
  email: string
  needs_verification: true
}

export const authApi = {
  /** Step 1: validate data + send OTP to email. Does NOT create user yet. */
  async register(
    email: string,
    password: string,
    display_name: string,
  ): Promise<VerificationSentResponse> {
    const res = await api.post<VerificationSentResponse>('/api/v1/auth/register', {
      email,
      password,
      display_name,
    })
    return res.data
  },

  /** Step 2: submit 6-digit OTP → creates user + returns JWT. */
  async verifyRegister(email: string, code: string): Promise<AuthTokenResponse> {
    const res = await api.post<AuthTokenResponse>('/api/v1/auth/verify-register', {
      email,
      code,
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
    const res = await api.get<User>('/api/v1/auth/me', {
      skipAuthRedirect: true,
    } as ApiRequestConfig)
    return res.data
  },

  async resetPassword(token: string, newPassword: string): Promise<{ message: string }> {
    const res = await api.post<{ message: string }>('/api/v1/auth/reset-password', {
      token,
      new_password: newPassword,
    })
    return res.data
  },

  /** OTP flow step 1: request a 6-digit code sent to email. */
  async forgotPasswordOtp(email: string): Promise<{ message: string }> {
    const res = await api.post<{ message: string }>('/api/v1/auth/forgot-password', { email })
    return res.data
  },

  /** OTP flow step 2: verify code + set new password. */
  async verifyResetOtp(
    email: string,
    code: string,
    newPassword: string,
  ): Promise<{ message: string }> {
    const res = await api.post<{ message: string }>('/api/v1/auth/verify-reset', {
      email,
      code,
      new_password: newPassword,
    })
    return res.data
  },
}

/** Dev-only token from ``POST /api/v1/dev/token`` (requires ``DEV_AUTH_ENABLED=true``). */
export async function fetchDevToken(): Promise<{ access_token: string }> {
  const res = await api.post<{ access_token: string; token_type?: string }>('/api/v1/dev/token')
  return { access_token: res.data.access_token }
}
