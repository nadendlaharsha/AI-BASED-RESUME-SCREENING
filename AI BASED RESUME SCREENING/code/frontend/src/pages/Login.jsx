import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { login, signup, getStatus } from '../api/client';
import { useAuth } from '../context/useAuth';
import './Login.css';

export default function Login() {
  const { user, loginUser } = useAuth();
  const navigate = useNavigate();
  const [tab, setTab] = useState('signin');
  const [email, setEmail] = useState(localStorage.getItem('rememberedEmail') || '');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [remember, setRemember] = useState(!!localStorage.getItem('rememberedEmail'));
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getStatus().catch(() => null);
  }, []);

  if (user) {
    navigate('/job-config');
    return null;
  }

  const handleLogin = async (e) => {
    e.preventDefault();
    if (!email || !password) { setError('Please enter email and password.'); return; }
    setLoading(true); setError('');
    try {
      const res = await login(email, password);
      if (remember) localStorage.setItem('rememberedEmail', email);
      else localStorage.removeItem('rememberedEmail');
      loginUser(res.data.user, res.data.session);
      navigate('/job-config');
    } catch (err) {
      if (err.code === 'ERR_NETWORK' || err.response?.status === 502) {
        setError('Backend server is not running. Please start the Flask API first.');
      } else {
        setError(err.response?.data?.error || 'Invalid email or password.');
      }
    } finally { setLoading(false); }
  };

  const handleSignup = async (e) => {
    e.preventDefault();
    if (!email || !password || !confirm) { setError('All fields required.'); return; }
    if (password.length < 6) { setError('Password must be at least 6 characters.'); return; }
    if (password !== confirm) { setError('Passwords do not match.'); return; }
    setLoading(true); setError('');
    try {
      await signup(email, password);
      localStorage.setItem('rememberedEmail', email);
      setSuccess('Account created! Please sign in.');
      setTab('signin');
    } catch (err) {
      if (err.code === 'ERR_NETWORK' || err.response?.status === 502) {
        setError('Backend server is not running. Please start the Flask API first.');
      } else {
        setError(err.response?.data?.error || 'Signup failed.');
      }
    } finally { setLoading(false); }
  };

  return (
    <div className="login-page">
      <div className="login-card glass-card">
        <h1>🔐 Login</h1>

        <div className="tabs">
          <button className={`tab ${tab === 'signin' ? 'active' : ''}`} onClick={() => { setTab('signin'); setError(''); }}>Sign In</button>
          <button className={`tab ${tab === 'signup' ? 'active' : ''}`} onClick={() => { setTab('signup'); setError(''); }}>Sign Up</button>
        </div>

        {error && <div className="alert alert-error">{error}</div>}
        {success && <div className="alert alert-success">{success}</div>}

        {tab === 'signin' ? (
          <form onSubmit={handleLogin}>
            <div className="form-group">
              <label>Email</label>
              <input className="input" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input className="input" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••" />
            </div>
            <label className="checkbox-label">
              <input type="checkbox" checked={remember} onChange={e => setRemember(e.target.checked)} />
              Remember my email
            </label>
            <button className="btn btn-primary btn-full" type="submit" disabled={loading} style={{ marginTop: 16 }}>
              {loading ? 'Signing in...' : 'Login'}
            </button>
          </form>
        ) : (
          <form onSubmit={handleSignup}>
            <div className="form-group">
              <label>Email</label>
              <input className="input" type="email" value={email} onChange={e => setEmail(e.target.value)} placeholder="you@example.com" />
            </div>
            <div className="form-group">
              <label>Password</label>
              <input className="input" type="password" value={password} onChange={e => setPassword(e.target.value)} placeholder="••••••" />
            </div>
            <div className="form-group">
              <label>Confirm Password</label>
              <input className="input" type="password" value={confirm} onChange={e => setConfirm(e.target.value)} placeholder="••••••" />
            </div>
            <button className="btn btn-primary btn-full" type="submit" disabled={loading}>
              {loading ? 'Creating...' : 'Create Account'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
