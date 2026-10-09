import { useEffect, useState } from 'react'
import { getMeetings } from '../api'
import StatusBadge from './StatusBadge'

const API_URL = import.meta.env.VITE_API_URL

// Turns an error of the list request into a message for the user.
function listErrorMessage(error) {
  // error.response exists only when the backend answered
  if (!error.response) {
    return `Backend is not available at ${API_URL}. Make sure it is running and try again.`
  }
  return `Could not load the meetings (HTTP ${error.response.status}).`
}

// reloadKey: the list is loaded again every time this number changes.
// onView: called with the id of the meeting whose View button was clicked.
function MeetingList({ reloadKey, onView }) {
  // null until the first answer arrives
  const [meetings, setMeetings] = useState(null)
  const [error, setError] = useState(null)
  // Increased by the "Try again" button
  const [attempt, setAttempt] = useState(0)

  useEffect(() => {
    // Set by the cleanup below when a newer request has started (or the
    // component is gone), so the answer of this one is thrown away
    let ignore = false

    getMeetings()
      .then((data) => {
        if (!ignore) {
          setMeetings(data)
          setError(null)
        }
      })
      .catch((error) => {
        if (!ignore) {
          setError(listErrorMessage(error))
        }
      })

    return () => {
      ignore = true
    }
  }, [reloadKey, attempt])

  function handleRetry() {
    // Back to the loading state, then the effect runs again
    setError(null)
    setMeetings(null)
    setAttempt(attempt + 1)
  }

  if (error) {
    return (
      <div className="alert alert-danger mb-0" role="alert">
        <p>{error}</p>
        <button
          type="button"
          className="btn btn-outline-danger btn-sm"
          onClick={handleRetry}
        >
          Try again
        </button>
      </div>
    )
  }

  if (meetings === null) {
    return (
      <div className="d-flex align-items-center gap-2 text-secondary">
        <div className="spinner-border spinner-border-sm" aria-hidden="true" />
        <span role="status">Loading meetings...</span>
      </div>
    )
  }

  if (meetings.length === 0) {
    return (
      <p className="text-secondary text-center py-4 mb-0">
        No meetings yet. Upload your first meeting to get started.
      </p>
    )
  }

  return (
    // table-responsive: on a narrow screen the table scrolls sideways
    // instead of breaking the page
    <div className="table-responsive">
      <table className="table table-hover align-middle mb-0">
        <thead>
          <tr>
            <th>Meeting</th>
            <th>Uploaded</th>
            <th>Status</th>
            <th className="text-end">Action items</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {meetings.map((meeting) => (
            // key tells React which row is which when the list changes
            <tr key={meeting.id}>
              {/* The title is written by the AI, so it is missing until the
                  meeting is processed */}
              <td>{meeting.title ?? meeting.original_filename}</td>
              <td className="text-nowrap">
                {new Date(meeting.uploaded_at).toLocaleString()}
              </td>
              <td>
                <StatusBadge status={meeting.status} />
              </td>
              <td className="text-end">{meeting.action_item_count}</td>
              <td className="text-end">
                <button
                  type="button"
                  className="btn btn-outline-primary btn-sm"
                  onClick={() => onView(meeting.id)}
                >
                  View
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

export default MeetingList
