import { useEffect, useId, useRef } from 'react'

// A window that asks the user to confirm an action, over the rest of the page.
// It is the browser's own <dialog> element: showModal() darkens the page
// behind it, keeps the focus inside the window and closes it on Esc. It is
// styled with Bootstrap classes and .confirm-dialog in index.css.
// open: whether the window is shown.
// title: the question, e.g. 'Process the interview again?'.
// children: the text under the title.
// confirmLabel: the text of the button that does the action.
// danger: true for an action that loses data; the button is then red.
// onConfirm: called when the user clicks the confirm button.
// onCancel: called on Cancel, on Esc and on a click outside the window.
function ConfirmDialog({
  open,
  title,
  children,
  confirmLabel,
  danger = false,
  onConfirm,
  onCancel,
}) {
  // useRef: a reference to the <dialog> element itself, to call its methods
  const dialogRef = useRef(null)
  // A unique id, so the window is announced by its title
  const titleId = useId()

  // The window is opened and closed only through the open prop: the parent
  // decides, React only passes it on to the element
  useEffect(() => {
    const dialog = dialogRef.current
    if (open && !dialog.open) {
      dialog.showModal()
    } else if (!open && dialog.open) {
      dialog.close()
    }
  }, [open])

  function handleCancel(event) {
    // Esc: the browser would close the window by itself; the parent does it
    // instead, so open stays true to what is on the screen
    event.preventDefault()
    onCancel()
  }

  function handleClick(event) {
    // A click on the darkened page behind the window lands on the <dialog>
    // itself; a click inside lands on one of its children
    if (event.target === dialogRef.current) {
      onCancel()
    }
  }

  return (
    <dialog
      ref={dialogRef}
      className="confirm-dialog"
      aria-labelledby={titleId}
      onCancel={handleCancel}
      onClick={handleClick}
    >
      <div className="p-4">
        <h2 id={titleId} className="h5 mb-3">
          {title}
        </h2>
        <div className="mb-4">{children}</div>
        <div className="d-flex justify-content-end gap-2">
          {/* Cancel comes first, so showModal puts the focus on it and Enter
              does not start the action by accident */}
          <button
            type="button"
            className="btn btn-outline-secondary"
            onClick={onCancel}
          >
            Cancel
          </button>
          <button
            type="button"
            className={danger ? 'btn btn-danger' : 'btn btn-primary'}
            onClick={onConfirm}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </dialog>
  )
}

export default ConfirmDialog
