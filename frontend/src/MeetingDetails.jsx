import { useEffect, useState } from 'react'
import { getMeeting, reprocessMeeting } from './api'
import StatusBadge from './StatusBadge'

const API_URL = import.meta.env.VITE_API_URL

// The statuses in which the backend is still working on the meeting, and the
// text shown for each of them
const PROGRESS_STEPS = {
  uploaded: 'Waiting to start...',
  transcribing: 'Transcribing...',
  summarizing: 'Generating summary...',
}

// How often the details are loaded again while the meeting is being processed
const REFRESH_INTERVAL_MS = 3000

// Turns an error of the details request into a message for the user.
function loadErrorMessage(error) {
  // error.response exists only when the backend answered
  if (!error.response) {
    return `Backend is not available at ${API_URL}. Make sure it is running and try again.`
  }
  if (error.response.status === 404) {
    return 'Meeting not found.'
  }
  return `Could not load the meeting (HTTP ${error.response.status}).`
}

// Turns an error of the "process again" request into a message for the user.
function reprocessErrorMessage(error) {
  if (!error.response) {
    return `Backend is not available at ${API_URL}. Make sure it is running and try again.`
  }

  const { status, data } = error.response
  // The backend sends {"detail": "..."}
  const detail = typeof data?.detail === 'string' ? data.detail : null
  return detail ?? `Could not start the processing (HTTP ${status}).`
}

// meetingId: the id of the meeting to show.
// onBack: called when the user clicks the Back button.
function MeetingDetails({ meetingId, onBack }) {
  // null until the first answer arrives
  const [meeting, setMeeting] = useState(null)
  const [error, setError] = useState(null)
  // Increased by the "Try again" button
  const [attempt, setAttempt] = useState(0)
  // true when the last refresh during the processing did not get an answer
  const [refreshFailed, setRefreshFailed] = useState(false)
  // true while the "process again" request is running
  const [reprocessing, setReprocessing] = useState(false)
  const [reprocessError, setReprocessError] = useState(null)

  // undefined when the meeting is not loaded yet or is not being processed
  const progressStep = meeting ? PROGRESS_STEPS[meeting.status] : undefined
  const inProgress = progressStep !== undefined

  useEffect(() => {
    // Set by the cleanup below when a newer request has started (or the
    // component is gone), so the answer of this one is thrown away
    let ignore = false

    getMeeting(meetingId)
      .then((data) => {
        if (!ignore) {
          setMeeting(data)
          setError(null)
        }
      })
      .catch((error) => {
        if (!ignore) {
          setError(loadErrorMessage(error))
        }
      })

    return () => {
      ignore = true
    }
  }, [meetingId, attempt])

  // Loads the details again every few seconds while the meeting is being
  // processed. The cleanup stops the timer when the processing is over
  // (inProgress changes) and when the user leaves the page.
  useEffect(() => {
    if (!inProgress) {
      return
    }

    let ignore = false
    const timer = setInterval(() => {
      getMeeting(meetingId)
        .then((data) => {
          if (!ignore) {
            setMeeting(data)
            setRefreshFailed(false)
          }
        })
        // What is on the screen stays, and the next tick tries again
        .catch(() => {
          if (!ignore) {
            setRefreshFailed(true)
          }
        })
    }, REFRESH_INTERVAL_MS)

    return () => {
      ignore = true
      clearInterval(timer)
    }
  }, [meetingId, inProgress])

  function handleRetry() {
    // Back to the loading state, then the effect runs again
    setError(null)
    setMeeting(null)
    setAttempt(attempt + 1)
  }

  // The "Try again" button of a failed meeting
  async function handleReprocess() {
    setReprocessing(true)
    setReprocessError(null)
    try {
      await reprocessMeeting(meetingId)
    } catch (error) {
      // 409 means the meeting is already being processed (e.g. it was started
      // from another tab), so the details are only loaded again
      if (error.response?.status !== 409) {
        setReprocessError(reprocessErrorMessage(error))
        setReprocessing(false)
        return
      }
    }
    // Makes the first effect load the details again. The meeting on the
    // screen stays until the answer arrives; its new status then starts the
    // refreshing above.
    setAttempt(attempt + 1)
    setReprocessing(false)
  }

  return (
    <div className="card shadow-sm">
      <div className="card-header bg-white d-flex justify-content-between align-items-center gap-3 py-3">
        <div className="d-flex align-items-center flex-wrap gap-2">
          {/* The title is written by the AI, so it is missing until the
              meeting is processed */}
          <h2 className="h5 mb-0">
            {meeting
              ? (meeting.title ?? meeting.original_filename)
              : 'Meeting details'}
          </h2>
          {meeting && <StatusBadge status={meeting.status} />}
        </div>
        <button
          type="button"
          className="btn btn-outline-secondary"
          onClick={onBack}
        >
          Back
        </button>
      </div>

      <div className="card-body">
        {error ? (
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
        ) : meeting === null ? (
          <div className="d-flex align-items-center gap-2 text-secondary">
            <div
              className="spinner-border spinner-border-sm"
              aria-hidden="true"
            />
            <span role="status">Loading meeting...</span>
          </div>
        ) : (
          <>
            {inProgress && (
              <div
                className="alert alert-info d-flex align-items-center flex-wrap gap-2"
                role="status"
              >
                <div
                  className="spinner-border spinner-border-sm"
                  aria-hidden="true"
                />
                <span>{progressStep}</span>
                {refreshFailed && (
                  <span className="small">
                    Could not refresh the status, trying again...
                  </span>
                )}
              </div>
            )}
            {meeting.status === 'failed' && (
              <div className="alert alert-danger" role="alert">
                <p className="fw-semibold mb-1">Processing failed</p>
                <p>{meeting.error_message ?? 'Unknown error.'}</p>
                {reprocessError && <p>{reprocessError}</p>}
                <button
                  type="button"
                  className="btn btn-outline-danger btn-sm"
                  onClick={handleReprocess}
                  disabled={reprocessing}
                >
                  {reprocessing ? 'Starting...' : 'Try again'}
                </button>
              </div>
            )}
            <MeetingContent meeting={meeting} />
          </>
        )}
      </div>
    </div>
  )
}

