import axios from 'axios'

// The only place in the frontend that talks to the backend, and the only one
// that reads its address.
export const API_URL = import.meta.env.VITE_API_URL

const api = axios.create({
  baseURL: API_URL,
})

// Turns an error of a request into a message for the user.
// fallback: what could not be done, e.g. 'Could not load the meetings'. It is
// used when the backend answered without a message of its own.
export function getErrorMessage(error, fallback) {
  // error.response exists only when the backend answered
  if (!error.response) {
    return `Backend is not available at ${API_URL}. Make sure it is running and try again.`
  }

  const { status, data } = error.response
  // The backend sends {"detail": "..."}, written for the user. For validation
  // errors (422) detail is a list, which is not shown.
  if (typeof data?.detail === 'string') {
    return data.detail
  }
  return `${fallback} (HTTP ${status}).`
}

export async function getHealth() {
  const response = await api.get('/api/health')
  return response.data
}

// Returns the rows of the meetings list, the newest first.
export async function getMeetings() {
  const response = await api.get('/api/meetings')
  return response.data
}

// Returns everything about one meeting: the transcript, the summary, the key
// topics and the action items. They are empty until the processing is done.
export async function getMeeting(id) {
  const response = await api.get(`/api/meetings/${id}`)
  return response.data
}

// Starts the processing of the meeting again and returns the meeting with its
// new status. The backend answers at once; the processing runs after that.
export async function reprocessMeeting(id) {
  const response = await api.post(`/api/meetings/${id}/process`)
  return response.data
}

// Sends the video as multipart/form-data and returns the created meeting.
// onProgress is called with the percentage (0-100) sent so far.
export async function uploadMeeting(file, onProgress) {
  // The field name must match the parameter of the upload endpoint ("file").
  // The Content-Type header is not set here: the browser adds it together
  // with the boundary that separates the parts of the body.
  const formData = new FormData()
  formData.append('file', file)

  const response = await api.post('/api/meetings', formData, {
    onUploadProgress: (event) => {
      // total is missing when the browser cannot tell the size of the body
      if (onProgress && event.total) {
        onProgress(Math.round((event.loaded / event.total) * 100))
      }
    },
  })
  return response.data
}
