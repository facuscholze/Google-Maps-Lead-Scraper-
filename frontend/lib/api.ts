"use client";

// Thin fetch wrapper: attaches the JWT from localStorage and normalizes errors.

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem("avascho_token");
}

export function setToken(token: string | null) {
  if (typeof window === "undefined") return;
  if (token) window.localStorage.setItem("avascho_token", token);
  else window.localStorage.removeItem("avascho_token");
}

export function clearSession() {
  setToken(null);
  window.location.href = "/login";
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = buildHeaders(options);
  const response = await fetch(path, { ...options, headers });
  if (response.status === 401 && !path.includes("/auth/login")) {
    clearSession();
    throw new ApiError(401, "Sesión expirada");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

function buildHeaders(options: RequestInit = {}): Record<string, string> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function readError(response: Response): Promise<string> {
  let detail = response.statusText;
  try {
    const body = await response.json();
    detail = typeof body.detail === "string" ? body.detail : JSON.stringify(body.detail || body);
  } catch {
    /* noop */
  }
  return detail;
}

/**
 * Same authenticated request, but the body is returned as a Blob so binary
 * downloads (CSV/XLSX exports) keep working through the API client.
 */
async function requestBlob(path: string): Promise<Blob> {
  const response = await fetch(path, { headers: buildHeaders() });
  if (response.status === 401) {
    clearSession();
    throw new ApiError(401, "Sesión expirada");
  }
  if (!response.ok) {
    throw new ApiError(response.status, await readError(response));
  }
  return response.blob();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  getBlob: (path: string) => requestBlob(path),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body !== undefined ? JSON.stringify(body) : undefined }),
  put: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PUT", body: body !== undefined ? JSON.stringify(body) : undefined }),
  patch: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "PATCH", body: body !== undefined ? JSON.stringify(body) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: "DELETE" }),
};
