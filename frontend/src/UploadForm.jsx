import { useState } from 'react'
import { uploadMeeting } from './api'

const API_URL = import.meta.env.VITE_API_URL

// Only a filter for the file dialog: the user can still pick any file, and
// the backend is the one that decides what is accepted.
const ACCEPTED_FILES =
  'video/mp4,video/quicktime,video/webm,video/x-matroska,.mp4,.mov,.webm,.mkv'

function formatSize(bytes) {
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

// Turns an error of the upload request into a message for the user.
function uploadErrorMessage(error) {
  // error.response exists only when the backend answered
  if (!error.response) {
    return `Backend is not available at ${API_URL}. Make sure it is running and try again.`
  }

  const { status, data } = error.response
  // The backend sends {"detail": "..."}; for validation errors (422) detail
  // is a list, which is not shown to the user
  const detail = typeof data?.detail === 'string' ? data.detail : null

  if (status === 415) {
    return 'This file type is not supported. Choose a video file: .mp4, .mov, .webm or .mkv.'
  }
  if (status === 413) {
    return detail ? `The file is too large. ${detail}.` : 'The file is too large.'
  }
  return detail ?? `Upload failed (HTTP ${status}).`
}

function UploadForm({ onUploaded }) {
  const [file, setFile] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [error, setError] = useState(null)

  function handleFileChange(event) {
    // files is empty when the user closes the dialog without choosing
    setFile(event.target.files[0] ?? null)
    setError(null)
  }

  async function handleSubmit(event) {
    // Without this the browser would send the form itself and reload the page
    event.preventDefault()
    if (!file) {
      return
    }

    setUploading(true)
    setProgress(0)
    setError(null)
    try {
      const meeting = await uploadMeeting(file, setProgress)
      onUploaded(meeting)
    } catch (error) {
      setError(uploadErrorMessage(error))
    } finally {
      setUploading(false)
    }
  }

  return (
    <form className="upload-form" onSubmit={handleSubmit}>
      <h2>Upload a meeting</h2>

      <input
        type="file"
        accept={ACCEPTED_FILES}
        onChange={handleFileChange}
        disabled={uploading}
      />

      {file && (
        <p className="file-info">
          {file.name} ({formatSize(file.size)})
        </p>
      )}

      <button type="submit" disabled={!file || uploading}>
        {uploading ? 'Uploading...' : 'Upload'}
      </button>

      {uploading && (
        <div className="upload-progress">
          <progress value={progress} max="100" />
          {/* At 100% the whole file has been sent, but the backend is still
              saving it and has not answered yet */}
          <p>
            {progress < 100
              ? `Uploading: ${progress}%`
              : 'Upload finished, waiting for the server...'}
          </p>
        </div>
      )}

      {error && <p className="status-error">{error}</p>}
    </form>
  )
}

export default UploadForm
