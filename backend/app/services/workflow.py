"""Correction Engine + Review Workflow. Content is never overwritten: every change is a new version."""
from __future__ import annotations

import re

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import AuditRun, Comment, ContentVersion, Correction, Finding, ReviewDecision, Submission, now
from .audit_log import log_event
from .errors import DomainError




# Draft -> Under Review -> Changes Requested -> Revised -> Approved
TRANSITIONS = {
    "submit": ({"draft": "under_review", "changes_requested": "revised"}, {"creator", "admin"}),
    "request_changes": ({"under_review": "changes_requested", "revised": "changes_requested"}, {"reviewer"}),
    "approve": ({"under_review": "approved", "revised": "approved"}, {"reviewer"}),
}


def latest(sub: Submission) -> ContentVersion:
    return sub.versions[-1]


def latest_run(db: Session, sub: Submission) -> AuditRun | None:
    return db.scalars(select(AuditRun).where(AuditRun.submission_id == sub.id)
                      .order_by(AuditRun.created_at.desc(), AuditRun.id.desc())).first()


def _new_version(db: Session, sub: Submission, text: str, note: str, role: str) -> ContentVersion:
    v = ContentVersion(submission_id=sub.id, version_no=latest(sub).version_no + 1, text=text, change_note=note[:300],
                       created_by=role)
    db.add(v)
    sub.versions.append(v)
    sub.current_version = v.version_no
    sub.updated_at = now()
    if sub.status == "approved":
        sub.status = "draft"  # edited after approval -> needs re-approval
    return v


def _tidy(text: str, start: int, end_new: int) -> tuple[str, int]:
    """Collapse whitespace/punctuation artefacts only around the edited region (e.g. after a removal)."""
    lo, hi = max(0, start - 2), min(len(text), end_new + 2)
    region = text[lo:hi]
    fixed = re.sub(r"[ \t]{2,}", " ", region)
    fixed = re.sub(r" ([,.;:!?])", r"\1", fixed)
    return text[:lo] + fixed + text[hi:], len(region) - len(fixed)


def _locate(text: str, finding: Finding) -> int:
    if text[finding.start:finding.end] == finding.passage:
        return finding.start
    best, best_d = -1, None
    for m in re.finditer(re.escape(finding.passage), text):
        d = abs(m.start() - finding.start)
        if best_d is None or d < best_d:
            best, best_d = m.start(), d
    return best


def apply_correction(db: Session, sub: Submission, finding: Finding, role: str, edited_text: str | None) -> ContentVersion:
    if role not in ("creator", "admin"):
        raise DomainError("Only the content creator can apply corrections.", 403)
    if finding.status != "open":
        raise DomainError(f"This finding is already {finding.status}.", 409)
    if sub.status == "under_review" or sub.status == "revised":
        raise DomainError("Content is with a reviewer. Wait for a decision before editing.", 409)
    replacement = edited_text if edited_text is not None else finding.suggestion
    if replacement is None:
        raise DomainError("This finding has no suggested correction. Provide edited text instead.", 422)
    cur = latest(sub)
    pos = _locate(cur.text, finding)
    if pos < 0:
        raise DomainError("The flagged passage is no longer present in the latest version. Re-run the audit.", 409)
    new_text = cur.text[:pos] + replacement + cur.text[pos + len(finding.passage):]
    new_text, removed = _tidy(new_text, pos, pos + len(replacement))
    action = "edited" if edited_text is not None and edited_text != finding.suggestion else "accepted"
    v = _new_version(db, sub, new_text, f"{action.capitalize()} correction: “{finding.passage[:60]}” → “{replacement[:60]}”", role)
    db.flush()
    db.add(Correction(finding_id=finding.id, submission_id=sub.id, action=action, original=finding.passage,
                      applied_text=replacement, reason=finding.suggestion_reason or "", from_version=cur.version_no,
                      to_version=v.version_no, actor_role=role))
    finding.status = action
    # shift spans of the remaining open findings from the same run; overlapping ones go stale
    delta = len(replacement) - len(finding.passage) - removed
    for other in db.scalars(select(Finding).where(Finding.audit_run_id == finding.audit_run_id, Finding.status == "open",
                                                  Finding.id != finding.id)):
        o_pos = _locate(cur.text, other)
        if o_pos < 0:
            continue
        if o_pos >= pos + len(finding.passage):
            other.start, other.end = o_pos + delta, o_pos + delta + len(other.passage)
        elif o_pos + len(other.passage) <= pos:
            other.start, other.end = o_pos, o_pos + len(other.passage)
        else:
            other.status = "stale"
        if new_text[other.start:other.end] != other.passage and other.status == "open":
            idx = new_text.find(other.passage)
            if idx >= 0:
                other.start, other.end = idx, idx + len(other.passage)
            else:
                other.status = "stale"
        other.version_no = v.version_no
    log_event(db, sub.workspace_id, role, f"correction.{action}", sub.id,
              f"{action.capitalize()} correction for {finding.rule_label or finding.title} (v{cur.version_no} → v{v.version_no})",
              {"finding_id": finding.id, "original": finding.passage, "applied": replacement})
    db.commit()
    return v


