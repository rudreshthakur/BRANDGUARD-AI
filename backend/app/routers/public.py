"""Unauthenticated endpoints: health, system status, sample content/files, demo workspace creation."""
from __future__ import annotations

import io
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from functools import lru_cache

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..models import Workspace
from ..seed.northstar import GUIDELINES_V4_DRAFT, SAMPLES, create_workspace, documents, seed_northstar
from ..services import llm
from ..services.audit_log import log_event

router = APIRouter(prefix="/api")
APP_VERSION = "1.0.0-round2"
_hits: dict[str, deque] = defaultdict(deque)


@router.get("/health")
def health(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": db_ok,
            "database_backend": db.get_bind().dialect.name, "version": APP_VERSION}


@router.get("/system/status")
def system_status():
    return {"version": APP_VERSION, "ai": llm.ai_status(),
            "retrieval": "BM25 lexical retrieval over approved, workspace-scoped knowledge",
            "limits": {"max_upload_mb": settings.max_upload_mb, "max_content_chars": settings.max_content_chars,
                       "document_types": ["PDF", "DOCX", "TXT", "MD"], "image_types": ["PNG", "JPEG", "WEBP"]},
            "auth": "Demo role switch (Creator / Reviewer / Admin) — not production authentication"}


@router.get("/samples")
def samples():
    return {"synthetic": True, "brand": "Northstar Labs (fictional)", "samples": SAMPLES}


@lru_cache(maxsize=1)
def _sample_images() -> dict[str, bytes]:
    from PIL import Image, ImageDraw

    def make(bg, blocks):
        im = Image.new("RGB", (1080, 1080), bg)
        d = ImageDraw.Draw(im)
        for box, col in blocks:
            d.rectangle(box, fill=col)
        buf = io.BytesIO()
        im.save(buf, "PNG")
        return buf.getvalue()

    return {
        "northstar_onbrand_creative.png": make("#1B2A4A", [((80, 120, 1000, 520), "#F5F7FA"), ((80, 700, 560, 840), "#14B8A6"),
                                                         ((640, 700, 760, 840), "#F59E0B")]),
        "northstar_offbrand_creative.png": make("#7C3AED", [((80, 120, 1000, 600), "#EC4899"), ((80, 700, 560, 840), "#A855F7")]),
    }


@router.get("/samples/files")
def sample_files():
    files = [{"name": n, "kind": "knowledge", "description": "Synthetic Northstar brand document"} for n in documents()]
    files.append({"name": "Northstar_Brand_Guidelines_v4_draft.txt", "kind": "knowledge",
                  "description": "Draft v4 with changed rules and an embedded instruction (tests ingestion safety)"})
    files += [{"name": n, "kind": "image", "description": "Synthetic creative for the Visual Inspector"} for n in _sample_images()]
    return {"files": files}


@router.get("/samples/files/{name}")
def sample_file(name: str):
    docs = documents()
    if name in docs:
        return Response(docs[name], media_type="application/pdf",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})
    if name == "Northstar_Brand_Guidelines_v4_draft.txt":
        return Response(GUIDELINES_V4_DRAFT.encode(), media_type="text/plain",
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})
    imgs = _sample_images()
    if name in imgs:
        return Response(imgs[name], media_type="image/png")
    raise HTTPException(404, "Sample file not found.")


def _rate_limit(ip: str) -> None:
    q = _hits[ip]
    t = time.time()
    while q and t - q[0] > 3600:
        q.popleft()
    if len(q) >= settings.demo_rate_limit_per_hour:
        raise HTTPException(429, "Too many demo workspaces created from this address. Please reuse your current workspace.")
    q.append(t)


def cleanup_expired(db: Session) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=settings.sandbox_ttl_hours)
    ids = [w.id for w in db.scalars(select(Workspace).where(Workspace.is_demo.is_(True)))
           if (w.created_at.replace(tzinfo=timezone.utc) if w.created_at.tzinfo is None else w.created_at) < cutoff]
    if ids:
        db.execute(delete(Workspace).where(Workspace.id.in_(ids)))
        db.commit()
    return len(ids)


@router.post("/workspaces/demo", status_code=201)
def create_demo(request: Request, db: Session = Depends(get_db)):
    _rate_limit(request.client.host if request.client else "unknown")
    cleanup_expired(db)
    ws, token = create_workspace(db, "Northstar Labs demo workspace", "Northstar Labs", True)
    db.commit()
    seed_northstar(db, ws, with_activity=True)
    return {"workspace_id": ws.id, "token": token, "name": ws.name, "brand_name": ws.brand_name, "is_demo": True,
            "expires_in_hours": settings.sandbox_ttl_hours}


class NewWorkspace(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    brand_name: str = Field(min_length=1, max_length=120)


@router.post("/workspaces", status_code=201)
def create_blank(body: NewWorkspace, request: Request, db: Session = Depends(get_db)):
    _rate_limit(request.client.host if request.client else "unknown")
    ws, token = create_workspace(db, body.name.strip(), body.brand_name.strip(), False)
    log_event(db, ws.id, "admin", "workspace.created", None, f"Created empty workspace for {ws.brand_name}")
    db.commit()
    return {"workspace_id": ws.id, "token": token, "name": ws.name, "brand_name": ws.brand_name, "is_demo": False}
