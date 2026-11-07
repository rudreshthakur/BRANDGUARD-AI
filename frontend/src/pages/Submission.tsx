import { ArrowLeft, CheckCircle2, Loader2, MessageSquare, PenLine, RefreshCw, Send } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { EvidenceDrawer } from "../components/EvidenceDrawer";
import { FindingCard } from "../components/FindingCard";
import { Empty, ErrorNote, Spinner, StatusChip, useToast } from "../components/ui";
import { api } from "../lib/api";
import { channelLabel, citation, evidenceMeta, roleLabel, SEVERITY_ORDER, severityLabel, timeAgo } from "../lib/format";
import { segment, type Mark } from "../lib/segments";
import { useSession } from "../lib/session";
import { useApi } from "../lib/useApi";
import type { AuditEvent, Finding, Severity, SubmissionDetail } from "../lib/types";

type Filter = { severity: Severity | "all"; kind: string; status: "open" | "all" };

function Manuscript({ d, active, onMark }: { d: SubmissionDetail; active: string | null; onMark: (id: string) => void }) {
  const text = d.versions[d.versions.length - 1].text;
  const open = d.findings.filter((f) => f.status === "open" && f.version_no === d.current_version && text.slice(f.start, f.end) === f.passage);
  const marks: Mark[] = [
    ...open.map((f) => ({ id: f.id, start: f.start, end: f.end, kind: evidenceMeta[f.evidence_status].mark })),
    ...(d.audit_current ? (d.latest_audit?.verified_claims ?? []).map((v, i) => ({ id: `ok-${i}`, start: v.start, end: v.end, kind: "mark-ok" })) : []),
  ];
  const segs = segment(text, marks);
  return (
    <p className="manuscript whitespace-pre-wrap">
      {segs.map((s, i) =>
        s.mark ? (
          <span key={i} role={s.mark.id.startsWith("ok-") ? undefined : "button"} tabIndex={s.mark.id.startsWith("ok-") ? -1 : 0}
            title={s.mark.id.startsWith("ok-") ? "Verified against an approved fact" : "Show finding"}
            onClick={() => !s.mark!.id.startsWith("ok-") && onMark(s.mark!.id)}
            onKeyDown={(e) => { if ((e.key === "Enter" || e.key === " ") && !s.mark!.id.startsWith("ok-")) { e.preventDefault(); onMark(s.mark!.id); } }}
            className={`mark ${s.mark.kind} ${active === s.mark.id ? "mark-active" : ""}`}>{s.text}</span>
        ) : (<span key={i}>{s.text}</span>),
      )}
    </p>
  );
}

function Legend() {
  const items: [string, string][] = [["mark-rule", "Rule violation"], ["mark-conflict", "Conflicts with fact"], ["mark-outdated", "Outdated"],
    ["mark-gap", "Unverified claim"], ["mark-ok", "Verified"], ["mark-ctx", "AI observation"]];
  return (
    <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-graphite-mute" aria-label="Legend">
      {items.map(([c, l]) => <span key={c}><span className={`mark ${c} font-serif text-[13px] text-ink`}>abc</span> {l}</span>)}
    </div>
  );
}

