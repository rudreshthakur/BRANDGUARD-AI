import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Empty, ErrorNote, PageHeader, Spinner, StatusChip } from "../components/ui";
import { channelLabel, timeAgo } from "../lib/format";
import { useSession } from "../lib/session";
import { useApi } from "../lib/useApi";
import type { SubmissionStatus, SubmissionSummary } from "../lib/types";

const TABS: { key: string; label: string; statuses: SubmissionStatus[] | null }[] = [
  { key: "review", label: "Awaiting review", statuses: ["under_review", "revised"] },
  { key: "changes", label: "Changes requested", statuses: ["changes_requested"] },
  { key: "draft", label: "Drafts", statuses: ["draft"] },
  { key: "approved", label: "Approved", statuses: ["approved"] },
  { key: "all", label: "All", statuses: null },
];

export default function Review() {
  const { session } = useSession();
  const { data, error, loading, reload } = useApi<{ submissions: SubmissionSummary[] }>("/submissions");
  const [tab, setTab] = useState(session?.role === "reviewer" ? "review" : "all");
  const subs = data?.submissions ?? [];
  const counts = useMemo(() => Object.fromEntries(TABS.map((t) => [t.key, subs.filter((s) => !t.statuses || t.statuses.includes(s.status)).length])), [subs]);
  const current = TABS.find((t) => t.key === tab)!;
  const rows = subs.filter((s) => !current.statuses || current.statuses.includes(s.status));

  return (
    <div>
      <PageHeader title="Review Queue" intro="Every piece of content and where it stands. Reviewers approve or request changes; creators pick up requested revisions."
        actions={<Link to="/app/auditor" className="btn-primary">Audit new content</Link>} />
      <div className="mb-4 flex flex-wrap gap-6 border-b border-paper-edge" role="tablist">
        {TABS.map((t) => (
          <button key={t.key} role="tab" aria-selected={tab === t.key} className={`tab ${tab === t.key ? "tab-active" : ""}`} onClick={() => setTab(t.key)}>
            {t.label} <span className="text-graphite-faint">{counts[t.key] ?? 0}</span>
          </button>
        ))}
      </div>
      {loading && !data ? <Spinner /> : error ? <ErrorNote message={error} onRetry={reload} /> : rows.length === 0 ? (
        <Empty title={tab === "review" ? "Nothing is waiting for review" : "No content here yet"} action={<Link to="/app/auditor" className="btn-quiet">Open the Content Auditor</Link>}>
          {tab === "review" ? "When a creator submits content, it appears here for a decision." : "Audit some content to get started."}
        </Empty>
      ) : (
        <div className="panel overflow-x-auto">
          <table className="w-full min-w-[720px] text-left text-sm">
            <thead className="border-b border-paper-edge text-graphite-mute">
              <tr><th className="px-4 py-2.5 font-medium">Content</th><th className="px-4 py-2.5 font-medium">Channel</th><th className="px-4 py-2.5 font-medium">Status</th>
                <th className="px-4 py-2.5 font-medium">Open findings</th><th className="px-4 py-2.5 font-medium">Version</th><th className="px-4 py-2.5 font-medium">Updated</th></tr>
            </thead>
            <tbody>
              {rows.map((s) => {
                const sev = s.latest_audit?.stats.by_severity;
                return (
                  <tr key={s.id} className="border-b border-paper-edge last:border-0 hover:bg-paper/60">
                    <td className="max-w-md px-4 py-3">
                      <Link to={`/app/submissions/${s.id}`} className="font-medium text-ink hover:text-proof">{s.title}</Link>
                      {s.is_sample && <span className="ml-2 text-xs text-graphite-faint">synthetic sample</span>}
                      <div className="truncate font-serif text-[14px] text-graphite-mute">{s.excerpt}</div>
                    </td>
                    <td className="px-4 py-3 text-graphite">{channelLabel[s.channel] ?? s.channel}</td>
                    <td className="px-4 py-3"><StatusChip status={s.status} /></td>
                    <td className="px-4 py-3">
                      {!s.latest_audit ? <span className="text-graphite-faint">Not audited</span> : s.open_findings === 0 ? <span className="text-ev-ok">None</span> : (
                        <span className="text-graphite">{s.open_findings}{sev && (sev.critical || sev.high) ? <span className="text-sev-high"> ({(sev.critical ?? 0) + (sev.high ?? 0)} high+ at last audit)</span> : null}</span>
                      )}
                      {!s.audit_current && s.latest_audit && <div className="text-xs text-ev-outdated">Needs re-audit</div>}
                    </td>
                    <td className="px-4 py-3 text-graphite">v{s.current_version}</td>
                    <td className="px-4 py-3 text-graphite-mute">{timeAgo(s.updated_at)}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
