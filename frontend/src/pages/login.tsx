import { isAxiosError } from 'axios'
import { type FormEvent, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '../components/atoms/button'
import { Spinner } from '../components/atoms/spinner'
import { TextInput } from '../components/atoms/text-input'
import api, { setAuthToken } from '../services/api'

import styles from './login.module.css'

export default function LoginPage() {
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setLoading(true)
    setError(null)
    try {
      const { data } = await api.post<{ access_token: string }>('/api/v1/auth/login', { email, password })
      setAuthToken(data.access_token)
      navigate('/projects', { replace: true })
    } catch (err) {
      if (isAxiosError(err)) {
        const detail = (err.response?.data as { detail?: string })?.detail
        setError(detail ?? 'Đăng nhập thất bại')
      } else {
        setError('Đăng nhập thất bại')
      }
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className={styles.page}>
      <div className={styles.card}>
        <h1 className={styles.title}>Đăng nhập</h1>
        <form onSubmit={handleSubmit} className={styles.form} noValidate>
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
            autoComplete="current-password"
          />
          {error ? <p className={styles.error}>{error}</p> : null}
          <Button type="submit" variant="primary" disabled={loading}>
            {loading ? <Spinner /> : null}
            {loading ? 'Đang đăng nhập…' : 'Đăng nhập'}
          </Button>
        </form>
        <p className={styles.footer}>
          Chưa có tài khoản?{' '}
          <Link to="/register" className={styles.link}>
            Đăng ký
          </Link>
        </p>
      </div>
    </div>
  )
}
