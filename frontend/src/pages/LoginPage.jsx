import { useState } from 'react'
import { Link } from 'react-router'
import { getAuthErrorMessage, useAuth } from '../authContext'

// The page at /login
function LoginPage() {
  const { login } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  // true while the request is running
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(event) {
    // Without this the browser would send the form itself and load the page
    // again
    event.preventDefault()
    setSubmitting(true)
    setError(null)
    try {
      await login(email, password)
      // Nothing else to do: GuestOnly sees the user and opens the interviews
    } catch (error) {
      // A wrong email or password: the backend's own message
      setError(getAuthErrorMessage(error, 'Could not log in'))
      setSubmitting(false)
    }
  }

  return (
    <div className="row justify-content-center">
      <div className="col-md-6 col-lg-4">
        <div className="card shadow-sm">
          <div className="card-body p-4">
            <h1 className="h4 mb-4">Log in</h1>

            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label htmlFor="login-email" className="form-label">
                  Email
                </label>
                <input
                  id="login-email"
                  type="email"
                  className="form-control"
                  autoComplete="email"
                  value={email}
                  onChange={(event) => setEmail(event.target.value)}
                  disabled={submitting}
                  required
                  autoFocus
                />
              </div>

              <div className="mb-3">
                <label htmlFor="login-password" className="form-label">
                  Password
                </label>
                <input
                  id="login-password"
                  type="password"
                  className="form-control"
                  autoComplete="current-password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={submitting}
                  required
                />
              </div>

              {error && (
                <div className="alert alert-danger" role="alert">
                  {error}
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary w-100"
                disabled={submitting}
              >
                {submitting ? 'Logging in...' : 'Log in'}
              </button>
            </form>

            <p className="text-center mt-3 mb-0">
              No account yet? <Link to="/register">Create an account</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default LoginPage
