import { useState } from 'react'
import { Link } from 'react-router'
import { PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH } from '../api'
import { getAuthErrorMessage, useAuth } from '../authContext'

// The page at /register
function RegisterPage() {
  const { register } = useAuth()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  // true while the request is running
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    // Only the frontend asks for the password twice, so only it compares
    // them; the backend gets the password once
    if (password !== confirmPassword) {
      setError('The passwords do not match.')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      // The backend logs the new user in at once, so GuestOnly then opens
      // the interviews
      await register(email, password)
    } catch (error) {
      // E.g. 409 for a taken email or 422 for an email domain that is not
      // allowed, each with the backend's own message
      setError(
        getAuthErrorMessage(
          error,
          'Could not create the account. Check the email address and the password',
        ),
      )
      setSubmitting(false)
    }
  }

  return (
    <div className="row justify-content-center">
      <div className="col-md-6 col-lg-4">
        <div className="card shadow-sm">
          <div className="card-body p-4">
            <h1 className="h4 mb-4">Create an account</h1>

            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label htmlFor="register-email" className="form-label">
                  Email
                </label>
                <input
                  id="register-email"
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
                <label htmlFor="register-password" className="form-label">
                  Password
                </label>
                {/* minLength and maxLength: the browser itself refuses a
                    password the backend would not accept */}
                <input
                  id="register-password"
                  type="password"
                  className="form-control"
                  autoComplete="new-password"
                  value={password}
                  minLength={PASSWORD_MIN_LENGTH}
                  maxLength={PASSWORD_MAX_LENGTH}
                  onChange={(event) => setPassword(event.target.value)}
                  disabled={submitting}
                  required
                />
                <div className="form-text">
                  At least {PASSWORD_MIN_LENGTH} characters.
                </div>
              </div>

              <div className="mb-3">
                <label htmlFor="register-confirm-password" className="form-label">
                  Confirm password
                </label>
                <input
                  id="register-confirm-password"
                  type="password"
                  className="form-control"
                  autoComplete="new-password"
                  value={confirmPassword}
                  maxLength={PASSWORD_MAX_LENGTH}
                  onChange={(event) => setConfirmPassword(event.target.value)}
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
                {submitting ? 'Creating account...' : 'Create account'}
              </button>
            </form>

            <p className="text-center mt-3 mb-0">
              Already have an account? <Link to="/login">Log in</Link>
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}

export default RegisterPage
