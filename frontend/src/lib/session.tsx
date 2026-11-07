import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api, loadSession, saveSession, setApiSession, type Session } from "./api";
import type { Role } from "./types";

interface Ctx {
  session: Session | null;
  launchDemo: () => Promise<Session>;
  createWorkspace: (name: string, brand: string) => Promise<Session>;
  setRole: (r: Role) => void;
  leave: () => void;
}

const SessionContext = createContext<Ctx | null>(null);

interface WsResponse { workspace_id: string; token: string; brand_name: string; is_demo: boolean }

export function SessionProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<Session | null>(() => loadSession());

  const apply = useCallback((s: Session | null) => {
    setApiSession(s);
    saveSession(s);
    setSession(s);
  }, []);

  const launchDemo = useCallback(async () => {
    const r = await api<WsResponse>("/api/workspaces/demo", { method: "POST" });
    const s: Session = { workspaceId: r.workspace_id, token: r.token, role: "creator", brandName: r.brand_name, isDemo: true };
    apply(s);
    return s;
  }, [apply]);

  const createWorkspace = useCallback(async (name: string, brand: string) => {
    const r = await api<WsResponse>("/api/workspaces", { method: "POST", json: { name, brand_name: brand } });
    const s: Session = { workspaceId: r.workspace_id, token: r.token, role: "admin", brandName: r.brand_name, isDemo: false };
    apply(s);
    return s;
  }, [apply]);

  const setRole = useCallback((role: Role) => {
    setSession((prev) => {
      if (!prev) return prev;
      const next = { ...prev, role };
      setApiSession(next);
      saveSession(next);
      return next;
    });
  }, []);

  const leave = useCallback(() => apply(null), [apply]);

  const value = useMemo(() => ({ session, launchDemo, createWorkspace, setRole, leave }), [session, launchDemo, createWorkspace, setRole, leave]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession() {
  const c = useContext(SessionContext);
  if (!c) throw new Error("useSession outside provider");
  return c;
}