def reject_correction(db: Session, sub: Submission, finding: Finding, role: str, reason: str) -> None:
    if role not in ("creator", "admin", "reviewer"):
        raise DomainError("Not permitted.", 403)
    if finding.status != "open":
        raise DomainError(f"This finding is already {finding.status}.", 409)
    finding.status = "rejected"
    db.add(Correction(finding_id=finding.id, submission_id=sub.id, action="rejected", original=finding.passage,
                      applied_text=None, reason=reason[:1000], from_version=latest(sub).version_no, to_version=None,
                      actor_role=role))
    if reason.strip():
        db.add(Comment(submission_id=sub.id, author_role=role, body=f"Dismissed finding “{finding.title}”: {reason.strip()}",
                       version_no=latest(sub).version_no, finding_id=finding.id))
    log_event(db, sub.workspace_id, role, "correction.rejected", sub.id,
              f"Rejected suggestion for {finding.rule_label or finding.title}; original text preserved",
              {"finding_id": finding.id, "reason": reason[:300]})
    db.commit()


def edit_content(db: Session, sub: Submission, text: str, note: str, role: str) -> ContentVersion:
    if role not in ("creator", "admin"):
        raise DomainError("Only the content creator can edit content.", 403)
    if sub.status in ("under_review", "revised"):
        raise DomainError("Content is with a reviewer. Wait for a decision before editing.", 409)
    if text == latest(sub).text:
        raise DomainError("No changes to save.", 422)
    v = _new_version(db, sub, text, note or "Manual edit", role)
    log_event(db, sub.workspace_id, role, "content.edited", sub.id, f"Saved manual edit as v{v.version_no}")
    db.commit()
    return v


def transition(db: Session, sub: Submission, action: str, role: str, note: str) -> ReviewDecision:
    if action not in TRANSITIONS:
        raise DomainError("Unknown action.", 400)
    mapping, roles = TRANSITIONS[action]
    if role not in roles:
        raise DomainError(f"The {role} role cannot perform '{action.replace('_', ' ')}'. Switch role to "
                          f"{' or '.join(sorted(roles))}.", 403)
    if sub.status not in mapping:
        raise DomainError(f"Cannot {action.replace('_', ' ')} while status is '{sub.status.replace('_', ' ')}'.", 409)
    cur = latest(sub)
    run = latest_run(db, sub)
    open_findings = []
    if run is not None:
        open_findings = db.scalars(select(Finding).where(Finding.audit_run_id == run.id, Finding.status == "open")).all()
    if action == "submit":
        if run is None or run.version_no != cur.version_no:
            raise DomainError("Run a brand audit on the latest version before submitting for review.", 409)
    if action == "request_changes" and not note.strip():
        raise DomainError("Explain what needs to change so the creator can act on it.", 422)
    if action == "approve":
        if run is None or run.version_no != cur.version_no:
            raise DomainError("The latest version has not been audited. Ask the creator to re-run the audit.", 409)
        blocking = [f for f in open_findings if f.severity in ("critical", "high")]
        if blocking and len(note.strip()) < 10:
            raise DomainError(f"{len(blocking)} high/critical finding(s) are still open. Add an approval justification "
                              "(10+ characters) to override, or request changes.", 422)
    decision_name = {"submit": "resubmitted" if sub.status == "changes_requested" else "submitted",
                     "request_changes": "changes_requested", "approve": "approved"}[action]
    frm, to = sub.status, mapping[sub.status]
    sub.status = to
    sub.updated_at = now()
    d = ReviewDecision(submission_id=sub.id, decision=decision_name, from_status=frm, to_status=to, note=note[:2000],
                       version_no=cur.version_no, open_findings_at_decision=len(open_findings), actor_role=role)
    db.add(d)
    if note.strip():
        db.add(Comment(submission_id=sub.id, author_role=role, body=note.strip()[:2000], version_no=cur.version_no))
    log_event(db, sub.workspace_id, role, f"review.{decision_name}", sub.id,
              f"{decision_name.replace('_', ' ').capitalize()} v{cur.version_no} ({frm.replace('_', ' ')} → {to.replace('_', ' ')})",
              {"open_findings": len(open_findings), "note": note[:300]})
    db.commit()
    return d
