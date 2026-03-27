/**
 * Typed fetch wrapper for the AIphaWatch API.
 * Adds Authorization header and handles JSON responses.
 */

const API_BASE = "/api";

/** Get the auth token (placeholder — Cognito SDK integration in Phase 2). */
function getAuthToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("auth_token");
}

/** Build headers with optional auth token. */
function buildHeaders(extra?: Record<string, string>): HeadersInit {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...extra,
  };
  const token = getAuthToken();
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }
  return headers;
}

/** Typed GET request. */
export async function apiGet<T>(path: string): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: buildHeaders(),
  });
  if (!res.ok) throw new Error(`GET ${path}: ${res.status}`);
  return res.json();
}

/** Typed POST request. */
export async function apiPost<T>(
  path: string,
  body?: unknown
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    headers: buildHeaders(),
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`POST ${path}: ${res.status}`);
  return res.json();
}

/**
 * Build a full SSE URL for chat message streaming.
 * Returns the URL string (not a fetch — SSE is handled by useSSE hook).
 */
export function chatSSEUrl(sessionId: string): string {
  return `${API_BASE}/chat/sessions/${sessionId}/messages`;
}
