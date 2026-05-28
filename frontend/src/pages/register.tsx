import { isAxiosError } from 'axios'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
  GitBranch,
  Loader2,
  Lock,
  Mail,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  User,
  Users,
  Zap,
} from 'lucide-react'
import { type FormEvent, useMemo, useRef, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../contexts/auth-context'
import { ForgotPasswordModal } from '../components/molecules/forgot-password-modal'
import { TermsModal, type TermsType } from '../components/molecules/terms-modal'
import { resolveApiBaseURL } from '../services/api'

import styles from './login.module.css'
import otpStyles from './register-otp.module.css'

function GithubMark({ size = 18 }: { size?: number }) {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="currentColor"
      aria-hidden="true"
      focusable="false"
    >
      <path d="M12 .297c-6.63 0-12 5.373-12 12 0 5.303 3.438 9.8 8.205 11.385.6.113.82-.258.82-.577 0-.285-.01-1.04-.015-2.04-3.338.724-4.042-1.61-4.042-1.61C4.422 18.07 3.633 17.7 3.633 17.7c-1.087-.744.084-.729.084-.729 1.205.084 1.838 1.236 1.838 1.236 1.07 1.835 2.809 1.305 3.495.998.108-.776.417-1.305.76-1.605-2.665-.3-5.466-1.332-5.466-5.93 0-1.31.465-2.38 1.235-3.22-.135-.303-.54-1.523.105-3.176 0 0 1.005-.322 3.3 1.23.96-.267 1.98-.399 3-.405 1.02.006 2.04.138 3 .405 2.28-1.552 3.285-1.23 3.285-1.23.645 1.653.24 2.873.12 3.176.765.84 1.23 1.91 1.23 3.22 0 4.61-2.805 5.625-5.475 5.92.42.36.81 1.096.81 2.22 0 1.606-.015 2.896-.015 3.286 0 .315.21.69.825.57C20.565 22.092 24 17.592 24 12.297c0-6.627-5.373-12-12-12" />
    </svg>
  )
}

type StrengthLevel = 'weak' | 'fair' | 'good' | 'strong'
type Step = 'form' | 'otp'
type SubmitState = 'idle' | 'loading' | 'success'

function getPasswordStrength(password: string): {
  level: StrengthLevel | null
  segments: number
  label: string
} {
  if (!password) return { level: null, segments: 0, label: '' }
  const hasNumber = /\d/.test(password)
  const hasSymbol = /[^A-Za-z0-9]/.test(password)
  const len = password.length
  if (len >= 8 && hasNumber && hasSymbol) return { level: 'strong', segments: 4, label: 'Strong' }
  if (len >= 8 && (hasNumber || hasSymbol)) return { level: 'good', segments: 3, label: 'Good' }
  if (len >= 8) return { level: 'fair', segments: 2, label: 'Fair' }
  return { level: 'weak', segments: 1, label: 'Weak' }
}

// ── OTP Input — 6 separate boxes ─────────────────────────────────────────────

