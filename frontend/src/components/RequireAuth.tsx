import { Navigate, Outlet, useLocation } from 'react-router-dom'
import { useAppSelector } from '../app/hooks'

export function RequireAuth() {
  const access = useAppSelector((s) => s.auth.access)
  const location = useLocation()

  if (!access) {
    return <Navigate to="/login" state={{ from: location }} replace />
  }
  return <Outlet />
}