// The sections of a loaded meeting. A section is shown only when the meeting
// has something for it: the transcript arrives before the summary, and it
// stays when the summary could not be generated.
function MeetingContent({ meeting }) {
  return (
    <>
      <dl className="row mb-0">
        <dt className="col-sm-3">File</dt>
        <dd className="col-sm-9">{meeting.original_filename}</dd>
        <dt className="col-sm-3">Uploaded</dt>
        <dd className="col-sm-9">
          {new Date(meeting.uploaded_at).toLocaleString()}
        </dd>
        {meeting.processed_at && (
          <>
            <dt className="col-sm-3">Processed</dt>
            <dd className="col-sm-9">
              {new Date(meeting.processed_at).toLocaleString()}
            </dd>
          </>
        )}
      </dl>

      {meeting.summary && (
        <section className="mt-4">
          <h3 className="h6">Summary</h3>
          <p>{meeting.summary}</p>

          {meeting.key_topics?.length > 0 && (
            <>
              <h4 className="h6">Key topics</h4>
              <ul className="mb-0">
                {/* The index is the key: two topics can have the same text,
                    and the list is never reordered */}
                {meeting.key_topics.map((topic, index) => (
                  <li key={index}>{topic}</li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}

      {/* Only for a processed meeting: before that an empty list would only
          mean that the items have not been generated yet */}
      {meeting.status === 'done' && (
        <section className="mt-4">
          <h3 className="h6">Action items</h3>
          {meeting.action_items.length === 0 ? (
            <p className="text-secondary mb-0">No action items.</p>
          ) : (
            <ul className="mb-0">
              {meeting.action_items.map((item) => (
                <li key={item.id}>
                  {/* The assignee is missing when the meeting does not say
                      who is responsible */}
                  {item.assignee && <strong>{item.assignee}: </strong>}
                  {item.description}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}

      {meeting.transcript && (
        <section className="mt-4">
          <h3 className="h6">Transcript</h3>
          <div className="transcript border rounded bg-body-tertiary p-3">
            {meeting.transcript}
          </div>
        </section>
      )}
    </>
  )
}

export default MeetingDetails
