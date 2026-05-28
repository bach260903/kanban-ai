/**
 * /auth/callback — handles the redirect from GitHub OAuth.
 *
 * Backend redirects here with:
 *   /auth/callback?token={jwt}          ← success
 *   /auth/callback?error={reason}       ← failure (optional)
 *
 * Security: token is read once, then stripped from the URL via replaceState
 * before persisting or redirecting.
 */

import { useEffect, useRef, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { Spinner } from '../components/atoms/spinner'
import { authApi } from '../services/auth-api'
import { setAuthToken } from '../services/api'

import styles from './auth-callback.module.css'

type CallbackPhase = 'loading' | 'error'

export default function AuthCallbackPage() {
  const [searchParams] = useSearchParams()
  const started = useRef(false)
  const [phase, setPhase] = useState<CallbackPhase>('loading')
  const [errorMessage, setErrorMessage] = useState<string | null>(null)

  useEffect(() => {
    if (started.current) return
    started.current = true

    const token = searchParams.get('token')
    const error = searchParams.get('error')

    // Strip credentials from the address bar immediately
    window.history.replaceState({}, document.title, '/auth/callback')

    void (async () => {
      if (token) {
        setAuthToken(token)
        try {
          await authApi.getMe(token)
          window.location.replace('/dashboard')
        } catch {
          setAuthToken(null)
          setErrorMessage('Could not verify your session. Please sign in again.')
          setPhase('error')
          window.setTimeout(() => {
            window.location.replace('/login?error=github_failed')
          }, 1800)
        }
        return
      }

      const reason = error ?? 'github_failed'
      window.location.replace(`/login?error=${encodeURIComponent(reason)}`)
    })()
  }, [searchParams])

  return (
    <div className={styles.shell} role="status" aria-live="polite" aria-busy={phase === 'loading'}>
      <div className={styles.card}>
        {phase === 'loading' ? (
          <>
            <Spinner aria-label="Signing in with GitHub" />
            <h1 className={styles.title}>Signing you in with GitHub…</h1>
            <p className={styles.sub}>Please wait while we finish setting up your session.</p>
          </>
        ) : (
          <>
            <h1 className={styles.title}>Sign-in failed</h1>
            <p className={styles.sub}>{errorMessage ?? 'Redirecting to login…'}</p>
          </>
        )}
      </div>
    </div>
  )
}
