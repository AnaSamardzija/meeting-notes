import axios from 'axios'

// The only place in the frontend that talks to the backend.
const api = axios.create({
  baseURL: import.meta.env.VITE_API_URL,
})

export async function getHealth() {
  const response = await api.get('/api/health')
  return response.data
}
