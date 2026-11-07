from __future__ import annotations

import re
from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_workspace, require_admin
from ..models import Chunk, Fact, Source, Term, Workspace
from ..serializers import chunk_out, fact_out, source_out, term_out
from ..services.audit_log import log_event
from ..services.auditor import build_context
from ..services.claims import UNIT_MAP
from ..services.ingestion import approve_source, compare_versions, ingest_document, propose_rules

router = APIRouter(prefix="/api/w/{workspace_id}/knowledge")


def _sources(db: Session, ws: Workspace) -> dict[str, Source]:
    return {s.id: s for s in db.scalars(select(Source).where(Source.workspace_id == ws.id))}


def _get(db: Session, model, ws: Workspace, oid: str):
    obj = db.get(model, oid)
    if obj is None or obj.workspace_id != ws.id:
        raise HTTPException(404, f"{model.__name__} not found.")
    return obj


@router.get("/sources")
def list_sources(ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    rows = db.scalars(select(Source).where(Source.workspace_id == ws.id).order_by(Source.lineage_key, Source.version.desc())).all()
    return {"sources": [source_out(s) for s in rows]}


@router.get("/sources/{source_id}")
def get_source(source_id: str, ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    s = _get(db, Source, ws, source_id)
    out = source_out(s, with_chunks=True)
    out["proposed_rules"] = propose_rules(s.chunks)
    siblings = db.scalars(select(Source).where(Source.workspace_id == ws.id, Source.lineage_key == s.lineage_key,
                                               Source.id != s.id).order_by(Source.version)).all()
    out["other_versions"] = [{"id": x.id, "version": x.version, "status": x.status} for x in siblings]
    return out


@router.post("/sources", status_code=201)
async def upload_source(file: UploadFile = File(...), title: str = Form(default=""), authority: str = Form(default="Brand team"),
                        effective_date: str = Form(default=""), ws: Workspace = Depends(get_workspace),
                        role: str = Depends(require_admin), db: Session = Depends(get_db)):
    data = await file.read()
    eff = effective_date.strip() or None
    if eff and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", eff):
        raise HTTPException(422, "Effective date must be YYYY-MM-DD.")
    src = ingest_document(db, ws.id, file.filename or "upload.txt", data, title or None, role, authority or "Brand team", eff)
    out = source_out(src, with_chunks=True)
    out["proposed_rules"] = propose_rules(src.chunks)
    return out


class ApproveIn(BaseModel):
    accept_proposals: list[int] = Field(default_factory=list, max_length=100)


@router.post("/sources/{source_id}/approve")
def approve(source_id: str, body: ApproveIn, ws: Workspace = Depends(get_workspace), role: str = Depends(require_admin),
            db: Session = Depends(get_db)):
    s = _get(db, Source, ws, source_id)
    approve_source(db, s, role, body.accept_proposals)
    return source_out(s)


@router.post("/sources/{source_id}/reject")
def reject(source_id: str, ws: Workspace = Depends(get_workspace), role: str = Depends(require_admin),
           db: Session = Depends(get_db)):
    s = _get(db, Source, ws, source_id)
    if s.status != "pending_review":
        raise HTTPException(409, f"Only pending sources can be rejected (this one is {s.status}).")
    s.status = "rejected"
    log_event(db, ws.id, role, "knowledge.rejected", None, f"Rejected “{s.title}” v{s.version}; it will not be used as evidence")
    db.commit()
    return source_out(s)


@router.get("/sources/{source_id}/compare/{other_id}")
def compare(source_id: str, other_id: str, ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    a, b = _get(db, Source, ws, source_id), _get(db, Source, ws, other_id)
    old, new = (a, b) if a.version <= b.version else (b, a)
    return compare_versions(old, new)


@router.get("/facts")
def list_facts(ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    srcs = _sources(db, ws)
    rows = db.scalars(select(Fact).where(Fact.workspace_id == ws.id).order_by(Fact.subject, Fact.status, Fact.created_at)).all()
    return {"facts": [fact_out(f, srcs) for f in rows]}


class FactIn(BaseModel):
    statement: str = Field(min_length=5, max_length=600)
    subject: str = Field(default="", max_length=120)
    metric: str | None = Field(default=None, max_length=80)
    value: float | None = None
    unit: str | None = Field(default=None, max_length=30)
    keywords: list[str] = Field(default_factory=list, max_length=15)
    effective_date: str | None = Field(default=None, max_length=10)
    source_id: str | None = None
    page: int | None = Field(default=None, ge=1, le=10000)
    section: str | None = Field(default=None, max_length=200)

    @field_validator("unit")
    @classmethod
    def _unit(cls, v):
        if v is None or v == "":
            return None
        return UNIT_MAP.get(v.strip().lower(), v.strip().lower())

    @field_validator("keywords")
    @classmethod
    def _kw(cls, v):
        return [k.strip()[:40] for k in v if k.strip()]


def _check_fact(body: FactIn, db, ws):
    if (body.value is None) != (body.unit is None):
        raise HTTPException(422, "Provide both a value and a unit for quantified facts, or neither.")
    if body.value is not None and not body.keywords:
        raise HTTPException(422, "Quantified facts need at least one keyword so claims can be matched to them.")
    if body.source_id:
        _get(db, Source, ws, body.source_id)


@router.post("/facts", status_code=201)
def add_fact(body: FactIn, ws: Workspace = Depends(get_workspace), role: str = Depends(require_admin),
             db: Session = Depends(get_db)):
    _check_fact(body, db, ws)
    f = Fact(workspace_id=ws.id, status="approved", metric=body.metric or (re.sub(r"\W+", "_", body.statement.lower())[:40] if body.value is not None else None),
             **body.model_dump(exclude={"metric"}))
    db.add(f)
    db.flush()
    log_event(db, ws.id, role, "fact.approved", None, f"Approved fact {f.id}: {f.statement[:120]}")
    db.commit()
    return fact_out(f, _sources(db, ws))


@router.post("/facts/{fact_id}/supersede", status_code=201)
def supersede_fact(fact_id: str, body: FactIn, ws: Workspace = Depends(get_workspace), role: str = Depends(require_admin),
                   db: Session = Depends(get_db)):
    old = _get(db, Fact, ws, fact_id)
    if old.status != "approved":
        raise HTTPException(409, "Only an approved fact can be superseded.")
    _check_fact(body, db, ws)
    new = Fact(workspace_id=ws.id, status="approved", metric=old.metric, **body.model_dump(exclude={"metric"}))
    db.add(new)
    db.flush()
    old.status, old.superseded_by = "superseded", new.id
    log_event(db, ws.id, role, "fact.superseded", None, f"{old.id} superseded by {new.id}: {new.statement[:120]}",
              {"old": old.statement, "new": new.statement})
    db.commit()
    srcs = _sources(db, ws)
    return {"old": fact_out(old, srcs), "new": fact_out(new, srcs)}


class StatusIn(BaseModel):
    status: Literal["approved", "superseded", "draft", "disabled", "proposed"]


@router.patch("/facts/{fact_id}")
def set_fact_status(fact_id: str, body: StatusIn, ws: Workspace = Depends(get_workspace), role: str = Depends(require_admin),
                    db: Session = Depends(get_db)):
    f = _get(db, Fact, ws, fact_id)
    if body.status not in ("approved", "superseded", "draft"):
        raise HTTPException(422, "Facts can be approved, superseded or draft.")
    f.status = body.status
    log_event(db, ws.id, role, "fact.status", None, f"{f.id} set to {body.status}")
    db.commit()
    return fact_out(f, _sources(db, ws))


@router.get("/terms")
def list_terms(ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    srcs = _sources(db, ws)
    rows = db.scalars(select(Term).where(Term.workspace_id == ws.id).order_by(Term.kind, Term.term)).all()
    return {"terms": [term_out(t, srcs) for t in rows]}


CHANNELS = {"website", "instagram", "advertisement", "email", "presentation", "linkedin", "press_release"}


class TermIn(BaseModel):
    kind: Literal["prohibited", "preferred", "brand_name", "forbidden_claim", "required_phrase", "numeric_limit"]
    term: str = Field(min_length=1, max_length=200)
    replacement: str | None = Field(default=None, max_length=200)
    variants: list[str] = Field(default_factory=list, max_length=20)
    trigger: str | None = Field(default=None, max_length=200)
    limit_value: float | None = None
    severity: Literal["critical", "high", "medium", "low"] = "medium"
    category: Literal["terminology", "tone", "compliance", "channel", "brand_name"] = "terminology"
    explanation: str = Field(default="", max_length=600)
    channels: list[str] | None = None
    source_id: str | None = None
    page: int | None = Field(default=None, ge=1, le=10000)
    section: str | None = Field(default=None, max_length=200)

    @field_validator("trigger")
    @classmethod
    def _trigger(cls, v):
        if v:
            try:
                re.compile(v)
            except re.error as exc:
                raise ValueError(f"invalid trigger pattern: {exc}") from exc
        return v or None

    @field_validator("channels")
    @classmethod
    def _channels(cls, v):
        if not v:
            return None
        bad = [c for c in v if c not in CHANNELS]
        if bad:
            raise ValueError(f"unknown channel(s): {', '.join(bad)}")
        return v


@router.post("/terms", status_code=201)
def add_term(body: TermIn, ws: Workspace = Depends(get_workspace), role: str = Depends(require_admin),
             db: Session = Depends(get_db)):
    if body.kind == "preferred" and not body.variants:
        raise HTTPException(422, "Preferred terms need at least one discouraged variant to detect.")
    if body.kind == "numeric_limit" and body.limit_value is None:
        raise HTTPException(422, "Numeric limits need a limit value.")
    if body.source_id:
        _get(db, Source, ws, body.source_id)
    t = Term(workspace_id=ws.id, status="approved", **body.model_dump())
    if body.kind == "forbidden_claim":
        t.category = "compliance"
    db.add(t)
    db.flush()
    log_event(db, ws.id, role, "rule.created", None, f"Added {t.kind.replace('_', ' ')} rule “{t.term}”")
    db.commit()
    return term_out(t, _sources(db, ws))


@router.patch("/terms/{term_id}")
def set_term_status(term_id: str, body: StatusIn, ws: Workspace = Depends(get_workspace), role: str = Depends(require_admin),
                    db: Session = Depends(get_db)):
    t = _get(db, Term, ws, term_id)
    if body.status not in ("approved", "disabled", "proposed"):
        raise HTTPException(422, "Rules can be approved, disabled or proposed.")
    t.status = body.status
    log_event(db, ws.id, role, "rule.status", None, f"Rule “{t.term}” set to {body.status}")
    db.commit()
    return term_out(t, _sources(db, ws))


@router.get("/evidence/{evidence_id}")
def evidence(evidence_id: str, ws: Workspace = Depends(get_workspace), db: Session = Depends(get_db)):
    """Open a cited source. Returns the stored record plus surrounding context; 404 if it does not exist."""
    ctx = build_context(db, ws, "website")
    ev = ctx.validator.materialise(evidence_id)
    if ev is None:
        raise HTTPException(404, "Evidence not found in this workspace's knowledge base.")
    context = None
    if ev["type"] == "chunk":
        c = db.get(Chunk, evidence_id)
        neighbours = db.scalars(select(Chunk).where(Chunk.source_id == c.source_id).order_by(Chunk.ordinal)).all()
        context = {"source_id": c.source_id, "chunks": [chunk_out(x) for x in neighbours if abs(x.ordinal - c.ordinal) <= 1]}
    elif ev["type"] == "fact":
        f = db.get(Fact, evidence_id)
        ev["fact"] = fact_out(f, _sources(db, ws))
        if f.source_id:
            chunks = db.scalars(select(Chunk).where(Chunk.source_id == f.source_id, Chunk.page == f.page)).all() if f.page else []
            context = {"source_id": f.source_id, "chunks": [chunk_out(x) for x in chunks]}
    elif ev["type"] == "term":
        t = db.get(Term, evidence_id)
        ev["rule"] = term_out(t, _sources(db, ws))
        if t.source_id and t.page:
            chunks = db.scalars(select(Chunk).where(Chunk.source_id == t.source_id, Chunk.page == t.page)).all()
            context = {"source_id": t.source_id, "chunks": [chunk_out(x) for x in chunks]}
    ev["context"] = context
    return ev
