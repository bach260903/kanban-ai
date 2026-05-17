import { isAxiosError } from 'axios'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '../components/atoms/button'
import { Spinner } from '../components/atoms/spinner'
import { TextInput } from '../components/atoms/text-input'
import api, { setAuthToken } from '../services/api'

import styles from './login.module.css'

export default function RegisterPage() {
  const navigate = useNavigate()
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
      await api.post('/api/v1/auth/register', { email, password, display_name: displayName })
      const { data } = await api.post<{ access_token: string }>('/api/v1/auth/login', { email, password })
      setAuthToken(data.access_token)
      navigate('/projects', { replace: true })
    } catch (err) {
      if (isAxiosError(err)) {
        const detail = (err.response?.data as { detail?: string })?.detail
        setError(detail ?? 'Đăng ký thất bại')
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
          <Link to="/login" className={styles.link}>
            Đăng nhập
          </Link>
        </p>
      </div>
    </div>
  )
}
