import { API_URL } from '../api'

// status: the result of the health check in App.jsx:
// 'loading' | 'ok' | 'db-error' | 'error'
function BackendStatus({ status }) {
  if (!API_URL) {
    return (
      <div className="alert alert-danger" role="alert">
        VITE_API_URL is not set. Copy frontend/.env.example to frontend/.env
        and restart npm run dev.
      </div>
    )
  }

  // Nothing is shown while checking or when everything works
  if (status === 'loading' || status === 'ok') {
    return null
  }

  if (status === 'db-error') {
    return (
      <div className="alert alert-warning" role="alert">
        Backend is running, but the database is not available. Start it with
        docker compose up -d.
      </div>
    )
  }

  // The browser does not tell JavaScript whether the request failed because
  // the backend is down or because CORS blocked it, so the message names both.
  return (
    <div className="alert alert-danger" role="alert">
      Backend is not available at {API_URL}. Make sure the backend is running
      and that CORS_ORIGINS in .env allows this page's address (
      {window.location.origin}).
    </div>
  )
}

export default BackendStatus
