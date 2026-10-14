import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import AdminDashboard from './AdminDashboard.jsx'
import TechnicianDashboard from './TechnicianDashboard.jsx'

const isAdminDashboard = window.location.pathname.replace(/\/+$/, '') === '/admin-dashboard'
const isTechnicianDashboard = window.location.pathname.replace(/\/+$/, '') === '/technician-dashboard'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {isAdminDashboard ? <AdminDashboard /> : isTechnicianDashboard ? <TechnicianDashboard /> : <App />}
  </StrictMode>,
)
