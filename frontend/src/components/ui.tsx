import { AlertTriangle, Loader2, X } from "lucide-react";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";
import { evidenceMeta, severityLabel, statusMeta } from "../lib/format";
import type { EvidenceStatus, Severity, SubmissionStatus } from "../lib/types";

const sevDot: Record<Severity, string> = {
  critical: "bg-sev-critical", high: "bg-sev-high", medium: "bg-sev-medium", low: "bg-sev-low",
};

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-graphite">
      <span className={`inline-block h-2 w-2 rounded-full ${sevDot[severity]}`} aria-hidden />
      {severityLabel[severity]}
    </span>
  );
}

export function SeverityBar({ severity }: { severity: Severity }) {
  const h = { critical: "h-full", high: "h-3/4", medium: "h-1/2", low: "h-1/4" }[severity];
  return (
    <span className="relative inline-block h-4 w-1 rounded-full bg-paper-edge" aria-hidden>
      <span className={`absolute bottom-0 left-0 w-1 rounded-full ${sevDot[severity]} ${h}`} />
    </span>
  );
}

export function EvidenceChip({ status }: { status: EvidenceStatus }) {
  const m = evidenceMeta[status];
  return <span className={`chip ${m.tone}`} title={m.help}>{m.short}</span>;
}

export function StatusChip({ status }: { status: SubmissionStatus }) {
  const m = statusMeta[status];
  return <span className={`chip ${m.tone}`}>{m.label}</span>;
}

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 py-10 text-sm text-graphite-mute" role="status">
      <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> {label}…
    </div>
  );
}

export function ErrorNote({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-sev-critical">
      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
      <div className="flex-1">{message}</div>
      {onRetry && <button className="font-medium underline" onClick={onRetry}>Retry</button>}
    </div>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-paper-rule bg-white/60 px-6 py-10 text-center">
      <p className="font-medium text-ink">{title}</p>
      {children && <div className="mx-auto mt-1 max-w-md text-sm text-graphite-mute">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function PageHeader({ title, intro, actions }: { title: string; intro?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="max-w-2xl">
        <h1 className="text-2xl font-semibold">{title}</h1>
        {intro && <p className="mt-1 text-graphite-mute">{intro}</p>}
      </div>
      {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
    </div>
  );
}

export function Drawer({ open, onClose, title, children }: { open: boolean; onClose: () => void; title: string; children: ReactNode }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex justify-end" role="dialog" aria-modal="true" aria-label={title}>
      <button className="absolute inset-0 bg-ink/30" aria-label="Close panel" onClick={onClose} />
      <div className="relative flex h-full w-full max-w-xl flex-col bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-paper-edge px-5 py-4">
          <h2 className="text-lg font-semibold">{title}</h2>
          <button className="btn-ghost p-1.5" onClick={onClose} aria-label="Close"><X className="h-5 w-5" /></button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-5">{children}</div>
      </div>
    </div>
  );
}

interface Toast { id: number; text: string; tone: "ok" | "error" }
const ToastCtx = createContext<(text: string, tone?: "ok" | "error") => void>(() => {});
export const useToast = () => useContext(ToastCtx);

export function ToastProvider({ children }: { children: ReactNode }) {
  const [toasts, setToasts] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setToasts((t) => [...t, { id, text, tone }]);
    setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "error" ? 7000 : 3500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed bottom-5 right-5 z-[60] flex w-[min(380px,calc(100vw-2.5rem))] flex-col gap-2" aria-live="polite">
        {toasts.map((t) => (
          <div key={t.id} className={`pointer-events-auto rounded-md px-4 py-3 text-sm shadow-lg ${t.tone === "ok" ? "bg-ink text-white" : "bg-sev-critical text-white"}`}>
            {t.text}
          </div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}
