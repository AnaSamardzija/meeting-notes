import { Fragment, useEffect, useState } from 'react'
import {
  getErrorMessage,
  getUsers,
  PASSWORD_MAX_LENGTH,
  PASSWORD_MIN_LENGTH,
  setUserActive,
  setUserPassword,
} from '../api'
import { useAuth } from '../authContext'
import ConfirmDialog from '../components/ConfirmDialog'
import ErrorAlert from '../components/ErrorAlert'
import Loading from '../components/Loading'

// The form under a row of the table that gives the user a new password, e.g.
// when they forgot theirs. onDone is called after the password was set,
// onCancel when the admin closes the form.
function SetPasswordForm({ user, onDone, onCancel }) {
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  // true while the request is running
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  async function handleSubmit(event) {
    event.preventDefault()
    // As on the profile page, only the frontend asks for the password twice,
    // so only it compares them
    if (newPassword !== confirmPassword) {
      setError('The passwords do not match.')
      return
    }

    setSubmitting(true)
    setError(null)
    try {
      await setUserPassword(user.id, newPassword)
      // The parent closes the form, so its state is not changed any more
      onDone()
    } catch (error) {
      setError(getErrorMessage(error, 'Could not set the password'))
      setSubmitting(false)
    }
  }

  return (
    <form onSubmit={handleSubmit} className="py-2">
      <p className="mb-2">
        New password for <strong>{user.email}</strong>. Every login of the user
        ends; tell them the password, and they can change it on their profile
        page.
      </p>
      <div className="row g-2 align-items-start mb-2">
        <div className="col-md-5">
          <label htmlFor="admin-new-password" className="form-label small mb-1">
            New password
          </label>
          <input
            id="admin-new-password"
            type="password"
            className="form-control form-control-sm"
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
        <div className="col-md-5">
          <label
            htmlFor="admin-confirm-password"
            className="form-label small mb-1"
          >
            Confirm new password
          </label>
          <input
            id="admin-confirm-password"
            type="password"
            className="form-control form-control-sm"
            autoComplete="new-password"
            value={confirmPassword}
            maxLength={PASSWORD_MAX_LENGTH}
            onChange={(event) => setConfirmPassword(event.target.value)}
            disabled={submitting}
            required
          />
        </div>
      </div>

      {error && (
        <div className="alert alert-danger py-2" role="alert">
          {error}
        </div>
      )}

      <div className="d-flex gap-2">
        <button
          type="submit"
          className="btn btn-primary btn-sm"
          disabled={submitting}
        >
          {submitting ? 'Saving...' : 'Set password'}
        </button>
        <button
          type="button"
          className="btn btn-outline-secondary btn-sm"
          onClick={onCancel}
          disabled={submitting}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

// The page at /admin/users, only for the admin (RequireAdmin): every account,
// and the buttons that deactivate or activate it and set a new password.
// Users are never deleted, so their interviews stay.
function AdminUsersPage() {
  // The logged-in admin, whose own row has no buttons: the backend does not
  // let the admin deactivate themselves (400)
  const { user: currentUser } = useAuth()
  // null until the first answer arrives
  const [users, setUsers] = useState(null)
  const [loadError, setLoadError] = useState(null)
  // Increased by the "Try again" button
  const [attempt, setAttempt] = useState(0)
  // The id of the user whose activation or deactivation is running
  const [busyId, setBusyId] = useState(null)
  // The result of the last action, shown above the table
  const [message, setMessage] = useState(null)
  const [actionError, setActionError] = useState(null)
  // The user the confirmation window asks about, or null when it is closed
  const [confirmingUser, setConfirmingUser] = useState(null)
  // The id of the user whose password form is open, or null
  const [passwordUserId, setPasswordUserId] = useState(null)

  useEffect(() => {
    // Set by the cleanup when the page is gone, so the answer is thrown away
    let ignore = false

    getUsers()
      .then((data) => {
        if (!ignore) {
          setUsers(data)
        }
      })
      .catch((error) => {
        if (!ignore) {
          setLoadError(getErrorMessage(error, 'Could not load the users'))
        }
      })

    return () => {
      ignore = true
    }
  }, [attempt])

  function handleRetry() {
    setLoadError(null)
    setUsers(null)
    setAttempt(attempt + 1)
  }

  function clearMessages() {
    setMessage(null)
    setActionError(null)
  }

  async function changeActive(user, isActive) {
    clearMessages()
    setBusyId(user.id)
    try {
      const updated = await setUserActive(user.id, isActive)
      // The backend returns the updated user, which takes the place of the
      // old one; a function of the current list, which may have changed
      // while the request was running
      setUsers((current) =>
        current.map((item) => (item.id === updated.id ? updated : item)),
      )
      setMessage(
        `${updated.email} was ${isActive ? 'activated' : 'deactivated'}.`,
      )
    } catch (error) {
      setActionError(
        getErrorMessage(
          error,
          isActive
            ? 'Could not activate the account'
            : 'Could not deactivate the account',
        ),
      )
    } finally {
      setBusyId(null)
    }
  }

  function handleDeactivateConfirmed() {
    const user = confirmingUser
    setConfirmingUser(null)
    changeActive(user, false)
  }

  function handleOpenPasswordForm(user) {
    clearMessages()
    setPasswordUserId(user.id)
  }

  function handlePasswordSet(user) {
    setPasswordUserId(null)
    setMessage(
      `A new password was set for ${user.email}. They must change it after logging in.`,
    )
  }

  let content
  if (loadError) {
    content = <ErrorAlert message={loadError} onRetry={handleRetry} />
  } else if (users === null) {
    content = <Loading text="Loading users..." />
  } else {
    content = (
      <>
        {message && (
          <div className="alert alert-success" role="status">
            {message}
          </div>
        )}
        {actionError && (
          <div className="alert alert-danger" role="alert">
            {actionError}
          </div>
        )}

        {/* table-stack (index.css): on a narrow screen every row becomes a
            card, and data-label names the value of a cell there */}
        <div className="table-responsive">
          <table className="table table-stack align-middle mb-0">
            <thead>
              <tr>
                <th>Email</th>
                <th>Role</th>
                <th>Status</th>
                <th>Created</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {users.map((user) => {
                const isSelf = user.id === currentUser.id
                const busy = busyId === user.id
                return (
                  // Fragment: two rows (the user and the password form) with
                  // one key, without an element around them, which a table
                  // does not allow
                  <Fragment key={user.id}>
                    <tr>
                      <td className="text-break">{user.email}</td>
                      <td className="text-capitalize" data-label="Role">
                        {user.role}
                      </td>
                      <td>
                        {user.is_active ? (
                          <span className="badge text-bg-success">Active</span>
                        ) : (
                          <span className="badge text-bg-secondary">
                            Deactivated
                          </span>
                        )}
                      </td>
                      <td className="text-nowrap" data-label="Created">
                        {new Date(user.created_at).toLocaleString()}
                      </td>
                      <td className="text-end text-nowrap">
                        {isSelf ? (
                          <span className="small text-secondary">You</span>
                        ) : (
                          <div className="d-inline-flex gap-2">
                            {user.is_active ? (
                              <button
                                type="button"
                                className="btn btn-outline-danger btn-sm"
                                onClick={() => {
                                  clearMessages()
                                  setConfirmingUser(user)
                                }}
                                disabled={busy}
                              >
                                Deactivate
                              </button>
                            ) : (
                              <button
                                type="button"
                                className="btn btn-outline-success btn-sm"
                                onClick={() => changeActive(user, true)}
                                disabled={busy}
                              >
                                {busy ? 'Activating...' : 'Activate'}
                              </button>
                            )}
                            <button
                              type="button"
                              className="btn btn-outline-primary btn-sm"
                              onClick={() => handleOpenPasswordForm(user)}
                              disabled={busy || passwordUserId === user.id}
                            >
                              Set password
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                    {passwordUserId === user.id && (
                      <tr>
                        <td colSpan={5} className="bg-body-tertiary">
                          <SetPasswordForm
                            user={user}
                            onDone={() => handlePasswordSet(user)}
                            onCancel={() => setPasswordUserId(null)}
                          />
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      </>
    )
  }

  return (
    <div className="card shadow-sm">
      <div className="card-header bg-white py-3">
        <h1 className="h5 mb-0">Users</h1>
      </div>
      <div className="card-body">{content}</div>

      <ConfirmDialog
        open={confirmingUser !== null}
        title="Deactivate the account?"
        confirmLabel="Deactivate"
        danger
        onConfirm={handleDeactivateConfirmed}
        onCancel={() => setConfirmingUser(null)}
      >
        <p className="mb-0">
          {confirmingUser?.email} is logged out at once and cannot log in until
          the account is activated again. Their interviews are kept.
        </p>
      </ConfirmDialog>
    </div>
  )
}

export default AdminUsersPage
