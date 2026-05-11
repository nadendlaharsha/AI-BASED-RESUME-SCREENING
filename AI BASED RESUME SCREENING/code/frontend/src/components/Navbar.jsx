import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useState } from 'react';
import { useAuth } from '../context/useAuth';
import './Navbar.css';

export default function Navbar() {
  const { user, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
    setMobileMenuOpen(false);
  };

  const isActive = (path) => location.pathname === path;

  return (
    <nav className="navbar">
      <div className="navbar-inner">
        <Link to="/" className="navbar-brand">🎯 Resume Screener</Link>
        
        <button className="mobile-menu-btn" onClick={() => setMobileMenuOpen(!mobileMenuOpen)}>
          <span></span>
          <span></span>
          <span></span>
        </button>

        <div className={`navbar-links ${mobileMenuOpen ? 'mobile-open' : ''}`}>
          {user && (
            <>
              <Link to="/job-config" className={`nav-link ${isActive('/job-config') ? 'active' : ''}`} onClick={() => setMobileMenuOpen(false)}>📄 Job</Link>
              <Link to="/processing" className={`nav-link ${isActive('/processing') ? 'active' : ''}`} onClick={() => setMobileMenuOpen(false)}>⚙️ Process</Link>
              <Link to="/candidates" className={`nav-link ${isActive('/candidates') ? 'active' : ''}`} onClick={() => setMobileMenuOpen(false)}>👔 Results</Link>
              <Link to="/history" className={`nav-link ${isActive('/history') ? 'active' : ''}`} onClick={() => setMobileMenuOpen(false)}>📊 History</Link>
            </>
          )}
          {user ? (
            <button onClick={handleLogout} className="nav-link nav-logout">🚪 Logout</button>
          ) : (
            <Link to="/login" className={`nav-link ${isActive('/login') ? 'active' : ''}`} onClick={() => setMobileMenuOpen(false)}>🔐 Login</Link>
          )}
        </div>
      </div>
    </nav>
  );
}
