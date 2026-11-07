"""Request dependencies: workspace isolation (token per workspace) and the demo role switch.

The role header is a clearly labelled DEMO mechanism so judges can play Creator / Reviewer / Admin
without accounts. It is enforced server-side for every action, but it is not production authentication
(see SECURITY notes in ARCHITECTURE.md for the Supabase Auth plan).
"""
from __future__ import annotations

import hmac

from fastapi import Depends, Header, HTTPException, Path
from sqlalchemy.orm import Session

from .db import get_db
from .models import ROLES, Workspace
from .seed.northstar import hash_token


def get_workspace(workspace_id: str = Path(..., max_length=40), x_workspace_token: str = Header(default=""),
                  db: Session = Depends(get_db)) -> Workspace:
    ws = db.get(Workspace, workspace_id)
    if ws is None or not x_workspace_token or not hmac.compare_digest(ws.token_hash, hash_token(x_workspace_token)):
        # identical response for "missing" and "forbidden" so workspace IDs cannot be probed
        raise HTTPException(status_code=404, detail="Workspace not found or access token invalid. Launch a new demo workspace.")
    return ws


def get_role(x_demo_role: str = Header(default="creator")) -> str:
    role = x_demo_role.lower().strip()
    if role not in ROLES:
        raise HTTPException(status_code=400, detail=f"Unknown role '{role}'. Use one of: {', '.join(ROLES)}.")
    return role


def require_admin(role: str = Depends(get_role)) -> str:
    if role != "admin":
        raise HTTPException(status_code=403, detail="Only the Admin role can change approved brand knowledge. Switch role to Admin.")
    return role
