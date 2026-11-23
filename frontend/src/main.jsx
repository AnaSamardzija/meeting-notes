import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { BrowserRouter } from 'react-router'
// Bootstrap first, so the rules in index.css can override it
import 'bootstrap/dist/css/bootstrap.min.css'
import './index.css'
import App from './App.jsx'
import AuthProvider from './components/AuthProvider'

// BrowserRouter keeps the page in step with the address in the browser;
// AuthProvider knows who is logged in. Both wrap the whole app, so every
// component can use them.
createRoot(document.getElementById('root')).render(
  <StrictMode>
    <BrowserRouter>
      <AuthProvider>
        <App />
      </AuthProvider>
    </BrowserRouter>
  </StrictMode>,
)
