"""Relational data model. Every governed record is scoped to a workspace (organisation)."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (JSON, Boolean, CheckConstraint, DateTime, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def now() -> datetime:
    return datetime.now(timezone.utc)


def uid(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:10].upper()}"


ROLES = ("creator", "reviewer", "admin")
SEVERITIES = ("critical", "high", "medium", "low")
SUBMISSION_STATUSES = ("draft", "under_review", "changes_requested", "revised", "approved")


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uid("WS"))
    name: Mapped[str] = mapped_column(String(120))
    brand_name: Mapped[str] = mapped_column(String(120))
    token_hash: Mapped[str] = mapped_column(String(128))
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    tone_config: Mapped[dict] = mapped_column(JSON, default=dict)
    palette: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Source(Base):
    """A knowledge source (document version or manual entry set). Immutable once approved."""
    __tablename__ = "sources"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uid("SRC"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    lineage_key: Mapped[str] = mapped_column(String(200), index=True)
    version: Mapped[int] = mapped_column(Integer, default=1)
    kind: Mapped[str] = mapped_column(String(30), default="document")  # document | manual
    filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    mime: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="pending_review")  # pending_review|approved|superseded|rejected
    authority: Mapped[str] = mapped_column(String(120), default="Brand team")
    effective_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0)
    injection_flags: Mapped[list] = mapped_column(JSON, default=list)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    chunks: Mapped[list["Chunk"]] = relationship(back_populates="source", cascade="all, delete-orphan",
                                                  order_by="Chunk.ordinal")
    __table_args__ = (
        CheckConstraint("status in ('pending_review','approved','superseded','rejected')", name="ck_source_status"),
        UniqueConstraint("workspace_id", "lineage_key", "version", name="uq_source_version"),
    )


class Chunk(Base):
    __tablename__ = "chunks"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uid("CHUNK"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str] = mapped_column(ForeignKey("sources.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    text: Mapped[str] = mapped_column(Text)
    source: Mapped[Source] = relationship(back_populates="chunks")


class Fact(Base):
    """An approved product fact or approved marketing claim, optionally with a structured numeric value."""
    __tablename__ = "facts"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uid("FACT"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    statement: Mapped[str] = mapped_column(Text)
    subject: Mapped[str] = mapped_column(String(120), default="")
    metric: Mapped[str | None] = mapped_column(String(80), nullable=True)
    value: Mapped[float | None] = mapped_column(Float, nullable=True)
    unit: Mapped[str | None] = mapped_column(String(30), nullable=True)
    keywords: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="approved")  # approved|superseded|draft
    effective_date: Mapped[str | None] = mapped_column(String(20), nullable=True)
    superseded_by: Mapped[str | None] = mapped_column(String(40), nullable=True)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("status in ('approved','superseded','draft')", name="ck_fact_status"),)


class Term(Base):
    """A deterministic governance rule: terminology, brand names, forbidden claims, required phrases, limits."""
    __tablename__ = "terms"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uid("TERM"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    source_id: Mapped[str | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    kind: Mapped[str] = mapped_column(String(30))  # prohibited|preferred|brand_name|forbidden_claim|required_phrase|numeric_limit
    term: Mapped[str] = mapped_column(String(200))
    replacement: Mapped[str | None] = mapped_column(String(200), nullable=True)
    variants: Mapped[list] = mapped_column(JSON, default=list)
    trigger: Mapped[str | None] = mapped_column(String(200), nullable=True)
    limit_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    category: Mapped[str] = mapped_column(String(30), default="terminology")
    severity: Mapped[str] = mapped_column(String(10), default="medium")
    explanation: Mapped[str] = mapped_column(Text, default="")
    channels: Mapped[list | None] = mapped_column(JSON, nullable=True)  # None => all channels
    status: Mapped[str] = mapped_column(String(20), default="approved")  # approved|proposed|disabled
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (
        CheckConstraint("kind in ('prohibited','preferred','brand_name','forbidden_claim','required_phrase','numeric_limit')",
                        name="ck_term_kind"),
        CheckConstraint("severity in ('critical','high','medium','low')", name="ck_term_severity"),
        CheckConstraint("status in ('approved','proposed','disabled')", name="ck_term_status"),
    )


class Submission(Base):
    __tablename__ = "submissions"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uid("SUB"))
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    channel: Mapped[str] = mapped_column(String(30), default="website")
    status: Mapped[str] = mapped_column(String(30), default="draft")
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    is_sample: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    versions: Mapped[list["ContentVersion"]] = relationship(cascade="all, delete-orphan",
                                                            order_by="ContentVersion.version_no")
    __table_args__ = (CheckConstraint(
        "status in ('draft','under_review','changes_requested','revised','approved')", name="ck_sub_status"),)


class ContentVersion(Base):
    """Immutable content snapshot. Accepted corrections and edits always create a new row."""
    __tablename__ = "content_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    change_note: Mapped[str] = mapped_column(String(300), default="")
    created_by: Mapped[str] = mapped_column(String(20), default="creator")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (UniqueConstraint("submission_id", "version_no", name="uq_version"),)


class AuditRun(Base):
    __tablename__ = "audit_runs"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uid("RUN"))
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    ai_mode: Mapped[str] = mapped_column(String(30), default="disabled")
    ai_status: Mapped[str] = mapped_column(String(300), default="")
    knowledge_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    verified_claims: Mapped[list] = mapped_column(JSON, default=list)
    stats: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[str] = mapped_column(String(40), primary_key=True, default=lambda: uid("FND"))
    audit_run_id: Mapped[str] = mapped_column(ForeignKey("audit_runs.id", ondelete="CASCADE"), index=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    version_no: Mapped[int] = mapped_column(Integer)
    rule_id: Mapped[str] = mapped_column(String(60))
    rule_label: Mapped[str] = mapped_column(String(200), default="")
    category: Mapped[str] = mapped_column(String(30))
    severity: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    passage: Mapped[str] = mapped_column(Text)
    start: Mapped[int] = mapped_column(Integer)
    end: Mapped[int] = mapped_column(Integer)
    explanation: Mapped[str] = mapped_column(Text)
    evidence_status: Mapped[str] = mapped_column(String(30))
    evidence: Mapped[list] = mapped_column(JSON, default=list)
    confidence: Mapped[str] = mapped_column(String(10), default="high")
    suggestion: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggestion_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    origin: Mapped[str] = mapped_column(String(20), default="rule")  # rule|retrieval|ai|security
    channel: Mapped[str] = mapped_column(String(30), default="website")
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|accepted|edited|rejected|stale
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    __table_args__ = (CheckConstraint("severity in ('critical','high','medium','low')", name="ck_finding_severity"),)


class Correction(Base):
    __tablename__ = "corrections"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    finding_id: Mapped[str] = mapped_column(ForeignKey("findings.id", ondelete="CASCADE"), index=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    action: Mapped[str] = mapped_column(String(20))  # accepted|edited|rejected
    original: Mapped[str] = mapped_column(Text)
    applied_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    from_version: Mapped[int] = mapped_column(Integer)
    to_version: Mapped[int | None] = mapped_column(Integer, nullable=True)
    actor_role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class Comment(Base):
    __tablename__ = "comments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    author_role: Mapped[str] = mapped_column(String(20))
    body: Mapped[str] = mapped_column(Text)
    version_no: Mapped[int] = mapped_column(Integer)
    finding_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class ReviewDecision(Base):
    __tablename__ = "review_decisions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    submission_id: Mapped[str] = mapped_column(ForeignKey("submissions.id", ondelete="CASCADE"), index=True)
    decision: Mapped[str] = mapped_column(String(30))  # submitted|resubmitted|changes_requested|approved
    from_status: Mapped[str] = mapped_column(String(30))
    to_status: Mapped[str] = mapped_column(String(30))
    note: Mapped[str] = mapped_column(Text, default="")
    version_no: Mapped[int] = mapped_column(Integer)
    open_findings_at_decision: Mapped[int] = mapped_column(Integer, default=0)
    actor_role: Mapped[str] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)


class AuditEvent(Base):
    """Append-only activity log."""
    __tablename__ = "audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    submission_id: Mapped[str | None] = mapped_column(String(40), nullable=True, index=True)
    actor_role: Mapped[str] = mapped_column(String(20))
    action: Mapped[str] = mapped_column(String(60))
    summary: Mapped[str] = mapped_column(String(400), default="")
    details: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
