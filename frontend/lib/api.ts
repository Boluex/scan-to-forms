const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

type ApiOptions = RequestInit & { auth?: boolean };

export class ApiError extends Error {
  constructor(public status: number, public payload: unknown) {
    super(extractError(payload));
  }
}

export function extractError(payload: unknown): string {
  if (typeof payload === "string") return payload;
  if (!payload || typeof payload !== "object") return "Something went wrong.";
  const value = payload as Record<string, unknown>;
  if (value.error && typeof value.error === "object") return extractError((value.error as Record<string, unknown>).detail);
  if (typeof value.detail === "string") return value.detail;
  const first = Object.values(value)[0];
  if (Array.isArray(first)) return String(first[0]);
  if (typeof first === "string") return first;
  return "Something went wrong.";
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("scanforms_access", access);
  localStorage.setItem("scanforms_refresh", refresh);
}

export function clearTokens() {
  localStorage.removeItem("scanforms_access");
  localStorage.removeItem("scanforms_refresh");
}

export function hasSession() {
  return typeof window !== "undefined" && Boolean(localStorage.getItem("scanforms_access"));
}

async function refreshAccess(): Promise<string | null> {
  const refresh = localStorage.getItem("scanforms_refresh");
  if (!refresh) return null;
  const response = await fetch(`${API_URL}/auth/token/refresh/`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh }),
  });
  if (!response.ok) {
    clearTokens();
    return null;
  }
  const data = (await response.json()) as { access: string; refresh?: string };
  localStorage.setItem("scanforms_access", data.access);
  if (data.refresh) localStorage.setItem("scanforms_refresh", data.refresh);
  return data.access;
}

export async function api<T>(path: string, options: ApiOptions = {}, retry = true): Promise<T> {
  const headers = new Headers(options.headers);
  if (!(options.body instanceof FormData) && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  if (options.auth !== false && typeof window !== "undefined") {
    const token = localStorage.getItem("scanforms_access");
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (response.status === 401 && retry && options.auth !== false) {
    const token = await refreshAccess();
    if (token) return api<T>(path, options, false);
  }
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = await response.text();
    }
    throw new ApiError(response.status, payload);
  }
  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export async function download(path: string, fallbackName: string) {
  const headers = new Headers();
  const token = localStorage.getItem("scanforms_access");
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const response = await fetch(`${API_URL}${path}`, { headers });
  if (!response.ok) throw new Error("Download failed.");
  const blob = await response.blob();
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const link = window.document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = match?.[1] ?? fallbackName;
  link.click();
  URL.revokeObjectURL(link.href);
}

export { API_URL };

