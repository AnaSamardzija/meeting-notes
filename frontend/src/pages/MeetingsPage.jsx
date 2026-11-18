import { useState } from 'react'
import MeetingList from '../components/MeetingList'
import UploadForm from '../components/UploadForm'

// The page at /: the list of interviews and the upload form
function MeetingsPage() {
  // Whether the upload form is open
  const [showUpload, setShowUpload] = useState(false)
  // The meeting returned by the last successful upload, or null
  const [lastUploaded, setLastUploaded] = useState(null)
  // Increased after every upload, which makes MeetingList load again
  const [reloadKey, setReloadKey] = useState(0)

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
    <div className="card shadow-sm">
      <div className="card-header bg-white d-flex justify-content-between align-items-center py-3">
        <h2 className="h5 mb-0">Interviews</h2>
        {!showUpload && (
          <button
            type="button"
            className="btn btn-primary"
            onClick={handleOpenUpload}
          >
            Upload interview
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

        <MeetingList reloadKey={reloadKey} />
      </div>
    </div>
  )
}

export default MeetingsPage
