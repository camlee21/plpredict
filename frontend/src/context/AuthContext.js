import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { apiRequest, clearTokens, setTokens } from "../api/client";
import { clearPersistedCache } from "../api/persist";

const AuthContext = createContext(null);

// The logged-in user's own profile, kept so a reload can show the app at once
// instead of waiting on the server to confirm who you are first.
const USER_KEY = "user";

function readSavedUser() {
  try {
    const saved = localStorage.getItem(USER_KEY);
    return saved && localStorage.getItem("access") ? JSON.parse(saved) : null;
  } catch {
    return null;
  }
}

function saveUser(user) {
  try {
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
    else localStorage.removeItem(USER_KEY);
  } catch {
    // Storage unavailable: the app still works, it just checks on each load.
  }
}

export function AuthProvider({ children }) {
  const [initialUser] = useState(readSavedUser);
  const [user, setUser] = useState(initialUser);
  // With a saved profile there's nothing to wait for: pages render straight
  // away (from the saved cache too) while the check below runs.
  const [loading, setLoading] = useState(initialUser === null);
  const queryClient = useQueryClient();

  useEffect(() => saveUser(user), [user]);

  const loadMe = useCallback(async () => {
    try {
      setUser(await apiRequest("/api/auth/me/"));
    } catch (err) {
      // Only a definite "not logged in" ends the session. A network error or
      // a server still waking up keeps the saved profile, so a slow server
      // never logs anyone out.
      if (err.status === 401 || err.status === 403 || !initialUser) {
        queryClient.clear();
        clearPersistedCache();
        setUser(null);
      }
    } finally {
      setLoading(false);
    }
  }, [initialUser, queryClient]);

  useEffect(() => {
    if (localStorage.getItem("access")) {
      loadMe();
    } else {
      setLoading(false);
    }
  }, [loadMe]);

  // Nearly everything cached belongs to one user, so a different person
  // logging in on this browser must never see the last one's data - in
  // memory or in the copy saved for reloads.
  const forgetCachedData = () => {
    queryClient.clear();
    clearPersistedCache();
  };

  const applyAuthResponse = (data) => {
    forgetCachedData();
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
    forgetCachedData();
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
