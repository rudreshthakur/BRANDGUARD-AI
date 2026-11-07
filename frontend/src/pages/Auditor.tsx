import { Loader2, ShieldCheck } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorNote, PageHeader } from "../components/ui";
import { api } from "../lib/api";
import { channelLabel } from "../lib/format";
import { useSession } from "../lib/session";
import { useApi } from "../lib/useApi";
import type { Sample, SubmissionDetail } from "../lib/types";

const CHANNELS = ["website", "instagram", "advertisement", "email", "presentation", "linkedin", "press_release"];

export default function Auditor() {
  const { session, setRole } = useSession();
  const nav = useNavigate();
  const samples = useApi<{ samples: Sample[] }>("/api/samples");
  const [title, setTitle] = useState("");
  const [channel, setChannel] = useState("website");
  const [text, setText] = useState("");
  const [picked, setPicked] = useState<Sample | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const isReviewer = session?.role === "reviewer";

  function load(s: Sample) {
    setPicked(s); setTitle(s.title); setChannel(s.channel); setText(s.text); setErr(null);
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    if (!text.trim()) { setErr("Paste or type the content you want to check."); return; }
    setBusy(true); setErr(null);
    try {
      const r = await api<SubmissionDetail>("/submissions", { method: "POST", json: { title: title || "Untitled content", channel, text, run_audit: true } });
      nav(`/app/submissions/${r.id}`);
    } catch (e2) { setErr((e2 as Error).message); setBusy(false); }
  }

  return (
    <div>
      <PageHeader title="Content Auditor"
        intro="Paste marketing copy, pick the channel it’s for, and run a brand audit. Findings open on the next screen with their evidence and suggested fixes." />
      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <form onSubmit={submit} className="panel p-5">
          <div className="grid gap-4 sm:grid-cols-[1fr_12rem]">
            <div>
              <label htmlFor="t" className="label">Title</label>
              <input id="t" className="field" value={title} onChange={(e) => setTitle(e.target.value)} placeholder="e.g. Diwali campaign — Instagram caption" maxLength={200} />
            </div>
            <div>
              <label htmlFor="ch" className="label">Channel</label>
              <select id="ch" className="field" value={channel} onChange={(e) => setChannel(e.target.value)}>
                {CHANNELS.map((c) => <option key={c} value={c}>{channelLabel[c]}</option>)}
              </select>
            </div>
          </div>
          <div className="mt-4">
            <label htmlFor="txt" className="label">Content</label>
            <textarea id="txt" className="field manuscript min-h-[220px] text-[18px]" value={text} onChange={(e) => { setText(e.target.value); setPicked(null); }}
              placeholder="Paste the copy you’re about to publish…" maxLength={20000} />
            <div className="mt-1 flex justify-between text-xs text-graphite-mute">
              <span>{picked ? `Loaded sample: ${picked.label}. Expected: ${picked.expectation}` : "Channel-specific rules apply, e.g. Instagram captions need the brand hashtag."}</span>
              <span>{text.length.toLocaleString()} / 20,000</span>
            </div>
          </div>
          {err && <div className="mt-4"><ErrorNote message={err} /></div>}
          <div className="mt-5 flex flex-wrap items-center gap-3">
            {isReviewer ? (
              <>
                <p className="text-sm text-graphite">Reviewers decide on submitted content and don’t create it.</p>
                <button type="button" className="btn-quiet" onClick={() => setRole("creator")}>Switch to Creator</button>
              </>
            ) : (
              <button className="btn-primary px-5 py-2.5 text-[15px]" disabled={busy || !text.trim()}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden /> : <ShieldCheck className="h-4 w-4" aria-hidden />}
                {busy ? "Checking against approved knowledge…" : "Run brand audit"}
              </button>
            )}
          </div>
        </form>

        <aside aria-label="Sample content">
          <h2 className="font-semibold">Try a sample</h2>
          <p className="mb-3 text-sm text-graphite-mute">Synthetic Northstar Labs copy. Each one tests a different check, and one is fully compliant.</p>
          {samples.error && <ErrorNote message={samples.error} onRetry={samples.reload} />}
          <ul className="space-y-2">
            {(samples.data?.samples ?? []).map((s) => (
              <li key={s.key}>
                <button onClick={() => load(s)}
                  className={`w-full rounded-md border px-4 py-3 text-left transition-colors ${picked?.key === s.key ? "border-proof bg-proof-tint/50" : "border-paper-edge bg-white hover:border-paper-rule"}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-medium">{s.label}</span>
                    <span className="text-xs text-graphite-mute">{channelLabel[s.channel]}</span>
                  </div>
                  <p className="mt-0.5 line-clamp-2 font-serif text-[15px] text-graphite">{s.text}</p>
                </button>
              </li>
            ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
