import { useEffect, useState } from 'react'
import { Link, Outlet } from 'react-router'
import { getHealth } from '../api'
import { useAuth } from '../authContext'
import BackendStatus from './BackendStatus'

// What every page has: the navigation bar, the status of the backend and,
// in <Outlet />, the page of the current address.
function Layout() {
  const { user, logout } = useAuth()
  // 'loading' | 'ok' | 'db-error' | 'error'
  const [status, setStatus] = useState('loading')
  const [loggingOut, setLoggingOut] = useState(false)
  const [logoutError, setLogoutError] = useState(false)

  useEffect(() => {
    getHealth()
      .then((data) => setStatus(data?.status === 'ok' ? 'ok' : 'error'))
      // error.response exists only when the backend answered. 503 from the
      // health check means the backend runs but cannot reach the database.
      .catch((error) =>
        setStatus(error.response?.status === 503 ? 'db-error' : 'error'),
      )
  }, [])

  // On success the user is forgotten and RequireAuth sends the user to
  // /login, so nothing else needs to happen here
  async function handleLogout() {
    setLoggingOut(true)
    setLogoutError(false)
    try {
      await logout()
    } catch {
      setLogoutError(true)
    } finally {
      setLoggingOut(false)
    }
  }

  return (
    <>
      <nav className="navbar bg-primary" data-bs-theme="dark">
        <div className="container">
          <Link className="navbar-brand mb-0 h1" to="/">
            Meeting Notes AI
          </Link>
          {user && (
            // flex-wrap: on a narrow screen the links go to a second line
            // instead of pushing the page wider
            <div className="d-flex flex-wrap align-items-center gap-3">
              {logoutError && (
                <span className="small text-white">Could not log out</span>
              )}
              {/* Not while the password must be changed: RequireAuth would
                  send the admin back to /profile anyway */}
              {user.role === 'admin' && !user.must_change_password && (
                <Link className="nav-link text-white" to="/admin/users">
                  Users
                </Link>
              )}
              <Link className="nav-link text-white" to="/profile">
                {user.email}
              </Link>
              <button
                type="button"
                className="btn btn-outline-light btn-sm"
                onClick={handleLogout}
                disabled={loggingOut}
              >
                Logout
              </button>
            </div>
          )}
        </div>
      </nav>

      <main className="container py-4">
        <BackendStatus status={status} />
        <Outlet />
      </main>
    </>
  )
}

export default Layout
