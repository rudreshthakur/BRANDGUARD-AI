from __future__ import annotations

from sqlalchemy.orm import Session

from ..models import AuditEvent


def log_event(db: Session, workspace_id: str, actor_role: str, action: str, submission_id: str | None = None,
              summary: str = "", details: dict | None = None) -> None:
    db.add(AuditEvent(workspace_id=workspace_id, submission_id=submission_id, actor_role=actor_role, action=action,
                      summary=summary[:400], details=details or {}))
