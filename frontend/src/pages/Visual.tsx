import { Loader2, Upload } from "lucide-react";
import { useState } from "react";
import { ErrorNote, PageHeader, SeverityBadge, useToast } from "../components/ui";
import { api, fileUrl } from "../lib/api";
import { citation } from "../lib/format";
import type { Evidence, Severity } from "../lib/types";

interface VisualResult {
  width: number; height: number; tolerance: number; scope_note: string;
  dominant_colours: { hex: string; share: number; nearest_brand: string | null; nearest_hex: string | null; delta_e: number | null; on_palette: boolean }[];
  contrast: { colours: string[]; ratio: number; aa_normal: boolean } | null;
  findings: { id: string; category: string; severity: Severity; title: string; explanation: string; evidence: Evidence[]; needs_human_confirmation: boolean }[];
}

export default function Visual() {
  const toast = useToast();
  const [res, setRes] = useState<VisualResult | null>(null);
  const [preview, setPreview] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [pair, setPair] = useState({ foreground: "#14B8A6", background: "#F5F7FA" });
  const [ratio, setRatio] = useState<{ ratio: number; aa_normal: boolean; aa_large: boolean; aaa_normal: boolean } | null>(null);

  async function inspect(file: Blob, name: string) {
    setBusy(true); setErr(null); setRes(null);
    setPreview(URL.createObjectURL(file));
    const fd = new FormData();
    fd.append("file", file, name);
    try { setRes(await api<VisualResult>("/visual/inspect", { method: "POST", body: fd })); }
    catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  }
  async function sample(name: string) {
    try { const r = await fetch(fileUrl(name)); await inspect(await r.blob(), name); } catch { toast("Couldn’t load the sample image", "error"); }
  }
  async function checkPair(e: React.FormEvent) {
    e.preventDefault();
    try { setRatio(await api("/visual/contrast", { method: "POST", json: pair })); } catch (e2) { toast((e2 as Error).message, "error"); }
  }

  return (
    <div>
      <PageHeader title="Visual Inspector" intro="Upload a marketing creative to check its colours against the approved palette and test WCAG contrast. This basic version analyses colour only. Logo matching and typography checks are planned for Round 3." />
      <div className="grid gap-6 lg:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
        <div className="space-y-5">
          <div className="panel p-5">
            <label className="flex cursor-pointer flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed border-paper-rule px-4 py-8 text-center hover:border-proof/50">
              <Upload className="h-6 w-6 text-graphite-mute" aria-hidden />
              <span className="font-medium">Choose an image</span>
              <span className="text-xs text-graphite-mute">PNG, JPEG or WEBP, up to 5 MB</span>
              <input type="file" accept="image/png,image/jpeg,image/webp" className="sr-only" onChange={(e) => { const f = e.target.files?.[0]; if (f) void inspect(f, f.name); }} />
            </label>
            <div className="mt-3 flex flex-wrap gap-2 text-sm">
              <span className="text-graphite-mute">Or try a synthetic creative:</span>
              <button className="text-proof hover:underline" onClick={() => sample("northstar_onbrand_creative.png")}>on-brand</button>
              <button className="text-proof hover:underline" onClick={() => sample("northstar_offbrand_creative.png")}>off-brand</button>
            </div>
            {preview && <img src={preview} alt="Uploaded creative preview" className="mt-4 max-h-72 w-full rounded-md object-contain ring-1 ring-paper-edge" />}
          </div>
          <form onSubmit={checkPair} className="panel space-y-3 p-5">
            <h2 className="font-semibold">Text contrast checker</h2>
            <p className="text-sm text-graphite-mute">Exact WCAG 2.1 ratio for a text and background colour pair.</p>
            <div className="grid grid-cols-2 gap-3">
              {(["foreground", "background"] as const).map((k) => (
                <div key={k}>
                  <label className="label capitalize" htmlFor={k}>{k === "foreground" ? "Text" : "Background"}</label>
                  <div className="flex gap-2">
                    <input type="color" value={pair[k]} onChange={(e) => setPair({ ...pair, [k]: e.target.value })} className="h-9 w-10 rounded border border-paper-rule" aria-label={`${k} colour picker`} />
                    <input id={k} className="field" value={pair[k]} onChange={(e) => setPair({ ...pair, [k]: e.target.value })} maxLength={7} />
                  </div>
                </div>
              ))}
            </div>
            <button className="btn-quiet">Check contrast</button>
            {ratio && (
              <div className="rounded-md border border-paper-edge p-3 text-sm">
                <div className="flex items-center gap-3">
                  <span className="rounded px-3 py-1 font-medium" style={{ color: pair.foreground, background: pair.background }}>Sample text</span>
                  <span className="text-lg font-semibold tabular-nums">{ratio.ratio}:1</span>
                </div>
                <p className="mt-2 text-graphite">AA normal text: {ratio.aa_normal ? "pass" : "fail"}. AA large text: {ratio.aa_large ? "pass" : "fail"}. AAA: {ratio.aaa_normal ? "pass" : "fail"}.</p>
              </div>
            )}
          </form>
        </div>

        <div>
          {busy && <div className="flex items-center gap-2 text-sm text-graphite-mute"><Loader2 className="h-4 w-4 animate-spin" aria-hidden /> Analysing colours…</div>}
          {err && <ErrorNote message={err} />}
          {!res && !busy && !err && <div className="rounded-lg border border-dashed border-paper-rule px-6 py-16 text-center text-sm text-graphite-mute">Results appear here: dominant colours, palette matches, contrast and findings that need your confirmation.</div>}
          {res && (
            <div className="space-y-5">
              <div className="panel p-5">
                <h2 className="font-semibold">Dominant colours</h2>
                <p className="mb-3 text-xs text-graphite-mute">{res.width}×{res.height}px. Matched to the nearest palette colour with CIE ΔE. Within {res.tolerance} counts as on-palette.</p>
                <ul className="space-y-2">
                  {res.dominant_colours.map((c) => (
                    <li key={c.hex} className="flex items-center gap-3 text-sm">
                      <span className="h-8 w-8 shrink-0 rounded ring-1 ring-inset ring-black/10" style={{ background: c.hex }} aria-hidden />
                      <span className="w-20 font-medium">{c.hex}</span>
                      <span className="w-14 tabular-nums text-graphite">{c.share}%</span>
                      <span className={c.on_palette ? "text-ev-ok" : "text-sev-high"}>
                        {c.on_palette ? `Matches ${c.nearest_brand}` : c.nearest_brand ? `Off-palette (nearest ${c.nearest_brand}, ΔE ${c.delta_e})` : "No palette configured"}
                      </span>
                    </li>
                  ))}
                </ul>
                {res.contrast && <p className="mt-3 text-sm text-graphite">Contrast between the two dominant colours: <span className="font-medium">{res.contrast.ratio}:1</span> ({res.contrast.aa_normal ? "meets" : "below"} AA for normal text).</p>}
              </div>
              <div>
                <h2 className="mb-2 font-semibold">Findings ({res.findings.length})</h2>
                {res.findings.length === 0 ? <p className="panel p-4 text-sm text-ev-ok">All dominant colours are on-palette and the dominant pair meets AA contrast.</p> : (
                  <div className="space-y-3">
                    {res.findings.map((f) => (
                      <div key={f.id} className="panel p-4">
                        <SeverityBadge severity={f.severity} />
                        <h3 className="mt-1 font-semibold">{f.title}</h3>
                        <p className="mt-1 text-sm text-graphite">{f.explanation}</p>
                        {f.evidence.map((e) => <p key={e.id} className="mt-2 rounded-md bg-paper px-3 py-2 text-sm"><span className="font-medium">{citation(e)}</span>: {e.excerpt}</p>)}
                        {f.needs_human_confirmation && <p className="mt-2 text-xs text-graphite-mute">Heuristic. A person should confirm this.</p>}
                      </div>
                    ))}
                  </div>
                )}
              </div>
              <p className="text-xs text-graphite-mute">{res.scope_note}</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
