const BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

function getStoredToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("access_token");
}

function getRefreshToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("refresh_token");
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

async function tryRefresh(): Promise<string | null> {
  const refreshToken = getRefreshToken();
  if (!refreshToken) return null;
  try {
    const res = await fetch(`${BASE_URL}/api/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    localStorage.setItem("access_token", data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    return data.access_token as string;
  } catch {
    return null;
  }
}

async function apiFetchInternal<T>(
  path: string,
  options: RequestInit & { authToken?: string },
  retry: boolean,
): Promise<T> {
  const { authToken, ...fetchOptions } = options;
  const token = authToken ?? getStoredToken();

  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(fetchOptions.headers as Record<string, string>),
  };

  const res = await fetch(`${BASE_URL}${path}`, { ...fetchOptions, headers });

  if (res.status === 401 && !retry && !authToken) {
    const newToken = await tryRefresh();
    if (newToken) {
      return apiFetchInternal<T>(path, { ...options, authToken: newToken }, true);
    }
    const { clearAuth } = await import("./auth");
    clearAuth();
    if (typeof window !== "undefined") window.location.href = "/login";
    throw new ApiError(401, "Session expired");
  }

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore parse error
    }
    throw new ApiError(res.status, detail);
  }

  // 204 No Content
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export async function apiFetch<T = unknown>(
  path: string,
  options: RequestInit & { authToken?: string } = {},
): Promise<T> {
  return apiFetchInternal<T>(path, options, false);
}
