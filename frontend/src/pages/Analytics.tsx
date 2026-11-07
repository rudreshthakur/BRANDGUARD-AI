import { useState } from "react";
import { Link } from "react-router-dom";
import { Empty, ErrorNote, PageHeader, Spinner } from "../components/ui";
import { channelLabel, evidenceMeta, SEVERITY_ORDER, severityLabel } from "../lib/format";
import { useApi } from "../lib/useApi";
import type { EvidenceStatus, Severity } from "../lib/types";

interface Drift {
  scope: { include_samples: boolean; submissions: number; synthetic_samples: number };
  totals: Record<string, number>;
  by_severity: Record<Severity, number>;
  by_category: Record<string, number>;
  by_channel: Record<string, number>;
  by_evidence_status: Record<string, number>;
  channel_matrix: Record<string, Record<string, number>>;
  top_rules: { rule_id: string; label: string; category: string; count: number; submissions: number; channels: string[] }[];
  repeated_terms: { term: string; count: number }[];
  recurring_unsupported_claims: { claim: string; count: number }[];
  corrections: { accepted: number; edited: number; rejected: number };
  decisions: Record<string, number>;
  guideline_clarity_signals: { rule_id: string; label: string; decisions: number; rejected: number; reason: string }[];
  training_signals: { rule_id: string; label: string; count: number; submissions: number; reason: string }[];
  trend: { date: string; findings: number }[];
  notes: string[];
}

const sevFill: Record<Severity, string> = { critical: "#A1161B", high: "#C2410C", medium: "#A15C07", low: "#55607A" };

function Bars({ rows, fill = "#2949C6", unit = "finding" }: { rows: { label: string; value: number; hint?: string; color?: string }[]; fill?: string; unit?: string }) {
  const max = Math.max(1, ...rows.map((r) => r.value));
  if (rows.length === 0) return <p className="py-4 text-sm text-graphite-mute">No data yet.</p>;
  return (
    <ul className="space-y-2.5">
      {rows.map((r) => (
        <li key={r.label} className="grid grid-cols-[minmax(0,14rem)_1fr_2.5rem] items-center gap-3 text-sm" title={`${r.label}: ${r.value} ${unit}${r.value === 1 ? "" : "s"}${r.hint ? ` — ${r.hint}` : ""}`}>
          <span className="truncate text-graphite">{r.label}</span>
          <span className="h-3 rounded-r-[4px] bg-paper-edge/60" aria-hidden>
            <span className="block h-3 rounded-r-[4px]" style={{ width: `${(r.value / max) * 100}%`, background: r.color ?? fill, minWidth: r.value ? 4 : 0 }} />
          </span>
          <span className="text-right font-medium tabular-nums text-ink">{r.value}</span>
        </li>
      ))}
    </ul>
  );
}

function Card({ title, sub, children, className = "" }: { title: string; sub?: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={`panel p-5 ${className}`}>
      <h2 className="font-semibold">{title}</h2>
      {sub && <p className="mb-3 text-xs text-graphite-mute">{sub}</p>}
      {!sub && <div className="mb-3" />}
      {children}
    </section>
  );
}

