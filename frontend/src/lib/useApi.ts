import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { useSession } from "./session";

/** Fetch a workspace-scoped resource; re-fetches when the path or role changes. */
export function useApi<T>(path: string | null) {
  const { session } = useSession();
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(!!path);
  const seq = useRef(0);

  const reload = useCallback(async () => {
    if (!path) return;
    const id = ++seq.current;
    setLoading(true);
    try {
      const d = await api<T>(path);
      if (id === seq.current) { setData(d); setError(null); }
    } catch (e) {
      if (id === seq.current) setError((e as Error).message);
    } finally {
      if (id === seq.current) setLoading(false);
    }
  }, [path]);

  useEffect(() => { void reload(); }, [reload, session?.workspaceId]);
  return { data, setData, error, loading, reload };
}
