import { isAxiosError } from 'axios'
import { type FormEvent, useState } from 'react'
import { Link, useLocation, useNavigate, useSearchParams } from 'react-router-dom'

import { Button } from '../components/atoms/button'
import { Spinner } from '../components/atoms/spinner'
import { TextInput } from '../components/atoms/text-input'
import { useAuth } from '../contexts/auth-context'
import { getAuthRedirectTarget } from '../utils/auth-redirect'

import styles from './login.module.css'

export default function RegisterPage() {
  const navigate = useNavigate()
  const location = useLocation()
  const [searchParams] = useSearchParams()
  const { register } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      await register(email, password, displayName)
      navigate(getAuthRedirectTarget(location, searchParams), { replace: true })
    } catch (err) {
      if (isAxiosError(err)) {
        if (err.response?.status === 409) {
          setError('Email đã được sử dụng')
        } else {
          const detail = (err.response?.data as { detail?: string })?.detail
          setError(typeof detail === 'string' ? detail : 'Đăng ký thất bại')
        }
      } else {
        setError('Đăng ký thất bại')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <h1 className={styles.title}>Đăng ký</h1>
        <form onSubmit={handleSubmit} className={styles.form} noValidate>
          <TextInput
            label="Tên hiển thị"
            type="text"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            required
            disabled={loading}
            autoComplete="name"
          />
          <TextInput
            label="Email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            disabled={loading}
            autoComplete="email"
          />
          <TextInput
            label="Mật khẩu"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
            disabled={loading}
            autoComplete="new-password"
          />
          {error ? <p className={styles.error}>{error}</p> : null}
          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? <Spinner /> : null}
            {loading ? 'Đang tạo tài khoản…' : 'Đăng ký'}
          </Button>
        </form>
        <p className={styles.footer}>
          Đã có tài khoản?{' '}
          <Link to="/login" state={location.state} className={styles.link}>
            Đăng nhập
          </Link>
        </p>
      </div>
    </div>
  )
}
