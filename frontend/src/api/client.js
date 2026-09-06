const API_URL = process.env.REACT_APP_API_URL || "http://127.0.0.1:8000";

function getTokens() {
  return {
    access: localStorage.getItem("access"),
    refresh: localStorage.getItem("refresh"),
  };
}

export function setTokens({ access, refresh }) {
  if (access) localStorage.setItem("access", access);
  if (refresh) localStorage.setItem("refresh", refresh);
}

export function clearTokens() {
  localStorage.removeItem("access");
  localStorage.removeItem("refresh");
}

async function refreshAccessToken() {
  const { refresh } = getTokens();
  if (!refresh) return null;
  const response = await fetch(`${API_URL}/api/auth/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!response.ok) {
    clearTokens();
    return null;
  }
  const data = await response.json();
  setTokens({ access: data.access });
  return data.access;
}

/**
 * Thin fetch wrapper that attaches the JWT, retries once on a 401 after
 * refreshing the access token, and throws ApiError with parsed details
 * for anything else that isn't ok.
 */
export async function apiRequest(path, { method = "GET", body, auth = true } = {}) {
  const isFormData = body instanceof FormData;
  const doFetch = (accessToken) =>
    fetch(`${API_URL}${path}`, {
      method,
      headers: {
        // A FormData body (e.g. a profile picture upload) needs the browser
        // to set its own multipart Content-Type with the boundary - setting
        // it ourselves here would break the upload.
        ...(isFormData ? {} : { "Content-Type": "application/json" }),
        ...(auth && accessToken ? { Authorization: `Bearer ${accessToken}` } : {}),
      },
      body: body ? (isFormData ? body : JSON.stringify(body)) : undefined,
    });

  let { access } = getTokens();
  let response = await doFetch(access);

  if (response.status === 401 && auth) {
    access = await refreshAccessToken();
    if (access) {
      response = await doFetch(access);
    }
  }

  let data = null;
  const text = await response.text();
  if (text) {
    try {
      data = JSON.parse(text);
    } catch {
      data = { detail: text };
    }
  }

  if (!response.ok) {
    const message =
      (data && (data.detail || summarizeFieldErrors(data))) || `Request failed (${response.status})`;
    throw new ApiError(message, response.status, data);
  }

  return data;
}

function summarizeFieldErrors(data) {
  if (typeof data !== "object" || data === null) return null;
  const parts = Object.entries(data).map(([field, value]) => {
    const message = Array.isArray(value) ? value.join(" ") : value;
    return field === "non_field_errors" ? message : `${field}: ${message}`;
  });
  return parts.join(" ");
}

export class ApiError extends Error {
  constructor(message, status, data) {
    super(message);
    this.status = status;
    this.data = data;
  }
}

export { API_URL };
