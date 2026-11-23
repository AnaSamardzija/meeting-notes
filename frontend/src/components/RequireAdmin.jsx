import { Navigate, Outlet } from 'react-router'
import { useAuth } from '../authContext'

// Wraps the routes only the admin may open. It is used inside RequireAuth, so
// the user is always loaded here. Anyone else goes to the interviews.
// This only hides the pages: the backend itself answers 403 to everyone who
// is not an admin.
function RequireAdmin() {
  const { user } = useAuth()

  if (user.role !== 'admin') {
    return <Navigate to="/" replace />
  }

  return <Outlet />
}

export default RequireAdmin
