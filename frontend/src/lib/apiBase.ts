const envBase = import.meta.env.VITE_API_BASE_URL?.trim();

export function resolveApiBase(): string {
  if (envBase) {
    return envBase.replace(/\/$/, "");
  }

  if (typeof window !== "undefined") {
    return "/api";
  }

  return "http://localhost:8000/api";
}

export function resolveApiRoot(): string {
  const apiBase = resolveApiBase();
  if (/^https?:\/\//.test(apiBase)) {
    return apiBase.replace(/\/api$/, "");
  }
  if (typeof window !== "undefined") {
    return window.location.origin;
  }
  return "http://localhost:8000";
}

export function resolveWsRoot(): string {
  const apiBase = resolveApiBase();
  // If the API base is an absolute URL, derive the WS root from it.
  if (/^https?:\/\//.test(apiBase)) {
    return apiBase.replace(/\/api$/, "").replace(/^http/, "ws");
  }
  // Relative API base (same origin) — use window.location.
  if (typeof window !== "undefined") {
    return window.location.origin.replace(/^http/, "ws");
  }
  return "ws://localhost:8000";
}
