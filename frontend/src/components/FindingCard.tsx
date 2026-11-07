import { Bot, Check, FileText, Pencil, ShieldAlert, X } from "lucide-react";
import { useState } from "react";
import { citation, evidenceMeta } from "../lib/format";
import type { Finding, Role } from "../lib/types";
import { EvidenceChip, SeverityBadge, SeverityBar } from "./ui";

interface Props {
  f: Finding;
  role: Role;
  active: boolean;
  editable: boolean;
  onFocus: () => void;
  onEvidence: (id: string) => void;
  onAccept: (edited?: string) => Promise<void>;
  onReject: (reason: string) => Promise<void>;
}

const originLabel = { rule: "Deterministic rule", retrieval: "Evidence retrieval", ai: "AI contextual analysis", security: "Security scan" };
const statusLabel = { accepted: "Correction accepted", edited: "Edited correction applied", rejected: "Suggestion rejected — original kept", stale: "Superseded by a newer audit or edit", open: "" };

export function FindingCard({ f, role, active, editable, onFocus, onEvidence, onAccept, onReject }: Props) {
  const [mode, setMode] = useState<"idle" | "edit" | "reject">("idle");
  const [draft, setDraft] = useState(f.suggestion ?? f.passage);
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  const meta = evidenceMeta[f.evidence_status];
  const closed = f.status !== "open";
  const canAct = !closed && editable && (role === "creator" || role === "admin");
  const canDismiss = !closed && (role === "creator" || role === "admin" || role === "reviewer");

  async function run(fn: () => Promise<void>) {
    setBusy(true);
    try { await fn(); setMode("idle"); } finally { setBusy(false); }
  }

  return (
    <article id={`finding-${f.id}`} onClick={onFocus}
      className={`panel cursor-default p-4 transition-shadow ${active ? "ring-2 ring-proof/60" : ""} ${closed ? "opacity-70" : ""}`}>
      <div className="flex items-start gap-3">
        <div className="pt-1"><SeverityBar severity={f.severity} /></div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
            <SeverityBadge severity={f.severity} />
            <EvidenceChip status={f.evidence_status} />
            <span className="text-xs capitalize text-graphite-mute">{f.category.replace("_", " ")}</span>
          </div>
          <h3 className="mt-1.5 font-semibold leading-snug">{f.title}</h3>
          <p className="mt-1 text-sm text-graphite">{f.explanation}</p>

          {f.evidence.length > 0 ? (
            <div className="mt-3 space-y-1.5">
              {f.evidence.map((e) => (
                <button key={e.id + e.role} onClick={(ev) => { ev.stopPropagation(); onEvidence(e.id); }}
                  className="group flex w-full items-start gap-2 rounded-md border border-paper-edge bg-paper/50 px-3 py-2 text-left text-sm hover:border-proof/40 hover:bg-proof-tint/40">
                  <FileText className="mt-0.5 h-4 w-4 shrink-0 text-graphite-mute group-hover:text-proof" aria-hidden />
                  <span className="min-w-0">
                    <span className="block font-medium text-ink">
                      {e.role === "superseded" ? "Superseded: " : e.role === "current" ? "Current: " : ""}{citation(e)}
                    </span>
                    <span className="line-clamp-2 text-graphite-mute">{e.excerpt}</span>
                  </span>
                </button>
              ))}
            </div>
          ) : f.evidence_status !== "security" ? (
            <p className="mt-3 rounded-md bg-violet-50 px-3 py-2 text-sm text-ev-gap">Unable to verify against approved knowledge.</p>
          ) : null}

          {f.suggestion !== null && !closed && (
            <div className="mt-3 overflow-hidden rounded-md border border-paper-edge text-sm">
              <div className="grid sm:grid-cols-2">
                <div className="border-b border-paper-edge p-3 sm:border-b-0 sm:border-r">
                  <div className="mb-1 text-xs text-graphite-mute">Original</div>
                  <div className="font-serif text-[16px] text-ink"><span className="bg-red-50 line-through decoration-red-300">{f.passage}</span></div>
                </div>
                <div className="p-3">
                  <div className="mb-1 text-xs text-graphite-mute">Suggested</div>
                  <div className="font-serif text-[16px] text-ink">
                    {f.suggestion === "" ? <em className="text-graphite-mute">Remove this text</em> : <span className="bg-emerald-50">{f.suggestion}</span>}
                  </div>
                </div>
              </div>
              {f.suggestion_reason && <div className="border-t border-paper-edge bg-paper/60 px-3 py-2 text-graphite">{f.suggestion_reason}</div>}
            </div>
          )}
          {f.suggestion === null && !closed && f.suggestion_reason && (
            <p className="mt-3 text-sm text-graphite"><span className="font-medium">How to fix: </span>{f.suggestion_reason}</p>
          )}

          {mode === "edit" && (
            <div className="mt-3 space-y-2" onClick={(e) => e.stopPropagation()}>
              <label className="label" htmlFor={`edit-${f.id}`}>Your replacement for “{f.passage.slice(0, 60)}”</label>
              <textarea id={`edit-${f.id}`} className="field font-serif text-[16px]" rows={2} value={draft} onChange={(e) => setDraft(e.target.value)} />
              <div className="flex gap-2">
                <button className="btn-primary" disabled={busy} onClick={() => run(() => onAccept(draft))}>Apply my edit</button>
                <button className="btn-ghost" onClick={() => setMode("idle")}>Cancel</button>
              </div>
            </div>
          )}
          {mode === "reject" && (
            <div className="mt-3 space-y-2" onClick={(e) => e.stopPropagation()}>
              <label className="label" htmlFor={`rej-${f.id}`}>Why doesn’t this apply? (optional, shared with the reviewer)</label>
              <input id={`rej-${f.id}`} className="field" value={reason} onChange={(e) => setReason(e.target.value)} maxLength={500}
                placeholder="e.g. This figure was approved by legal on 3 Nov" />
              <div className="flex gap-2">
                <button className="btn-danger" disabled={busy} onClick={() => run(() => onReject(reason))}>Reject suggestion</button>
                <button className="btn-ghost" onClick={() => setMode("idle")}>Cancel</button>
              </div>
            </div>
          )}

          {mode === "idle" && !closed && (canAct || canDismiss) && (
            <div className="mt-3 flex flex-wrap gap-2" onClick={(e) => e.stopPropagation()}>
              {canAct && f.suggestion !== null && (
                <button className="btn-primary py-1.5" disabled={busy} onClick={() => run(() => onAccept())}>
                  <Check className="h-4 w-4" aria-hidden /> Accept
                </button>
              )}
              {canAct && (
                <button className="btn-quiet py-1.5" onClick={() => { setDraft(f.suggestion || f.passage); setMode("edit"); }}>
                  <Pencil className="h-4 w-4" aria-hidden /> Edit
                </button>
              )}
              {canDismiss && (
                <button className="btn-ghost py-1.5" onClick={() => setMode("reject")}>
                  <X className="h-4 w-4" aria-hidden /> Reject
                </button>
              )}
            </div>
          )}
          {!closed && !editable && (role === "creator" || role === "admin") && (
            <p className="mt-3 text-xs text-graphite-mute">Corrections are locked while a reviewer has this content.</p>
          )}
          {closed && <p className="mt-3 text-sm font-medium text-graphite">{statusLabel[f.status]}</p>}

          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 border-t border-paper-edge pt-2.5 text-xs text-graphite-mute">
            <span className="inline-flex items-center gap-1">
              {f.origin === "ai" ? <Bot className="h-3.5 w-3.5" aria-hidden /> : f.origin === "security" ? <ShieldAlert className="h-3.5 w-3.5" aria-hidden /> : null}
              {originLabel[f.origin]}
            </span>
            <span>Confidence: {f.confidence}</span>
            <span title={meta.help}>{meta.label}</span>
            <span className="ml-auto">{f.rule_id}</span>
          </div>
        </div>
      </div>
    </article>
  );
}
