export type Role = "creator" | "reviewer" | "admin";
export type Severity = "critical" | "high" | "medium" | "low";
export type EvidenceStatus =
  | "rule_violation" | "verified_conflict" | "outdated" | "unsupported" | "ambiguous" | "approved" | "security" | "contextual";
export type SubmissionStatus = "draft" | "under_review" | "changes_requested" | "revised" | "approved";

export interface Evidence {
  id: string;
  type: "fact" | "chunk" | "term" | "setting" | "palette";
  role: string;
  document: string;
  version: number | null;
  page: number | null;
  section: string | null;
  excerpt: string;
  status: string;
}

export interface Finding {
  id: string; audit_run_id: string; version_no: number; rule_id: string; rule_label: string; category: string;
  severity: Severity; title: string; passage: string; start: number; end: number; explanation: string;
  evidence_status: EvidenceStatus; evidence: Evidence[]; confidence: "high" | "medium" | "low";
  suggestion: string | null; suggestion_reason: string | null; origin: "rule" | "retrieval" | "ai" | "security";
  channel: string; status: "open" | "accepted" | "edited" | "rejected" | "stale"; created_at: string;
}

export interface VerifiedClaim { passage: string; start: number; end: number; status: "approved"; evidence: Evidence[] }

export interface AuditRun {
  id: string; version_no: number; ai_mode: string; ai_status: string;
  knowledge_snapshot: { approved_sources?: string[]; approved_facts?: number; indexed_chunks?: number };
  verified_claims: VerifiedClaim[];
  stats: { total: number; by_severity: Record<Severity, number>; deterministic: number; ai: number; verified_claims: number };
  created_at: string;
}

export interface Version { version_no: number; text: string; change_note: string; created_by: string; created_at: string }
export interface Comment { id: number; author_role: Role; body: string; version_no: number; finding_id: string | null; created_at: string }
export interface Decision {
  id: number; decision: string; from_status: string; to_status: string; note: string; version_no: number;
  open_findings_at_decision: number; actor_role: Role; created_at: string;
}
export interface Correction {
  id: number; finding_id: string; action: "accepted" | "edited" | "rejected"; original: string; applied_text: string | null;
  reason: string; from_version: number; to_version: number | null; actor_role: Role; created_at: string;
}

export interface SubmissionSummary {
  id: string; title: string; channel: string; status: SubmissionStatus; current_version: number; is_sample: boolean;
  created_at: string; updated_at: string; excerpt: string; latest_audit: AuditRun | null; open_findings: number;
  audit_current: boolean;
}

export interface SubmissionDetail extends SubmissionSummary {
  versions: Version[]; findings: Finding[]; runs: AuditRun[]; comments: Comment[]; decisions: Decision[];
  corrections: Correction[];
}

export interface Sample { key: string; title: string; channel: string; label: string; expectation: string; text: string }

export interface Source {
  id: string; title: string; version: number; lineage_key: string; kind: string; filename: string | null;
  status: "pending_review" | "approved" | "superseded" | "rejected"; authority: string; effective_date: string | null;
  page_count: number; chunk_count: number; injection_flags: { excerpt: string; offset: number }[]; is_synthetic: boolean;
  created_at: string; approved_at: string | null;
  chunks?: { id: string; ordinal: number; page: number | null; section: string | null; text: string }[];
  proposed_rules?: { kind: string; term: string; variants: string[]; replacement: string | null; page: number | null; section: string | null; excerpt: string }[];
  other_versions?: { id: string; version: number; status: string }[];
}

export interface Fact {
  id: string; statement: string; subject: string; metric: string | null; value: number | null; unit: string | null;
  keywords: string[]; status: "approved" | "superseded" | "draft"; effective_date: string | null; superseded_by: string | null;
  page: number | null; section: string | null; source: { id: string; title: string; version: number; status: string } | null;
}

export interface Term {
  id: string; kind: string; term: string; replacement: string | null; variants: string[]; trigger: string | null;
  limit_value: number | null; category: string; severity: Severity; explanation: string; channels: string[] | null;
  status: string; page: number | null; section: string | null; source: { id: string; title: string; version: number } | null;
}

export interface PaletteColour { name: string; hex: string; role: string; usage: string }

export interface WorkspaceSummary {
  id: string; name: string; brand_name: string; is_demo: boolean;
  tone_config: Record<string, unknown>; palette: PaletteColour[];
  counts: Record<string, number>;
  ai: { enabled: boolean; provider: string | null; model: string | null; message: string };
}

export interface AuditEvent { id: number; submission_id: string | null; actor_role: Role; action: string; summary: string; details: Record<string, unknown>; created_at: string }
