import { useEffect, useState } from 'react'
import { getErrorMessage, getMeetings } from '../api'
import { isInProgress, REFRESH_INTERVAL_MS } from '../meetingStatus'
import ErrorAlert from './ErrorAlert'
import Loading from './Loading'
import StatusBadge from './StatusBadge'

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
          setError(getErrorMessage(error, 'Could not load the meetings'))
        }
      })

    return () => {
      ignore = true
    }
  }, [reloadKey, attempt])

  // true when at least one meeting on the list is still being processed
  const hasInProgress =
    meetings !== null &&
    meetings.some((meeting) => isInProgress(meeting.status))

  // Loads the list again every few seconds while a meeting is being
  // processed, so its status and its number of action items stay up to date.
  // The cleanup stops the timer when no meeting is in progress any more
  // (hasInProgress changes) and when the user leaves the list.
  useEffect(() => {
    if (!hasInProgress) {
      return
    }

    let ignore = false
    const timer = setInterval(() => {
      getMeetings()
        .then((data) => {
          if (!ignore) {
            setMeetings(data)
          }
        })
        // What is on the screen stays, and the next tick tries again
        .catch(() => {})
    }, REFRESH_INTERVAL_MS)

    return () => {
      ignore = true
      clearInterval(timer)
    }
  }, [hasInProgress])

  function handleRetry() {
    // Back to the loading state, then the effect runs again
    setError(null)
    setMeetings(null)
    setAttempt(attempt + 1)
  }

  if (error) {
    return <ErrorAlert message={error} onRetry={handleRetry} />
  }

  if (meetings === null) {
    return <Loading text="Loading meetings..." />
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
