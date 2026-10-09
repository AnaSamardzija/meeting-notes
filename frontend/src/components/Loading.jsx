// A small spinner with a text next to it, shown while a request is running.
function Loading({ text }) {
  return (
    <div className="d-flex align-items-center gap-2 text-secondary">
      <div className="spinner-border spinner-border-sm" aria-hidden="true" />
      <span role="status">{text}</span>
    </div>
  )
}

export default Loading
