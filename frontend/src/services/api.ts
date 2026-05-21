import axios, { type AxiosError, type InternalAxiosRequestConfig } from 'axios'

const DEFAULT_BASE_URL = 'http://localhost:8000'

/** localStorage key for JWT (used until dedicated auth store exists). */
const TOKEN_KEY = 'neo_kanban_jwt'

export function getAuthToken(): string | null {
  if (typeof window === 'undefined') return null
  return localStorage.getItem(TOKEN_KEY)
}

export function setAuthToken(token: string | null): void {
  if (typeof window === 'undefined') return
  if (token == null || token === '') {
    localStorage.removeItem(TOKEN_KEY)
  } else {
    localStorage.setItem(TOKEN_KEY, token)
  }
}

function normalizeBaseUrl(url: string | undefined): string {
  const raw = (url ?? '').trim()
  if (!raw) return DEFAULT_BASE_URL
  return raw.replace(/\/$/, '')
}

/** Base URL for REST calls: explicit `VITE_API_URL`, else dev uses '' (Vite proxy → 127.0.0.1:8000). */
export function resolveApiBaseURL(): string {
  const raw = import.meta.env.VITE_API_URL
  if (raw != null && String(raw).trim() !== '') {
    return normalizeBaseUrl(String(raw))
  }
  if (import.meta.env.DEV) {
    return ''
  }
  return DEFAULT_BASE_URL
}

/** Avoid infinite "Loading workspace…" when backend/proxy is hung (default axios = no timeout). */
const API_TIMEOUT_MS = 30_000

export const api = axios.create({
  baseURL: resolveApiBaseURL(),
  headers: { 'Content-Type': 'application/json' },
  timeout: API_TIMEOUT_MS,
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAuthToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

function resolve401RedirectPath(): string {
  const env = import.meta.env.VITE_401_REDIRECT
  if (env != null && String(env).trim() !== '') {
    return String(env).trim()
  }
  if (import.meta.env.DEV) {
    return '/dev/auth'
  }
  return '/auth-required'
}

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      setAuthToken(null)
      const redirectPath = resolve401RedirectPath()
      const path = window.location.pathname
      if (path === '/dev/auth' || path === '/auth-required') {
        return Promise.reject(error)
      }
      const target = redirectPath.startsWith('http')
        ? redirectPath
        : new URL(redirectPath.startsWith('/') ? redirectPath : `/${redirectPath}`, window.location.origin)
            .href
      window.location.assign(target)
    }
    return Promise.reject(error)
  },
)

export default api
