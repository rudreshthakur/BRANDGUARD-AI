import type { EvidenceStatus, Severity, SubmissionStatus } from "./types";

export const SEVERITY_ORDER: Severity[] = ["critical", "high", "medium", "low"];

export const severityLabel: Record<Severity, string> = { critical: "Critical", high: "High", medium: "Medium", low: "Low" };

export const evidenceMeta: Record<EvidenceStatus, { label: string; short: string; tone: string; mark: string; help: string }> = {
  rule_violation: { label: "Confirmed rule violation", short: "Rule violation", tone: "text-ev-rule bg-red-50 ring-red-200",
    mark: "mark-rule", help: "The text breaks an approved rule. The rule is cited below." },
  verified_conflict: { label: "Conflicts with an approved fact", short: "Verified conflict", tone: "text-ev-conflict bg-orange-50 ring-orange-200",
    mark: "mark-conflict", help: "An approved fact covers this exact point and states something different." },
  outdated: { label: "Matches a superseded fact", short: "Outdated", tone: "text-ev-outdated bg-amber-50 ring-amber-200",
    mark: "mark-outdated", help: "This value was approved once but has since been replaced. The current value is shown." },
  unsupported: { label: "Unable to verify against approved knowledge", short: "Unsupported", tone: "text-ev-gap bg-violet-50 ring-violet-200",
    mark: "mark-gap", help: "No approved source backs this claim. That is an evidence gap, not proof the claim is false." },
  ambiguous: { label: "Ambiguous evidence", short: "Ambiguous", tone: "text-ev-gap bg-violet-50 ring-violet-200",
    mark: "mark-gap", help: "Related knowledge exists but doesn't settle the question. A human should decide." },
  approved: { label: "Approved claim", short: "Verified", tone: "text-ev-ok bg-emerald-50 ring-emerald-200",
    mark: "mark-ok", help: "Matches a current approved fact." },
  security: { label: "Security notice", short: "Security", tone: "text-graphite bg-slate-100 ring-slate-300",
    mark: "mark-security", help: "Suspicious embedded instruction. It was treated as plain text and had no effect." },
  contextual: { label: "AI contextual observation", short: "AI observation", tone: "text-proof bg-proof-tint ring-indigo-200",
    mark: "mark-ctx", help: "Suggested by the AI model. Only validated evidence is shown; judge it yourself." },
};

export const statusMeta: Record<SubmissionStatus, { label: string; tone: string }> = {
  draft: { label: "Draft", tone: "bg-slate-100 text-graphite ring-slate-300" },
  under_review: { label: "Under review", tone: "bg-proof-tint text-proof-dark ring-indigo-200" },
  changes_requested: { label: "Changes requested", tone: "bg-orange-50 text-sev-high ring-orange-200" },
  revised: { label: "Revised", tone: "bg-sky-50 text-sky-800 ring-sky-200" },
  approved: { label: "Approved", tone: "bg-emerald-50 text-ev-ok ring-emerald-200" },
};

export const channelLabel: Record<string, string> = {
  website: "Website", instagram: "Instagram", advertisement: "Advertisement", email: "Email",
  presentation: "Presentation", linkedin: "LinkedIn", press_release: "Press release",
};

export const roleLabel = { creator: "Creator", reviewer: "Reviewer", admin: "Admin" } as const;

export function timeAgo(iso: string): string {
  const d = new Date(iso.endsWith("Z") || iso.includes("+") ? iso : iso + "Z");
  const s = Math.max(0, (Date.now() - d.getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)} min ago`;
  if (s < 86400) return `${Math.floor(s / 3600)} h ago`;
  return d.toLocaleDateString(undefined, { day: "numeric", month: "short", year: "numeric" });
}

export function citation(e: { document: string; version: number | null; page: number | null; section: string | null }): string {
  const parts = [e.document + (e.version && !/\bv\d/.test(e.document) ? ` (v${e.version})` : "")];
  if (e.page) parts.push(`p. ${e.page}`);
  if (e.section) parts.push(e.section);
  return parts.join(", ");
}
