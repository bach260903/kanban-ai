import { isAxiosError } from 'axios'
import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'

import { Button } from '../components/atoms/button'
import { Spinner } from '../components/atoms/spinner'
import { getAuthToken, probeAuthToken, setAuthToken } from '../services/api'
import { fetchDevToken } from '../services/auth-api'

import styles from './dev-auth.module.css'

export default function DevAuth() {
  const navigate = useNavigate()
  const [busy, setBusy] = useState(false)
  const [checking, setChecking] = useState(Boolean(getAuthToken()))
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    if (!getAuthToken()) {
      setChecking(false)
      return
    }
    let cancelled = false
    void (async () => {
      const ok = await probeAuthToken()
      if (cancelled) return
      setChecking(false)
      if (ok) navigate('/projects', { replace: true })
    })()
    return () => {
      cancelled = true
    }
  }, [navigate])

  async function onGetToken() {
    setError(null)
    setBusy(true)
    try {
      const { access_token } = await fetchDevToken()
      setAuthToken(access_token)
      navigate('/projects', { replace: true })
    } catch (e) {
      if (isAxiosError(e)) {
        if (e.code === 'ECONNABORTED' || e.message.includes('timeout')) {
          setError(
            'Backend không phản hồi (timeout). Chạy uvicorn trên port 8000 và đặt DEV_AUTH_ENABLED=true trong .env.',
          )
          return
        }
        if (e.response?.status === 404) {
          setError('Dev auth tắt trên server. Thêm DEV_AUTH_ENABLED=true vào file .env rồi khởi động lại backend.')
          return
        }
        const detail = (e.response?.data as { detail?: unknown } | undefined)?.detail
        setError(typeof detail === 'string' ? detail : e.message)
        return
      }
      setError(e instanceof Error ? e.message : 'Không lấy được token.')
    } finally {
      setBusy(false)
    }
  }

  if (checking) {
    return (
      <div className={styles.page}>
        <Spinner aria-label="Checking session" />
        <p className={styles.sub}>Đang kiểm tra token…</p>
      </div>
    )
  }

  return (
    <div className={styles.page}>
      <h1 className={styles.title}>Dev login</h1>
      <p className={styles.sub}>
        API yêu cầu JWT. Trên môi trường local, bấm nút bên dưới để lấy token từ{' '}
        <code>POST /api/v1/dev/token</code> (chỉ khi <code>DEV_AUTH_ENABLED=true</code>).
      </p>
      {error ? <p className={styles.error}>{error}</p> : null}
      <div className={styles.actions}>
        <Button type="button" onClick={() => void onGetToken()} disabled={busy}>
          {busy ? 'Đang lấy token…' : 'Lấy dev token & vào Projects'}
        </Button>
        {busy ? <Spinner aria-label="Fetching dev token" /> : null}
      </div>
      <p className={styles.hint}>
        Backend: <code>cd backend</code> → <code>.\.venv\Scripts\Activate.ps1</code> →{' '}
        <code>uvicorn app.main:app --reload --port 8000</code>
        <br />
        Cần Postgres + Redis (ví dụ <code>docker compose up -d postgres redis</code>).
      </p>
      <p>
        <Link to="/projects">← Projects</Link>
      </p>
    </div>
  )
}
