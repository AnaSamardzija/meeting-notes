// The label and the Bootstrap badge color of each processing status
const STATUSES = {
  uploaded: { label: 'Uploaded', className: 'text-bg-secondary' },
  transcribing: { label: 'Transcribing', className: 'text-bg-primary' },
  summarizing: { label: 'Summarizing', className: 'text-bg-primary' },
  done: { label: 'Done', className: 'text-bg-success' },
  failed: { label: 'Failed', className: 'text-bg-danger' },
}

// Used by the meetings list and by the meeting details.
function StatusBadge({ status }) {
  // A status this page does not know yet is shown as it is
  const { label, className } = STATUSES[status] ?? {
    label: status,
    className: 'text-bg-secondary',
  }
  return <span className={`badge ${className}`}>{label}</span>
}

export default StatusBadge
