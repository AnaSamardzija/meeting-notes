import { Navigate, Route, Routes } from 'react-router'
import GuestOnly from './components/GuestOnly'
import Layout from './components/Layout'
import RequireAuth from './components/RequireAuth'
import LoginPage from './pages/LoginPage'
import MeetingPage from './pages/MeetingPage'
import MeetingsPage from './pages/MeetingsPage'
import RegisterPage from './pages/RegisterPage'

// The pages of the app and their addresses. A route without a path (the
// layout and the login checks) only wraps the routes inside it: it shows its
// own content and the matching child route in its <Outlet />.
function App() {
  return (
    <Routes>
      <Route element={<Layout />}>
        <Route element={<GuestOnly />}>
          <Route path="/login" element={<LoginPage />} />
          <Route path="/register" element={<RegisterPage />} />
        </Route>
        <Route element={<RequireAuth />}>
          <Route path="/" element={<MeetingsPage />} />
          <Route path="/meetings/:id" element={<MeetingPage />} />
        </Route>
        {/* Any other address goes to the interviews (or to /login) */}
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  )
}

export default App
