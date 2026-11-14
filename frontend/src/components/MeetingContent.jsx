import { useState } from 'react'
import CopyButton from './CopyButton'
import SummaryForm from './SummaryForm'
import {
  copySummary,
  copyText,
  roleAndLocation,
  SUMMARY_HEADINGS,
  summaryHeader,
} from '../summaryCopy'

// One section of the insights (likes, dislikes or wants): a heading and its
// items, each with a bold title. Nothing is shown when the section is empty.
// ordered: a numbered list, for the wants, which come the most important first.
function InsightList({ heading, items, ordered = false }) {
  if (!items?.length) {
    return null
  }

  // A tag name in a variable: JSX treats a capitalized name as the element to
  // create, so <List> becomes <ol> or <ul>
  const List = ordered ? 'ol' : 'ul'
  return (
    <section className="mt-3">
      <h4 className="h6">{heading}</h4>
      <List className="mb-0">
        {/* The index is the key: two items can have the same title, and the
            list is never reordered */}
        {items.map((item, index) => (
          <li key={index}>
            <strong>{item.title}:</strong> {item.explanation}
          </li>
        ))}
      </List>
    </section>
  )
}

// The sections of a loaded meeting. A section is shown only when the meeting
// has something for it: the transcript arrives before the insights, and it
// stays when the insights could not be generated.
// meeting: the loaded meeting.
// onSummarySaved: called with the updated meeting after the summary has been
// edited and saved.
function MeetingContent({ meeting, onSummarySaved }) {
  const { interviewee, insights } = meeting
  // Whether the summary is shown as the edit form
  const [editing, setEditing] = useState(false)
  // The backend accepts changes only when the processing is done (409
  // otherwise). The form is hidden as well if the processing starts again
  // while it is open.
  const canEdit = meeting.status === 'done'
  // The message of the last copy that failed; null when there is none. The
  // copy buttons are shown, like "Edit summary", only when the processing is
  // done.
  const [copyError, setCopyError] = useState(null)

  function handleSaved(updated) {
    onSummarySaved(updated)
    setEditing(false)
  }
  // The name, the role and the location are each null when the interview
  // does not say them
  const roleLine = roleAndLocation(interviewee)

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
        {/* Only when the user has changed the summary the AI wrote */}
        {meeting.edited_at && (
          <>
            <dt className="col-sm-3">Edited</dt>
            <dd className="col-sm-9">
              {new Date(meeting.edited_at).toLocaleString()}
            </dd>
          </>
        )}
      </dl>

      {copyError && canEdit && (
        <div className="alert alert-danger mt-3 mb-0" role="alert">
          {copyError}
        </div>
      )}

      {editing && canEdit ? (
        <SummaryForm
          meetingId={meeting.id}
          onSaved={handleSaved}
          onCancel={() => setEditing(false)}
        />
      ) : insights && (
        <section className="mt-4">
          <div className="d-flex justify-content-between align-items-start gap-2 mb-1">
            <h3 className="h5 mb-0">{summaryHeader(interviewee)}</h3>
            {canEdit && (
              <div className="d-flex gap-2">
                {/* Copies what is on the screen, with the user's changes:
                    after "Save" the meeting is replaced by the saved one */}
                <CopyButton
                  label="Copy summary"
                  onCopy={() => copySummary(meeting)}
                  onError={setCopyError}
                />
                <button
                  type="button"
                  className="btn btn-outline-primary btn-sm text-nowrap"
                  onClick={() => setEditing(true)}
                >
                  Edit summary
                </button>
              </div>
            )}
          </div>
          {roleLine && <p className="text-secondary mb-0">{roleLine}</p>}

          {insights.takeaway && (
            <section className="mt-3">
              <h4 className="h6">{SUMMARY_HEADINGS.takeaway}</h4>
              <p className="mb-0">{insights.takeaway}</p>
            </section>
          )}
          {insights.context && (
            <section className="mt-3">
              <h4 className="h6">{SUMMARY_HEADINGS.context}</h4>
              <p className="mb-0">{insights.context}</p>
            </section>
          )}
          <InsightList heading={SUMMARY_HEADINGS.likes} items={insights.likes} />
          <InsightList
            heading={SUMMARY_HEADINGS.dislikes}
            items={insights.dislikes}
          />
          <InsightList
            heading={SUMMARY_HEADINGS.wants}
            items={insights.wants}
            ordered
          />
        </section>
      )}

      {meeting.transcript && (
        <section className="mt-4">
          <div className="d-flex justify-content-between align-items-center gap-2 mb-2">
            <h3 className="h6 mb-0">Transcript</h3>
            {canEdit && (
              <CopyButton
                label="Copy transcript"
                onCopy={() => copyText(meeting.transcript)}
                onError={setCopyError}
              />
            )}
          </div>
          <div className="transcript border rounded bg-body-tertiary p-3">
            {meeting.transcript}
          </div>
        </section>
      )}
    </>
  )
}

export default MeetingContent
