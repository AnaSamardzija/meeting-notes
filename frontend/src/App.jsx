import { useEffect, useState } from 'react'
import { getHealth } from './api'
import UploadForm from './UploadForm'

const API_URL = import.meta.env.VITE_API_URL

function App() {
  // 'loading' | 'ok' | 'db-error' | 'error'
  const [status, setStatus] = useState('loading')
  // The meeting returned by the last successful upload, or null
  const [uploadedMeeting, setUploadedMeeting] = useState(null)

  useEffect(() => {
    getHealth()
      .then((data) => setStatus(data?.status === 'ok' ? 'ok' : 'error'))
      // error.response exists only when the backend answered. 503 from the
      // health check means the backend runs but cannot reach the database.
      .catch((error) =>
        setStatus(error.response?.status === 503 ? 'db-error' : 'error'),
      )
  }, [])

  return (
    <>
      <h1>Meeting Notes AI</h1>
      <BackendStatus status={status} />
      {uploadedMeeting ? (
        <UploadedMeeting
          meeting={uploadedMeeting}
          onUploadAnother={() => setUploadedMeeting(null)}
        />
      ) : (
        <UploadForm onUploaded={setUploadedMeeting} />
      )}
    </>
  )
}

// Temporary: shows what the upload returned. The meeting details page will
// replace it and follow the processing from there.
function UploadedMeeting({ meeting, onUploadAnother }) {
  return (
    <section className="uploaded-meeting">
      <h2>Meeting #{meeting.id}</h2>
      <p>File: {meeting.original_filename}</p>
      <p>Status: {meeting.status}</p>
      <p>Uploaded: {new Date(meeting.uploaded_at).toLocaleString()}</p>
      <button type="button" onClick={onUploadAnother}>
        Upload another
      </button>
    </section>
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

  if (status === 'db-error') {
    return (
      <p className="status-error">
        Backend is running, but the database is not available. Start it with
        docker compose up -d.
      </p>
    )
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
