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

export const api = axios.create({
  baseURL: normalizeBaseUrl(import.meta.env.VITE_API_URL),
  headers: { 'Content-Type': 'application/json' },
})

api.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const token = getAuthToken()
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      setAuthToken(null)
      const redirect = import.meta.env.VITE_401_REDIRECT ?? '/'
      const target = redirect.startsWith('http')
        ? redirect
        : new URL(redirect.startsWith('/') ? redirect : `/${redirect}`, window.location.origin).href
      window.location.assign(target)
    }
    return Promise.reject(error)
  }
)

export default api
