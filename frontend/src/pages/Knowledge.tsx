import { AlertTriangle, Download, Loader2, Upload } from "lucide-react";
import { useEffect, useState } from "react";
import { Empty, ErrorNote, PageHeader, SeverityBadge, Spinner, useToast } from "../components/ui";
import { api, fileUrl } from "../lib/api";
import { channelLabel, timeAgo } from "../lib/format";
import { useSession } from "../lib/session";
import { useApi } from "../lib/useApi";
import type { Fact, PaletteColour, Source, Term, WorkspaceSummary } from "../lib/types";

const srcStatus: Record<Source["status"], string> = {
  approved: "bg-emerald-50 text-ev-ok ring-emerald-200", pending_review: "bg-amber-50 text-ev-outdated ring-amber-200",
  superseded: "bg-slate-100 text-graphite ring-slate-300", rejected: "bg-red-50 text-sev-critical ring-red-200",
};
const srcLabel: Record<Source["status"], string> = { approved: "Approved", pending_review: "Pending review", superseded: "Superseded", rejected: "Rejected" };
const kindLabel: Record<string, string> = {
  prohibited: "Prohibited term", preferred: "Preferred term", brand_name: "Brand name", forbidden_claim: "Forbidden claim",
  required_phrase: "Required phrase", numeric_limit: "Numeric limit",
};

function AdminNote() {
  const { session, setRole } = useSession();
  if (session?.role === "admin") return null;
  return (
    <div className="mb-4 flex flex-wrap items-center justify-between gap-3 rounded-md border border-paper-edge bg-white px-4 py-2.5 text-sm text-graphite">
      <span>You’re viewing approved knowledge. Only the Admin role can change it.</span>
      <button className="btn-quiet py-1.5" onClick={() => setRole("admin")}>Switch to Admin</button>
    </div>
  );
}

