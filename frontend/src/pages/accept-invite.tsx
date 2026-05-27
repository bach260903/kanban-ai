import { isAxiosError } from 'axios'
import { useEffect, useRef, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Spinner } from '../components/atoms/spinner'
import { showErrorToast, showSuccessToast } from '../lib/toast'
import { acceptInvite } from '../services/member-api'

import styles from './accept-invite.module.css'

type AcceptView = 'loading' | 'expired' | 'used' | 'error'

export default function AcceptInvitePage() {
  const { token } = useParams()
  const navigate = useNavigate()
  const [view, setView] = useState<AcceptView>('loading')
  const [errorDetail, setErrorDetail] = useState<string | null>(null)
  const started = useRef(false)

  useEffect(() => {
    if (!token) {
      setView('error')
      setErrorDetail('Token lời mời không hợp lệ.')
      return
    }
    if (started.current) return
    started.current = true

    void (async () => {
      try {
        await acceptInvite(token)
        navigate('/dashboard', {
          replace: true,
          state: { toast: 'Bạn đã tham gia project' },
        })
      } catch (err) {
        if (isAxiosError(err)) {
          const detail = (err.response?.data as { detail?: unknown } | undefined)?.detail
          if (err.response?.status === 410) {
            if (detail === 'Invitation already used') {
              setView('used')
              return
            }
            setView('expired')
            return
          }
          if (err.response?.status === 409) {
            showSuccessToast('Bạn đã là thành viên của project này')
            navigate('/dashboard', { replace: true })
            return
          }
          const message =
            typeof detail === 'string' ? detail : 'Không thể chấp nhận lời mời'
          setErrorDetail(message)
          setView('error')
          showErrorToast(message)
          return
        }
        setErrorDetail('Không thể chấp nhận lời mời')
        setView('error')
        showErrorToast('Không thể chấp nhận lời mời')
      }
    })()
  }, [token, navigate])

  if (view === 'loading') {
    return (
      <div className={styles.shell}>
        <Spinner aria-label="Đang xử lý lời mời" />
        <p className={styles.message}>Đang chấp nhận lời mời…</p>
      </div>
    )
  }

  if (view === 'expired') {
    return (
      <div className={styles.shell}>
        <span className={styles.icon} aria-hidden="true">
          ⏰
        </span>
        <h1 className={styles.title}>Link đã hết hạn</h1>
        <p className={styles.message}>Liên hệ Owner để lấy link mới.</p>
        <Link to="/dashboard">Về Dashboard</Link>
      </div>
    )
  }

  if (view === 'used') {
    return (
      <div className={styles.shell}>
        <span className={styles.icon} aria-hidden="true">
          ✓
        </span>
        <h1 className={styles.title}>Link đã được sử dụng</h1>
        <p className={styles.message}>Lời mời này không còn hiệu lực.</p>
        <Link to="/dashboard">Về Dashboard</Link>
      </div>
    )
  }

  return (
    <div className={styles.shell}>
      <h1 className={styles.title}>Không thể tham gia project</h1>
      <p className={styles.message}>{errorDetail ?? 'Đã xảy ra lỗi khi xử lý lời mời.'}</p>
      <Link to="/dashboard">Về Dashboard</Link>
    </div>
  )
}
