import { useEffect, useState } from 'react'
import { getHealth } from './api'
import BackendStatus from './components/BackendStatus'
import MeetingDetails from './components/MeetingDetails'
import MeetingList from './components/MeetingList'
import UploadForm from './components/UploadForm'

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

export default App
