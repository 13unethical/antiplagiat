export interface AuthUser {
  id: string;
  email: string;
  full_name: string;
  role: "superadmin" | "school_admin" | "teacher";
  org_id: string | null;
  status: string;
}

import { DEMO, demoUser } from "./demo";

export function getUser(): AuthUser | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = localStorage.getItem("user");
    if (raw) return JSON.parse(raw) as AuthUser;
    return DEMO ? demoUser : null;
  } catch {
    return DEMO ? demoUser : null;
  }
}

export function setAuth(accessToken: string, refreshToken: string, user: AuthUser): void {
  localStorage.setItem("access_token", accessToken);
  localStorage.setItem("refresh_token", refreshToken);
  localStorage.setItem("user", JSON.stringify(user));
}

export function clearAuth(): void {
  localStorage.removeItem("access_token");
  localStorage.removeItem("refresh_token");
  localStorage.removeItem("user");
}

export function isAuthenticated(): boolean {
  return getUser() !== null;
}
