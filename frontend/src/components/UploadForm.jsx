import { useState } from 'react'
import { getErrorMessage, uploadMeeting } from '../api'

// Only a filter for the file dialog: the user can still pick any file, and
// the backend is the one that decides what is accepted.
const ACCEPTED_FILES =
  'video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv'

// The same limit as MAX_UPLOAD_MB of the backend. It only saves the user from
// sending a file the backend would refuse anyway; the backend still checks.
// NaN when VITE_MAX_UPLOAD_MB is not set, and then nothing is checked here.
const MAX_UPLOAD_MB = Number(import.meta.env.VITE_MAX_UPLOAD_MB)

function formatSize(bytes) {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// onUploaded: called with the created meeting after a successful upload.
// onCancel: called when the user closes the form without uploading.
function UploadForm({ onUploaded, onCancel }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)

  // Known as soon as a file is chosen, before anything is sent
  const tooLarge =
    file !== null &&
    MAX_UPLOAD_MB > 0 &&
    file.size > MAX_UPLOAD_MB * 1024 * 1024

  function handleFileChange(event) {
    // files is empty when the user closes the dialog without choosing
    setFile(event.target.files[0] ?? null)
    setError(null)
  }

  async function handleSubmit(event) {
    // Without this the browser would send the form itself and reload the page
    event.preventDefault()
    if (!file || tooLarge) {
      return
    }

    setUploading(true)
    setProgress(0)
    setError(null)
    try {
      const meeting = await uploadMeeting(file, setProgress)
      onUploaded(meeting)
    } catch (error) {
      setError(getErrorMessage(error, 'Upload failed'))
    } finally {
      setUploading(false)
    }
  }

  return (
    <form
      className="border rounded bg-body-tertiary p-3 mb-4"
      onSubmit={handleSubmit}
    >
      <h3 className="h6">Upload a meeting</h3>

      <div className="mb-3">
        {/* htmlFor is the "for" attribute of HTML: it ties the label to the
            input with the same id */}
        <label htmlFor="meeting-file" className="form-label">
          Video file (.mp4, .mov, .webm or .mkv)
        </label>
        <input
          id="meeting-file"
          type="file"
          className="form-control"
          accept={ACCEPTED_FILES}
          onChange={handleFileChange}
          disabled={uploading}
        />
        {file && (
          <div className="form-text">
            {file.name} ({formatSize(file.size)})
          </div>
        )}
      </div>

      {uploading && (
        <div className="mb-3">
          <div
            className="progress"
            role="progressbar"
            aria-label="Upload progress"
            aria-valuenow={progress}
            aria-valuemin="0"
            aria-valuemax="100"
          >
            {/* Bootstrap draws the bar as wide as this element */}
            <div className="progress-bar" style={{ width: `${progress}%` }} />
          </div>
          {/* At 100% the whole file has been sent, but the backend is still
              saving it and has not answered yet */}
          <div className="form-text">
            {progress < 100
              ? `Uploading: ${progress}%`
              : 'Upload finished, waiting for the server...'}
          </div>
        </div>
      )}

      {tooLarge && (
        <div className="alert alert-danger" role="alert">
          The file is larger than {MAX_UPLOAD_MB} MB. Choose a smaller file.
        </div>
      )}

      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}

      <div className="d-flex gap-2">
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!file || tooLarge || uploading}
        >
          {uploading ? 'Uploading...' : 'Upload'}
        </button>
        {/* The request cannot be stopped from here, so closing the form is
            not offered while it runs */}
        <button
          type="button"
          className="btn btn-outline-secondary"
          onClick={onCancel}
          disabled={uploading}
        >
          Cancel
        </button>
      </div>
    </form>
  )
}

export default UploadForm
