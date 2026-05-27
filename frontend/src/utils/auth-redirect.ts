import type { Location } from 'react-router-dom'

const BLOCKED_PATHS = new Set(['/login', '/register', '/dev/auth', '/auth-required'])

/** Only allow same-origin relative paths (prevent open redirects). */
export function isSafeRedirectPath(path: string): boolean {
  if (!path.startsWith('/') || path.startsWith('//')) return false
  const pathname = path.split(/[?#]/)[0] ?? path
  return !BLOCKED_PATHS.has(pathname)
}

export function getAuthRedirectTarget(
  location: Location,
  searchParams?: URLSearchParams,
): string {
  const state = location.state as { from?: Location } | null
  const from = state?.from
  if (from?.pathname && isSafeRedirectPath(from.pathname)) {
    return `${from.pathname}${from.search ?? ''}${from.hash ?? ''}`
  }

  const returnTo = searchParams?.get('returnTo')
  if (returnTo && isSafeRedirectPath(returnTo)) {
    return returnTo
  }

  return '/dashboard'
}

export function buildLoginPath(returnPath?: string): string {
  if (returnPath && isSafeRedirectPath(returnPath)) {
    return `/login?returnTo=${encodeURIComponent(returnPath)}`
  }
  return '/login'
}
