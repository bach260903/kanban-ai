/**
 * ForgotPasswordModal — OTP-based password reset (3 steps):
 *   1. Enter email  →  POST /auth/forgot-password  (sends 6-digit code)
 *   2. Enter OTP + new password  →  POST /auth/verify-reset
 *   3. Success screen
 */

import { isAxiosError } from 'axios'
import {
  AlertCircle,
  ArrowLeft,
  CheckCircle2,
  Eye,
  EyeOff,
  KeyRound,
  Loader2,
  Lock,
  Mail,
  RefreshCw,
  X,
} from 'lucide-react'
import {
  type FormEvent,
  useCallback,
  useEffect,
  useRef,
  useState,
} from 'react'

import { authApi } from '../../services/auth-api'
import styles from './forgot-password-modal.module.css'

export interface ForgotPasswordModalProps {
  open: boolean
  onClose: () => void
}

type Step = 'email' | 'otp' | 'success'

// ── 6-box OTP input (reused from register) ──────────────────────────────────
function OtpInput({
  value,
  onChange,
  disabled,
}: {
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
    const next = digits.slice()
    for (let j = 0; j < raw.length && i + j < 6; j++) next[i + j] = raw[j]
    onChange(next.join(''))
    refs.current[Math.min(i + raw.length, 5)]?.focus()
  }

  function handlePaste(e: React.ClipboardEvent) {
    e.preventDefault()
    const pasted = e.clipboardData.getData('text').replace(/\D/g, '').slice(0, 6)
    onChange(pasted.padEnd(6, '').slice(0, 6))
    refs.current[Math.min(pasted.length, 5)]?.focus()
  }

  return (
    <div className={styles.otpBoxes} onPaste={handlePaste}>
      {Array.from({ length: 6 }, (_, i) => (
        <input
          key={i}
          ref={(el) => { refs.current[i] = el }}
          type="text"
          inputMode="numeric"
          maxLength={1}
          value={digits[i] ?? ''}
          onChange={(e) => handleChange(i, e)}
          onKeyDown={(e) => handleKey(i, e)}
          onFocus={(e) => e.target.select()}
          disabled={disabled}
          className={`${styles.otpBox} ${digits[i] ? styles.otpBoxFilled : ''}`}
          aria-label={`Digit ${i + 1}`}
          autoComplete={i === 0 ? 'one-time-code' : 'off'}
        />
      ))}
    </div>
  )
}

