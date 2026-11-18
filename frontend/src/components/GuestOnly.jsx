import { Navigate, Outlet } from 'react-router'
import { useAuth } from '../authContext'
import Loading from './Loading'

// Wraps /login and /register: a user who is already logged in goes to the
// interviews. This is also what happens right after a successful login or
// registration, when the user is set.
function GuestOnly() {
  const { user } = useAuth()

  if (user === undefined) {
    return <Loading text="Loading..." />
  }

  if (user) {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}

export default GuestOnly
