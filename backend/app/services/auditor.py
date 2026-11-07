"""Review orchestrator: security scan -> deterministic rules -> claim verification -> AI analysis
-> merge/deduplicate -> final evidence validation -> persist."""
from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from ..models import AuditRun, Finding, Submission, Term, Workspace
from . import llm
from .audit_log import log_event
from .claims import verify_claims
from .evidence import UNABLE_TO_VERIFY, EvidenceValidator
from .findings import SEVERITY_RANK, FindingDraft
from .retrieval import Retriever
from .rules import AuditContext, run_rules
from .security import injection_findings

NEEDS_EVIDENCE = {"rule_violation", "verified_conflict", "outdated"}


def build_context(db: Session, ws: Workspace, channel: str) -> AuditContext:
    terms = db.scalars(select(Term).where(Term.workspace_id == ws.id)).all()
    retriever = Retriever(db, ws.id)
    validator = EvidenceValidator(retriever, terms, ws.tone_config, ws.palette)
    return AuditContext(workspace=ws, terms=terms, retriever=retriever, validator=validator, channel=channel)


def _dedupe(drafts: list[FindingDraft]) -> list[FindingDraft]:
    drafts = sorted(drafts, key=lambda d: (d.origin == "ai", SEVERITY_RANK[d.severity], d.start))
    kept: list[FindingDraft] = []
    for d in drafts:
        dup = False
        for k in kept:
            same_span = d.start == k.start and d.end == k.end
            if same_span and (d.rule_id == k.rule_id or d.category == k.category):
                dup = True
            elif d.origin == "ai" and d.overlaps(k):
                dup = True  # deterministic findings win over AI on the same text
            elif d.rule_id.startswith(("ABSOLUTE", "UNSUPPORTED", "COMPARATIVE")) and k.category == "compliance" \
                    and k.evidence_status == "rule_violation" and d.overlaps(k):
                dup = True
            if dup:
                break
        if not dup:
            kept.append(d)
    return kept


def finalise_evidence(drafts: list[FindingDraft], validator: EvidenceValidator, text: str) -> list[FindingDraft]:
    """Last line of defence: every displayed evidence item must re-validate and every passage must exist."""
    out = []
    for d in drafts:
        if text[d.start:d.end] != d.passage:
            idx = text.find(d.passage)
            if idx < 0:
                continue
            d.start, d.end = idx, idx + len(d.passage)
        rep = validator.validate(d.evidence)
        superseded = [e for e in d.evidence if e.get("role") == "superseded"]
        d.evidence = rep.kept + [e for e in superseded if e["id"] not in {k["id"] for k in rep.kept}
                                 and validator.materialise(e["id"]) is not None]
        if d.evidence_status in NEEDS_EVIDENCE and not d.evidence:
            d.evidence_status = "ambiguous"
            d.confidence = "low"
            d.explanation = f"{UNABLE_TO_VERIFY} {d.explanation}"
        out.append(d)
    return out


def run_audit(db: Session, ws: Workspace, sub: Submission, actor_role: str) -> AuditRun:
    version = sub.versions[-1]
    text = version.text
    ctx = build_context(db, ws, sub.channel)
    drafts: list[FindingDraft] = []
    drafts += injection_findings(text)
    drafts += run_rules(text, ctx)
    claim_findings, verified = verify_claims(text, ctx)
    drafts += claim_findings
    ai_findings, ai_mode, ai_msg = llm.analyse(text, sub.channel, ctx.retriever, ctx.validator)
    drafts += ai_findings
    drafts = finalise_evidence(_dedupe(drafts), ctx.validator, text)
    drafts.sort(key=lambda d: (SEVERITY_RANK[d.severity], d.start))

    # older open findings on this submission no longer reflect the latest audit
    db.execute(update(Finding).where(Finding.submission_id == sub.id, Finding.status == "open").values(status="stale"))

    sev = {s: 0 for s in SEVERITY_RANK}
    for d in drafts:
        sev[d.severity] += 1
    run = AuditRun(submission_id=sub.id, version_no=version.version_no, ai_mode=ai_mode, ai_status=ai_msg,
                   knowledge_snapshot=ctx.retriever.snapshot(), verified_claims=verified,
                   stats={"total": len(drafts), "by_severity": sev,
                          "deterministic": sum(1 for d in drafts if d.origin in ("rule", "retrieval", "security")),
                          "ai": sum(1 for d in drafts if d.origin == "ai"), "verified_claims": len(verified)})
    db.add(run)
    db.flush()
    for d in drafts:
        db.add(Finding(audit_run_id=run.id, submission_id=sub.id, workspace_id=ws.id, version_no=version.version_no,
                       channel=sub.channel, **{k: v for k, v in d.as_dict().items()}))
    log_event(db, ws.id, actor_role, "audit.run", sub.id,
              f"Brand audit on v{version.version_no}: {len(drafts)} finding(s), {len(verified)} verified claim(s)",
              {"run_id": run.id, "by_severity": sev, "ai_mode": ai_mode})
    db.commit()
    return run