// ── Main component ──────────────────────────────────────────────────────────
export function ForgotPasswordModal({ open, onClose }: ForgotPasswordModalProps) {
  const [step, setStep] = useState<Step>('email')
  const [email, setEmail] = useState('')
  const [otpValue, setOtpValue] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [showPwd, setShowPwd] = useState(false)
  const [showConfirm, setShowConfirm] = useState(false)

  const [loading, setLoading] = useState(false)
  const [errorMsg, setErrorMsg] = useState<string | null>(null)
  const [resendCooldown, setResendCooldown] = useState(0)

  const emailRef = useRef<HTMLInputElement>(null)

  // Reset everything when modal opens/closes
  useEffect(() => {
    if (!open) return
    setStep('email')
    setEmail('')
    setOtpValue('')
    setNewPassword('')
    setConfirmPassword('')
    setShowPwd(false)
    setShowConfirm(false)
    setLoading(false)
    setErrorMsg(null)
    setResendCooldown(0)
    const t = window.setTimeout(() => emailRef.current?.focus(), 60)
    return () => clearTimeout(t)
  }, [open])

  // ESC closes when not loading
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !loading) onClose()
    },
    [onClose, loading],
  )
  useEffect(() => {
    if (!open) return
    window.addEventListener('keydown', handleKeyDown)
    return () => window.removeEventListener('keydown', handleKeyDown)
  }, [open, handleKeyDown])

  function startResendCooldown() {
    setResendCooldown(60)
    const id = window.setInterval(() => {
      setResendCooldown((c) => {
        if (c <= 1) { clearInterval(id); return 0 }
        return c - 1
      })
    }, 1000)
  }

  function extractError(err: unknown, fallback: string): string {
    if (isAxiosError(err)) {
      const raw = (err.response?.data as { detail?: unknown })?.detail
      if (typeof raw === 'string') return raw
    }
    return fallback
  }

  // Step 1: send OTP
  async function handleEmailSubmit(e: FormEvent) {
    e.preventDefault()
    if (!email.trim()) return
    setLoading(true)
    setErrorMsg(null)
    try {
      await authApi.forgotPasswordOtp(email.trim())
      setStep('otp')
      startResendCooldown()
    } catch (err) {
      setErrorMsg(extractError(err, 'Không thể gửi mã. Vui lòng thử lại.'))
    } finally {
      setLoading(false)
    }
  }

  // Resend OTP
  async function handleResend() {
    if (resendCooldown > 0) return
    setOtpValue('')
    setErrorMsg(null)
    setLoading(true)
    try {
      await authApi.forgotPasswordOtp(email.trim())
      startResendCooldown()
    } catch (err) {
      setErrorMsg(extractError(err, 'Không thể gửi lại mã. Vui lòng thử lại.'))
    } finally {
      setLoading(false)
    }
  }

  // Step 2: verify OTP + new password
  async function handleOtpSubmit(e: FormEvent) {
    e.preventDefault()
    if (otpValue.length !== 6) {
      setErrorMsg('Vui lòng nhập đủ 6 chữ số.')
      return
    }
    if (newPassword.length < 8) {
      setErrorMsg('Mật khẩu mới phải có ít nhất 8 ký tự.')
      return
    }
    if (newPassword !== confirmPassword) {
      setErrorMsg('Mật khẩu xác nhận không khớp.')
      return
    }
    setErrorMsg(null)
    setLoading(true)
    try {
      await authApi.verifyResetOtp(email.trim(), otpValue, newPassword)
      setStep('success')
    } catch (err) {
      setErrorMsg(extractError(err, 'Xác nhận thất bại. Kiểm tra lại mã và thử lại.'))
      setOtpValue('')
    } finally {
      setLoading(false)
    }
  }

  if (!open) return null

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
            {step === 'email' && 'Quên mật khẩu'}
            {step === 'otp' && 'Nhập mã xác nhận'}
            {step === 'success' && 'Hoàn tất'}
          </h2>
          <button
            type="button"
            className={styles.closeBtn}
            onClick={onClose}
            disabled={loading}
            aria-label="Đóng"
          >
            <X size={18} strokeWidth={2} aria-hidden="true" />
          </button>
        </div>

        {/* ── Step 1: Email ─────────────────────────────────────── */}
        {step === 'email' && (
          <>
            <p className={styles.desc}>
              Nhập email đã đăng ký. Chúng tôi sẽ gửi mã 6 chữ số để đặt lại mật khẩu.
            </p>
            <form onSubmit={handleEmailSubmit} className={styles.form} noValidate>
              <div className={styles.field}>
                <span className={styles.fieldIcon} aria-hidden="true">
                  <Mail size={16} strokeWidth={2} />
                </span>
                <input
                  ref={emailRef}
                  id="forgot-email"
                  type="email"
                  className={`${styles.fieldInput} ${errorMsg ? styles.fieldInputError : ''}`}
                  value={email}
                  onChange={(e) => { setEmail(e.target.value); setErrorMsg(null) }}
                  placeholder="you@example.com"
                  autoComplete="email"
                  required
                  disabled={loading}
                />
              </div>

              {errorMsg && (
                <p className={styles.errorAlert} role="alert" aria-live="polite">
                  <AlertCircle size={13} aria-hidden="true" />
                  <span>{errorMsg}</span>
                </p>
              )}

              <div className={styles.actions}>
                <button
                  type="button"
                  className={styles.cancelBtn}
                  onClick={onClose}
                  disabled={loading}
                >
                  Huỷ
                </button>
                <button
                  type="submit"
                  className={styles.submitBtn}
                  disabled={loading || !email.trim()}
                >
                  {loading && <Loader2 size={14} className={styles.spin} aria-hidden="true" />}
                  <span>{loading ? 'Đang gửi…' : 'Gửi mã xác nhận'}</span>
                </button>
              </div>
            </form>
          </>
        )}

        {/* ── Step 2: OTP + new password ────────────────────────── */}
        {step === 'otp' && (
          <>
            <div className={styles.otpIconWrap} aria-hidden="true">
              <KeyRound size={28} strokeWidth={1.8} className={styles.otpIcon} />
            </div>
            <p className={styles.desc}>
              Nhập mã 6 chữ số đã gửi đến{' '}
              <strong className={styles.emailHighlight}>{email}</strong>{' '}
              và mật khẩu mới của bạn.
            </p>

            <form onSubmit={handleOtpSubmit} className={styles.form} noValidate>
              <OtpInput
                value={otpValue}
                onChange={setOtpValue}
                disabled={loading}
              />

              {/* New password */}
              <div className={styles.pwdField}>
                <span className={styles.fieldIcon} aria-hidden="true">
                  <Lock size={16} strokeWidth={2} />
                </span>
                <input
                  id="reset-new-pwd"
                  type={showPwd ? 'text' : 'password'}
                  className={styles.fieldInput}
                  value={newPassword}
                  onChange={(e) => { setNewPassword(e.target.value); setErrorMsg(null) }}
                  placeholder="Mật khẩu mới (tối thiểu 8 ký tự)"
                  autoComplete="new-password"
                  disabled={loading}
                  minLength={8}
                />
                <button
                  type="button"
                  className={styles.eyeBtn}
                  onClick={() => setShowPwd((v) => !v)}
                  aria-label={showPwd ? 'Ẩn mật khẩu' : 'Hiện mật khẩu'}
                >
                  {showPwd
                    ? <EyeOff size={16} strokeWidth={2} aria-hidden="true" />
                    : <Eye size={16} strokeWidth={2} aria-hidden="true" />}
                </button>
              </div>

              {/* Confirm password */}
              <div className={styles.pwdField}>
                <span className={styles.fieldIcon} aria-hidden="true">
                  <Lock size={16} strokeWidth={2} />
                </span>
                <input
                  id="reset-confirm-pwd"
                  type={showConfirm ? 'text' : 'password'}
                  className={styles.fieldInput}
                  value={confirmPassword}
                  onChange={(e) => { setConfirmPassword(e.target.value); setErrorMsg(null) }}
                  placeholder="Xác nhận mật khẩu mới"
                  autoComplete="new-password"
                  disabled={loading}
                />
                <button
                  type="button"
                  className={styles.eyeBtn}
                  onClick={() => setShowConfirm((v) => !v)}
                  aria-label={showConfirm ? 'Ẩn xác nhận' : 'Hiện xác nhận'}
                >
                  {showConfirm
                    ? <EyeOff size={16} strokeWidth={2} aria-hidden="true" />
                    : <Eye size={16} strokeWidth={2} aria-hidden="true" />}
                </button>
              </div>

              {errorMsg && (
                <p className={styles.errorAlert} role="alert" aria-live="polite">
                  <AlertCircle size={13} aria-hidden="true" />
                  <span>{errorMsg}</span>
                </p>
              )}

              <button
                type="submit"
                className={styles.submitBtn}
                disabled={loading || otpValue.length !== 6 || !newPassword || !confirmPassword}
                style={{ width: '100%' }}
              >
                {loading && <Loader2 size={14} className={styles.spin} aria-hidden="true" />}
                <span>{loading ? 'Đang xác nhận…' : 'Đặt lại mật khẩu'}</span>
              </button>

              <div className={styles.resendRow}>
                <button
                  type="button"
                  className={styles.backBtn}
                  onClick={() => { setStep('email'); setOtpValue(''); setErrorMsg(null) }}
                  disabled={loading}
                >
                  <ArrowLeft size={13} aria-hidden="true" />
                  Quay lại
                </button>
                <button
                  type="button"
                  className={styles.resendBtn}
                  onClick={() => void handleResend()}
                  disabled={loading || resendCooldown > 0}
                >
                  {loading
                    ? <Loader2 size={13} className={styles.spin} aria-hidden="true" />
                    : <RefreshCw size={13} aria-hidden="true" />}
                  {resendCooldown > 0 ? `Gửi lại sau ${resendCooldown}s` : 'Gửi lại mã'}
                </button>
              </div>
            </form>
          </>
        )}

        {/* ── Step 3: Success ───────────────────────────────────── */}
        {step === 'success' && (
          <div className={styles.successState}>
            <span className={styles.successIcon} aria-hidden="true">
              <CheckCircle2 size={42} strokeWidth={1.6} />
            </span>
            <p className={styles.successTitle}>Mật khẩu đã được đặt lại!</p>
            <p className={styles.successDesc}>
              Mật khẩu của <strong>{email}</strong> đã được cập nhật thành công.
              Vui lòng đăng nhập bằng mật khẩu mới.
            </p>
            <button type="button" className={styles.doneBtn} onClick={onClose}>
              Đăng nhập ngay
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