function VersionDiff({ d }: { d: SubmissionDetail }) {
  const n = d.versions.length;
  const [from, setFrom] = useState(Math.max(1, n - 1));
  const [to, setTo] = useState(n);
  const [ops, setOps] = useState<{ op: string; text: string }[] | null>(null);
  useEffect(() => { setFrom(Math.max(1, n - 1)); setTo(n); }, [n]);
  useEffect(() => {
    if (from === to) { setOps(null); return; }
    api<{ ops: { op: string; text: string }[] }>(`/submissions/${d.id}/diff?frm=${from}&to=${to}`).then((r) => setOps(r.ops)).catch(() => setOps(null));
  }, [d.id, from, to]);
  return (
    <div className="grid gap-6 lg:grid-cols-[18rem_1fr]">
      <ol className="space-y-2">
        {[...d.versions].reverse().map((v) => (
          <li key={v.version_no} className="rounded-md border border-paper-edge bg-white px-3 py-2 text-sm">
            <div className="flex justify-between"><span className="font-medium">Version {v.version_no}</span><span className="text-xs text-graphite-mute">{timeAgo(v.created_at)}</span></div>
            <div className="text-graphite-mute">{v.change_note}</div>
            <div className="text-xs text-graphite-faint">by {roleLabel[v.created_by as "creator"] ?? v.created_by}</div>
          </li>
        ))}
      </ol>
      <div>
        {n < 2 ? <Empty title="Only the original version exists">Accepting a correction or saving an edit creates version 2. The original stays here unchanged.</Empty> : (
          <>
            <div className="mb-3 flex flex-wrap items-center gap-2 text-sm">
              <label htmlFor="vfrom">Compare</label>
              <select id="vfrom" className="field w-auto" value={from} onChange={(e) => setFrom(+e.target.value)}>
                {d.versions.map((v) => <option key={v.version_no} value={v.version_no}>v{v.version_no}</option>)}
              </select>
              <label htmlFor="vto">with</label>
              <select id="vto" className="field w-auto" value={to} onChange={(e) => setTo(+e.target.value)}>
                {d.versions.map((v) => <option key={v.version_no} value={v.version_no}>v{v.version_no}</option>)}
              </select>
            </div>
            <div className="panel p-5 font-serif text-[17px] leading-8">
              {ops ? ops.map((o, i) => o.op === "equal" ? <span key={i}>{o.text}</span>
                : o.op === "delete" ? <del key={i} className="bg-red-50 text-sev-critical decoration-red-300">{o.text}</del>
                : <ins key={i} className="bg-emerald-50 text-ev-ok no-underline">{o.text}</ins>)
                : <span className="text-graphite-mute">Choose two different versions.</span>}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Discussion({ d, onPost }: { d: SubmissionDetail; onPost: (body: string) => Promise<void> }) {
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const items = [
    ...d.comments.map((c) => ({ t: c.created_at, k: `c${c.id}`, el: (
      <div className="text-sm"><span className="font-medium">{roleLabel[c.author_role]}</span> <span className="text-graphite-mute">on v{c.version_no}, {timeAgo(c.created_at)}</span><p className="mt-0.5 text-graphite">{c.body}</p></div>) })),
    ...d.decisions.map((x) => ({ t: x.created_at, k: `d${x.id}`, el: (
      <div className="text-sm"><span className="font-medium">{roleLabel[x.actor_role]}</span> {x.decision.replace("_", " ")} v{x.version_no}
        <span className="text-graphite-mute"> ({x.from_status.replace("_", " ")} to {x.to_status.replace("_", " ")}, {x.open_findings_at_decision} open finding{x.open_findings_at_decision === 1 ? "" : "s"}), {timeAgo(x.created_at)}</span></div>) })),
  ].sort((a, b) => a.t.localeCompare(b.t));
  return (
    <div className="max-w-2xl">
      {items.length === 0 ? <p className="text-sm text-graphite-mute">No comments or decisions yet.</p> : (
        <ol className="space-y-3 border-l border-paper-rule pl-4">{items.map((i) => <li key={i.k}>{i.el}</li>)}</ol>
      )}
      <form className="mt-5 flex gap-2" onSubmit={async (e) => { e.preventDefault(); if (!body.trim()) return; setBusy(true); try { await onPost(body); setBody(""); } finally { setBusy(false); } }}>
        <label htmlFor="cmt" className="sr-only">Add a comment</label>
        <input id="cmt" className="field" placeholder="Add a comment for the team" value={body} onChange={(e) => setBody(e.target.value)} maxLength={2000} />
        <button className="btn-quiet shrink-0" disabled={busy || !body.trim()}><MessageSquare className="h-4 w-4" aria-hidden /> Comment</button>
      </form>
    </div>
  );
}

export default function SubmissionPage() {
  const { id } = useParams();
  const { session } = useSession();
  const toast = useToast();
  const role = session!.role;
  const { data: d, setData, error, loading, reload } = useApi<SubmissionDetail>(`/submissions/${id}`);
  const events = useApi<{ events: AuditEvent[] }>(`/events?submission_id=${id}&limit=100`);
  const [active, setActive] = useState<string | null>(null);
  const [evidence, setEvidence] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>({ severity: "all", kind: "all", status: "open" });
  const [tab, setTab] = useState<"versions" | "discussion" | "activity">("versions");
  const [busy, setBusy] = useState<string | null>(null);
  const [note, setNote] = useState("");
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState("");

  async function act(label: string, fn: () => Promise<SubmissionDetail>, okMsg: string) {
    setBusy(label);
    try { const r = await fn(); setData(r); toast(okMsg); void events.reload(); return true; }
    catch (e) { toast((e as Error).message, "error"); return false; }
    finally { setBusy(null); }
  }

  const findings = useMemo(() => (d?.findings ?? []).filter((f) =>
    (filter.status === "all" || f.status === "open") &&
    (filter.severity === "all" || f.severity === filter.severity) &&
    (filter.kind === "all" || f.evidence_status === filter.kind || f.category === filter.kind)), [d, filter]);

  if (loading && !d) return <Spinner label="Loading submission" />;
  if (error && !d) return <ErrorNote message={error} onRetry={reload} />;
  if (!d) return null;

  const run = d.latest_audit;
  const editable = !["under_review", "revised"].includes(d.status);
  const openFindings = d.findings.filter((f) => f.status === "open");
  const blocking = openFindings.filter((f) => f.severity === "critical" || f.severity === "high").length;
  const verified = d.audit_current ? run?.verified_claims ?? [] : [];
  const kinds = Array.from(new Set(d.findings.map((f) => f.evidence_status)));
  const focus = (fid: string) => { setActive(fid); document.getElementById(`finding-${fid}`)?.scrollIntoView({ behavior: "smooth", block: "center" }); };

  const transition = (action: "submit" | "request_changes" | "approve", msg: string) =>
    act(action, () => api<SubmissionDetail>(`/submissions/${d.id}/transition`, { method: "POST", json: { action, note } }), msg).then((ok) => ok && setNote(""));

  return (
    <div>
      <Link to="/app/review" className="mb-3 inline-flex items-center gap-1 text-sm text-graphite-mute hover:text-ink"><ArrowLeft className="h-4 w-4" aria-hidden /> All content</Link>
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold">{d.title}</h1>
            <StatusChip status={d.status} />
            {d.is_sample && <span className="chip bg-slate-100 text-graphite ring-slate-300">Synthetic sample</span>}
          </div>
          <p className="mt-1 text-sm text-graphite-mute">
            {channelLabel[d.channel] ?? d.channel}, version {d.current_version}
            {run && `, audited ${timeAgo(run.created_at)} against v${run.version_no}`}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          {(role === "creator" || role === "admin") && editable && (
            <button className="btn-quiet" onClick={() => { setDraft(d.versions[d.versions.length - 1].text); setEditing((v) => !v); }}>
              <PenLine className="h-4 w-4" aria-hidden /> {editing ? "Close editor" : "Edit text"}
            </button>
          )}
          <button className="btn-ink" disabled={busy !== null} onClick={() => act("audit", () => api(`/submissions/${d.id}/audit`, { method: "POST" }), "Brand audit complete")}>
            {busy === "audit" ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <RefreshCw className="h-4 w-4" aria-hidden />}
            {run ? "Re-run brand audit" : "Run brand audit"}
          </button>
        </div>
      </div>

      {!d.audit_current && run && (
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-ev-outdated">
          <span>Version {d.current_version} has changes the last audit (v{run.version_no}) hasn’t checked. Re-run the audit to confirm your fixes before submitting.</span>
        </div>
      )}

      {/* decision bar */}
      <section className="panel mb-6 p-4" aria-label="Review decision">
        <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
          <div className="min-w-0 flex-1">
            {d.status === "approved" ? (
              <p className="flex items-center gap-2 font-medium text-ev-ok"><CheckCircle2 className="h-5 w-5" aria-hidden /> Approved for publication by a reviewer. Editing it again returns it to draft.</p>
            ) : role === "reviewer" ? (
              ["under_review", "revised"].includes(d.status)
                ? <p className="text-sm text-graphite">Your decision. {blocking > 0 ? `${blocking} high or critical finding${blocking === 1 ? " is" : "s are"} still open, so approving requires a written justification.` : "No high or critical findings are open."}</p>
                : <p className="text-sm text-graphite-mute">This content is {d.status.replace("_", " ")}. Reviewers act once the creator submits it.</p>
            ) : (
              ["draft", "changes_requested"].includes(d.status)
                ? <p className="text-sm text-graphite">{d.status === "changes_requested" ? "The reviewer asked for changes. Fix the findings, re-run the audit, then resubmit." : "Fix what you agree with, re-run the audit, then submit for review."} {openFindings.length > 0 && `${openFindings.length} finding${openFindings.length === 1 ? "" : "s"} open.`}</p>
                : <p className="text-sm text-graphite-mute">Waiting for a reviewer decision. Switch to the Reviewer role at the top to make it.</p>
            )}
          </div>
          {((role === "reviewer" && ["under_review", "revised"].includes(d.status)) || ((role === "creator" || role === "admin") && ["draft", "changes_requested"].includes(d.status))) && (
            <div className="flex w-full flex-wrap items-center gap-2 lg:w-auto">
              <label htmlFor="note" className="sr-only">Decision note</label>
              <input id="note" className="field lg:w-80" value={note} onChange={(e) => setNote(e.target.value)} maxLength={2000}
                placeholder={role === "reviewer" ? "Note for the creator (required to request changes)" : "Note for the reviewer (optional)"} />
              {role === "reviewer" ? (
                <>
                  <button className="btn-quiet" disabled={busy !== null} onClick={() => transition("request_changes", "Changes requested")}>Request changes</button>
                  <button className="btn-primary" disabled={busy !== null} onClick={() => transition("approve", "Approved")}><CheckCircle2 className="h-4 w-4" aria-hidden /> Approve</button>
                </>
              ) : (
                <button className="btn-primary" disabled={busy !== null} onClick={() => transition("submit", d.status === "changes_requested" ? "Resubmitted for review" : "Submitted for review")}>
                  <Send className="h-4 w-4" aria-hidden /> {d.status === "changes_requested" ? "Resubmit for review" : "Submit for review"}
                </button>
              )}
            </div>
          )}
        </div>
      </section>

      <div className="grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <section aria-label="Content" className="space-y-4">
          <div className="panel">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-paper-edge px-5 py-3">
              <h2 className="text-sm font-semibold">Content, version {d.current_version}</h2>
              {run && (
                <div className="flex flex-wrap gap-3 text-xs">
                  {SEVERITY_ORDER.map((s) => run.stats.by_severity?.[s] ? <span key={s} className="text-graphite">{run.stats.by_severity[s]} {severityLabel[s].toLowerCase()}</span> : null)}
                  <span className="text-ev-ok">{run.stats.verified_claims} verified</span>
                </div>
              )}
            </div>
            <div className="px-6 py-6">
              {editing ? (
                <div className="space-y-3">
                  <label htmlFor="draft" className="label">Edit content. Saving creates a new version; earlier versions stay unchanged.</label>
                  <textarea id="draft" className="field manuscript min-h-[200px]" value={draft} onChange={(e) => setDraft(e.target.value)} />
                  <div className="flex gap-2">
                    <button className="btn-primary" disabled={busy !== null} onClick={() => act("save", () => api(`/submissions/${d.id}/content`, { method: "PUT", json: { text: draft, note: "Manual edit" } }), "Saved as a new version").then((ok) => ok && setEditing(false))}>Save as new version</button>
                    <button className="btn-ghost" onClick={() => setEditing(false)}>Cancel</button>
                  </div>
                </div>
              ) : <Manuscript d={d} active={active} onMark={focus} />}
            </div>
            <div className="border-t border-paper-edge px-5 py-3"><Legend /></div>
          </div>

          {verified.length > 0 && (
            <div className="panel p-5">
              <h2 className="text-sm font-semibold">Verified against approved facts</h2>
              <p className="text-xs text-graphite-mute">These claims match current approved knowledge, so they were not flagged.</p>
              <ul className="mt-3 space-y-2">
                {verified.map((v, i) => (
                  <li key={i} className="flex flex-wrap items-baseline gap-2 text-sm">
                    <CheckCircle2 className="h-4 w-4 shrink-0 translate-y-0.5 text-ev-ok" aria-hidden />
                    <span className="font-serif text-[16px]">“{v.passage}”</span>
                    {v.evidence.map((e) => (
                      <button key={e.id} className="text-proof underline-offset-2 hover:underline" onClick={() => setEvidence(e.id)}>{citation(e)}</button>
                    ))}
                  </li>
                ))}
              </ul>
            </div>
          )}

          {run && (
            <div className="rounded-md border border-paper-edge bg-white/60 px-4 py-3 text-xs leading-5 text-graphite-mute">
              <div><span className="font-medium text-graphite">Checked against:</span> {(run.knowledge_snapshot.approved_sources ?? []).join(", ") || "no approved documents"}; {run.knowledge_snapshot.approved_facts ?? 0} approved facts.</div>
              <div><span className="font-medium text-graphite">AI analysis:</span> {run.ai_status}</div>
            </div>
          )}
        </section>

        <section aria-label="Findings">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="mr-auto text-lg font-semibold">Findings <span className="text-graphite-mute">({findings.length})</span></h2>
            <label className="sr-only" htmlFor="fsev">Severity</label>
            <select id="fsev" className="field w-auto py-1.5" value={filter.severity} onChange={(e) => setFilter({ ...filter, severity: e.target.value as Filter["severity"] })}>
              <option value="all">All severities</option>{SEVERITY_ORDER.map((s) => <option key={s} value={s}>{severityLabel[s]}</option>)}
            </select>
            <label className="sr-only" htmlFor="fkind">Type</label>
            <select id="fkind" className="field w-auto py-1.5" value={filter.kind} onChange={(e) => setFilter({ ...filter, kind: e.target.value })}>
              <option value="all">All types</option>{kinds.map((k) => <option key={k} value={k}>{evidenceMeta[k].short}</option>)}
            </select>
            <label className="sr-only" htmlFor="fst">Status</label>
            <select id="fst" className="field w-auto py-1.5" value={filter.status} onChange={(e) => setFilter({ ...filter, status: e.target.value as Filter["status"] })}>
              <option value="open">Open</option><option value="all">All, including resolved</option>
            </select>
          </div>
          {!run ? <Empty title="Not audited yet">Run a brand audit to check this content against approved knowledge.</Empty>
            : findings.length === 0 ? (
              <Empty title={openFindings.length === 0 && filter.status === "open" ? "No open findings" : "Nothing matches these filters"}>
                {openFindings.length === 0 && filter.status === "open"
                  ? (d.audit_current ? "The latest audit found no issues with approved rules or facts. A reviewer still makes the final decision." : "All findings are resolved. Re-run the audit to confirm.")
                  : "Try widening the filters."}
              </Empty>
            ) : (
              <div className="space-y-3">
                {findings.map((f: Finding) => (
                  <FindingCard key={f.id} f={f} role={role} active={active === f.id} editable={editable} onFocus={() => setActive(f.id)} onEvidence={setEvidence}
                    onAccept={async (edited) => { await act("accept", () => api(`/submissions/${d.id}/findings/${f.id}/accept`, { method: "POST", json: { edited_text: edited ?? null } }), edited !== undefined ? "Your edit was applied as a new version" : "Correction accepted as a new version"); }}
                    onReject={async (reason) => { await act("reject", () => api(`/submissions/${d.id}/findings/${f.id}/reject`, { method: "POST", json: { reason } }), "Suggestion rejected. Original text kept"); }} />
                ))}
              </div>
            )}
        </section>
      </div>

      <section className="mt-10">
        <div className="mb-4 flex gap-6 border-b border-paper-edge" role="tablist">
          {([["versions", `Versions (${d.versions.length})`], ["discussion", `Discussion (${d.comments.length + d.decisions.length})`], ["activity", "Activity"]] as const).map(([k, l]) => (
            <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? "tab-active" : ""}`} onClick={() => setTab(k)}>{l}</button>
          ))}
        </div>
        {tab === "versions" && <VersionDiff d={d} />}
        {tab === "discussion" && <Discussion d={d} onPost={async (body) => { await act("comment", () => api(`/submissions/${d.id}/comments`, { method: "POST", json: { body } }), "Comment added"); }} />}
        {tab === "activity" && (
          <ol className="max-w-3xl space-y-2 text-sm">
            {(events.data?.events ?? []).map((e) => (
              <li key={e.id} className="flex gap-3"><span className="w-24 shrink-0 text-graphite-mute">{timeAgo(e.created_at)}</span><span className="w-20 shrink-0 font-medium">{roleLabel[e.actor_role]}</span><span className="text-graphite">{e.summary}</span></li>
            ))}
          </ol>
        )}
      </section>

      <EvidenceDrawer evidenceId={evidence} onClose={() => setEvidence(null)} />
    </div>
  );
}
