// The statuses in which the backend is still working on a meeting. They match
// IN_PROGRESS_STATUSES in backend/app/services/processing.py.
const IN_PROGRESS_STATUSES = ['uploaded', 'transcribing', 'summarizing']

export function isInProgress(status) {
  return IN_PROGRESS_STATUSES.includes(status)
}

// How often the list and the details are loaded again while a meeting is
// being processed
export const REFRESH_INTERVAL_MS = 3000
