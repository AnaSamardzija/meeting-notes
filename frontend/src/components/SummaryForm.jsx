import { useEffect, useState } from 'react'
import { getErrorMessage, getSummary, updateSummary } from '../api'
import ErrorAlert from './ErrorAlert'
import Loading from './Loading'

// How the items of likes, dislikes and wants are written. The backend reads
// the text the same way (backend/app/services/summary.py).
const ITEMS_HINT =
  'One item per paragraph: the first line is the title, the next lines the explanation. Leave an empty line between items.'

// One text field of the form with its label. hint: a short help text under
// the field, read by screen readers together with the label.
function TextField({ name, label, rows, hint, value, onChange, disabled }) {
  const id = `summary-${name}`
  return (
    <div className="mb-3">
      <label htmlFor={id} className="form-label fw-semibold">
        {label}
      </label>
      <textarea
        id={id}
        name={name}
        className="form-control"
        rows={rows}
        value={value}
        onChange={onChange}
        disabled={disabled}
        aria-describedby={hint ? `${id}-hint` : undefined}
      />
      {hint && (
        <div id={`${id}-hint`} className="form-text">
          {hint}
        </div>
      )}
    </div>
  )
}

// The whole summary as one form, shown in place of the summary on the
// interview details. It loads the summary as text from the backend, which
// also turns the text back into items when it is saved.
// meetingId: the id of the interview.
// onSaved: called with the updated meeting after the summary has been saved.
// onCancel: called when the user clicks Cancel.
function SummaryForm({ meetingId, onSaved, onCancel }) {
  // The values of the fields; null until the summary has been loaded
  const [form, setForm] = useState(null)
  const [loadError, setLoadError] = useState(null)
  // Increased by the "Try again" button of the load error
  const [attempt, setAttempt] = useState(0)
  const [saving, setSaving] = useState(false)
  const [saveError, setSaveError] = useState(null)

  useEffect(() => {
    // See MeetingDetails: the answer of an old request is thrown away
    let ignore = false

    getSummary(meetingId)
      .then((data) => {
        if (!ignore) {
          setForm(data)
          setLoadError(null)
        }
      })
      .catch((error) => {
        if (!ignore) {
          setLoadError(getErrorMessage(error, 'Could not load the summary'))
        }
      })

    return () => {
      ignore = true
    }
  }, [meetingId, attempt])

  function handleRetry() {
    setLoadError(null)
    setAttempt(attempt + 1)
  }

  // One handler for all the fields: the name attribute of the field is the
  // key in form. [name]: a key taken from a variable
  function handleChange(event) {
    const { name, value } = event.target
    setForm({ ...form, [name]: value })
  }

  async function handleSubmit(event) {
    // Without this the browser would send the form itself and reload the page
    event.preventDefault()
    if (saving) {
      return
    }

    setSaving(true)
    setSaveError(null)
    try {
      const updated = await updateSummary(meetingId, form)
      onSaved(updated)
    } catch (error) {
      setSaveError(getErrorMessage(error, 'Could not save the summary'))
      setSaving(false)
    }
  }

  const cancelButton = (
    <button
      type="button"
      className="btn btn-outline-secondary"
      onClick={onCancel}
      disabled={saving}
    >
      Cancel
    </button>
  )

  if (loadError) {
    return (
      <section className="mt-4">
        <ErrorAlert message={loadError} onRetry={handleRetry} />
        <div className="mt-3">{cancelButton}</div>
      </section>
    )
  }

  if (form === null) {
    return (
      <section className="mt-4">
        <Loading text="Loading summary..." />
      </section>
    )
  }

  // The props that every text field gets in the same way
  const field = (name) => ({
    name,
    value: form[name],
    onChange: handleChange,
    disabled: saving,
  })

  return (
    <form className="mt-4" onSubmit={handleSubmit}>
      <h3 className="h5 mb-3">Edit summary</h3>

      {/* row / col-md-4: the three small fields side by side on a wide
          screen, one under the other on a narrow one */}
      <div className="row g-3 mb-3">
        {[
          ['name', 'Name'],
          ['role', 'Role'],
          ['location', 'Location'],
        ].map(([name, label]) => (
          <div className="col-md-4" key={name}>
            <label htmlFor={`summary-${name}`} className="form-label fw-semibold">
              {label}
            </label>
            <input
              type="text"
              id={`summary-${name}`}
              className="form-control"
              {...field(name)}
            />
          </div>
        ))}
      </div>

      <TextField label="Takeaway" rows={3} {...field('takeaway')} />
      <TextField label="Context" rows={4} {...field('context')} />
      <TextField
        label="What they like"
        rows={8}
        hint={ITEMS_HINT}
        {...field('likes')}
      />
      <TextField
        label="What they dislike"
        rows={8}
        hint={ITEMS_HINT}
        {...field('dislikes')}
      />
      <TextField
        label="What they want"
        rows={8}
        hint={`${ITEMS_HINT} The most important first.`}
        {...field('wants')}
      />

      {saveError && (
        <div className="alert alert-danger" role="alert">
          {saveError}
        </div>
      )}
      <div className="d-flex gap-2">
        <button type="submit" className="btn btn-primary" disabled={saving}>
          {saving ? 'Saving...' : 'Save'}
        </button>
        {cancelButton}
      </div>
    </form>
  )
}

export default SummaryForm
