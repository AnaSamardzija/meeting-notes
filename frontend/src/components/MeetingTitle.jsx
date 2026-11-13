import { useState } from 'react'
import { getErrorMessage, TITLE_MAX_LENGTH, updateMeeting } from '../api'
import StatusBadge from './StatusBadge'

// A pencil, drawn inline so no icon library is needed (the "pencil" icon of
// Bootstrap Icons, MIT license). currentColor: the color of the button text.
function PencilIcon() {
  return (
    <svg
      xmlns="http://www.w3.org/2000/svg"
      width="16"
      height="16"
      fill="currentColor"
      viewBox="0 0 16 16"
      aria-hidden="true"
    >
      <path d="M12.146.146a.5.5 0 0 1 .708 0l3 3a.5.5 0 0 1 0 .708l-10 10a.5.5 0 0 1-.168.11l-5 2a.5.5 0 0 1-.65-.65l2-5a.5.5 0 0 1 .11-.168zM11.207 2.5 13.5 4.793 14.793 3.5 12.5 1.207zm1.586 3L10.5 3.207 4 9.707V10h.5a.5.5 0 0 1 .5.5v.5h.5a.5.5 0 0 1 .5.5v.5h.293zm-9.761 5.175-.106.106-1.528 3.821 3.821-1.528.106-.106A.5.5 0 0 1 5 12.5V12h-.5a.5.5 0 0 1-.5-.5V11h-.5a.5.5 0 0 1-.468-.325" />
    </svg>
  )
}

// The status and the title in the header of the interview details, with a
// pencil button that turns the title into a small form. The status is part of
// this component so that it can be hidden while the title is edited.
// meeting: the loaded meeting.
// onSaved: called with the updated meeting after the title has been saved.
function MeetingTitle({ meeting, onSaved }) {
  // Whether the form is shown instead of the title
  const [editing, setEditing] = useState(false)
  // The text in the input while editing
  const [draft, setDraft] = useState('')
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState(null)

  // The backend removes the spaces around the title too, and refuses an
  // empty title
  const trimmed = draft.trim()

  function handleEdit() {
    // Starts from the current title; empty while the AI has not written one
    setDraft(meeting.title ?? '')
    setError(null)
    setEditing(true)
  }

  function handleCancel() {
    setEditing(false)
    setError(null)
  }

  async function handleSubmit(event) {
    // Without this the browser would send the form itself and reload the page
    event.preventDefault()
    if (!trimmed || saving) {
      return
    }

    setSaving(true)
    setError(null)
    try {
      const updated = await updateMeeting(meeting.id, { title: trimmed })
      onSaved(updated)
      setEditing(false)
    } catch (error) {
      setError(getErrorMessage(error, 'Could not save the title'))
    } finally {
      setSaving(false)
    }
  }

  if (!editing) {
    // A fragment: the status, the title and the button become three items of
    // the flex row in MeetingDetails
    return (
      <>
        <StatusBadge status={meeting.status} />
        {/* Without a title of its own (the AI has not written one yet), the
            name of the file is shown */}
        <h2 className="h5 mb-0">{meeting.title ?? meeting.original_filename}</h2>
        {/* The button has only an icon, so aria-label and title give it a
            name: for screen readers and as a tooltip */}
        <button
          type="button"
          className="btn btn-link btn-sm text-secondary p-1"
          onClick={handleEdit}
          aria-label="Edit title"
          title="Edit title"
        >
          <PencilIcon />
        </button>
      </>
    )
  }

  return (
    // Enter in the input submits the form, the same as clicking Save
    <form className="flex-grow-1" onSubmit={handleSubmit}>
      {/* input-group: Bootstrap joins the input and the buttons into one row */}
      <div className="input-group">
        <input
          type="text"
          className="form-control"
          aria-label="Title"
          value={draft}
          maxLength={TITLE_MAX_LENGTH}
          onChange={(event) => setDraft(event.target.value)}
          disabled={saving}
          // Puts the cursor in the input as soon as the form opens
          autoFocus
        />
        <button
          type="submit"
          className="btn btn-primary"
          disabled={!trimmed || saving}
        >
          {saving ? 'Saving...' : 'Save'}
        </button>
        <button
          type="button"
          className="btn btn-outline-secondary"
          onClick={handleCancel}
          disabled={saving}
        >
          Cancel
        </button>
      </div>
      {error && (
        <div className="text-danger small mt-1" role="alert">
          {error}
        </div>
      )}
    </form>
  )
}

export default MeetingTitle
