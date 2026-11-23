import { useState } from 'react'
import {
  changePassword,
  getErrorMessage,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
} from '../api'
import { useAuth } from '../authContext'

// The page at /profile: the account of the logged-in user and the form that
// changes the password. RequireAuth lets only a logged-in user in, so user is
// always set here.
function ProfilePage() {
  const { user } = useAuth()
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  // true while the request is running
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)
  const [changed, setChanged] = useState(false)

  async function handleSubmit(event) {
    event.preventDefault()
    setChanged(false)
    // As on the register page, only the frontend asks for the new password
    // twice, so only it compares them
    if (newPassword !== confirmPassword) {
      setError('The new passwords do not match.')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      await changePassword(currentPassword, newPassword)
      setCurrentPassword('')
      setNewPassword('')
      setConfirmPassword('')
      setChanged(true)
    } catch (error) {
      // E.g. 400 for a wrong current password, with the backend's message
      setError(getErrorMessage(error, 'Could not change the password'))
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="row justify-content-center">
      <div className="col-md-8 col-lg-6">
        <div className="card shadow-sm mb-4">
          <div className="card-body p-4">
            <h1 className="h4 mb-4">Profile</h1>
            <dl className="row mb-0">
              <dt className="col-sm-4">Email</dt>
              <dd className="col-sm-8">{user.email}</dd>
              <dt className="col-sm-4">Role</dt>
              <dd className="col-sm-8 text-capitalize">{user.role}</dd>
              <dt className="col-sm-4">Account created</dt>
              <dd className="col-sm-8 mb-0">
                {new Date(user.created_at).toLocaleString()}
              </dd>
            </dl>
          </div>
        </div>

        <div className="card shadow-sm">
          <div className="card-body p-4">
            <h2 className="h5 mb-4">Change password</h2>

            <form onSubmit={handleSubmit}>
              <div className="mb-3">
                <label htmlFor="current-password" className="form-label">
                  Current password
                </label>
                <input
                  id="current-password"
                  type="password"
                  className="form-control"
                  autoComplete="current-password"
                  value={currentPassword}
                  maxLength={PASSWORD_MAX_LENGTH}
                  onChange={(event) => setCurrentPassword(event.target.value)}
                  disabled={submitting}
                  required
                />
              </div>

              <div className="mb-3">
                <label htmlFor="new-password" className="form-label">
                  New password
                </label>
                {/* minLength and maxLength: the browser itself refuses a
                    password the backend would not accept */}
                <input
                  id="new-password"
                  type="password"
                  className="form-control"
                  autoComplete="new-password"
                  value={newPassword}
                  minLength={PASSWORD_MIN_LENGTH}
                  maxLength={PASSWORD_MAX_LENGTH}
                  onChange={(event) => setNewPassword(event.target.value)}
                  disabled={submitting}
                  required
                />
                <div className="form-text">
                  At least {PASSWORD_MIN_LENGTH} characters.
                </div>
              </div>

              <div className="mb-3">
                <label htmlFor="confirm-new-password" className="form-label">
                  Confirm new password
                </label>
                <input
                  id="confirm-new-password"
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
              {changed && (
                <div className="alert alert-success" role="status">
                  Password changed. You were logged out everywhere else.
                </div>
              )}

              <button type="submit" className="btn btn-primary" disabled={submitting}>
                {submitting ? 'Changing password...' : 'Change password'}
              </button>
            </form>
          </div>
        </div>
      </div>
    </div>
  )
}

export default ProfilePage
