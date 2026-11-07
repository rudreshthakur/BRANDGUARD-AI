import { Link } from "react-router-dom";
import { ErrorNote, PageHeader, Spinner, StatusChip } from "../components/ui";
import { timeAgo } from "../lib/format";
import { useSession } from "../lib/session";
import { useApi } from "../lib/useApi";
import type { SubmissionSummary, WorkspaceSummary } from "../lib/types";

export default function Overview() {
  const { session } = useSession();
  const ws = useApi<WorkspaceSummary>("");
  const subs = useApi<{ submissions: SubmissionSummary[] }>("/submissions");
  if (ws.loading && !ws.data) return <Spinner />;
  if (ws.error) return <ErrorNote message={ws.error} onRetry={ws.reload} />;
  const w = ws.data!;
  const c = w.counts;
  const role = session?.role;
  const next = role === "reviewer"
    ? { text: `${c.in_review} item${c.in_review === 1 ? "" : "s"} waiting for your decision.`, to: "/app/review", cta: "Open review queue" }
    : role === "admin"
      ? { text: c.pending_sources ? `${c.pending_sources} document${c.pending_sources === 1 ? "" : "s"} waiting for approval.` : "Approved knowledge is up to date.", to: "/app/knowledge", cta: "Manage brand knowledge" }
      : { text: "Check a draft before it goes out.", to: "/app/auditor", cta: "Audit content" };

  return (
    <div>
      <PageHeader title={w.brand_name} intro={w.is_demo ? "Your private demo workspace. Everything here is synthetic Northstar Labs data, and changes affect only this copy." : "Workspace overview."} />
      <section className="panel mb-6 flex flex-wrap items-center justify-between gap-4 p-5">
        <p className="text-[17px]">{next.text}</p>
        <Link to={next.to} className="btn-primary">{next.cta}</Link>
      </section>

      <div className="grid gap-6 lg:grid-cols-3">
        <section className="panel p-5 lg:col-span-1">
          <h2 className="font-semibold">Approved knowledge</h2>
          <dl className="mt-3 space-y-2 text-sm">
            {([["Approved documents", c.approved_sources], ["Documents pending review", c.pending_sources], ["Approved facts", c.approved_facts],
              ["Superseded facts kept for history", c.superseded_facts], ["Active rules", c.active_rules]] as [string, number][]).map(([k, v]) => (
              <div key={k} className="flex justify-between border-b border-paper-edge pb-2 last:border-0"><dt className="text-graphite">{k}</dt><dd className="font-medium tabular-nums">{v}</dd></div>
            ))}
          </dl>
          <p className="mt-4 text-xs text-graphite-mute">{w.ai.message}</p>
        </section>

        <section className="panel p-5 lg:col-span-2">
          <div className="flex items-center justify-between">
            <h2 className="font-semibold">Recent content</h2>
            <Link to="/app/review" className="text-sm text-proof hover:underline">View all</Link>
          </div>
          {subs.loading && !subs.data ? <Spinner /> : (
            <ul className="mt-3 divide-y divide-paper-edge">
              {(subs.data?.submissions ?? []).slice(0, 6).map((s) => (
                <li key={s.id} className="flex items-center justify-between gap-4 py-2.5">
                  <div className="min-w-0">
                    <Link to={`/app/submissions/${s.id}`} className="font-medium hover:text-proof">{s.title}</Link>
                    <div className="text-xs text-graphite-mute">{s.open_findings} open finding{s.open_findings === 1 ? "" : "s"}, updated {timeAgo(s.updated_at)}</div>
                  </div>
                  <StatusChip status={s.status} />
                </li>
              ))}
            </ul>
          )}
        </section>
      </div>

      <section className="mt-6 grid gap-4 text-sm sm:grid-cols-3">
        {[["Creator", "Audit content, accept or edit fixes, submit for review."], ["Reviewer", "Open evidence, request changes, approve with justification."], ["Admin", "Upload guidelines, approve facts and rules, version specs."]].map(([r, d]) => (
          <div key={r} className="rounded-md border border-paper-edge bg-white/60 px-4 py-3"><span className="font-medium">{r}: </span><span className="text-graphite">{d}</span></div>
        ))}
      </section>
    </div>
  );
}
