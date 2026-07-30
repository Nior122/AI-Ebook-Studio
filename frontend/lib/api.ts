// Typed API client — the single HTTP gateway from the frontend to the backend.
// Auth: Clerk session token attached as Bearer header (client-side only).
// For server-side API calls use @/lib/server-api instead.

/** Base URL of the backend REST API. */
const API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL ?? "/api/v1";

/** Normalized API error thrown on non-2xx responses. */
export class ApiError extends Error {
  readonly status: number;
  readonly body: unknown;
  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function buildUrl(path: string, query?: Record<string, unknown>): string {
  const joined = path.startsWith("/") ? `${API_BASE_URL}${path}` : `${API_BASE_URL}/${path}`;
  // Support relative base URLs (e.g. "/api/v1" when proxying through Next.js).
  // new URL() requires an absolute URL, so only use it when we have a full
  // origin; otherwise fall back to string-based query concatenation.
  if (API_BASE_URL.startsWith("http://") || API_BASE_URL.startsWith("https://")) {
    const url = new URL(joined);
    if (query) {
      for (const [key, value] of Object.entries(query)) {
        if (value !== undefined && value !== null) {
          url.searchParams.set(key, String(value));
        }
      }
    }
    return url.toString();
  }
  // Relative path: build query string manually.
  let out = joined;
  if (query) {
    const params = new URLSearchParams();
    for (const [key, value] of Object.entries(query)) {
      if (value !== undefined && value !== null) {
        params.set(key, String(value));
      }
    }
    const qs = params.toString();
    if (qs) out += (out.includes("?") ? "&" : "?") + qs;
  }
  return out;
}

function safeJson(text: string): unknown {
  try { return JSON.parse(text); } catch { return text; }
}

// Module-level token set by ClerkTokenProvider on the client side.
let _clientToken: string | null = null;

/** Called by the ClerkTokenProvider component to inject the session token. */
export function setSessionToken(token: string | null) {
  _clientToken = token;
}

/** Get the Clerk session token (client-side only).
 *
 * If the token isn't available yet (Clerk still initializing), waits up to
 * 3 seconds polling for the session to become available before giving up.
 */
async function getToken(): Promise<string | null> {
  if (typeof window === "undefined") return null;
  if (_clientToken) return _clientToken;

  // Poll for Clerk session to become available (max ~3s).
  for (let attempt = 0; attempt < 10; attempt++) {
    const w = window as unknown as { Clerk?: { session?: { getToken: () => Promise<string | null> } } };
    if (w.Clerk?.session) {
      try {
        return await w.Clerk.session.getToken();
      } catch {
        return null;
      }
    }
    // Wait 300ms before checking again.
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  return null;
}

function extractErrorMessage(body: unknown): string | null {
  if (!body || typeof body !== "object") return null;
  const b = body as Record<string, unknown>;
  if (typeof b.detail === "string") return b.detail;
  if (b.error && typeof b.error === "object") {
    const e = b.error as Record<string, unknown>;
    if (typeof e.message === "string") return e.message;
  }
  return null;
}

/** Core request method. Attaches the Clerk session token as Bearer header. */
async function request<T>(
  path: string,
  init: RequestInit = {},
  query?: Record<string, unknown>,
): Promise<T> {
  try {
    const headers = new Headers(init.headers);
    if (init.body && !headers.has("Content-Type")) {
      headers.set("Content-Type", "application/json");
    }
    if (!headers.has("Accept")) {
      headers.set("Accept", "application/json");
    }

    const token = await getToken();
    if (token) {
      headers.set("Authorization", `Bearer ${token}`);
    }

    const url = buildUrl(path, query);
    let res = await fetch(url, { ...init, headers });

    // If we get 401 and had a token, refresh the token and retry once.
    if (res.status === 401 && token) {
      const w = window as unknown as { Clerk?: { session?: { getToken: () => Promise<string | null> } } };
      if (w.Clerk?.session) {
        try {
          const freshToken = await w.Clerk.session.getToken();
          if (freshToken && freshToken !== token) {
            _clientToken = freshToken;
            headers.set("Authorization", `Bearer ${freshToken}`);
            res = await fetch(url, { ...init, headers });
          }
        } catch {
          // fall through to original 401 response
        }
      }
    }

    if (res.status === 204) return undefined as T;

    const raw = await res.text();
    const body = raw ? safeJson(raw) : null;

    if (!res.ok) {
      const msg = extractErrorMessage(body);
      const message = msg ?? (res.statusText || "Request failed");
      throw new ApiError(message, res.status, body);
    }
    return body as T;
  } catch (err) {
    if (err instanceof ApiError) throw err;
    throw new ApiError(
      err instanceof Error ? err.message : "Request failed",
      0,
      null,
    );
  }
}

export const apiClient = {
  get: <T>(path: string, query?: Record<string, unknown>) =>
    request<T>(path, { method: "GET" }, query),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "POST", body: data === undefined ? undefined : JSON.stringify(data) }),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PUT", body: data === undefined ? undefined : JSON.stringify(data) }),
  patch: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: "PATCH", body: data === undefined ? undefined : JSON.stringify(data) }),
  delete: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
