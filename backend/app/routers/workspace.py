from __future__ import annotations

import re

from fastapi import APIRouter, Depends, File, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_role, get_workspace, require_admin
from ..models import AuditEvent, Fact, Source, Submission, Term, Workspace
from ..serializers import iso
from ..services import llm
from ..services.analytics import drift_report
from ..services.audit_log import log_event
from ..services.auditor import build_context
from ..services.visual import check_pair, inspect_image

router = APIRouter(prefix="/api/w/{workspace_id}")


@router.get("")
def workspace_summary(ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    def count(model, *conds):
        return db.scalar(select(func.count()).select_from(model).where(model.workspace_id == ws.id, *conds)) or 0
    return {
        "id": ws.id, "name": ws.name, "brand_name": ws.brand_name, "is_demo": ws.is_demo,
        "tone_config": ws.tone_config, "palette": ws.palette, "created_at": iso(ws.created_at),
        "counts": {
            "approved_sources": count(Source, Source.status == "approved"),
            "pending_sources": count(Source, Source.status == "pending_review"),
            "approved_facts": count(Fact, Fact.status == "approved"),
            "superseded_facts": count(Fact, Fact.status == "superseded"),
            "active_rules": count(Term, Term.status == "approved"),
            "submissions": count(Submission),
            "in_review": count(Submission, Submission.status.in_(["under_review", "revised"])),
            "approved_submissions": count(Submission, Submission.status == "approved"),
        },
        "ai": llm.ai_status(),
    }


class PaletteColour(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    hex: str
    role: str = Field(default="accent", max_length=20)
    usage: str = Field(default="", max_length=200)

    @field_validator("hex")
    @classmethod
    def _hex(cls, v: str) -> str:
        if not re.fullmatch(r"#?[0-9a-fA-F]{6}", v.strip()):
            raise ValueError("hex must look like #1B2A4A")
        return "#" + v.strip().lstrip("#").upper()


class SettingsIn(BaseModel):
    flag_repeated_exclamations: bool | None = None
    flag_all_caps: bool | None = None
    max_sentence_words: int | None = Field(default=None, ge=0, le=200)
    voice: str | None = Field(default=None, max_length=500)
    palette: list[PaletteColour] | None = Field(default=None, max_length=20)


@router.put("/settings")
def update_settings(body: SettingsIn, ws: Workspace = Depends(get_workspace), role: str = Depends(require_admin),
                    db: Session = Depends(get_db)):
    tone = dict(ws.tone_config or {})
    for k in ("flag_repeated_exclamations", "flag_all_caps", "max_sentence_words", "voice"):
        v = getattr(body, k)
        if v is not None:
            tone[k] = v
    ws.tone_config = tone
    if body.palette is not None:
        old = {p["hex"]: p for p in ws.palette or []}
        ws.palette = [{**old.get(p.hex, {}), **p.model_dump()} for p in body.palette]
    log_event(db, ws.id, role, "settings.updated", None, "Updated brand voice / palette settings", body.model_dump(exclude_none=True))
    db.commit()
    return {"tone_config": ws.tone_config, "palette": ws.palette}


@router.get("/events")
def events(limit: int = 200, submission_id: str | None = None, ws: Workspace = Depends(get_workspace),
           db: Session = Depends(get_db)):
    q = select(AuditEvent).where(AuditEvent.workspace_id == ws.id)
    if submission_id:
        q = q.where(AuditEvent.submission_id == submission_id)
    rows = db.scalars(q.order_by(AuditEvent.id.desc()).limit(min(max(limit, 1), 500))).all()
    return {"events": [{"id": e.id, "submission_id": e.submission_id, "actor_role": e.actor_role, "action": e.action,
                        "summary": e.summary, "details": e.details, "created_at": iso(e.created_at)} for e in rows]}


@router.get("/analytics")
def analytics(include_samples: bool = True, ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    return drift_report(db, ws.id, include_samples)


@router.post("/visual/inspect")
async def visual_inspect(file: UploadFile = File(...), ws: Workspace = Depends(get_workspace),
                         role: str = Depends(get_role), db: Session = Depends(get_db)):
    data = await file.read()
    result = inspect_image(data, ws.palette or [])
    validator = build_context(db, ws, "advertisement").validator
    for f in result["findings"]:
        f["evidence"] = [ev for ev in (validator.materialise(e["id"]) for e in f["evidence"]) if ev]
    if not ws.palette:
        result["scope_note"] += " No brand palette is configured for this workspace, so palette checks were skipped."
    log_event(db, ws.id, role, "visual.inspected", None,
              f"Visual inspection of “{(file.filename or 'image')[:80]}”: {len(result['findings'])} finding(s)")
    db.commit()
    return result


class ContrastIn(BaseModel):
    foreground: str = Field(max_length=9)
    background: str = Field(max_length=9)


@router.post("/visual/contrast")
def contrast(body: ContrastIn, ws: Workspace = Depends(get_workspace)):
    return check_pair(body.foreground, body.background)
