import { useEffect, useState } from 'react'

// How long the button says "Copied" after a successful copy
const COPIED_DURATION_MS = 2000

// A button that copies something to the clipboard and then shows "Copied"
// for a moment.
// label: the text of the button, e.g. "Copy summary".
// onCopy: an async function that writes to the clipboard and throws when the
// browser does not allow it.
// onError: called with the error message when the copy fails, and with null
// when it succeeds, so that an earlier message goes away.
function CopyButton({ label, onCopy, onError }) {
  // true for a moment after a successful copy
  const [copied, setCopied] = useState(false)

  // Turns "Copied" back into the label. The cleanup stops the timer when the
  // button is gone before it fires (e.g. the user leaves the page).
  useEffect(() => {
    if (!copied) {
      return
    }
    const timer = setTimeout(() => setCopied(false), COPIED_DURATION_MS)
    return () => clearTimeout(timer)
  }, [copied])

  async function handleClick() {
    try {
      await onCopy()
      onError(null)
      setCopied(true)
    } catch {
      onError('Could not copy to the clipboard. The browser did not allow it.')
    }
  }

  return (
    <button
      type="button"
      className="btn btn-outline-secondary btn-sm text-nowrap"
      onClick={handleClick}
    >
      {copied ? 'Copied' : label}
    </button>
  )
}

export default CopyButton
