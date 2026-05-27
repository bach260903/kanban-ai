import { isAxiosError } from 'axios'
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  GitBranch,
  Loader2,
  Lock,
  Mail,
  Sparkles,
  User,
  Users,
  Zap,
} from 'lucide-react'
import { type FormEvent, useMemo, useState } from 'react'
import { Link, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../contexts/auth-context'

import styles from './login.module.css'

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
type SubmitState = 'idle' | 'loading' | 'success'

function getPasswordStrength(password: string): {
  level: StrengthLevel | null
  segments: number
  label: string
} {
  if (!password) {
    return { level: null, segments: 0, label: '' }
  }
  const hasNumber = /\d/.test(password)
  const hasSymbol = /[^A-Za-z0-9]/.test(password)
  const len = password.length

  if (len >= 8 && hasNumber && hasSymbol) {
    return { level: 'strong', segments: 4, label: 'Strong' }
  }
  if (len >= 6 && (hasNumber || hasSymbol)) {
    return { level: 'good', segments: 3, label: 'Good' }
  }
  if (len >= 6) {
    return { level: 'fair', segments: 2, label: 'Fair' }
  }
  return { level: 'weak', segments: 1, label: 'Weak' }
}

export default function RegisterPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const { register } = useAuth()

  const [displayName, setDisplayName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [termsAccepted, setTermsAccepted] = useState(false)
  const [submitState, setSubmitState] = useState<SubmitState>('idle')
  const [emailError, setEmailError] = useState<string | null>(null)
  const [passwordError, setPasswordError] = useState<string | null>(null)
  const [termsError, setTermsError] = useState<string | null>(null)
  const [generalError, setGeneralError] = useState<string | null>(null)

  const loading = submitState === 'loading'
  const success = submitState === 'success'
  const strength = useMemo(() => getPasswordStrength(password), [password])
  const showStrength = password.length > 0
  const submitDisabled = loading || success || !termsAccepted

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setEmailError(null)
    setPasswordError(null)
    setTermsError(null)
    setGeneralError(null)

    let hasClientError = false
    if (!termsAccepted) {
      setTermsError('You must accept the Terms of Service and Privacy Policy.')
      hasClientError = true
    }
    if (strength.level === 'weak') {
      setPasswordError('Password is too weak. Use at least 6 characters.')
      hasClientError = true
    }
    if (hasClientError) return

    setSubmitState('loading')
    try {
      await register(email, password, displayName)
      setSubmitState('success')
      window.setTimeout(() => {
        navigate('/projects', { replace: true })
      }, 450)
    } catch (err) {
      if (isAxiosError(err)) {
        if (err.response?.status === 409) {
          setEmailError('This email is already registered.')
        } else {
          const detail = (err.response?.data as { detail?: string })?.detail
          setGeneralError(typeof detail === 'string' ? detail : 'Registration failed. Please try again.')
        }
      } else {
        setGeneralError('Registration failed. Please try again.')
      }
      setSubmitState('idle')
    }
  }

  return (
    <div className={styles.shell}>
      <aside className={styles.heroPanel} aria-label="Neo Kanban product highlights">
        <div className={styles.brand}>
          <span className={styles.brandMark} aria-hidden="true">
            <Zap size={20} strokeWidth={2.4} />
          </span>
          <span className={styles.brandWord}>
            Neo<span>Kanban</span>
          </span>
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
              <span className={styles.featureIcon} aria-hidden="true">
                <Sparkles size={18} strokeWidth={2.2} />
              </span>
              <span className={styles.featureText}>AI writes SPEC &amp; PLAN from your intent</span>
            </li>
            <li className={styles.featureItem}>
              <span className={styles.featureIcon} aria-hidden="true">
                <GitBranch size={18} strokeWidth={2.2} />
              </span>
              <span className={styles.featureText}>Coder Agent generates code in sandbox</span>
            </li>
            <li className={styles.featureItem}>
              <span className={styles.featureIcon} aria-hidden="true">
                <Users size={18} strokeWidth={2.2} />
              </span>
              <span className={styles.featureText}>Collaborate with your team in real-time</span>
            </li>
          </ul>
        </div>

        <div className={styles.heroPanelCta}>
          <span>Already have an account?</span>
          <Link to="/login" state={location.state} className={styles.heroPanelCtaLink}>
            Sign in →
          </Link>
        </div>
      </aside>

      <section className={styles.formPanel} aria-labelledby="register-heading">
        <div className={styles.formInner}>
          <div className={styles.brandMobile}>
            <span className={styles.brandMark} aria-hidden="true">
              <Zap size={16} strokeWidth={2.4} />
            </span>
            <span className={styles.brandWord}>
              Neo<span>Kanban</span>
            </span>
          </div>

          <header className={styles.welcomeHead}>
            <h1 id="register-heading" className={styles.welcomeTitle}>
              Create account
            </h1>
            <p className={styles.welcomeSub}>Get started for free</p>
          </header>

          <form onSubmit={handleSubmit} className={styles.loginForm} noValidate>
            <div className={styles.fieldGroup}>
              <div className={styles.field}>
                <input
                  id="register-name"
                  name="name"
                  type="text"
                  className={styles.fieldInput}
                  value={displayName}
                  onChange={(e) => setDisplayName(e.target.value)}
                  placeholder="Jane Developer"
                  autoComplete="name"
                  required
                  disabled={loading || success}
                />
                <label htmlFor="register-name" className={styles.fieldLabel}>
                  Display name
                </label>
                <span className={styles.fieldIcon} aria-hidden="true">
                  <User size={18} strokeWidth={2} />
                </span>
              </div>
            </div>

            <div className={styles.fieldGroup}>
              <div className={styles.field}>
                <input
                  id="register-email"
                  name="email"
                  type="email"
                  className={`${styles.fieldInput} ${emailError ? styles.fieldInputInvalid : ''}`}
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value)
                    if (emailError) setEmailError(null)
                  }}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                  disabled={loading || success}
                  aria-invalid={!!emailError}
                  aria-describedby={emailError ? 'register-email-error' : undefined}
                />
                <label htmlFor="register-email" className={styles.fieldLabel}>
                  Email
                </label>
                <span className={styles.fieldIcon} aria-hidden="true">
                  <Mail size={18} strokeWidth={2} />
                </span>
              </div>
              {emailError ? (
                <p id="register-email-error" className={styles.fieldError} role="alert" aria-live="polite">
                  {emailError}
                </p>
              ) : null}
            </div>

            <div className={styles.fieldGroup}>
              <div className={styles.field}>
                <input
                  id="register-password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  className={`${styles.fieldInput} ${styles.fieldInputPassword} ${passwordError ? styles.fieldInputInvalid : ''}`}
                  value={password}
                  onChange={(e) => {
                    setPassword(e.target.value)
                    if (passwordError) setPasswordError(null)
                  }}
                  placeholder="••••••••"
                  autoComplete="new-password"
                  minLength={8}
                  required
                  disabled={loading || success}
                  aria-invalid={!!passwordError}
                  aria-describedby={
                    [
                      showStrength ? 'register-strength' : null,
                      passwordError ? 'register-password-error' : null,
                    ]
                      .filter(Boolean)
                      .join(' ') || undefined
                  }
                />
                <label htmlFor="register-password" className={styles.fieldLabel}>
                  Password
                </label>
                <span className={styles.fieldIcon} aria-hidden="true">
                  <Lock size={18} strokeWidth={2} />
                </span>
                <button
                  type="button"
                  className={styles.passwordToggle}
                  onClick={() => setShowPassword((v) => !v)}
                  disabled={loading || success}
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                  aria-pressed={showPassword}
                >
                  {showPassword ? (
                    <EyeOff size={18} strokeWidth={2} aria-hidden="true" />
                  ) : (
                    <Eye size={18} strokeWidth={2} aria-hidden="true" />
                  )}
                </button>
              </div>

              {showStrength ? (
                <div
                  id="register-strength"
                  className={styles.strengthWrap}
                  aria-live="polite"
                  aria-atomic="true"
                >
                  <div className={styles.strengthBar} aria-hidden="true">
                    {[1, 2, 3, 4].map((segment) => (
                      <span
                        key={segment}
                        className={[
                          styles.strengthSegment,
                          segment <= strength.segments ? styles[`strength${strength.level}`] : '',
                        ]
                          .filter(Boolean)
                          .join(' ')}
                      />
                    ))}
                  </div>
                  <span className={styles.strengthLabel}>{strength.label}</span>
                </div>
              ) : null}

              {passwordError ? (
                <p
                  id="register-password-error"
                  className={styles.fieldError}
                  role="alert"
                  aria-live="polite"
                >
                  {passwordError}
                </p>
              ) : null}
            </div>

            <div className={styles.termsGroup}>
              <input
                id="register-terms"
                name="terms"
                type="checkbox"
                className={styles.termsCheckbox}
                checked={termsAccepted}
                onChange={(e) => {
                  setTermsAccepted(e.target.checked)
                  if (termsError) setTermsError(null)
                }}
                disabled={loading || success}
                aria-required="true"
                aria-invalid={!!termsError}
                aria-describedby={termsError ? 'register-terms-error' : 'register-terms-label'}
              />
              <label id="register-terms-label" htmlFor="register-terms" className={styles.termsLabel}>
                I agree to the{' '}
                <a href="#" className={styles.termsLink} onClick={(e) => e.preventDefault()}>
                  Terms of Service
                </a>{' '}
                and{' '}
                <a href="#" className={styles.termsLink} onClick={(e) => e.preventDefault()}>
                  Privacy Policy
                </a>
              </label>
            </div>
            {termsError ? (
              <p id="register-terms-error" className={styles.fieldError} role="alert" aria-live="polite">
                {termsError}
              </p>
            ) : null}

            {generalError ? (
              <p className={styles.alert} role="alert" aria-live="polite" aria-atomic="true">
                <AlertCircle size={16} className={styles.alertIcon} aria-hidden="true" />
                <span>{generalError}</span>
              </p>
            ) : null}

            <button
              type="submit"
              className={`${styles.submitBtn} ${success ? styles.submitBtnSuccess : ''}`}
              disabled={submitDisabled}
              aria-disabled={submitDisabled}
              aria-label={
                loading ? 'Creating account…' : success ? 'Account created, redirecting' : 'Sign up'
              }
            >
              {loading ? (
                <Loader2 size={18} className={styles.spin} aria-hidden="true" />
              ) : success ? (
                <CheckCircle2 size={18} aria-hidden="true" />
              ) : null}
              <span>
                {loading ? 'Creating account…' : success ? 'Account created!' : 'Sign up'}
              </span>
            </button>

            <div className={styles.divider} aria-hidden="true">
              <span>or</span>
            </div>

            <button
              type="button"
              className={styles.oauthBtn}
              disabled={loading || success}
              aria-label="Continue with GitHub (coming soon)"
              title="Coming soon"
            >
              <GithubMark size={18} />
              <span>Continue with GitHub</span>
            </button>
          </form>

          <p className={styles.formFooter}>
            Already have an account?
            <Link to="/login" state={location.state} className={styles.formFooterLink}>
              Sign in
            </Link>
          </p>
        </div>
      </section>
    </div>
  )
}
