import { Navigate, useLocation } from 'react-router-dom'

import { useAuth } from '../../contexts/auth-context'
import { Spinner } from '../atoms/spinner'

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const { user, isLoading } = useAuth()
  const location = useLocation()

  if (isLoading) {
    return <Spinner aria-label="Authenticating..." />
  }

  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }

  return <>{children}</>
}
