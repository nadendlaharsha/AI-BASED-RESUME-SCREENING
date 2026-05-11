import { createContext, useState } from 'react';

const AuthContext = createContext(null);

function safeParseJSON(value) {
  if (!value) return null;
  try {
    return JSON.parse(value);
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => safeParseJSON(localStorage.getItem('user')));
  const [session, setSession] = useState(() => safeParseJSON(localStorage.getItem('session')));
  const loading = false;

  const loginUser = (userData, sessionData) => {
    setUser(userData);
    setSession(sessionData);
    localStorage.setItem('user', JSON.stringify(userData));
    localStorage.setItem('session', JSON.stringify(sessionData));
  };

  const logout = () => {
    setUser(null);
    setSession(null);
    localStorage.removeItem('user');
    localStorage.removeItem('session');
    localStorage.removeItem('rememberedEmail');
  };

  return (
    <AuthContext.Provider value={{ user, session, loading, loginUser, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export default AuthContext;
