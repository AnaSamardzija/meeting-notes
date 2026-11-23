import { Navigate, Outlet } from 'react-router'
import { useAuth } from '../authContext'
import Loading from './Loading'

// Wraps the routes that need a login. <Outlet /> is the place where the
// matching child route (the list or the details) is shown.
function RequireAuth() {
  const { user } = useAuth()

  if (user === undefined) {
    return <Loading text="Loading..." />
  }

  // replace: /login takes the place of the protected address in the browser
  // history, so the Back button does not lead to it again
  if (user === null) {
    return <Navigate to="/login" replace />
  }

  return <Outlet />
}

export default RequireAuth
