import { useState } from "react";
import { Link } from "react-router-dom";
import { ErrorNote, PageHeader, Spinner } from "../components/ui";
import { roleLabel } from "../lib/format";
import { useApi } from "../lib/useApi";
import type { AuditEvent } from "../lib/types";

const GROUPS: Record<string, string> = { all: "All activity", audit: "Audits", correction: "Corrections", review: "Review decisions", knowledge: "Knowledge changes" };

export default function History() {
  const { data, error, loading, reload } = useApi<{ events: AuditEvent[] }>("/events?limit=500");
  const [g, setG] = useState("all");
  if (loading && !data) return <Spinner />;
  if (error) return <ErrorNote message={error} onRetry={reload} />;
  const rows = data!.events.filter((e) => g === "all" || e.action.startsWith(g) || (g === "knowledge" && /^(fact|rule|settings)\./.test(e.action)));
  return (
    <div>
      <PageHeader title="Audit History" intro="An append-only record of who did what and when: audits, corrections, review decisions and changes to approved knowledge." />
      <div className="mb-4 flex flex-wrap gap-2">
        {Object.entries(GROUPS).map(([k, l]) => (
          <button key={k} onClick={() => setG(k)} className={`rounded-full px-3 py-1 text-sm ${g === k ? "bg-ink text-white" : "bg-white text-graphite ring-1 ring-paper-rule hover:text-ink"}`}>{l}</button>
        ))}
      </div>
      <div className="panel overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-sm">
          <thead className="border-b border-paper-edge text-graphite-mute"><tr><th className="px-4 py-2.5 font-medium">When</th><th className="px-4 py-2.5 font-medium">Role</th><th className="px-4 py-2.5 font-medium">Event</th><th className="px-4 py-2.5 font-medium">Content</th></tr></thead>
          <tbody>
            {rows.map((e) => (
              <tr key={e.id} className="border-b border-paper-edge last:border-0">
                <td className="whitespace-nowrap px-4 py-2.5 text-graphite-mute">{new Date(e.created_at.endsWith("Z") || e.created_at.includes("+") ? e.created_at : e.created_at + "Z").toLocaleString()}</td>
                <td className="px-4 py-2.5 font-medium">{roleLabel[e.actor_role]}</td>
                <td className="px-4 py-2.5 text-graphite">{e.summary}</td>
                <td className="px-4 py-2.5">{e.submission_id ? <Link className="text-proof hover:underline" to={`/app/submissions/${e.submission_id}`}>Open</Link> : <span className="text-graphite-faint">Workspace</span>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {rows.length === 0 && <p className="p-5 text-sm text-graphite-mute">No events in this category.</p>}
      </div>
    </div>
  );
}
