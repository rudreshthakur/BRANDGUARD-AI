import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ErrorNote, PageHeader, Spinner, useToast } from "../components/ui";
import { api } from "../lib/api";
import { useSession } from "../lib/session";
import { useApi } from "../lib/useApi";
import type { PaletteColour, WorkspaceSummary } from "../lib/types";

export default function Settings() {
  const { session, launchDemo } = useSession();
  const nav = useNavigate();
  const toast = useToast();
  const { data, error, loading, reload } = useApi<WorkspaceSummary>("");
  const [tone, setTone] = useState({ flag_repeated_exclamations: true, flag_all_caps: true, max_sentence_words: 32, voice: "" });
  const [palette, setPalette] = useState<PaletteColour[]>([]);
  const admin = session?.role === "admin";

  useEffect(() => {
    if (!data) return;
    const t = data.tone_config as Record<string, unknown>;
    setTone({ flag_repeated_exclamations: !!t.flag_repeated_exclamations, flag_all_caps: !!t.flag_all_caps, max_sentence_words: Number(t.max_sentence_words ?? 0), voice: String(t.voice ?? "") });
    setPalette(data.palette);
  }, [data]);

  if (loading && !data) return <Spinner />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;

  async function save() {
    try { await api("/settings", { method: "PUT", json: { ...tone, palette } }); toast("Settings saved"); void reload(); }
    catch (e) { toast((e as Error).message, "error"); }
  }

  return (
    <div className="max-w-3xl space-y-6">
      <PageHeader title="Settings" />
      <section className="panel p-5">
        <h2 className="font-semibold">AI contextual analysis</h2>
        <p className={`mt-1 text-sm ${data!.ai.enabled ? "text-ev-ok" : "text-graphite"}`}>{data!.ai.message}</p>
        <p className="mt-2 text-sm text-graphite-mute">
          Deterministic rules and evidence retrieval always run. To enable AI analysis, the server operator sets BRANDGUARD_LLM_PROVIDER and BRANDGUARD_LLM_API_KEY on the backend.
          Keys are never sent to the browser. AI findings are labelled, their passages must match the content exactly, and they can only cite evidence BrandGuard retrieved.
        </p>
      </section>

      <section className="panel space-y-4 p-5">
        <div className="flex items-center justify-between"><h2 className="font-semibold">Brand voice and palette</h2>{!admin && <span className="text-xs text-graphite-mute">Admin only</span>}</div>
        <fieldset disabled={!admin} className="space-y-3 disabled:opacity-60">
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={tone.flag_repeated_exclamations} onChange={(e) => setTone({ ...tone, flag_repeated_exclamations: e.target.checked })} /> Flag repeated exclamation marks</label>
          <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={tone.flag_all_caps} onChange={(e) => setTone({ ...tone, flag_all_caps: e.target.checked })} /> Flag all-caps emphasis</label>
          <div className="flex items-center gap-2 text-sm"><label htmlFor="msw">Maximum words per sentence (0 turns it off)</label>
            <input id="msw" type="number" min={0} max={200} className="field w-24" value={tone.max_sentence_words} onChange={(e) => setTone({ ...tone, max_sentence_words: Number(e.target.value) })} /></div>
          <div><label className="label" htmlFor="voice">Voice description</label><textarea id="voice" className="field" rows={2} value={tone.voice} onChange={(e) => setTone({ ...tone, voice: e.target.value })} /></div>
          <div>
            <div className="label">Palette</div>
            <ul className="space-y-2">
              {palette.map((p, i) => (
                <li key={i} className="grid grid-cols-[2.5rem_1fr_7rem_6rem_2rem] items-center gap-2">
                  <input type="color" value={p.hex} onChange={(e) => setPalette(palette.map((x, j) => j === i ? { ...x, hex: e.target.value.toUpperCase() } : x))} className="h-9 w-10 rounded border border-paper-rule" aria-label={`${p.name} colour`} />
                  <input className="field" value={p.name} onChange={(e) => setPalette(palette.map((x, j) => j === i ? { ...x, name: e.target.value } : x))} aria-label="Colour name" />
                  <input className="field" value={p.hex} onChange={(e) => setPalette(palette.map((x, j) => j === i ? { ...x, hex: e.target.value } : x))} aria-label="Hex" />
                  <select className="field" value={p.role} onChange={(e) => setPalette(palette.map((x, j) => j === i ? { ...x, role: e.target.value } : x))} aria-label="Role">
                    {["primary", "accent", "neutral", "highlight"].map((r) => <option key={r}>{r}</option>)}
                  </select>
                  <button type="button" className="btn-ghost p-1" aria-label={`Remove ${p.name}`} onClick={() => setPalette(palette.filter((_, j) => j !== i))}>×</button>
                </li>
              ))}
            </ul>
            <button type="button" className="mt-2 text-sm text-proof hover:underline" onClick={() => setPalette([...palette, { name: "New colour", hex: "#2949C6", role: "accent", usage: "" }])}>Add colour</button>
          </div>
          <button type="button" className="btn-primary" onClick={save}>Save settings</button>
        </fieldset>
      </section>

      {session?.isDemo && (
        <section className="panel p-5">
          <h2 className="font-semibold">Start the demo over</h2>
          <p className="mt-1 text-sm text-graphite-mute">Opens a fresh copy of the Northstar Labs workspace. Your current copy stays reachable until it expires after 72 hours.</p>
          <button className="btn-quiet mt-3" onClick={async () => { try { await launchDemo(); nav("/app/auditor"); toast("Fresh demo workspace ready"); } catch (e) { toast((e as Error).message, "error"); } }}>Open a fresh demo workspace</button>
        </section>
      )}
      <section className="text-sm text-graphite-mute">
        <p>Workspace ID: {data!.id}. Access is limited to this browser through a private token. The role switch is a demonstration aid, not production sign-in.</p>
      </section>
    </div>
  );
}
