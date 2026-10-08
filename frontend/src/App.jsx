import { useEffect, useState } from 'react'
import { getHealth } from './api'

const API_URL = import.meta.env.VITE_API_URL

function App() {
  // 'loading' | 'ok' | 'error'
  const [status, setStatus] = useState('loading')

  useEffect(() => {
    getHealth()
      .then((data) => setStatus(data?.status === 'ok' ? 'ok' : 'error'))
      .catch(() => setStatus('error'))
  }, [])

  return (
    <>
      <h1>Meeting Notes AI</h1>
      <BackendStatus status={status} />
    </>
  )
}

function BackendStatus({ status }) {
  if (!API_URL) {
    return (
      <p className="status-error">
        VITE_API_URL is not set. Copy frontend/.env.example to frontend/.env
        and restart npm run dev.
      </p>
    )
  }

  if (status === 'loading') {
    return <p>Checking backend...</p>
  }

  if (status === 'ok') {
    return <p className="status-ok">Backend is available.</p>
  }

  // The browser does not tell JavaScript whether the request failed because
  // the backend is down or because CORS blocked it, so the message names both.
  return (
    <p className="status-error">
      Backend is not available at {API_URL}. Make sure the backend is running
      and that CORS_ORIGINS in .env allows this page's address (
      {window.location.origin}).
    </p>
  )
}

export default App
