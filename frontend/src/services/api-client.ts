import axios, { type AxiosError, type AxiosInstance, type InternalAxiosRequestConfig } from 'axios'

import { showErrorToast } from '../lib/toast'
import { buildLoginPath } from '../utils/auth-redirect'

import { resolveApiBaseURL, setAuthToken } from './api'

/** Resolve ``/api/v1`` base (Vite proxy in dev, ``VITE_API_URL`` in production). */
export function resolveApiV1BaseURL(): string {
  const root = resolveApiBaseURL()
  if (!root) {
    return '/api/v1'
  }
  return `${root.replace(/\/$/, '')}/api/v1`
}

/** REST API v1 prefix. */
export const BASE_URL = resolveApiV1BaseURL()

type ClientRequestConfig = InternalAxiosRequestConfig & { skipAuthRedirect?: boolean }

const AUTH_PATHS = new Set([
  '/dev/auth',
  '/auth-required',
  '/login',
  '/register',
  '/reset-password',
  '/auth/callback',
])

function attachResponseInterceptor(client: AxiosInstance): AxiosInstance {
  client.interceptors.response.use(
    (response) => response,
    (error: AxiosError) => {
      const status = error.response?.status
      const skipRedirect = (error.config as ClientRequestConfig | undefined)?.skipAuthRedirect

      if (status === 401 && !skipRedirect) {
        setAuthToken(null)
        const path = window.location.pathname
        if (!AUTH_PATHS.has(path)) {
          const returnPath = `${window.location.pathname}${window.location.search}${window.location.hash}`
          window.location.assign(buildLoginPath(returnPath))
        }
      } else if (status === 403) {
        showErrorToast('Không đủ quyền thực hiện thao tác này')
      } else if (status != null && status >= 500) {
        showErrorToast('Lỗi server, vui lòng thử lại sau')
      }

      return Promise.reject(error)
    },
  )
  return client
}

/**
 * Axios client with optional Bearer token.
 * Use for authenticated calls after login (spec 003 T022 / T114).
 */
export function createApiClient(token: string | null): AxiosInstance {
  const client = axios.create({
    baseURL: BASE_URL,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  return attachResponseInterceptor(client)
}
