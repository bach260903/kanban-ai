import { isAxiosError } from 'axios'
import {
  AlertCircle,
  CheckCircle2,
  Eye,
  EyeOff,
  GitBranch,
  Loader2,
  Lock,
  Zap,
} from 'lucide-react'
import { type FormEvent, useEffect, useMemo, useState } from 'react'
import { Link, Navigate, useNavigate, useSearchParams } from 'react-router-dom'

import { authApi } from '../services/auth-api'

import styles from './login.module.css'

type SubmitState = 'idle' | 'loading' | 'success'

function messageFromError(err: unknown): string {
  if (isAxiosError(err)) {
    const detail = (err.response?.data as { detail?: string } | undefined)?.detail
    if (typeof detail === 'string' && detail.trim()) return detail
    if (err.response?.status === 400) {
      return 'Link đặt lại mật khẩu không hợp lệ hoặc đã hết hạn.'
    }
    return err.message || 'Không thể đặt lại mật khẩu. Vui lòng thử lại.'
  }
  if (err instanceof Error) return err.message
  return 'Không thể đặt lại mật khẩu. Vui lòng thử lại.'
}

export default function ResetPasswordPage() {
  const navigate = useNavigate()
  const [searchParams] = useSearchParams()
  const token = searchParams.get('token')

  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)
  const [submitState, setSubmitState] = useState<SubmitState>('idle')
  const [error, setError] = useState<string | null>(null)
  const [fieldErrors, setFieldErrors] = useState<{ password?: string; confirm?: string }>({})

  const loading = submitState === 'loading'
  const success = submitState === 'success'

  const passwordInvalid = useMemo(() => {
    if (!password) return false
    return password.length < 8
  }, [password])

  const confirmInvalid = useMemo(() => {
    if (!confirmPassword) return false
    return password !== confirmPassword
  }, [password, confirmPassword])

  useEffect(() => {
    if (!success) return undefined
    const id = window.setTimeout(() => {
      navigate('/login', { replace: true, state: { toast: 'Mật khẩu đã được cập nhật. Vui lòng đăng nhập.' } })
    }, 2200)
    return () => window.clearTimeout(id)
  }, [success, navigate])

  if (!token) {
    return <Navigate to="/login" replace state={{ toast: 'Link đặt lại mật khẩu không hợp lệ.' }} />
  }

  function validateFields(): boolean {
    const next: { password?: string; confirm?: string } = {}
    if (password.length < 8) {
      next.password = 'Mật khẩu phải có ít nhất 8 ký tự.'
    }
    if (password !== confirmPassword) {
      next.confirm = 'Mật khẩu xác nhận không khớp.'
    }
    setFieldErrors(next)
    return Object.keys(next).length === 0
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    if (!validateFields()) return

    setSubmitState('loading')
    setError(null)
    try {
      await authApi.resetPassword(token, password)
      setSubmitState('success')
    } catch (err) {
      setError(messageFromError(err))
      setSubmitState('idle')
    }
  }

  return (
    <div className={styles.shell}>
      <aside className={styles.heroPanel} aria-hidden="true">
        <div className={styles.brand}>
          <span className={styles.brandMark}>
            <Zap size={20} strokeWidth={2.4} />
          </span>
          <span className={styles.brandWord}>
            Neo<span>Kanban</span>
          </span>
        </div>
        <div className={styles.heroBody}>
          <h2 className={styles.heroTagline}>
            Secure <span className={styles.heroTaglineAccent}>access</span>
          </h2>
          <p className={styles.heroSubtagline}>
            Choose a strong password to protect your workspace and agent runs.
          </p>
        </div>
      </aside>

      <section className={styles.formPanel} aria-labelledby="reset-password-title">
        <div className={styles.formInner}>
          <div className={styles.brandMobile}>
            <span className={styles.brandMark} aria-hidden="true">
              <GitBranch size={18} strokeWidth={2.2} />
            </span>
            <span className={styles.brandWord}>
              Neo<span>Kanban</span>
            </span>
          </div>

          <header className={styles.welcomeHead}>
            <h1 id="reset-password-title" className={styles.welcomeTitle}>
              Đặt lại mật khẩu
            </h1>
            <p className={styles.welcomeSub}>
              Nhập mật khẩu mới cho tài khoản của bạn (tối thiểu 8 ký tự).
            </p>
          </header>

          {success ? (
            <div className={`${styles.alert} ${styles.alertSuccess}`} role="status" aria-live="polite">
              <CheckCircle2 size={16} className={styles.alertIcon} aria-hidden="true" />
              <span>
                Mật khẩu đã được cập nhật. Đang chuyển đến trang đăng nhập…
              </span>
            </div>
          ) : (
            <form className={styles.loginForm} onSubmit={handleSubmit} noValidate>
              <div className={styles.fieldGroup}>
                <div className={styles.field}>
                  <input
                    id="reset-password"
                    type={showPassword ? 'text' : 'password'}
                    className={`${styles.fieldInput} ${
                      passwordInvalid || fieldErrors.password ? styles.fieldInputInvalid : ''
                    }`}
                    value={password}
                    onChange={(e) => {
                      setPassword(e.target.value)
                      setFieldErrors((prev) => ({ ...prev, password: undefined }))
                      setError(null)
                    }}
                    placeholder=" "
                    autoComplete="new-password"
                    required
                    minLength={8}
                    disabled={loading}
                    aria-invalid={Boolean(passwordInvalid || fieldErrors.password)}
                    aria-describedby={
                      fieldErrors.password ? 'reset-password-error' : 'reset-password-hint'
                    }
                  />
                  <label htmlFor="reset-password" className={styles.fieldLabel}>
                    Mật khẩu mới
                  </label>
                  <span className={styles.fieldIcon} aria-hidden="true">
                    <Lock size={16} strokeWidth={2} />
                  </span>
                  <button
                    type="button"
                    className={styles.passwordToggle}
                    onClick={() => setShowPassword((v) => !v)}
                    disabled={loading}
                    aria-label={showPassword ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                  >
                    {showPassword ? (
                      <EyeOff size={18} strokeWidth={2} aria-hidden="true" />
                    ) : (
                      <Eye size={18} strokeWidth={2} aria-hidden="true" />
                    )}
                  </button>
                </div>
                {fieldErrors.password ? (
                  <p id="reset-password-error" className={styles.inlineError} role="alert">
                    {fieldErrors.password}
                  </p>
                ) : (
                  <p id="reset-password-hint" className={styles.fieldHint}>
                    Tối thiểu 8 ký tự.
                  </p>
                )}
              </div>

              <div className={styles.fieldGroup}>
                <div className={styles.field}>
                  <input
                    id="reset-password-confirm"
                    type={showConfirm ? 'text' : 'password'}
                    className={`${styles.fieldInput} ${
                      confirmInvalid || fieldErrors.confirm ? styles.fieldInputInvalid : ''
                    }`}
                    value={confirmPassword}
                    onChange={(e) => {
                      setConfirmPassword(e.target.value)
                      setFieldErrors((prev) => ({ ...prev, confirm: undefined }))
                      setError(null)
                    }}
                    placeholder=" "
                    autoComplete="new-password"
                    required
                    disabled={loading}
                    aria-invalid={Boolean(confirmInvalid || fieldErrors.confirm)}
                    aria-describedby={
                      fieldErrors.confirm ? 'reset-confirm-error' : undefined
                    }
                  />
                  <label htmlFor="reset-password-confirm" className={styles.fieldLabel}>
                    Xác nhận mật khẩu
                  </label>
                  <span className={styles.fieldIcon} aria-hidden="true">
                    <Lock size={16} strokeWidth={2} />
                  </span>
                  <button
                    type="button"
                    className={styles.passwordToggle}
                    onClick={() => setShowConfirm((v) => !v)}
                    disabled={loading}
                    aria-label={showConfirm ? 'Ẩn xác nhận' : 'Hiện xác nhận'}
                  >
                    {showConfirm ? (
                      <EyeOff size={18} strokeWidth={2} aria-hidden="true" />
                    ) : (
                      <Eye size={18} strokeWidth={2} aria-hidden="true" />
                    )}
                  </button>
                </div>
                {fieldErrors.confirm ? (
                  <p id="reset-confirm-error" className={styles.inlineError} role="alert">
                    {fieldErrors.confirm}
                  </p>
                ) : null}
              </div>

              {error ? (
                <p className={styles.alert} role="alert" aria-live="polite">
                  <AlertCircle size={16} className={styles.alertIcon} aria-hidden="true" />
                  <span>{error}</span>
                </p>
              ) : null}

              <button
                type="submit"
                className={styles.submitBtn}
                disabled={loading || !password || !confirmPassword}
              >
                {loading ? (
                  <Loader2 size={18} className={styles.spin} aria-hidden="true" />
                ) : (
                  <CheckCircle2 size={18} aria-hidden="true" />
                )}
                <span>{loading ? 'Đang lưu…' : 'Đặt lại mật khẩu'}</span>
              </button>
            </form>
          )}

          <p className={styles.footer}>
            <Link to="/login" className={styles.link}>
              Quay lại đăng nhập
            </Link>
          </p>
        </div>
      </section>
    </div>
  )
}
