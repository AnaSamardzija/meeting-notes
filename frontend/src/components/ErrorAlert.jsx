// message: the error text for the user.
// onRetry: called when the user clicks the "Try again" button.
function ErrorAlert({ message, onRetry }) {
  return (
    <div className="alert alert-danger mb-0" role="alert">
      <p>{message}</p>
      <button
        type="button"
        className="btn btn-outline-danger btn-sm"
        onClick={onRetry}
      >
        Try again
      </button>
    </div>
  )
}

export default ErrorAlert
