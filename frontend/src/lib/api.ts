import type { Role } from "./types";

const BASE = (import.meta.env.VITE_API_BASE as string | undefined)?.replace(/\/$/, "") ?? "";
const KEY = "brandguard.session.v1";

export interface Session { workspaceId: string; token: string; role: Role; brandName: string; isDemo: boolean }

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(KEY);
    return raw ? (JSON.parse(raw) as Session) : null;
  } catch {
    return null;
  }
}

export function saveSession(s: Session | null) {
  try {
    if (s) localStorage.setItem(KEY, JSON.stringify(s));
    else localStorage.removeItem(KEY);
  } catch {
    /* storage unavailable (private mode) — session lives in memory only */
  }
}

export class ApiError extends Error {
  constructor(message: string, public status: number) {
    super(message);
  }
}

let current: Session | null = loadSession();
export const setApiSession = (s: Session | null) => { current = s; };

export async function api<T>(path: string, init: RequestInit & { json?: unknown } = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (current) {
    headers.set("X-Workspace-Token", current.token);
    headers.set("X-Demo-Role", current.role);
  }
  let body = init.body;
  if (init.json !== undefined) {
    headers.set("Content-Type", "application/json");
    body = JSON.stringify(init.json);
  }
  const url = path.startsWith("/api") ? BASE + path : `${BASE}/api/w/${current?.workspaceId}${path}`;
  let res: Response;
  try {
    res = await fetch(url, { ...init, headers, body });
  } catch {
    throw new ApiError("Can't reach the BrandGuard server. Check your connection and try again.", 0);
  }
  if (!res.ok) {
    let detail = `Request failed (${res.status}).`;
    try {
      const data = await res.json();
      if (data?.detail) detail = typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail);
    } catch { /* non-JSON error */ }
    throw new ApiError(detail, res.status);
  }
  return (await res.json()) as T;
}

export const fileUrl = (name: string) => `${BASE}/api/samples/files/${encodeURIComponent(name)}`;
