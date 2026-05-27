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
  ShieldCheck,
  Zap,
} from 'lucide-react'
import { type FormEvent, useState } from 'react'

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
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import { useAuth } from '../contexts/auth-context'
import { getAuthRedirectTarget } from '../utils/auth-redirect'

import styles from './login.module.css'

type SubmitState = 'idle' | 'loading' | 'success'

export default function LoginPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const { login } = useAuth()

  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [remember, setRemember] = useState(false)
  const [showPassword, setShowPassword] = useState(false)
  const [submitState, setSubmitState] = useState<SubmitState>('idle')
  const [error, setError] = useState<string | null>(null)

  const loading = submitState === 'loading'
  const success = submitState === 'success'
  const hasError = error !== null

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setSubmitState('loading')
    setError(null)
    try {
      await login(email, password)
      setSubmitState('success')
      window.setTimeout(() => {
        navigate(getAuthRedirectTarget(location, searchParams), { replace: true })
      }, 450)
    } catch (err) {
      let message = 'Email hoặc mật khẩu không đúng'
      if (isAxiosError(err)) {
        if (err.code === 'ECONNABORTED' || err.message.includes('timeout')) {
          message =
            'Backend không phản hồi. Kiểm tra uvicorn port 8000 đang chạy và Postgres đã sẵn sàng, rồi thử lại.'
        } else if (!err.response) {
          message = 'Không kết nối được backend. Kiểm tra uvicorn port 8000 và thử restart server.'
        } else {
          const detail = (err.response?.data as { detail?: string })?.detail
          if (typeof detail === 'string') message = detail
        }
      }
      setError(message)
      setSubmitState('idle')
    }
  }

  return (
    <div className={styles.shell}>
      {/* ---------------- LEFT HERO PANEL (desktop only) ---------------- */}
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
            From Intent to <span className={styles.heroTaglineAccent}>Code</span>
          </h2>
          <p className={styles.heroSubtagline}>
            AI-agentic Kanban for developer teams. Turn a feature intent into spec, plan, and
            shipped code — humans stay in control at every gate.
          </p>

          <ul className={styles.featureList}>
            <li className={styles.featureItem}>
              <span className={styles.featureIcon} aria-hidden="true">
                <Zap size={18} strokeWidth={2.2} />
              </span>
              <span className={styles.featureText}>
                AI generates SPEC &amp; PLAN from your intent
              </span>
            </li>
            <li className={styles.featureItem}>
              <span className={styles.featureIcon} aria-hidden="true">
                <GitBranch size={18} strokeWidth={2.2} />
              </span>
              <span className={styles.featureText}>
                Coder Agent writes code in sandbox Git workspaces
              </span>
            </li>
            <li className={styles.featureItem}>
              <span className={styles.featureIcon} aria-hidden="true">
                <ShieldCheck size={18} strokeWidth={2.2} />
              </span>
              <span className={styles.featureText}>
                Human-in-the-Loop at every critical step
              </span>
            </li>
          </ul>
        </div>

        <div className={styles.heroFooter}>
          <span className={styles.versionBadge}>
            <span className={styles.versionDot} aria-hidden="true" />
            v0.1 · alpha
          </span>
          <span>Powered by LangGraph</span>
        </div>
      </aside>

      {/* ---------------- RIGHT FORM PANEL ---------------- */}
      <section className={styles.formPanel} aria-labelledby="login-heading">
        <div className={styles.formInner}>
          {/* Mobile-only brand (desktop already has it in left panel) */}
          <div className={styles.brandMobile}>
            <span className={styles.brandMark} aria-hidden="true">
              <Zap size={16} strokeWidth={2.4} />
            </span>
            <span className={styles.brandWord}>
              Neo<span>Kanban</span>
            </span>
          </div>

          <header className={styles.welcomeHead}>
            <h1 id="login-heading" className={styles.welcomeTitle}>
              Welcome back
            </h1>
            <p className={styles.welcomeSub}>Sign in to your workspace</p>
          </header>

          <form onSubmit={handleSubmit} className={styles.loginForm} noValidate>
            {/* Email */}
            <div className={styles.fieldGroup}>
              <div className={styles.field}>
                <input
                  id="login-email"
                  type="email"
                  className={`${styles.fieldInput} ${hasError ? styles.fieldInputInvalid : ''}`}
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                  disabled={loading || success}
                  aria-invalid={hasError}
                  aria-describedby={hasError ? 'login-error' : undefined}
                />
                <label htmlFor="login-email" className={styles.fieldLabel}>
                  Email
                </label>
                <span className={styles.fieldIcon} aria-hidden="true">
                  <Mail size={18} strokeWidth={2} />
                </span>
              </div>
            </div>

            {/* Password */}
            <div className={styles.fieldGroup}>
              <div className={styles.field}>
                <input
                  id="login-password"
                  type={showPassword ? 'text' : 'password'}
                  className={`${styles.fieldInput} ${hasError ? styles.fieldInputInvalid : ''}`}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  autoComplete="current-password"
                  minLength={8}
                  required
                  disabled={loading || success}
                  aria-invalid={hasError}
                  aria-describedby={hasError ? 'login-error' : undefined}
                />
                <label htmlFor="login-password" className={styles.fieldLabel}>
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
            </div>

            {/* Remember + Forgot */}
            <div className={styles.rowBetween}>
              <label className={styles.checkboxLabel}>
                <input
                  type="checkbox"
                  checked={remember}
                  onChange={(e) => setRemember(e.target.checked)}
                  disabled={loading || success}
                />
                <span>Remember me</span>
              </label>
              <Link to="/login" className={styles.forgotLink}>
                Forgot password?
              </Link>
            </div>

            {/* Error alert — assertive announce */}
            {error ? (
              <p
                id="login-error"
                className={styles.alert}
                role="alert"
                aria-live="polite"
                aria-atomic="true"
              >
                <AlertCircle size={16} className={styles.alertIcon} aria-hidden="true" />
                <span>{error}</span>
              </p>
            ) : null}

            {/* Submit */}
            <button
              type="submit"
              className={`${styles.submitBtn} ${success ? styles.submitBtnSuccess : ''}`}
              disabled={loading || success}
              aria-label={loading ? 'Signing in…' : success ? 'Signed in, redirecting' : 'Sign in'}
            >
              {loading ? (
                <Loader2 size={18} className={styles.spin} aria-hidden="true" />
              ) : success ? (
                <CheckCircle2 size={18} aria-hidden="true" />
              ) : null}
              <span>
                {loading ? 'Signing in…' : success ? 'Welcome back!' : 'Sign in'}
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
            Don&apos;t have an account?
            <Link
              to="/register"
              state={location.state}
              className={styles.formFooterLink}
            >
              Register
            </Link>
          </p>
        </div>
      </section>
    </div>
  )
}
