import { useEffect, useState } from 'react'
import { getHealth } from './api'
import MeetingDetails from './MeetingDetails'
import MeetingList from './MeetingList'
import UploadForm from './UploadForm'

const API_URL = import.meta.env.VITE_API_URL

function App() {
  // 'loading' | 'ok' | 'db-error' | 'error'
  const [status, setStatus] = useState('loading')
  // Whether the upload form is open
  const [showUpload, setShowUpload] = useState(false)
  // The meeting returned by the last successful upload, or null
  const [lastUploaded, setLastUploaded] = useState(null)
  // Increased after every upload, which makes MeetingList load again
  const [reloadKey, setReloadKey] = useState(0)
  // The id of the meeting whose View button was clicked, or null for the list
  const [selectedMeetingId, setSelectedMeetingId] = useState(null)

  useEffect(() => {
    getHealth()
      .then((data) => setStatus(data?.status === 'ok' ? 'ok' : 'error'))
      // error.response exists only when the backend answered. 503 from the
      // health check means the backend runs but cannot reach the database.
      .catch((error) =>
        setStatus(error.response?.status === 503 ? 'db-error' : 'error'),
      )
  }, [])

  function handleUploaded(meeting) {
    setShowUpload(false)
    setLastUploaded(meeting)
    setReloadKey(reloadKey + 1)
  }

  function handleOpenUpload() {
    setShowUpload(true)
    setLastUploaded(null)
  }

  return (
    <>
      <nav className="navbar bg-primary" data-bs-theme="dark">
        <div className="container">
          <span className="navbar-brand mb-0 h1">Meeting Notes AI</span>
        </div>
      </nav>

      <main className="container py-4">
        <BackendStatus status={status} />

        {selectedMeetingId !== null ? (
          <MeetingDetails
            meetingId={selectedMeetingId}
            onBack={() => setSelectedMeetingId(null)}
          />
        ) : (
          <div className="card shadow-sm">
            <div className="card-header bg-white d-flex justify-content-between align-items-center py-3">
              <h2 className="h5 mb-0">My Meetings</h2>
              {!showUpload && (
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={handleOpenUpload}
                >
                  Upload meeting
                </button>
              )}
            </div>

            <div className="card-body">
              {showUpload && (
                <UploadForm
                  onUploaded={handleUploaded}
                  onCancel={() => setShowUpload(false)}
                />
              )}

              {lastUploaded && (
                <div className="alert alert-success" role="alert">
                  {lastUploaded.original_filename} was uploaded and is being
                  processed.
                </div>
              )}

              <MeetingList
                reloadKey={reloadKey}
                onView={setSelectedMeetingId}
              />
            </div>
          </div>
        )}
      </main>
    </>
  )
}

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

export default App
