/**
 * ForgotPasswordModal — email-based password reset flow.
 *
 * Usage:
 *   const [open, setOpen] = useState(false)
 *   <ForgotPasswordModal open={open} onClose={() => setOpen(false)} />
 *
 * Calls POST /api/v1/auth/forgot-password. The backend always returns 200
 * (prevents email enumeration) and sends a reset link if the address is registered.
 */

import { isAxiosError } from 'axios'
import { AlertCircle, CheckCircle2, Loader2, Mail, X } from 'lucide-react'
import { type FormEvent, useCallback, useEffect, useRef, useState } from 'react'

import api from '../../services/api'
import styles from './forgot-password-modal.module.css'

export interface ForgotPasswordModalProps {
  open: boolean
  onClose: () => void
}

type SendState = 'idle' | 'loading' | 'success' | 'error'

export function ForgotPasswordModal({ open, onClose }: ForgotPasswordModalProps) {
  const [email, setEmail] = useState('')
  const [sendState, setSendState] = useState<SendState>('idle')
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const emailRef = useRef<HTMLInputElement>(null)

  // Reset form + auto-focus email when modal opens
  useEffect(() => {
    if (!open) return
    setEmail('')
    setSendState('idle')
    setErrorMsg(null)
    const t = window.setTimeout(() => emailRef.current?.focus(), 60)
    return () => clearTimeout(t)
  }, [open])

  // ESC key closes when not loading
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && sendState !== 'loading') onClose()
    },
    [onClose, sendState],
  )

  useEffect(() => {
    if (!open) return
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, handleKeyDown])

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setSendState('loading')
    setErrorMsg(null)

    try {
      await api.post('/api/v1/auth/forgot-password', { email: email.trim() })
      setSendState('success')
    } catch (err) {
      let msg = 'Could not send reset email. Please try again.'
      if (isAxiosError(err)) {
        const detail = (err.response?.data as { detail?: string } | undefined)?.detail
        if (typeof detail === 'string') msg = detail
      }
      setErrorMsg(msg)
      setSendState('error')
    }
  }

  if (!open) return null

  const loading = sendState === 'loading'
  const success = sendState === 'success'

  return (
    <div
      className={styles.backdrop}
      role="presentation"
      onClick={loading ? undefined : onClose}
    >
      <div
        className={styles.panel}
        role="dialog"
        aria-modal="true"
        aria-labelledby="forgot-pwd-title"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className={styles.header}>
          <h2 id="forgot-pwd-title" className={styles.title}>
            Reset password
          </h2>
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            disabled={loading}
            aria-label="Close reset password dialog"
          >
            <X size={18} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>

        {/* Success state */}
        {success ? (
          <div className={styles.successState}>
            <span className={styles.successIcon} aria-hidden="true">
              <CheckCircle2 size={42} strokeWidth={1.6} />
            </span>
            <p className={styles.successTitle}>Check your inbox</p>
            <p className={styles.successDesc}>
              If <strong>{email}</strong> is registered, you'll receive a reset link shortly.
              Check your spam folder if it doesn&apos;t arrive within a few minutes.
            </p>
            <button type="button" className={styles.doneBtn} onClick={onClose}>
              Done
            </button>
          </div>
        ) : (
          /* Form state */
          <>
            <p className={styles.desc}>
              Enter your email and we&apos;ll send you a link to reset your password.
            </p>

            <form onSubmit={handleSubmit} className={styles.form} noValidate>
              <div className={styles.field}>
                <span className={styles.fieldIcon} aria-hidden="true">
                  <Mail size={16} strokeWidth={2} />
                </span>
                <input
                  ref={emailRef}
                  id="forgot-email"
                  type="email"
                  className={`${styles.fieldInput} ${sendState === 'error' ? styles.fieldInputError : ''}`}
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    if (sendState === 'error') {
                      setSendState('idle')
                      setErrorMsg(null)
                    }
                  }}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                  disabled={loading}
                  aria-required="true"
                  aria-invalid={sendState === 'error'}
                  aria-describedby={errorMsg ? 'forgot-email-error' : undefined}
                />
              </div>

              {errorMsg ? (
                <p
                  id="forgot-email-error"
                  className={styles.errorAlert}
                  role="alert"
                  aria-live="polite"
                >
                  <AlertCircle size={13} aria-hidden="true" />
                  <span>{errorMsg}</span>
                </p>
              ) : null}

              <div className={styles.actions}>
                <button
                  type="button"
                  className={styles.cancelBtn}
                  onClick={onClose}
                  disabled={loading}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className={styles.submitBtn}
                  disabled={loading || !email.trim()}
                  aria-label={loading ? 'Sending reset link…' : 'Send reset link'}
                >
                  {loading ? (
                    <Loader2 size={14} className={styles.spin} aria-hidden="true" />
                  ) : null}
                  <span>{loading ? 'Sending…' : 'Send reset link'}</span>
                </button>
              </div>
            </form>
          </>
        )}
      </div>
    </div>
  )
}
