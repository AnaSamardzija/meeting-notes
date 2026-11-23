import { createContext, useContext } from 'react'
import { getErrorMessage } from './api'

// A context makes one value available to every component inside its provider
// (AuthProvider), without passing it through the props of each component on
// the way. This one holds:
// - user: undefined while the app is still asking the backend, null when
//   nobody is logged in, otherwise the user from /api/auth/me
// - login(email, password), register(email, password), logout()
// - changePassword(currentPassword, newPassword), which also loads the user
//   again (must_change_password becomes false)
export const AuthContext = createContext(null)

// Returns the value above, e.g. const { user, logout } = useAuth()
export function useAuth() {
  return useContext(AuthContext)
}

// Thrown by login and register when the backend accepted the email and the
// password, but the browser did not send the login cookie back with the next
// request. The usual reason in development: the page is open at another
// address than the one in CORS_ORIGINS (127.0.0.1 instead of localhost).
export class LoginCookieError extends Error {
  constructor() {
    super(
      `You were logged in, but the browser did not keep the login cookie. Open the app at the address set in CORS_ORIGINS (for example http://localhost:5173) and try again.`,
    )
    this.name = 'LoginCookieError'
  }
}

// Turns an error of login or register into a message for the user, like
// getErrorMessage in api.js, which does not know LoginCookieError
export function getAuthErrorMessage(error, fallback) {
  if (error instanceof LoginCookieError) {
    return error.message
  }
  return getErrorMessage(error, fallback)
}
