import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Navbar from './components/Navbar'
import ProtectedRoute from './components/ProtectedRoute'
import Home from './pages/Home'
import Login from './pages/Login'
import JobConfig from './pages/JobConfig'
import Processing from './pages/Processing'
import Candidates from './pages/Candidates'
import History from './pages/History'

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/job-config" element={<ProtectedRoute><JobConfig /></ProtectedRoute>} />
        <Route path="/processing" element={<ProtectedRoute><Processing /></ProtectedRoute>} />
        <Route path="/candidates" element={<ProtectedRoute><Candidates /></ProtectedRoute>} />
        <Route path="/history" element={<ProtectedRoute><History /></ProtectedRoute>} />
      </Routes>
    </BrowserRouter>
  )
}