export default function Analytics() {
  const [samples, setSamples] = useState(true);
  const { data: d, error, loading, reload } = useApi<Drift>(`/analytics?include_samples=${samples}`);
  if (loading && !d) return <Spinner label="Computing brand drift" />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  if (!d) return null;
  const cats = Array.from(new Set(Object.values(d.channel_matrix).flatMap((m) => Object.keys(m))));
  const matrixMax = Math.max(1, ...Object.values(d.channel_matrix).flatMap((m) => Object.values(m)));
  const corrTotal = d.corrections.accepted + d.corrections.edited + d.corrections.rejected;
  const trendMax = Math.max(1, ...d.trend.map((t) => t.findings));

  return (
    <div>
      <PageHeader title="Brand Drift Intelligence"
        intro="Patterns across real reviews in this workspace: which rules keep getting broken, which claims keep appearing without evidence, and which guidelines may be unclear."
        actions={
          <label className="inline-flex items-center gap-2 text-sm text-graphite">
            <input type="checkbox" checked={samples} onChange={(e) => setSamples(e.target.checked)} /> Include synthetic sample reviews
          </label>
        } />
      <p className="mb-5 rounded-md border border-paper-edge bg-white/70 px-4 py-2.5 text-sm text-graphite">
        Computed live from this workspace’s stored audits, corrections and decisions. {d.scope.synthetic_samples > 0 && samples
          ? `${d.scope.synthetic_samples} of ${d.scope.submissions} submissions are synthetic samples seeded into the demo and run through the real engine.`
          : `${d.scope.submissions} submission${d.scope.submissions === 1 ? "" : "s"} included.`} Nothing here is invented or estimated.
      </p>

      {d.totals.findings === 0 ? (
        <Empty title="No reviews to analyse yet" action={<Link to="/app/auditor" className="btn-primary">Audit content</Link>}>
          Brand drift appears once content has been audited. {samples ? "" : "Try including the synthetic samples."}
        </Empty>
      ) : (
        <>
          <div className="mb-6 grid grid-cols-2 gap-px overflow-hidden rounded-lg border border-paper-edge bg-paper-edge md:grid-cols-5">
            {([["Submissions", d.totals.submissions], ["Unique findings", d.totals.findings], ["Still open", d.totals.open_findings],
              ["In review", d.totals.in_review], ["Approved", d.totals.approved_submissions]] as [string, number][]).map(([k, v]) => (
              <div key={k} className="bg-white px-5 py-4"><div className="text-2xl font-semibold tabular-nums">{v}</div><div className="text-sm text-graphite-mute">{k}</div></div>
            ))}
          </div>

          <div className="grid gap-6 lg:grid-cols-2">
            <Card title="Most frequently triggered rules" sub="Unique occurrences, with how many separate submissions each rule affected.">
              <Bars rows={d.top_rules.map((r) => ({ label: r.label, value: r.count, hint: `${r.submissions} submission(s); ${r.channels.map((c) => channelLabel[c] ?? c).join(", ")}` }))} />
            </Card>
            <Card title="Findings by severity" sub="Each bar is labelled; colour repeats the severity name.">
              <Bars rows={SEVERITY_ORDER.map((s) => ({ label: severityLabel[s], value: d.by_severity[s] ?? 0, color: sevFill[s] }))} />
              <div className="mt-5 border-t border-paper-edge pt-4">
                <h3 className="mb-3 text-sm font-medium">By evidence outcome</h3>
                <Bars rows={Object.entries(d.by_evidence_status).map(([k, v]) => ({ label: evidenceMeta[k as EvidenceStatus]?.short ?? k, value: v }))} />
              </div>
            </Card>

            <Card title="Signals for the brand team" sub="Generated from patterns, not opinions. Each signal lists the evidence behind it." className="lg:col-span-2">
              {d.guideline_clarity_signals.length === 0 && d.training_signals.length === 0 ? (
                <p className="text-sm text-graphite-mute">No recurring patterns yet. Signals appear when a rule fires across 2+ submissions, or when creators reject at least half of a rule’s suggestions (minimum 2 decisions).</p>
              ) : (
                <ul className="divide-y divide-paper-edge">
                  {d.guideline_clarity_signals.map((s) => (
                    <li key={`c${s.rule_id}`} className="py-3 text-sm"><span className="font-medium">Possibly unclear guideline: {s.label}.</span> <span className="text-graphite">{s.reason} ({s.rejected} of {s.decisions} decisions rejected.)</span></li>
                  ))}
                  {d.training_signals.map((s) => (
                    <li key={`t${s.rule_id}`} className="py-3 text-sm"><span className="font-medium">Recurring issue: {s.label}.</span> <span className="text-graphite">{s.reason} ({s.count} occurrences across {s.submissions} submissions.)</span></li>
                  ))}
                </ul>
              )}
            </Card>

            <Card title="Repeated terminology and tone violations">
              {d.repeated_terms.length === 0 ? <p className="text-sm text-graphite-mute">None recorded.</p> : (
                <Bars rows={d.repeated_terms.map((t) => ({ label: `“${t.term}”`, value: t.count }))} unit="occurrence" />
              )}
            </Card>
            <Card title="Recurring unverified claims" sub="Claims marked ‘Unable to verify’. Repeats suggest a fact the team should approve or retire.">
              {d.recurring_unsupported_claims.length === 0 ? <p className="text-sm text-graphite-mute">None recorded.</p> : (
                <Bars rows={d.recurring_unsupported_claims.map((t) => ({ label: `“${t.claim}”`, value: t.count }))} fill="#7A4BC2" unit="occurrence" />
              )}
            </Card>

            <Card title="Issues across channels" sub="Findings per channel and category. Darker cells have more findings.">
              <div className="overflow-x-auto">
                <table className="w-full text-left text-sm">
                  <thead><tr><th className="py-1.5 pr-3 font-medium text-graphite-mute">Channel</th>{cats.map((c) => <th key={c} className="px-1.5 py-1.5 text-center text-xs font-medium capitalize text-graphite-mute">{c.replace("_", " ")}</th>)}</tr></thead>
                  <tbody>
                    {Object.entries(d.channel_matrix).map(([ch, m]) => (
                      <tr key={ch}>
                        <td className="py-1 pr-3 text-graphite">{channelLabel[ch] ?? ch}</td>
                        {cats.map((c) => {
                          const v = m[c] ?? 0;
                          const a = v / matrixMax;
                          return (
                            <td key={c} className="p-0.5" title={`${channelLabel[ch] ?? ch}, ${c}: ${v}`}>
                              <div className="flex h-8 items-center justify-center rounded text-xs font-medium tabular-nums"
                                style={{ background: v ? `rgba(41,73,198,${0.12 + a * 0.75})` : "#F6F7F9", color: a > 0.5 ? "#fff" : "#16213A" }}>{v || ""}</div>
                            </td>
                          );
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </Card>

            <Card title="How creators responded to suggestions" sub={corrTotal ? `${corrTotal} decisions recorded.` : "No correction decisions yet."}>
              <Bars rows={[{ label: "Accepted as suggested", value: d.corrections.accepted }, { label: "Accepted with edits", value: d.corrections.edited },
                { label: "Rejected, original kept", value: d.corrections.rejected }]} unit="decision" />
              {d.trend.length > 0 && (
                <div className="mt-5 border-t border-paper-edge pt-4">
                  <h3 className="mb-2 text-sm font-medium">New findings by day</h3>
                  <div className="flex h-24 items-end gap-1.5">
                    {d.trend.map((t) => (
                      <div key={t.date} className="flex flex-1 flex-col items-center gap-1" title={`${t.date}: ${t.findings} findings`}>
                        <span className="text-[11px] tabular-nums text-graphite">{t.findings}</span>
                        <span className="w-full max-w-10 rounded-t-[4px] bg-proof" style={{ height: `${(t.findings / trendMax) * 64}px`, minHeight: 4 }} />
                        <span className="text-[11px] text-graphite-mute">{t.date.slice(5)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </Card>
          </div>
          <ul className="mt-6 space-y-1 text-xs text-graphite-mute">{d.notes.map((n) => <li key={n}>{n}</li>)}</ul>
        </>
      )}
    </div>
  );
}
