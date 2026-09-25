const API_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
type ApiOptions = RequestInit & { auth?: boolean };
export class ApiError extends Error {
  constructor(
    public status: number,
    public payload: unknown,
  ) {
    super(extractError(payload));
  }
}
export function extractError(payload: unknown): string {
  if (typeof payload === "string") return payload;
  if (Array.isArray(payload)) return payload.map(extractError).join(" ");
  if (!payload || typeof payload !== "object") return "Something went wrong.";
  const value = payload as Record<string, unknown>;
  if (value.error) return extractError(value.error);
  if (value.detail) return extractError(value.detail);
  return Object.entries(value)
    .filter(([key]) => key !== "status")
    .map(([key, item]) => `${key}: ${extractError(item)}`)
    .join(" ");
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
  return (
    typeof window !== "undefined" &&
    Boolean(localStorage.getItem("scanforms_access"))
  );
}
let refreshing: Promise<string | null> | null = null;
async function refreshAccess() {
  if (refreshing) return refreshing;
  refreshing = (async () => {
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
    const data = await response.json();
    setTokens(data.access, data.refresh ?? refresh);
    return data.access as string;
  })();
  try {
    return await refreshing;
  } finally {
    refreshing = null;
  }
}
export async function authorizedFetch(
  path: string,
  options: ApiOptions = {},
  retry = true,
): Promise<Response> {
  const headers = new Headers(options.headers);
  if (
    !(options.body instanceof FormData) &&
    options.body &&
    !headers.has("Content-Type")
  )
    headers.set("Content-Type", "application/json");
  if (options.auth !== false && typeof window !== "undefined") {
    const token = localStorage.getItem("scanforms_access");
    if (token) headers.set("Authorization", `Bearer ${token}`);
  }
  const response = await fetch(`${API_URL}${path}`, { ...options, headers });
  if (
    response.status === 401 &&
    retry &&
    options.auth !== false &&
    (await refreshAccess())
  )
    return authorizedFetch(path, options, false);
  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.clone().json();
    } catch {
      payload = await response.text();
    }
    throw new ApiError(response.status, payload);
  }
  return response;
}
export async function api<T>(
  path: string,
  options: ApiOptions = {},
): Promise<T> {
  const response = await authorizedFetch(path, options);
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}
export async function download(path: string, fallbackName: string) {
  const response = await authorizedFetch(path);
  const blob = await response.blob();
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = fallbackName;
  link.click();
  setTimeout(() => URL.revokeObjectURL(link.href), 1000);
}
export async function logout() {
  const refresh = localStorage.getItem("scanforms_refresh");
  try {
    if (refresh)
      await api("/auth/logout/", {
        method: "POST",
        body: JSON.stringify({ refresh }),
      });
  } finally {
    clearTokens();
  }
}
export { API_URL };
