import { useEffect, useId, useState } from 'react'
import { Link } from 'react-router'
import { getErrorMessage, getMeeting, reprocessMeeting } from '../api'
import ConfirmDialog from './ConfirmDialog'
import ErrorAlert from './ErrorAlert'
import Loading from './Loading'
import MeetingContent from './MeetingContent'
import MeetingTitle from './MeetingTitle'
import { isInProgress, REFRESH_INTERVAL_MS } from '../meetingStatus'

// The text shown for each status in which the backend is still working on
// the meeting
const PROGRESS_STEPS = {
  uploaded: 'Waiting to start...',
  transcribing: 'Transcribing...',
  summarizing: 'Generating summary...',
}

// meetingId: the id of the meeting to show.
function MeetingDetails({ meetingId }) {
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
  // true while the window that asks to confirm the processing is open
  const [confirmingReprocess, setConfirmingReprocess] = useState(false)
  // The choice in that window: true for "New transcript and summary", false
  // for "New summary only"
  const [newTranscript, setNewTranscript] = useState(false)
  // A unique prefix for the ids of the radio buttons, which their labels
  // point to
  const choiceId = useId()

  // false when the meeting is not loaded yet or is not being processed
  const inProgress = meeting !== null && isInProgress(meeting.status)
  const progressStep = inProgress ? PROGRESS_STEPS[meeting.status] : undefined
  // For the text of the window that asks to confirm the processing
  const isFailed = meeting?.status === 'failed'
  const isEdited = Boolean(meeting?.edited_at)
  // Only a meeting with a transcript can get a new summary alone; one without
  // is always transcribed, so the window then has no choice
  const hasTranscript = Boolean(meeting?.transcript)
  // A failed meeting can have a summary too: the last one that was made
  const hasSummary = Boolean(meeting?.insights)

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
          setError(getErrorMessage(error, 'Could not load the interview'))
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

  // The "Try again" button of a failed meeting and the "Process again" button
  // of a processed one. Both only open the window that asks to confirm: every
  // processing uses Gemini tokens, and its new summary replaces the old one,
  // even an edited one.
  function handleReprocessClick() {
    // The cheaper choice is selected every time the window opens
    setNewTranscript(false)
    setConfirmingReprocess(true)
  }

  function handleReprocessConfirmed() {
    setConfirmingReprocess(false)
    reprocess(hasTranscript && newTranscript)
  }

  async function reprocess(transcribe) {
    setReprocessing(true)
    setReprocessError(null)
    try {
      await reprocessMeeting(meetingId, { transcribe })
    } catch (error) {
      // 409 means the meeting is already being processed (e.g. it was started
      // from another tab), so the details are only loaded again
      if (error.response?.status !== 409) {
        setReprocessError(
          getErrorMessage(error, 'Could not start the processing'),
        )
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
        {/* flex-grow-1: the form for the title gets all the room up to the
            Back button */}
        <div className="d-flex align-items-center flex-wrap gap-2 flex-grow-1">
          {meeting ? (
            // The status, the title and its pencil button. The PATCH returns
            // the whole meeting, so it simply replaces the one on the screen
            <MeetingTitle meeting={meeting} onSaved={setMeeting} />
          ) : (
            <h2 className="h5 mb-0">Interview details</h2>
          )}
        </div>
        <div className="d-flex gap-2">
          {/* A processed interview can be processed again, e.g. after the
              prompt has been improved. A failed one has "Try again" below */}
          {meeting?.status === 'done' && (
            <button
              type="button"
              className="btn btn-outline-secondary text-nowrap"
              onClick={handleReprocessClick}
              disabled={reprocessing}
            >
              {reprocessing ? 'Starting...' : 'Process again'}
            </button>
          )}
          <Link to="/" className="btn btn-outline-secondary">
            Back
          </Link>
        </div>
      </div>

      <div className="card-body">
        {error ? (
          <ErrorAlert message={error} onRetry={handleRetry} />
        ) : meeting === null ? (
          <Loading text="Loading interview..." />
        ) : (
          <>
            {/* For a failed meeting the error is shown in its alert below */}
            {reprocessError && meeting.status !== 'failed' && (
              <div className="alert alert-danger" role="alert">
                {reprocessError}
              </div>
            )}
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
                  onClick={handleReprocessClick}
                  disabled={reprocessing}
                >
                  {reprocessing ? 'Starting...' : 'Try again'}
                </button>
              </div>
            )}
            {/* The PUT returns the whole meeting, so it replaces the one on
                the screen, as for the title */}
            <MeetingContent meeting={meeting} onSummarySaved={setMeeting} />
          </>
        )}
      </div>

      {/* The text depends on the meeting: one with a transcript offers a new
          summary only or a new transcript too, and one with a summary keeps
          it until the new one is ready. An edited one loses the changes of
          the user when the new summary arrives (then the button is red) */}
      <ConfirmDialog
        open={confirmingReprocess}
        title={isFailed ? 'Try processing again?' : 'Process the interview again?'}
        confirmLabel={isFailed ? 'Try again' : 'Process again'}
        danger={isEdited}
        onConfirm={handleReprocessConfirmed}
        onCancel={() => setConfirmingReprocess(false)}
      >
        <div className="vstack gap-2">
          {hasTranscript ? (
            // Controlled radio buttons: React keeps the choice in
            // newTranscript, checked shows it and onChange changes it
            <fieldset>
              <legend className="visually-hidden">What to make</legend>
              <div className="form-check">
                <input
                  className="form-check-input"
                  type="radio"
                  name={`${choiceId}-choice`}
                  id={`${choiceId}-summary`}
                  checked={!newTranscript}
                  onChange={() => setNewTranscript(false)}
                />
                <label className="form-check-label" htmlFor={`${choiceId}-summary`}>
                  New summary only
                </label>
                <div className="form-text mt-0">
                  Gemini writes a new summary from the current transcript.
                </div>
              </div>
              <div className="form-check mt-2">
                <input
                  className="form-check-input"
                  type="radio"
                  name={`${choiceId}-choice`}
                  id={`${choiceId}-transcript`}
                  checked={newTranscript}
                  onChange={() => setNewTranscript(true)}
                />
                <label
                  className="form-check-label"
                  htmlFor={`${choiceId}-transcript`}
                >
                  New transcript and summary
                </label>
                <div className="form-text mt-0">
                  Takes longer, uses many more tokens and replaces the current
                  transcript.
                </div>
              </div>
            </fieldset>
          ) : (
            <p className="mb-0">
              Gemini transcribes and summarizes the interview.
            </p>
          )}
          <p className="mb-0">This uses Gemini tokens, which costs money.</p>
          {hasSummary &&
            (isEdited ? (
              <p className="mb-0">
                The summary has been edited. When the new summary is ready, it
                replaces your changes, and they cannot be restored. If the
                processing fails, your changes are kept.
              </p>
            ) : (
              <p className="mb-0">
                The current summary stays until the new one is ready, and it is
                kept if the processing fails.
              </p>
            ))}
        </div>
      </ConfirmDialog>
    </div>
  )
}

export default MeetingDetails
