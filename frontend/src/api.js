import axios from 'axios'

// The only place in the frontend that talks to the backend.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

export async function getHealth() {
  const response = await api.get('/api/health')
  return response.data
}

// Returns the rows of the meetings list, the newest first.
export async function getMeetings() {
  const response = await api.get('/api/meetings')
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
