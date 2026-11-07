from __future__ import annotations

from .models import AuditRun, Chunk, Comment, ContentVersion, Correction, Fact, Finding, ReviewDecision, Source, Submission, Term


def iso(dt):
    return dt.isoformat() if dt else None


def source_out(s: Source, with_chunks: bool = False) -> dict:
    d = {"id": s.id, "title": s.title, "version": s.version, "lineage_key": s.lineage_key, "kind": s.kind,
         "filename": s.filename, "status": s.status, "authority": s.authority, "effective_date": s.effective_date,
         "page_count": s.page_count, "chunk_count": len(s.chunks), "injection_flags": s.injection_flags,
         "is_synthetic": s.is_synthetic, "created_at": iso(s.created_at), "approved_at": iso(s.approved_at)}
    if with_chunks:
        d["chunks"] = [chunk_out(c) for c in s.chunks]
    return d


def chunk_out(c: Chunk) -> dict:
    return {"id": c.id, "ordinal": c.ordinal, "page": c.page, "section": c.section, "text": c.text}


def fact_out(f: Fact, sources: dict[str, Source]) -> dict:
    src = sources.get(f.source_id) if f.source_id else None
    return {"id": f.id, "statement": f.statement, "subject": f.subject, "metric": f.metric, "value": f.value,
            "unit": f.unit, "keywords": f.keywords, "status": f.status, "effective_date": f.effective_date,
            "superseded_by": f.superseded_by, "page": f.page, "section": f.section,
            "source": {"id": src.id, "title": src.title, "version": src.version, "status": src.status} if src else None,
            "created_at": iso(f.created_at)}


def term_out(t: Term, sources: dict[str, Source]) -> dict:
    src = sources.get(t.source_id) if t.source_id else None
    return {"id": t.id, "kind": t.kind, "term": t.term, "replacement": t.replacement, "variants": t.variants,
            "trigger": t.trigger, "limit_value": t.limit_value, "category": t.category, "severity": t.severity,
            "explanation": t.explanation, "channels": t.channels, "status": t.status, "page": t.page, "section": t.section,
            "source": {"id": src.id, "title": src.title, "version": src.version} if src else None}


def version_out(v: ContentVersion) -> dict:
    return {"version_no": v.version_no, "text": v.text, "change_note": v.change_note, "created_by": v.created_by,
            "created_at": iso(v.created_at)}


def finding_out(f: Finding) -> dict:
    return {"id": f.id, "audit_run_id": f.audit_run_id, "version_no": f.version_no, "rule_id": f.rule_id,
            "rule_label": f.rule_label, "category": f.category, "severity": f.severity, "title": f.title,
            "passage": f.passage, "start": f.start, "end": f.end, "explanation": f.explanation,
            "evidence_status": f.evidence_status, "evidence": f.evidence, "confidence": f.confidence,
            "suggestion": f.suggestion, "suggestion_reason": f.suggestion_reason, "origin": f.origin,
            "channel": f.channel, "status": f.status, "created_at": iso(f.created_at)}


def run_out(r: AuditRun) -> dict:
    return {"id": r.id, "version_no": r.version_no, "ai_mode": r.ai_mode, "ai_status": r.ai_status,
            "knowledge_snapshot": r.knowledge_snapshot, "verified_claims": r.verified_claims, "stats": r.stats,
            "created_at": iso(r.created_at)}


def submission_summary(s: Submission, run: AuditRun | None, open_count: int) -> dict:
    return {"id": s.id, "title": s.title, "channel": s.channel, "status": s.status, "current_version": s.current_version,
            "is_sample": s.is_sample, "created_at": iso(s.created_at), "updated_at": iso(s.updated_at),
            "excerpt": s.versions[-1].text[:160] if s.versions else "",
            "latest_audit": run_out(r) if (r := run) else None, "open_findings": open_count,
            "audit_current": bool(run and run.version_no == s.current_version)}


def comment_out(c: Comment) -> dict:
    return {"id": c.id, "author_role": c.author_role, "body": c.body, "version_no": c.version_no,
            "finding_id": c.finding_id, "created_at": iso(c.created_at)}


def decision_out(d: ReviewDecision) -> dict:
    return {"id": d.id, "decision": d.decision, "from_status": d.from_status, "to_status": d.to_status, "note": d.note,
            "version_no": d.version_no, "open_findings_at_decision": d.open_findings_at_decision,
            "actor_role": d.actor_role, "created_at": iso(d.created_at)}


def correction_out(c: Correction) -> dict:
    return {"id": c.id, "finding_id": c.finding_id, "action": c.action, "original": c.original,
            "applied_text": c.applied_text, "reason": c.reason, "from_version": c.from_version,
            "to_version": c.to_version, "actor_role": c.actor_role, "created_at": iso(c.created_at)}
