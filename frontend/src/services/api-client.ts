import axios, { type AxiosInstance } from 'axios'

import { resolveApiBaseURL } from './api'

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

/**
 * Axios client with optional Bearer token.
 * Use for authenticated calls after login (spec 003 T022).
 */
export function createApiClient(token: string | null): AxiosInstance {
  const client = axios.create({
    baseURL: BASE_URL,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  })
  return client
}
