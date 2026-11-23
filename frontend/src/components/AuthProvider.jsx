import { useEffect, useState } from 'react'
import {
  changePassword as changePasswordRequest,
  getMe,
  login as loginRequest,
  logout as logoutRequest,
  register as registerRequest,
  setUnauthorizedHandler,
} from '../api'
import { AuthContext, LoginCookieError } from '../authContext'

// Knows who is logged in and gives it, together with login, register and
// logout, to every component inside it (see authContext.js).
function AuthProvider({ children }) {
  // undefined: still asking the backend; null: nobody is logged in
  const [user, setUser] = useState(undefined)

  useEffect(() => {
    // Any 401 from the backend means the login is gone (it expired, or the
    // account was deactivated). Forgetting the user is enough: RequireAuth
    // then sends the user to /login.
    setUnauthorizedHandler(() => setUser(null))

    // The login cookie may still be in the browser from an earlier visit;
    // /api/auth/me tells whether it is valid. JavaScript cannot read the
    // cookie itself (it is httpOnly), so asking the backend is the only way.
    let ignore = false
    getMe()
      .then((data) => {
        if (!ignore) {
          setUser(data)
        }
      })
      // 401, or the backend is not available (BackendStatus shows that)
      .catch(() => {
        if (!ignore) {
          setUser(null)
        }
      })

    return () => {
      ignore = true
      setUnauthorizedHandler(null)
    }
  }, [])

  // After the login or the registration the user is loaded from
  // /api/auth/me, which also checks that the browser really sends the new
  // login cookie with the requests.
  async function loadUser() {
    try {
      setUser(await getMe())
    } catch (error) {
      if (error.response?.status === 401) {
        throw new LoginCookieError()
      }
      throw error
    }
  }

  // The errors of these functions (wrong password, taken email...) are
  // passed on, so the login and register pages can show them
  async function login(email, password) {
    await loginRequest(email, password)
    await loadUser()
  }

  async function register(email, password) {
    await registerRequest(email, password)
    await loadUser()
  }

  // The user is forgotten only when the backend has deleted the cookie;
  // otherwise the next page load would log the user in again
  async function logout() {
    await logoutRequest()
    setUser(null)
  }

  // After the change the user is loaded again: must_change_password is false
  // now, so RequireAuth lets the user leave the profile page. It also checks
  // that the browser keeps the new login cookie the backend sent.
  async function changePassword(currentPassword, newPassword) {
    await changePasswordRequest(currentPassword, newPassword)
    await loadUser()
  }

  return (
    <AuthContext.Provider
      value={{ user, login, register, logout, changePassword }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export default AuthProvider
