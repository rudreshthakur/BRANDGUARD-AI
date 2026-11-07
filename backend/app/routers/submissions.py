from __future__ import annotations

import difflib
import re
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_role, get_workspace
from ..models import AuditRun, Comment, ContentVersion, Correction, Finding, ReviewDecision, Submission, Workspace
from ..serializers import (comment_out, correction_out, decision_out, finding_out, run_out, submission_summary,
                           version_out)
from ..services.audit_log import log_event
from ..services.auditor import run_audit
from ..services.errors import DomainError
from ..services.workflow import apply_correction, edit_content, latest_run, reject_correction, transition

router = APIRouter(prefix="/api/w/{workspace_id}/submissions")
Channel = Literal["website", "instagram", "advertisement", "email", "presentation", "linkedin", "press_release"]


def _sub(db: Session, ws: Workspace, sid: str) -> Submission:
    s = db.get(Submission, sid)
    if s is None or s.workspace_id != ws.id:
        raise HTTPException(404, "Submission not found.")
    return s


def _clean(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\x00", "")
    return re.sub(r"[ \t]+\n", "\n", text).strip()


def _validate_text(v: str) -> str:
    v = _clean(v)
    if not v:
        raise ValueError("Content is empty.")
    if len(v) > settings.max_content_chars:
        raise ValueError(f"Content exceeds {settings.max_content_chars:,} characters.")
    return v


class SubmissionIn(BaseModel):
    title: str = Field(default="Untitled content", max_length=200)
    channel: Channel = "website"
    text: str = Field(min_length=1)
    run_audit: bool = True

    @field_validator("text")
    @classmethod
    def _text(cls, v: str) -> str:
        return _validate_text(v)


@router.get("")
def list_submissions(status: str | None = None, ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    q = select(Submission).where(Submission.workspace_id == ws.id)
    if status:
        q = q.where(Submission.status.in_(status.split(",")))
    subs = db.scalars(q.order_by(Submission.updated_at.desc())).all()
    out = []
    for s in subs:
        run = latest_run(db, s)
        open_count = db.scalar(select(func.count()).select_from(Finding).where(
            Finding.audit_run_id == run.id, Finding.status == "open")) if run else 0
        out.append(submission_summary(s, run, open_count or 0))
    return {"submissions": out}


@router.post("", status_code=201)
def create_submission(body: SubmissionIn, ws: Workspace = Depends(get_workspace), role: str = Depends(get_role),
                      db: Session = Depends(get_db)):
    if role == "reviewer":
        raise HTTPException(403, "Reviewers inspect and decide on content. Switch to the Creator role to submit content.")
    s = Submission(workspace_id=ws.id, title=body.title.strip() or "Untitled content", channel=body.channel)
    db.add(s)
    db.flush()
    v = ContentVersion(submission_id=s.id, version_no=1, text=body.text, change_note="Original submission", created_by=role)
    db.add(v)
    s.versions.append(v)
    log_event(db, ws.id, role, "submission.created", s.id, f"Created “{s.title}” ({s.channel})")
    db.commit()
    if body.run_audit:
        run_audit(db, ws, s, role)
    return detail(s.id, ws, db)


@router.get("/{submission_id}")
def get_submission(submission_id: str, ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    return detail(submission_id, ws, db)


def detail(submission_id: str, ws: Workspace, db: Session) -> dict:
    s = _sub(db, ws, submission_id)
    run = latest_run(db, s)
    findings = db.scalars(select(Finding).where(Finding.audit_run_id == run.id)).all() if run else []
    open_count = sum(1 for f in findings if f.status == "open")
    out = submission_summary(s, run, open_count)
    out["versions"] = [version_out(v) for v in s.versions]
    out["findings"] = [finding_out(f) for f in sorted(findings, key=lambda f: (
        {"critical": 0, "high": 1, "medium": 2, "low": 3}[f.severity], f.start))]
    out["runs"] = [run_out(r) for r in db.scalars(select(AuditRun).where(AuditRun.submission_id == s.id)
                                                   .order_by(AuditRun.created_at)).all()]
    out["comments"] = [comment_out(c) for c in db.scalars(select(Comment).where(Comment.submission_id == s.id)
                                                          .order_by(Comment.id)).all()]
    out["decisions"] = [decision_out(d) for d in db.scalars(select(ReviewDecision).where(
        ReviewDecision.submission_id == s.id).order_by(ReviewDecision.id)).all()]
    out["corrections"] = [correction_out(c) for c in db.scalars(select(Correction).where(
        Correction.submission_id == s.id).order_by(Correction.id)).all()]
    return out


@router.post("/{submission_id}/audit")
def audit(submission_id: str, ws: Workspace = Depends(get_workspace), role: str = Depends(get_role),
          db: Session = Depends(get_db)):
    s = _sub(db, ws, submission_id)
    run_audit(db, ws, s, role)
    return detail(s.id, ws, db)


class ContentIn(BaseModel):
    text: str = Field(min_length=1)
    note: str = Field(default="", max_length=300)

    @field_validator("text")
    @classmethod
    def _text(cls, v):
        return _validate_text(v)


@router.put("/{submission_id}/content")
def update_content(submission_id: str, body: ContentIn, ws: Workspace = Depends(get_workspace),
                   role: str = Depends(get_role), db: Session = Depends(get_db)):
    s = _sub(db, ws, submission_id)
    edit_content(db, s, body.text, body.note, role)
    return detail(s.id, ws, db)


class AcceptIn(BaseModel):
    edited_text: str | None = Field(default=None, max_length=2000)


def _finding(db: Session, s: Submission, fid: str) -> Finding:
    f = db.get(Finding, fid)
    if f is None or f.submission_id != s.id:
        raise HTTPException(404, "Finding not found.")
    return f


@router.post("/{submission_id}/findings/{finding_id}/accept")
def accept(submission_id: str, finding_id: str, body: AcceptIn, ws: Workspace = Depends(get_workspace),
           role: str = Depends(get_role), db: Session = Depends(get_db)):
    s = _sub(db, ws, submission_id)
    apply_correction(db, s, _finding(db, s, finding_id), role, body.edited_text)
    return detail(s.id, ws, db)


class RejectIn(BaseModel):
    reason: str = Field(default="", max_length=1000)


@router.post("/{submission_id}/findings/{finding_id}/reject")
def reject(submission_id: str, finding_id: str, body: RejectIn, ws: Workspace = Depends(get_workspace),
           role: str = Depends(get_role), db: Session = Depends(get_db)):
    s = _sub(db, ws, submission_id)
    reject_correction(db, s, _finding(db, s, finding_id), role, body.reason)
    return detail(s.id, ws, db)


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=2000)
    finding_id: str | None = None


@router.post("/{submission_id}/comments", status_code=201)
def comment(submission_id: str, body: CommentIn, ws: Workspace = Depends(get_workspace), role: str = Depends(get_role),
            db: Session = Depends(get_db)):
    s = _sub(db, ws, submission_id)
    if body.finding_id:
        _finding(db, s, body.finding_id)
    db.add(Comment(submission_id=s.id, author_role=role, body=body.body.strip(), version_no=s.current_version,
                   finding_id=body.finding_id))
    log_event(db, ws.id, role, "comment.added", s.id, f"{role.capitalize()} commented on v{s.current_version}")
    db.commit()
    return detail(s.id, ws, db)


class TransitionIn(BaseModel):
    action: Literal["submit", "request_changes", "approve"]
    note: str = Field(default="", max_length=2000)


@router.post("/{submission_id}/transition")
def do_transition(submission_id: str, body: TransitionIn, ws: Workspace = Depends(get_workspace),
                  role: str = Depends(get_role), db: Session = Depends(get_db)):
    s = _sub(db, ws, submission_id)
    transition(db, s, body.action, role, body.note)
    return detail(s.id, ws, db)


@router.get("/{submission_id}/diff")
def diff(submission_id: str, frm: int, to: int, ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    s = _sub(db, ws, submission_id)
    versions = {v.version_no: v.text for v in s.versions}
    if frm not in versions or to not in versions:
        raise DomainError("Unknown version number.", 404)
    a, b = re.findall(r"\S+|\s+", versions[frm]), re.findall(r"\S+|\s+", versions[to])
    ops = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=a, b=b, autojunk=False).get_opcodes():
        if tag == "equal":
            ops.append({"op": "equal", "text": "".join(a[i1:i2])})
        else:
            if i2 > i1:
                ops.append({"op": "delete", "text": "".join(a[i1:i2])})
            if j2 > j1:
                ops.append({"op": "insert", "text": "".join(b[j1:j2])})
    return {"from": frm, "to": to, "ops": ops}
