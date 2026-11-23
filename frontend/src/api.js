import axios from 'axios'

// The only place in the frontend that talks to the backend, and the only one
// that reads its address.
export const API_URL = import.meta.env.VITE_API_URL

// The longest title the backend accepts (TITLE_MAX_LENGTH in
// backend/app/schemas.py)
export const TITLE_MAX_LENGTH = 255

// The length of a password the registration accepts (PASSWORD_MIN_LENGTH and
// PASSWORD_MAX_LENGTH in backend/app/schemas.py)
export const PASSWORD_MIN_LENGTH = 10
export const PASSWORD_MAX_LENGTH = 128

// withCredentials: the browser sends the login cookie (and accepts the one the
// login sets) although the backend runs on another origin. The page cannot
// read the cookie itself: it is httpOnly.
const api = axios.create({
  baseURL: API_URL,
  withCredentials: true,
})

// The answer of a failed login is 401 too, but there it means a wrong email or
// password, which the login page shows as a message
const LOGIN_URL = '/api/auth/login'

// The function called when the backend answers 401 (not logged in, or the
// login has expired). AuthProvider sets it; it forgets the user, which sends
// the user to /login.
let onUnauthorized = null

export function setUnauthorizedHandler(handler) {
  onUnauthorized = handler
}

// An interceptor runs for every answer before the code that sent the request
// gets it. The first function gets the successful answers, the second the
// errors. The error is still passed on, so the caller stops as before.
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (
      error.response?.status === 401 &&
      error.config?.url !== LOGIN_URL &&
      onUnauthorized
    ) {
      onUnauthorized()
    }
    return Promise.reject(error)
  },
)

// Turns an error of a request into a message for the user.
// fallback: what could not be done, e.g. 'Could not load the interviews'. It is
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

// Logs in; the backend puts the login cookie into the browser. Returns the user.
export async function login(email, password) {
  const response = await api.post(LOGIN_URL, { email, password })
  return response.data
}

// Creates a regular account and logs it in at once (the backend sets the
// cookie, as for the login). Returns the new user.
export async function register(email, password) {
  const response = await api.post('/api/auth/register', { email, password })
  return response.data
}

// Asks the backend to delete the login cookie; JavaScript cannot delete an
// httpOnly cookie itself.
export async function logout() {
  await api.post('/api/auth/logout')
}

// Returns the logged-in user ({ id, email, role, ... }). Fails with 401 when
// nobody is logged in.
export async function getMe() {
  const response = await api.get('/api/auth/me')
  return response.data
}

// Changes the password of the logged-in user. The backend logs out every
// other browser and gives this one a new login cookie. A wrong current
// password is a 400 with a message for the user.
export async function changePassword(currentPassword, newPassword) {
  await api.post('/api/auth/password', {
    current_password: currentPassword,
    new_password: newPassword,
  })
}

// Returns the rows of the meetings list, the newest first.
export async function getMeetings() {
  const response = await api.get('/api/meetings')
  return response.data
}

// Returns everything about one meeting (an interview): the transcript, the
// interviewee and the insights. They are empty until the processing is done.
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

// Changes the given fields of the meeting (for now only { title }) and
// returns the whole updated meeting.
export async function updateMeeting(id, data) {
  const response = await api.patch(`/api/meetings/${id}`, data)
  return response.data
}

// Returns the summary of a processed meeting in the shape of the edit form:
// { name, role, location, takeaway, context, likes, dislikes, wants }, all of
// them text. likes, dislikes and wants have one paragraph per item.
export async function getSummary(id) {
  const response = await api.get(`/api/meetings/${id}/summary`)
  return response.data
}

// Replaces the summary with the edited one (the same shape as getSummary
// returns) and returns the whole updated meeting.
export async function updateSummary(id, summary) {
  const response = await api.put(`/api/meetings/${id}/summary`, summary)
  return response.data
}

// Sends the video and the title as multipart/form-data and returns the
// created meeting. An empty title lets the AI write one. onProgress is called
// with the percentage (0-100) sent so far.
export async function uploadMeeting(file, title, onProgress) {
  // The field names must match the parameters of the upload endpoint ("file"
  // and "title"). The Content-Type header is not set here: the browser adds
  // it together with the boundary that separates the parts of the body.
  const formData = new FormData()
  formData.append('file', file)
  formData.append('title', title)

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