function OtpInput({ value, onChange, disabled }: {
  value: string
  onChange: (v: string) => void
  disabled?: boolean
}) {
  const refs = useRef<(HTMLInputElement | null)[]>([])
  const digits = value.padEnd(6, '').slice(0, 6).split('')

  function handleKey(i: number, e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === 'Backspace') {
      const next = digits.slice()
      if (next[i]) {
        next[i] = ''
      } else if (i > 0) {
        next[i - 1] = ''
        refs.current[i - 1]?.focus()
      }
      onChange(next.join(''))
      e.preventDefault()
    } else if (e.key === 'ArrowLeft' && i > 0) {
      refs.current[i - 1]?.focus()
    } else if (e.key === 'ArrowRight' && i < 5) {
      refs.current[i + 1]?.focus()
    }
  }

  function handleChange(i: number, e: React.ChangeEvent<HTMLInputElement>) {
    const raw = e.target.value.replace(/\D/g, '')
    if (!raw) return
    // Support paste — fill from position i
    const next = digits.slice()
    for (let j = 0; j < raw.length && i + j < 6; j++) {
      next[i + j] = raw[j]
    }
    onChange(next.join(''))
    const focusIdx = Math.min(i + raw.length, 5)
    refs.current[focusIdx]?.focus()
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    onChange(pasted.padEnd(6, '').slice(0, 6))
    refs.current[Math.min(pasted.length, 5)]?.focus()
  }

  return (
    <div className={otpStyles.otpBoxes} onPaste={handlePaste}>
      {Array.from({ length: 6 }, (_, i) => (
        <input
          key={i}
          ref={el => { refs.current[i] = el }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={digits[i] ?? ''}
          onChange={e => handleChange(i, e)}
          onKeyDown={e => handleKey(i, e)}
          onFocus={e => e.target.select()}
          disabled={disabled}
          className={`${otpStyles.otpBox} ${digits[i] ? otpStyles.otpBoxFilled : ''}`}
          aria-label={`Digit ${i + 1}`}
          autoComplete={i === 0 ? 'one-time-code' : 'off'}
        />
      ))}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────────

export default function RegisterPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { register, verifyRegister } = useAuth()

  // Step 1 — registration form
  const [step, setStep] = useState<Step>('form')
  const [pendingEmail, setPendingEmail] = useState('')

  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [termsAccepted, setTermsAccepted] = useState(false)
  const [termsModalType, setTermsModalType] = useState<TermsType | null>(null)
  const [forgotOpen, setForgotOpen] = useState(false)
  const [submitState, setSubmitState] = useState<SubmitState>('idle')
  const [nameError, setNameError] = useState<string | null>(null)
  const [emailError, setEmailError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [termsError, setTermsError] = useState<string | null>(null)
  const [generalError, setGeneralError] = useState<string | null>(null)
  const [githubLoading, setGithubLoading] = useState(false)

  // Step 2 — OTP
  const [otpValue, setOtpValue] = useState('')
  const [otpState, setOtpState] = useState<SubmitState>('idle')
  const [otpError, setOtpError] = useState<string | null>(null)
  const [resendCooldown, setResendCooldown] = useState(0)

  const loading = submitState === 'loading'
  const success = submitState === 'success'
  const strength = useMemo(() => getPasswordStrength(password), [password])
  const showStrength = password.length > 0
  const submitDisabled = loading || success || !termsAccepted

  // ── Step 1 submit ───────────────────────────────────────────────────────────
  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setNameError(null)
    setEmailError(null)
    setPasswordError(null)
    setTermsError(null)
    setGeneralError(null)

    let hasClientError = false
    if (!displayName.trim()) {
      setNameError('Display name is required.')
      hasClientError = true
    }
    if (!termsAccepted) {
      setTermsError('You must accept the Terms of Service and Privacy Policy.')
      hasClientError = true
    }
    if (password.length < 8) {
      setPasswordError('Password must be at least 8 characters long.')
      hasClientError = true
    }
    if (hasClientError) return

    setSubmitState('loading')
    try {
      const res = await register(email, password, displayName)
      setPendingEmail(res.email)
      setStep('otp')
      startResendCooldown()
    } catch (err) {
      if (isAxiosError(err)) {
        if (err.response?.status === 409) {
          setEmailError('This email is already registered.')
        } else {
          const raw = (err.response?.data as { detail?: unknown })?.detail
          if (typeof raw === 'string') {
            setGeneralError(raw)
          } else if (Array.isArray(raw) && raw.length > 0) {
            // Pydantic validation error — pick the first message
            const first = raw[0] as { msg?: string; loc?: string[] }
            const field = first.loc?.slice(-1)[0] ?? ''
            const msg = first.msg ?? 'Validation error'
            setGeneralError(field ? `${field}: ${msg}` : msg)
          } else {
            setGeneralError('Registration failed. Please try again.')
          }
        }
      } else {
        setGeneralError('Registration failed. Please try again.')
      }
    } finally {
      setSubmitState('idle')
    }
  }

  // ── Step 2 OTP verify ───────────────────────────────────────────────────────
  async function handleOtpSubmit(e: FormEvent) {
    e.preventDefault()
    if (otpValue.length !== 6) {
      setOtpError('Please enter all 6 digits.')
      return
    }
    setOtpError(null)
    setOtpState('loading')
    try {
      await verifyRegister(pendingEmail, otpValue)
      setOtpState('success')
      window.setTimeout(() => navigate('/projects', { replace: true }), 450)
    } catch (err) {
      if (isAxiosError(err)) {
        const detail = (err.response?.data as { detail?: string })?.detail
        setOtpError(typeof detail === 'string' ? detail : 'Verification failed. Check your code and try again.')
      } else {
        setOtpError('Verification failed. Please try again.')
      }
      setOtpState('idle')
      setOtpValue('')
    }
  }

  // ── Resend OTP ──────────────────────────────────────────────────────────────
  function startResendCooldown() {
    setResendCooldown(60)
    const id = window.setInterval(() => {
      setResendCooldown(c => {
        if (c <= 1) { clearInterval(id); return 0 }
        return c - 1
      })
    }, 1000)
  }

  async function handleResend() {
    if (resendCooldown > 0) return
    setOtpError(null)
    setOtpValue('')
    setGeneralError(null)
    setSubmitState('loading')
    try {
      await register(email, password, displayName)
      startResendCooldown()
    } catch (err) {
      const detail = isAxiosError(err)
        ? (err.response?.data as { detail?: string })?.detail
        : undefined
      setOtpError(typeof detail === 'string' ? detail : 'Could not resend. Please try again.')
    } finally {
      setSubmitState('idle')
    }
  }

  // ── GitHub OAuth ────────────────────────────────────────────────────────────
  async function handleGithubLogin() {
    setGithubLoading(true)
    setGeneralError(null)
    const url = `${resolveApiBaseURL()}/api/v1/auth/github`
    try {
      const res = await fetch(url, { redirect: 'manual' })
      if (res.type === 'opaqueredirect' || (res.status >= 300 && res.status < 400)) {
        window.location.href = url
        return
      }
      const data = await res.json().catch(() => null) as { detail?: string } | null
      setGeneralError(
        data?.detail ?? 'GitHub OAuth is not configured on the server. Use email & password instead.',
      )
    } catch {
      setGeneralError('Cannot reach the server. Make sure the backend is running on port 8000.')
    } finally {
      setGithubLoading(false)
    }
  }

  // ── Shared hero panel ───────────────────────────────────────────────────────
  const heroPanel = (
    <aside className={styles.heroPanel} aria-label="Neo Kanban product highlights">
      <div className={styles.brand}>
        <span className={styles.brandMark} aria-hidden="true"><Zap size={20} strokeWidth={2.4} /></span>
        <span className={styles.brandWord}>Neo<span>Kanban</span></span>
      </div>
      <div className={styles.heroBody}>
        <h2 className={styles.heroTagline}>
          Start building with <span className={styles.heroTaglineAccent}>AI</span>
        </h2>
        <p className={styles.heroSubtagline}>
          Join developer teams shipping faster with AI-agentic Kanban
        </p>
        <ul className={styles.featureList}>
          <li className={styles.featureItem}>
            <span className={styles.featureIcon} aria-hidden="true"><Sparkles size={18} strokeWidth={2.2} /></span>
            <span className={styles.featureText}>AI writes SPEC &amp; PLAN from your intent</span>
          </li>
          <li className={styles.featureItem}>
            <span className={styles.featureIcon} aria-hidden="true"><GitBranch size={18} strokeWidth={2.2} /></span>
            <span className={styles.featureText}>Coder Agent generates code in sandbox</span>
          </li>
          <li className={styles.featureItem}>
            <span className={styles.featureIcon} aria-hidden="true"><Users size={18} strokeWidth={2.2} /></span>
            <span className={styles.featureText}>Collaborate with your team in real-time</span>
          </li>
        </ul>
      </div>
      <div className={styles.heroPanelCta}>
        <span>Already have an account?</span>
        <Link to="/login" state={location.state} className={styles.heroPanelCtaLink}>Sign in →</Link>
      </div>
    </aside>
  )

  // ── OTP step ────────────────────────────────────────────────────────────────
  if (step === 'otp') {
    const otpLoading = otpState === 'loading'
    const otpSuccess = otpState === 'success'

    return (
      <div className={styles.shell}>
        {heroPanel}
        <section className={styles.formPanel} aria-labelledby="otp-heading">
          <div className={styles.formInner}>
            <div className={styles.brandMobile}>
              <span className={styles.brandMark} aria-hidden="true"><Zap size={16} strokeWidth={2.4} /></span>
              <span className={styles.brandWord}>Neo<span>Kanban</span></span>
            </div>

            <header className={styles.welcomeHead}>
              <div className={otpStyles.otpIconWrap} aria-hidden="true">
                <ShieldCheck size={32} strokeWidth={1.8} className={otpStyles.otpIcon} />
              </div>
              <h1 id="otp-heading" className={styles.welcomeTitle}>Verify your email</h1>
              <p className={styles.welcomeSub}>
                We sent a 6-digit code to{' '}
                <strong className={otpStyles.emailHighlight}>{pendingEmail}</strong>
              </p>
            </header>

            <form onSubmit={handleOtpSubmit} className={styles.loginForm} noValidate>
              <OtpInput
                value={otpValue}
                onChange={setOtpValue}
                disabled={otpLoading || otpSuccess}
              />

              {otpError && (
                <p className={styles.alert} role="alert" aria-live="polite" aria-atomic="true">
                  <AlertCircle size={16} className={styles.alertIcon} aria-hidden="true" />
                  <span>{otpError}</span>
                </p>
              )}

              <button
                type="submit"
                className={`${styles.submitBtn} ${otpSuccess ? styles.submitBtnSuccess : ''}`}
                disabled={otpLoading || otpSuccess || otpValue.length !== 6}
              >
                {otpLoading ? (
                  <Loader2 size={18} className={styles.spin} aria-hidden="true" />
                ) : otpSuccess ? (
                  <CheckCircle2 size={18} aria-hidden="true" />
                ) : null}
                <span>
                  {otpLoading ? 'Verifying…' : otpSuccess ? 'Verified! Redirecting…' : 'Verify & create account'}
                </span>
              </button>

              <div className={otpStyles.resendRow}>
                <button
                  type="button"
                  className={otpStyles.resendBtn}
                  onClick={() => void handleResend()}
                  disabled={resendCooldown > 0 || submitState === 'loading'}
                >
                  {submitState === 'loading' ? (
                    <Loader2 size={13} className={styles.spin} aria-hidden="true" />
                  ) : (
                    <RefreshCw size={13} aria-hidden="true" />
                  )}
                  {resendCooldown > 0
                    ? `Resend code in ${resendCooldown}s`
                    : 'Resend code'}
                </button>

                <button
                  type="button"
                  className={otpStyles.backBtn}
                  onClick={() => { setStep('form'); setOtpValue(''); setOtpError(null) }}
                >
                  <ArrowLeft size={13} aria-hidden="true" />
                  Back
                </button>
              </div>
            </form>

            <p className={otpStyles.otpHint}>
              Didn&rsquo;t get the email? Check your spam folder or go back to change your email address.
            </p>
          </div>
        </section>

        <ForgotPasswordModal open={forgotOpen} onClose={() => setForgotOpen(false)} />
        <TermsModal type={termsModalType} onClose={() => setTermsModalType(null)} />
      </div>
    )
  }

  // ── Step 1: registration form ───────────────────────────────────────────────
  return (
    <div className={styles.shell}>
      {heroPanel}

      <section className={styles.formPanel} aria-labelledby="register-heading">
        <div className={styles.formInner}>
          <div className={styles.brandMobile}>
            <span className={styles.brandMark} aria-hidden="true"><Zap size={16} strokeWidth={2.4} /></span>
            <span className={styles.brandWord}>Neo<span>Kanban</span></span>
          </div>

          <header className={styles.welcomeHead}>
            <h1 id="register-heading" className={styles.welcomeTitle}>Create account</h1>
            <p className={styles.welcomeSub}>Get started for free</p>
          </header>

          <form onSubmit={handleSubmit} className={styles.loginForm} noValidate>
            <div className={styles.fieldGroup}>
              <div className={styles.field}>
                <input id="register-name" name="name" type="text"
                  className={`${styles.fieldInput} ${nameError ? styles.fieldInputInvalid : ''}`}
                  value={displayName}
                  onChange={(e) => { setDisplayName(e.target.value); if (nameError) setNameError(null) }}
                  placeholder="Jane Developer" autoComplete="name"
                  required disabled={loading || success}
                  aria-invalid={!!nameError}
                  aria-describedby={nameError ? 'register-name-error' : undefined} />
                <label htmlFor="register-name" className={styles.fieldLabel}>Display name</label>
                <span className={styles.fieldIcon} aria-hidden="true"><User size={18} strokeWidth={2} /></span>
              </div>
              {nameError && (
                <p id="register-name-error" className={styles.fieldError} role="alert" aria-live="polite">
                  {nameError}
                </p>
              )}
            </div>

            <div className={styles.fieldGroup}>
              <div className={styles.field}>
                <input id="register-email" name="email" type="email"
                  className={`${styles.fieldInput} ${emailError ? styles.fieldInputInvalid : ''}`}
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); if (emailError) setEmailError(null) }}
                  placeholder="you@example.com" autoComplete="email"
                  required disabled={loading || success}
                  aria-invalid={!!emailError}
                  aria-describedby={emailError ? 'register-email-error' : undefined} />
                <label htmlFor="register-email" className={styles.fieldLabel}>Email</label>
                <span className={styles.fieldIcon} aria-hidden="true"><Mail size={18} strokeWidth={2} /></span>
              </div>
              {emailError && (
                <p id="register-email-error" className={styles.fieldError} role="alert" aria-live="polite">
                  {emailError}
                </p>
              )}
            </div>

            <div className={styles.fieldGroup}>
              <div className={styles.field}>
                <input id="register-password" name="password"
                  type={showPassword ? 'text' : 'password'}
                  className={`${styles.fieldInput} ${styles.fieldInputPassword} ${passwordError ? styles.fieldInputInvalid : ''}`}
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); if (passwordError) setPasswordError(null) }}
                  placeholder="••••••••" autoComplete="new-password"
                  minLength={8} required disabled={loading || success}
                  aria-invalid={!!passwordError}
                  aria-describedby={[showStrength ? 'register-strength' : null, passwordError ? 'register-password-error' : null].filter(Boolean).join(' ') || undefined} />
                <label htmlFor="register-password" className={styles.fieldLabel}>Password</label>
                <span className={styles.fieldIcon} aria-hidden="true"><Lock size={18} strokeWidth={2} /></span>
                <button type="button" className={styles.passwordToggle}
                  onClick={() => setShowPassword(v => !v)}
                  disabled={loading || success}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}>
                  {showPassword
                    ? <EyeOff size={18} strokeWidth={2} aria-hidden="true" />
                    : <Eye size={18} strokeWidth={2} aria-hidden="true" />}
                </button>
              </div>

              {showStrength && (
                <div id="register-strength" className={styles.strengthWrap} aria-live="polite" aria-atomic="true">
                  <div className={styles.strengthBar} aria-hidden="true">
                    {[1, 2, 3, 4].map(seg => (
                      <span key={seg} className={[styles.strengthSegment, seg <= strength.segments ? styles[`strength${strength.level}`] : ''].filter(Boolean).join(' ')} />
                    ))}
                  </div>
                  <span className={styles.strengthLabel}>{strength.label}</span>
                </div>
              )}
              {passwordError && (
                <p id="register-password-error" className={styles.fieldError} role="alert" aria-live="polite">{passwordError}</p>
              )}
            </div>

            <div className={styles.termsGroup}>
              <input id="register-terms" name="terms" type="checkbox"
                className={styles.termsCheckbox}
                checked={termsAccepted}
                onChange={(e) => { setTermsAccepted(e.target.checked); if (termsError) setTermsError(null) }}
                disabled={loading || success}
                aria-required="true" aria-invalid={!!termsError}
                aria-describedby={termsError ? 'register-terms-error' : 'register-terms-label'} />
              <label id="register-terms-label" htmlFor="register-terms" className={styles.termsLabel}>
                I agree to the{' '}
                <button type="button" className={styles.termsLink} onClick={() => setTermsModalType('terms')} disabled={loading || success}>Terms of Service</button>
                {' '}and{' '}
                <button type="button" className={styles.termsLink} onClick={() => setTermsModalType('privacy')} disabled={loading || success}>Privacy Policy</button>
              </label>
            </div>
            {termsError && (
              <p id="register-terms-error" className={styles.fieldError} role="alert" aria-live="polite">{termsError}</p>
            )}

            {generalError && (
              <p className={styles.alert} role="alert" aria-live="polite" aria-atomic="true">
                <AlertCircle size={16} className={styles.alertIcon} aria-hidden="true" />
                <span>{generalError}</span>
              </p>
            )}

            <button type="submit"
              className={`${styles.submitBtn} ${success ? styles.submitBtnSuccess : ''}`}
              disabled={submitDisabled}
              aria-disabled={submitDisabled}>
              {loading
                ? <Loader2 size={18} className={styles.spin} aria-hidden="true" />
                : success ? <CheckCircle2 size={18} aria-hidden="true" /> : null}
              <span>{loading ? 'Sending code…' : success ? 'Code sent!' : 'Send verification code'}</span>
            </button>

            <div className={styles.divider} aria-hidden="true"><span>or</span></div>

            <button type="button" className={styles.oauthBtn}
              disabled={loading || success || githubLoading}
              aria-label="Continue with GitHub"
              onClick={handleGithubLogin}>
              <GithubMark size={18} />
              <span>{githubLoading ? 'Connecting…' : 'Continue with GitHub'}</span>
            </button>
          </form>

          <p className={styles.formFooter}>
            Already have an account?
            <Link to="/login" state={location.state} className={styles.formFooterLink}>Sign in</Link>
          </p>
          <p className={styles.formFooter}>
            <button type="button" className={styles.forgotLink} onClick={() => setForgotOpen(true)}>
              Forgot your password?
            </button>
          </p>
        </div>
      </section>

      <ForgotPasswordModal open={forgotOpen} onClose={() => setForgotOpen(false)} />
      <TermsModal type={termsModalType} onClose={() => setTermsModalType(null)} />
    </div>
  )
}
