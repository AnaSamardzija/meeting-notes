import { Navigate, Outlet, useLocation } from 'react-router'
import { useAuth } from '../authContext'
import Loading from './Loading'

// The only page a user whose password was set by the admin may open until
// they change it (the backend answers 403 everywhere else)
const PASSWORD_CHANGE_PATH = '/profile'

// Wraps the routes that need a login. <Outlet /> is the place where the
// matching child route (the list or the details) is shown.
function RequireAuth() {
  const { user } = useAuth()
  // The address that is open now, e.g. { pathname: '/meetings/3' }
  const location = useLocation()

  if (user === undefined) {
    return <Loading text="Loading..." />
  }

  // replace: /login takes the place of the protected address in the browser
  // history, so the Back button does not lead to it again
  if (user === null) {
    return <Navigate to="/login" replace />
  }

  // Also right after the login: GuestOnly sends the user to /, and from
  // there they come here
  if (user.must_change_password && location.pathname !== PASSWORD_CHANGE_PATH) {
    return <Navigate to={PASSWORD_CHANGE_PATH} replace />
  }

  return <Outlet />
}

export default RequireAuth
