import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../../contexts/auth-context'
import { AppShell } from '../organisms/app-shell'
import { Spinner } from '../atoms/spinner'

import styles from './auth-guard.module.css'

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return (
      <div className={styles.loadingShell}>
        <Spinner aria-label="Authenticating..." />
      </div>
    )
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <AppShell>{children}</AppShell>
}