function SourceReview({ id, onDone }: { id: string; onDone: () => void }) {
  const { session } = useSession();
  const toast = useToast();
  const { data: s, error, reload } = useApi<Source>(`/knowledge/sources/${id}`);
  const [accept, setAccept] = useState<number[]>([]);
  const [cmp, setCmp] = useState<{ changes: { section: string; change: string; old?: string; new?: string }[] } | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { setAccept([]); setCmp(null); }, [id]);
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (!s) return <Spinner />;
  const admin = session?.role === "admin";
  const prev = s.other_versions?.filter((o) => o.version < s.version).pop();

  async function decide(action: "approve" | "reject") {
    setBusy(true);
    try {
      await api(`/knowledge/sources/${s!.id}/${action}`, { method: "POST", json: action === "approve" ? { accept_proposals: accept } : undefined });
      toast(action === "approve" ? "Approved and indexed as evidence" : "Rejected. It won’t be used as evidence");
      onDone(); void reload();
    } catch (e) { toast((e as Error).message, "error"); } finally { setBusy(false); }
  }

  return (
    <div className="panel p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold">{s.title}</h3>
          <p className="text-sm text-graphite-mute">Version {s.version}, {s.filename}, {s.page_count ? `${s.page_count} pages, ` : ""}{s.chunk_count} extracted sections. Authority: {s.authority}{s.effective_date ? `, effective ${s.effective_date}` : ""}.</p>
        </div>
        <span className={`chip ${srcStatus[s.status]}`}>{srcLabel[s.status]}</span>
      </div>

      {s.injection_flags.length > 0 && (
        <div className="mt-4 flex gap-3 rounded-md border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-ev-outdated">
          <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" aria-hidden />
          <div><span className="font-medium">This document contains text that reads like instructions to an AI system.</span> It is stored as plain text and can’t change how BrandGuard behaves. Check it before approving.
            <ul className="mt-1 list-disc pl-5">{s.injection_flags.map((f, i) => <li key={i} className="font-serif">“{f.excerpt}”</li>)}</ul></div>
        </div>
      )}

      {s.status === "pending_review" && (s.proposed_rules?.length ?? 0) > 0 && (
        <div className="mt-5">
          <h4 className="text-sm font-semibold">Rules found in this document</h4>
          <p className="text-xs text-graphite-mute">Proposed by pattern matching, so nothing applies until an admin ticks it and approves.</p>
          <ul className="mt-2 space-y-1.5">
            {s.proposed_rules!.map((p, i) => (
              <li key={i} className="flex items-start gap-2 text-sm">
                <input id={`pr-${i}`} type="checkbox" className="mt-1" disabled={!admin} checked={accept.includes(i)}
                  onChange={(e) => setAccept((a) => e.target.checked ? [...a, i] : a.filter((x) => x !== i))} />
                <label htmlFor={`pr-${i}`}><span className="font-medium">{kindLabel[p.kind]}: “{p.term}”</span>
                  {p.variants.length > 0 && <> instead of “{p.variants.join("”, “")}”</>}{p.replacement && <>, use “{p.replacement}”</>}
                  <span className="block text-xs text-graphite-mute">Source text: “{p.excerpt}”{p.section ? `, ${p.section}` : ""}</span></label>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="mt-5">
        <h4 className="text-sm font-semibold">Extracted text</h4>
        <div className="mt-2 max-h-80 space-y-2 overflow-y-auto pr-1">
          {s.chunks?.map((c) => (
            <div key={c.id} className="rounded-md border border-paper-edge px-3 py-2 text-sm">
              <div className="text-xs text-graphite-mute">{[c.page ? `Page ${c.page}` : null, c.section, c.id].filter(Boolean).join(", ")}</div>
              <p className="text-graphite">{c.text}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="mt-5 flex flex-wrap gap-2">
        {s.status === "pending_review" && admin && (
          <>
            <button className="btn-primary" disabled={busy} onClick={() => decide("approve")}>
              {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden />} Approve as authoritative{accept.length ? ` with ${accept.length} rule${accept.length === 1 ? "" : "s"}` : ""}
            </button>
            <button className="btn-danger" disabled={busy} onClick={() => decide("reject")}>Reject</button>
          </>
        )}
        {prev && (
          <button className="btn-quiet" onClick={() => api<typeof cmp>(`/knowledge/sources/${s.id}/compare/${prev.id}`).then(setCmp)}>Compare with v{prev.version}</button>
        )}
      </div>
      {s.status === "pending_review" && prev && <p className="mt-2 text-xs text-graphite-mute">Approving makes this the authoritative version and marks v{prev.version} as superseded.</p>}
      {cmp && (
        <div className="mt-4 space-y-2">
          {cmp.changes.length === 0 ? <p className="text-sm text-graphite-mute">No text changes between versions.</p> : cmp.changes.map((c, i) => (
            <div key={i} className="rounded-md border border-paper-edge p-3 text-sm">
              <div className="font-medium">{c.section} <span className="font-normal text-graphite-mute">({c.change})</span></div>
              {c.old && <p className="mt-1 bg-red-50 px-2 py-1 text-graphite line-through decoration-red-300">{c.old}</p>}
              {c.new && <p className="mt-1 bg-emerald-50 px-2 py-1 text-graphite">{c.new}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function Documents() {
  const { session } = useSession();
  const toast = useToast();
  const { data, error, loading, reload } = useApi<{ sources: Source[] }>("/knowledge/sources");
  const files = useApi<{ files: { name: string; kind: string; description: string }[] }>("/api/samples/files");
  const [sel, setSel] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [meta, setMeta] = useState({ title: "", authority: "Brand team", effective_date: "", replaces: "" });
  const [busy, setBusy] = useState(false);

  async function upload(e: React.FormEvent) {
    e.preventDefault();
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file); fd.append("title", meta.title); fd.append("authority", meta.authority); fd.append("effective_date", meta.effective_date); fd.append("replaces_source_id", meta.replaces);
    setBusy(true);
    try {
      const s = await api<Source>("/knowledge/sources", { method: "POST", body: fd });
      toast("Uploaded. Review the extracted text before approving");
      setFile(null); setMeta({ title: "", authority: "Brand team", effective_date: "", replaces: "" });
      (document.getElementById("doc-file") as HTMLInputElement | null)?.form?.reset();
      await reload(); setSel(s.id);
    } catch (e2) { toast((e2 as Error).message, "error"); } finally { setBusy(false); }
  }

  return (
    <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
      <div className="space-y-5">
        {session?.role === "admin" && (
          <form onSubmit={upload} className="panel space-y-3 p-5">
            <h3 className="font-semibold">Upload a guideline or spec sheet</h3>
            <p className="text-sm text-graphite-mute">PDF, DOCX, TXT or MD up to 10 MB. Uploads stay pending until you approve them, so nothing becomes evidence automatically.</p>
            <input id="doc-file" type="file" accept=".pdf,.docx,.txt,.md" className="block w-full text-sm file:mr-3 file:rounded-md file:border-0 file:bg-ink file:px-3 file:py-2 file:text-sm file:text-white"
              onChange={(e) => setFile(e.target.files?.[0] ?? null)} aria-label="Document file" />
            <div className="grid gap-3 sm:grid-cols-3">
              <input className="field" placeholder="Title (optional)" value={meta.title} onChange={(e) => setMeta({ ...meta, title: e.target.value })} aria-label="Title" />
              <input className="field" placeholder="Authority" value={meta.authority} onChange={(e) => setMeta({ ...meta, authority: e.target.value })} aria-label="Authority" />
              <input className="field" type="date" value={meta.effective_date} onChange={(e) => setMeta({ ...meta, effective_date: e.target.value })} aria-label="Effective date" />
            </div>
            <div>
              <label className="label" htmlFor="replaces">This document is</label>
              <select id="replaces" className="field" value={meta.replaces} onChange={(e) => setMeta({ ...meta, replaces: e.target.value })}>
                <option value="">A new document</option>
                {(data?.sources ?? []).filter((s) => s.status === "approved").map((s) => <option key={s.id} value={s.id}>A new version of {s.title}</option>)}
              </select>
              {meta.replaces && <p className="mt-1 text-xs text-graphite-mute">Once approved, it supersedes the current version, which stays available for comparison.</p>}
            </div>
            <button className="btn-primary" disabled={!file || busy}>{busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <Upload className="h-4 w-4" aria-hidden />} Upload and extract</button>
          </form>
        )}
        {loading && !data ? <Spinner /> : error ? <ErrorNote message={error} onRetry={reload} /> : (
          <ul className="panel divide-y divide-paper-edge">
            {data!.sources.length === 0 && <li className="p-5"><Empty title="No documents yet">Upload your brand guidelines to start building approved knowledge.</Empty></li>}
            {data!.sources.map((s) => (
              <li key={s.id}>
                <button onClick={() => setSel(s.id)} className={`flex w-full items-center justify-between gap-3 px-4 py-3 text-left hover:bg-paper/60 ${sel === s.id ? "bg-proof-tint/40" : ""}`}>
                  <span className="min-w-0">
                    <span className="block truncate font-medium">{s.title}</span>
                    <span className="text-xs text-graphite-mute">v{s.version}, {s.chunk_count} sections{s.effective_date ? `, effective ${s.effective_date}` : ""}, added {timeAgo(s.created_at)}</span>
                  </span>
                  <span className="flex shrink-0 items-center gap-2">
                    {s.injection_flags.length > 0 && <AlertTriangle className="h-4 w-4 text-ev-outdated" aria-label="Contains flagged text" />}
                    <span className={`chip ${srcStatus[s.status]}`}>{srcLabel[s.status]}</span>
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="text-sm">
          <h3 className="font-semibold">Sample files to try</h3>
          <p className="text-graphite-mute">Synthetic files for testing ingestion. The v4 draft changes a rule and contains a hidden instruction.</p>
          <ul className="mt-2 space-y-1">
            {(files.data?.files ?? []).filter((f) => f.kind === "knowledge").map((f) => (
              <li key={f.name}><a className="inline-flex items-center gap-1.5 text-proof hover:underline" href={fileUrl(f.name)} download><Download className="h-3.5 w-3.5" aria-hidden />{f.name}</a></li>
            ))}
          </ul>
        </div>
      </div>
      <div>{sel ? <SourceReview id={sel} onDone={reload} /> : <Empty title="Select a document">Pick a document to inspect its extracted sections, flagged text and version history.</Empty>}</div>
    </div>
  );
}

const emptyFact = { statement: "", subject: "", value: "", unit: "", keywords: "", effective_date: "" };

function Facts() {
  const { session } = useSession();
  const toast = useToast();
  const { data, error, loading, reload } = useApi<{ facts: Fact[] }>("/knowledge/facts");
  const [form, setForm] = useState(emptyFact);
  const [superseding, setSuperseding] = useState<Fact | null>(null);
  const [open, setOpen] = useState(false);
  const admin = session?.role === "admin";

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const body = { statement: form.statement, subject: form.subject, value: form.value === "" ? null : Number(form.value), unit: form.unit || null,
      keywords: form.keywords.split(",").map((k) => k.trim()).filter(Boolean), effective_date: form.effective_date || null };
    try {
      await api(superseding ? `/knowledge/facts/${superseding.id}/supersede` : "/knowledge/facts", { method: "POST", json: body });
      toast(superseding ? "New version approved. Previous fact marked superseded" : "Fact approved");
      setForm(emptyFact); setSuperseding(null); setOpen(false); void reload();
    } catch (e2) { toast((e2 as Error).message, "error"); }
  }

  function supersede(f: Fact) {
    setSuperseding(f); setOpen(true);
    setForm({ statement: f.statement, subject: f.subject, value: f.value?.toString() ?? "", unit: f.unit ?? "", keywords: f.keywords.join(", "), effective_date: new Date().toISOString().slice(0, 10) });
  }

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  const facts = data!.facts;
  return (
    <div className="space-y-5">
      {admin && !open && <button className="btn-primary" onClick={() => { setSuperseding(null); setForm(emptyFact); setOpen(true); }}>Add approved fact</button>}
      {admin && open && (
        <form onSubmit={save} className="panel space-y-3 p-5">
          <h3 className="font-semibold">{superseding ? `New version of ${superseding.id}` : "Add an approved fact"}</h3>
          {superseding && <p className="text-sm text-graphite-mute">The current fact becomes superseded and stays in history. Content that repeats the old value will be flagged as outdated.</p>}
          <textarea className="field" rows={2} placeholder="Statement, e.g. Northstar Beacon battery life is up to 12 hours." value={form.statement} onChange={(e) => setForm({ ...form, statement: e.target.value })} aria-label="Statement" required />
          <div className="grid gap-3 sm:grid-cols-4">
            <input className="field" placeholder="Subject (product)" value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} aria-label="Subject" />
            <input className="field" type="number" step="any" placeholder="Value (optional)" value={form.value} onChange={(e) => setForm({ ...form, value: e.target.value })} aria-label="Value" />
            <input className="field" placeholder="Unit: %, hours, apps, $" value={form.unit} onChange={(e) => setForm({ ...form, unit: e.target.value })} aria-label="Unit" />
            <input className="field" type="date" value={form.effective_date} onChange={(e) => setForm({ ...form, effective_date: e.target.value })} aria-label="Effective date" />
          </div>
          <input className="field" placeholder="Matching keywords, comma separated (e.g. battery, battery life, charge)" value={form.keywords} onChange={(e) => setForm({ ...form, keywords: e.target.value })} aria-label="Keywords" />
          <p className="text-xs text-graphite-mute">Quantified facts need a value, a unit and keywords. Claims are matched by unit and nearby keywords, then compared by value.</p>
          <div className="flex gap-2"><button className="btn-primary">{superseding ? "Approve new version" : "Approve fact"}</button><button type="button" className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button></div>
        </form>
      )}
      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-paper-edge text-graphite-mute"><tr>
            <th className="px-4 py-2.5 font-medium">Fact</th><th className="px-4 py-2.5 font-medium">Value</th><th className="px-4 py-2.5 font-medium">Source</th><th className="px-4 py-2.5 font-medium">Status</th>{admin && <th className="px-4 py-2.5" />}
          </tr></thead>
          <tbody>
            {facts.map((f) => (
              <tr key={f.id} className={`border-b border-paper-edge last:border-0 ${f.status !== "approved" ? "text-graphite-mute" : ""}`}>
                <td className="max-w-md px-4 py-3"><div className="font-serif text-[15px]">{f.statement}</div><div className="text-xs text-graphite-faint">{f.id}{f.keywords.length ? `, matches: ${f.keywords.join(", ")}` : ""}</div></td>
                <td className="whitespace-nowrap px-4 py-3">{f.value !== null ? `${f.value} ${f.unit}` : "Qualitative"}</td>
                <td className="px-4 py-3 text-graphite">{f.source ? `${f.source.title}${f.page ? `, p. ${f.page}` : ""}` : "Entered by admin"}</td>
                <td className="px-4 py-3">
                  <span className={`chip ${f.status === "approved" ? "bg-emerald-50 text-ev-ok ring-emerald-200" : "bg-slate-100 text-graphite ring-slate-300"}`}>{f.status === "approved" ? "Approved" : f.status === "superseded" ? "Superseded" : "Draft"}</span>
                  {f.effective_date && <div className="mt-0.5 text-xs text-graphite-faint">from {f.effective_date}</div>}
                </td>
                {admin && <td className="px-4 py-3 text-right">{f.status === "approved" && <button className="text-sm text-proof hover:underline" onClick={() => supersede(f)}>New version</button>}</td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

const emptyRule = { kind: "prohibited", term: "", replacement: "", variants: "", severity: "medium", explanation: "", channels: "", limit_value: "", trigger: "" };

function Rules() {
  const { session } = useSession();
  const toast = useToast();
  const { data, error, loading, reload } = useApi<{ terms: Term[] }>("/knowledge/terms");
  const [form, setForm] = useState(emptyRule);
  const [open, setOpen] = useState(false);
  const admin = session?.role === "admin";

  async function save(e: React.FormEvent) {
    e.preventDefault();
    const body = {
      kind: form.kind, term: form.term, replacement: form.replacement || null,
      variants: form.variants.split(",").map((v) => v.trim()).filter(Boolean), severity: form.severity, explanation: form.explanation,
      channels: form.channels ? [form.channels] : null, limit_value: form.limit_value === "" ? null : Number(form.limit_value), trigger: form.trigger || null,
      category: form.kind === "forbidden_claim" || form.kind === "numeric_limit" ? "compliance" : form.channels ? "channel" : "terminology",
    };
    try { await api("/knowledge/terms", { method: "POST", json: body }); toast("Rule added and active"); setForm(emptyRule); setOpen(false); void reload(); }
    catch (e2) { toast((e2 as Error).message, "error"); }
  }
  async function toggle(t: Term) {
    try { await api(`/knowledge/terms/${t.id}`, { method: "PATCH", json: { status: t.status === "approved" ? "disabled" : "approved" } }); void reload(); }
    catch (e) { toast((e as Error).message, "error"); }
  }

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  return (
    <div className="space-y-5">
      {admin && !open && <button className="btn-primary" onClick={() => setOpen(true)}>Add rule</button>}
      {admin && open && (
        <form onSubmit={save} className="panel space-y-3 p-5">
          <h3 className="font-semibold">Add a governance rule</h3>
          <div className="grid gap-3 sm:grid-cols-3">
            <select className="field" value={form.kind} onChange={(e) => setForm({ ...form, kind: e.target.value })} aria-label="Rule type">
              {Object.entries(kindLabel).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
            </select>
            <input className="field" required placeholder={form.kind === "preferred" ? "Preferred term" : form.kind === "numeric_limit" ? "Label, e.g. Discount" : "Term or phrase"} value={form.term} onChange={(e) => setForm({ ...form, term: e.target.value })} aria-label="Term" />
            <select className="field" value={form.severity} onChange={(e) => setForm({ ...form, severity: e.target.value })} aria-label="Severity">
              {["critical", "high", "medium", "low"].map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
            </select>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {(form.kind === "prohibited" || form.kind === "forbidden_claim") && <input className="field" placeholder="Approved replacement (optional)" value={form.replacement} onChange={(e) => setForm({ ...form, replacement: e.target.value })} aria-label="Replacement" />}
            {(form.kind === "preferred" || form.kind === "brand_name") && <input className="field sm:col-span-2" placeholder="Wrong variants to catch, comma separated" value={form.variants} onChange={(e) => setForm({ ...form, variants: e.target.value })} aria-label="Variants" />}
            {form.kind === "numeric_limit" && <><input className="field" type="number" placeholder="Maximum %" value={form.limit_value} onChange={(e) => setForm({ ...form, limit_value: e.target.value })} aria-label="Limit" /><input className="field" placeholder="Context words, e.g. off|discount" value={form.trigger} onChange={(e) => setForm({ ...form, trigger: e.target.value })} aria-label="Trigger" /></>}
            {form.kind === "required_phrase" && <input className="field" placeholder="Only when text mentions (optional regex)" value={form.trigger} onChange={(e) => setForm({ ...form, trigger: e.target.value })} aria-label="Trigger" />}
            <select className="field" value={form.channels} onChange={(e) => setForm({ ...form, channels: e.target.value })} aria-label="Channel">
              <option value="">All channels</option>{Object.entries(channelLabel).map(([k, l]) => <option key={k} value={k}>{l} only</option>)}
            </select>
          </div>
          <input className="field" placeholder="Why this rule exists (shown to creators)" value={form.explanation} onChange={(e) => setForm({ ...form, explanation: e.target.value })} aria-label="Explanation" />
          <div className="flex gap-2"><button className="btn-primary">Add rule</button><button type="button" className="btn-ghost" onClick={() => setOpen(false)}>Cancel</button></div>
        </form>
      )}
      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[760px] text-left text-sm">
          <thead className="border-b border-paper-edge text-graphite-mute"><tr>
            <th className="px-4 py-2.5 font-medium">Rule</th><th className="px-4 py-2.5 font-medium">Type</th><th className="px-4 py-2.5 font-medium">Severity</th><th className="px-4 py-2.5 font-medium">Scope</th><th className="px-4 py-2.5 font-medium">Source</th>{admin && <th className="px-4 py-2.5" />}
          </tr></thead>
          <tbody>
            {data!.terms.map((t) => (
              <tr key={t.id} className={`border-b border-paper-edge last:border-0 ${t.status !== "approved" ? "opacity-50" : ""}`}>
                <td className="max-w-sm px-4 py-3">
                  <div className="font-medium">“{t.term}”{t.replacement && <span className="font-normal text-graphite"> → use “{t.replacement}”</span>}{t.limit_value !== null && <span className="font-normal text-graphite"> max {t.limit_value}%</span>}</div>
                  {t.variants.length > 0 && <div className="text-xs text-graphite-mute">Catches: {t.variants.join(", ")}</div>}
                  <div className="text-xs text-graphite-faint">{t.explanation}</div>
                </td>
                <td className="px-4 py-3 text-graphite">{kindLabel[t.kind]}</td>
                <td className="px-4 py-3"><SeverityBadge severity={t.severity} /></td>
                <td className="px-4 py-3 text-graphite">{t.channels ? t.channels.map((c) => channelLabel[c]).join(", ") : "All channels"}</td>
                <td className="px-4 py-3 text-graphite">{t.source ? `${t.source.title}${t.page ? `, p. ${t.page}` : ""}` : "Entered by admin"}</td>
                {admin && <td className="px-4 py-3 text-right"><button className="text-sm text-proof hover:underline" onClick={() => toggle(t)}>{t.status === "approved" ? "Disable" : "Enable"}</button></td>}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Voice() {
  const { data, error, loading, reload } = useApi<WorkspaceSummary>("");
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  const t = data!.tone_config as Record<string, string | number | boolean>;
  return (
    <div className="grid gap-6 lg:grid-cols-2">
      <div className="panel p-5">
        <h3 className="font-semibold">Brand voice checks</h3>
        <p className="mt-2 font-serif text-[17px] text-ink">{String(t.voice ?? "No voice description set.")}</p>
        <ul className="mt-4 space-y-1.5 text-sm text-graphite">
          <li>Repeated exclamation marks: {t.flag_repeated_exclamations ? "flagged" : "allowed"}</li>
          <li>All-caps emphasis: {t.flag_all_caps ? "flagged" : "allowed"}</li>
          <li>Maximum sentence length: {t.max_sentence_words ? `${t.max_sentence_words} words` : "not checked"}</li>
        </ul>
        <p className="mt-4 text-xs text-graphite-mute">Admins can change these in Settings. Deeper tone analysis runs only when an AI provider is configured.</p>
      </div>
      <div className="panel p-5">
        <h3 className="font-semibold">Colour palette</h3>
        {data!.palette.length === 0 ? <p className="mt-2 text-sm text-graphite-mute">No palette configured. Add one in Settings to enable visual checks.</p> : (
          <ul className="mt-3 space-y-2.5">
            {data!.palette.map((p: PaletteColour) => (
              <li key={p.hex} className="flex items-center gap-3 text-sm">
                <span className="h-9 w-9 shrink-0 rounded-md ring-1 ring-inset ring-black/10" style={{ background: p.hex }} aria-hidden />
                <span><span className="font-medium">{p.name}</span> <span className="text-graphite-mute">{p.hex}, {p.role}</span><span className="block text-xs text-graphite-mute">{p.usage}</span></span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

export default function Knowledge() {
  const [tab, setTab] = useState<"docs" | "facts" | "rules" | "voice">("docs");
  return (
    <div>
      <PageHeader title="Brand Knowledge" intro="The approved sources every audit is checked against. Only approved, current knowledge is used as evidence. Superseded items stay for history and catch outdated claims." />
      <AdminNote />
      <div className="mb-5 flex flex-wrap gap-6 border-b border-paper-edge" role="tablist">
        {([["docs", "Documents"], ["facts", "Approved facts"], ["rules", "Rules & terminology"], ["voice", "Voice & palette"]] as const).map(([k, l]) => (
          <button key={k} role="tab" aria-selected={tab === k} className={`tab ${tab === k ? "tab-active" : ""}`} onClick={() => setTab(k)}>{l}</button>
        ))}
      </div>
      {tab === "docs" && <Documents />}
      {tab === "facts" && <Facts />}
      {tab === "rules" && <Rules />}
      {tab === "voice" && <Voice />}
    </div>
  );
}
