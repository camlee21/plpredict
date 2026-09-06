import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiRequest, clearTokens, setTokens } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  const loadMe = useCallback(async () => {
    try {
      const me = await apiRequest("/api/auth/me/");
      setUser(me);
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (localStorage.getItem("access")) {
      loadMe();
    } else {
      setLoading(false);
    }
  }, [loadMe]);

  const applyAuthResponse = (data) => {
    setTokens({ access: data.access, refresh: data.refresh });
    setUser(data.user);
  };

  const login = async (usernameOrEmail, password) => {
    const data = await apiRequest("/api/auth/login/", {
      method: "POST",
      auth: false,
      body: { username_or_email: usernameOrEmail, password },
    });
    applyAuthResponse(data);
  };

  const register = async (username, email, password) => {
    const data = await apiRequest("/api/auth/register/", {
      method: "POST",
      auth: false,
      body: { username, email, password },
    });
    applyAuthResponse(data);
  };

  const loginWithGoogle = async (idToken) => {
    const data = await apiRequest("/api/auth/google/", {
      method: "POST",
      auth: false,
      body: { id_token: idToken },
    });
    applyAuthResponse(data);
  };

  const logout = () => {
    clearTokens();
    setUser(null);
  };

  return (
    <AuthContext.Provider
      value={{ user, loading, login, register, loginWithGoogle, logout, setUser }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  return useContext(AuthContext);
}
