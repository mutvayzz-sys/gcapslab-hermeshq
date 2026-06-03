import axios from "axios";
import type { AxiosError, InternalAxiosRequestConfig } from "axios";

import { resolveApiBase } from "../lib/apiBase";
import { useSessionStore } from "../stores/sessionStore";

const baseURL = resolveApiBase();

export const apiClient = axios.create({
  baseURL,
  timeout: 30_000, // 30 second timeout for all requests
});

// ── Refresh-token helpers ──────────────────────────────────────────────────

let _refreshPromise: Promise<string | null> | null = null;

async function _tryRefreshToken(): Promise<string | null> {
  const store = useSessionStore.getState();
  if (!store.token) return null;

  try {
    const { data } = await axios.post<{ access_token: string; expires_at: string }>(
      `${baseURL}/auth/refresh`,
      undefined,
      { withCredentials: true },
    );
    const newToken = data.access_token;
    store.setToken(newToken);
    return newToken;
  } catch {
    return null;
  }
}

function _queuedRefresh(): Promise<string | null> {
  if (!_refreshPromise) {
    _refreshPromise = _tryRefreshToken().finally(() => {
      _refreshPromise = null;
    });
  }
  return _refreshPromise;
}

// ── Interceptors ───────────────────────────────────────────────────────────

apiClient.interceptors.request.use((config) => {
  const token = useSessionStore.getState().token;
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  // Include cookies (for httpOnly auth cookie support)
  config.withCredentials = true;
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const status = error.response?.status;
    const requestUrl = error.config?.url ?? "";
    const isLoginAttempt = requestUrl.includes("/auth/login") || requestUrl.includes("/auth/refresh");
    const hadAuthHeader = Boolean(error.config?.headers?.Authorization);

    // If 401 and we have a session, try a token refresh once before logging out
    if (status === 401 && hadAuthHeader && !isLoginAttempt) {
      const hasSession = Boolean(useSessionStore.getState().token);
      if (hasSession) {
        const newToken = await _queuedRefresh();
        if (newToken && error.config) {
          // Clone the original request with the new token and retry
          const retryConfig = error.config;
          retryConfig.headers.set("Authorization", `Bearer ${newToken}`);
          return apiClient.request(retryConfig);
        }
        // Refresh also failed → log out
        useSessionStore.getState().logout();
      }
    }

    return Promise.reject(error);
  },
);
