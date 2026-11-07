"""Brand knowledge ingestion: Upload -> Validate -> Extract -> Chunk -> Metadata -> Review -> Approve -> Index.

Uploaded documents are untrusted. They never become approved knowledge automatically, extracted rules
are only *proposed*, and instruction-like text is flagged (and remains inert data).
"""
from __future__ import annotations

import difflib
import io
import re
import zipfile
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Chunk, Source, Term, now
from .audit_log import log_event
from .security import scan
from .errors import DomainError

ALLOWED = {".pdf": "application/pdf", ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
           ".txt": "text/plain", ".md": "text/markdown"}
MAX_CHUNK = 900


@dataclass
class Block:
    page: int | None
    section: str | None
    text: str


def detect_type(filename: str, data: bytes) -> str:
    ext = ("." + filename.rsplit(".", 1)[-1].lower()) if "." in filename else ""
    if ext not in ALLOWED:
        raise DomainError(f"Unsupported file type '{ext or 'none'}'. Supported: PDF, DOCX, TXT, MD.", 415)
    if len(data) == 0:
        raise DomainError("The file is empty.", 422)
    if len(data) > settings.max_upload_mb * 1024 * 1024:
        raise DomainError(f"File exceeds the {settings.max_upload_mb} MB limit.", 413)
    if ext == ".pdf" and not data.startswith(b"%PDF"):
        raise DomainError("File content is not a valid PDF.", 415)
    if ext == ".docx":
        if not data.startswith(b"PK"):
            raise DomainError("File content is not a valid DOCX.", 415)
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                if "word/document.xml" not in z.namelist():
                    raise DomainError("DOCX is missing its document body.", 415)
        except zipfile.BadZipFile as exc:
            raise DomainError("DOCX archive is corrupted.", 415) from exc
    if ext in (".txt", ".md"):
        if b"\x00" in data[:4096]:
            raise DomainError("Text file appears to be binary.", 415)
    return ext


def _is_heading(line: str) -> bool:
    s = line.strip()
    if not s or len(s) > 70 or s.endswith((".", ",", ";", ":")) and not re.match(r"^\d+(\.\d+)*\.?\s", s):
        return False
    if re.match(r"^(\d+(\.\d+)*\.?|[A-Z]\.)\s+[A-Z]", s):
        return True
    if s.startswith("#"):
        return True
    words = s.split()
    return len(words) <= 7 and (s.isupper() or sum(w[:1].isupper() for w in words) >= max(1, len(words) - 1)) and not s.endswith(".")


def extract_blocks(ext: str, data: bytes) -> tuple[list[Block], int]:
    if ext == ".pdf":
        import pymupdf
        try:
            doc = pymupdf.open(stream=data, filetype="pdf")
        except Exception as exc:  # noqa: BLE001 - parser errors are user-facing
            raise DomainError("The PDF could not be parsed.", 422) from exc
        if doc.needs_pass:
            raise DomainError("Password-protected PDFs are not supported.", 422)
        blocks: list[Block] = []
        section = None
        for pno, page in enumerate(doc, start=1):
            for line in page.get_text().splitlines():
                if _is_heading(line):
                    section = line.strip().lstrip("#").strip()
                    continue
                if line.strip():
                    blocks.append(Block(pno, section, line.strip()))
        return blocks, doc.page_count
    if ext == ".docx":
        import docx
        try:
            d = docx.Document(io.BytesIO(data))
        except Exception as exc:  # noqa: BLE001
            raise DomainError("The DOCX could not be parsed.", 422) from exc
        blocks, section = [], None
        for p in d.paragraphs:
            t = p.text.strip()
            if not t:
                continue
            if (p.style is not None and p.style.name.lower().startswith(("heading", "title"))) or _is_heading(t):
                section = t
                continue
            blocks.append(Block(None, section, t))
        return blocks, 0
    text = data.decode("utf-8", errors="replace")
    blocks, section = [], None
    for line in text.splitlines():
        if _is_heading(line):
            section = line.strip().lstrip("#").strip()
            continue
        if line.strip():
            blocks.append(Block(None, section, line.strip()))
    return blocks, 0


def chunk_blocks(blocks: list[Block]) -> list[Block]:
    """Group consecutive lines that share a page and section into ~paragraph-sized, source-linked chunks."""
    chunks: list[Block] = []
    for b in blocks:
        last = chunks[-1] if chunks else None
        if last and last.page == b.page and last.section == b.section and len(last.text) + len(b.text) < MAX_CHUNK:
            joiner = " " if not last.text.endswith((".", ":", "!", "?")) else "\n"
            last.text = f"{last.text}{joiner}{b.text}"
        else:
            chunks.append(Block(b.page, b.section, b.text))
    return chunks


Q = r"[\"“”'‘’]"
RULE_PATTERNS = [
    ("preferred", re.compile(rf"use\s+{Q}(?P<a>[^\"“”'‘’]{{2,40}}){Q}\s*(?:,\s*)?(?:instead of|not|rather than)\s+{Q}(?P<b>[^\"“”'‘’]{{2,40}}){Q}", re.I)),
    ("prohibited", re.compile(rf"(?:do not|don't|never)\s+(?:use|say|write)\s+{Q}(?P<a>[^\"“”'‘’]{{2,40}}){Q}(?:[^.]*?use\s+{Q}(?P<b>[^\"“”'‘’]{{2,40}}){Q})?", re.I)),
    ("prohibited", re.compile(rf"avoid\s+(?:the\s+(?:word|term|phrase)\s+)?{Q}(?P<a>[^\"“”'‘’]{{2,40}}){Q}", re.I)),
    ("forbidden_claim", re.compile(rf"(?:never|do not|don't)\s+claim\s+(?:that\s+)?(?:products?\s+(?:are|is)\s+)?{Q}(?P<a>[^\"“”'‘’]{{2,40}}){Q}", re.I)),
    ("brand_name", re.compile(rf"always\s+(?:write|spell)\s+{Q}(?P<a>[^\"“”'‘’]{{2,40}}){Q}", re.I)),
]


def propose_rules(chunks: list[Chunk]) -> list[dict]:
    proposals, seen = [], set()
    for c in chunks:
        for kind, rx in RULE_PATTERNS:
            for m in rx.finditer(c.text):
                a = m.group("a").strip()
                b = (m.groupdict().get("b") or "").strip() or None
                if kind == "preferred":
                    item = {"kind": "preferred", "term": a, "variants": [b] if b else [], "replacement": None}
                elif kind == "prohibited":
                    item = {"kind": "prohibited", "term": a, "variants": [], "replacement": b}
                else:
                    item = {"kind": kind, "term": a, "variants": [], "replacement": None}
                key = (item["kind"], item["term"].lower())
                if key in seen:
                    continue
                seen.add(key)
                item.update({"page": c.page, "section": c.section, "chunk_id": c.id, "excerpt": m.group(0)})
                proposals.append(item)
    return proposals


def lineage_key(title: str) -> str:
    t = re.sub(r"\.(pdf|docx|txt|md)$", "", title.lower())
    t = re.sub(r"\bv(ersion)?\s*\d+(\.\d+)*\b", "", t)
    t = re.sub(r"\(synthetic\)", "", t)
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-") or "document"


def ingest_document(db: Session, workspace_id: str, filename: str, data: bytes, title: str | None, role: str,
                    authority: str = "Brand team", effective_date: str | None = None, synthetic: bool = False) -> Source:
    ext = detect_type(filename, data)
    blocks, pages = extract_blocks(ext, data)
    if not blocks:
        raise DomainError("No extractable text was found (scanned images need OCR, which is not enabled).", 422)
    title = (title or filename).strip()[:200]
    key = lineage_key(title)
    prev = db.scalar(select(func.max(Source.version)).where(Source.workspace_id == workspace_id, Source.lineage_key == key)) or 0
    full_text = "\n".join(b.text for b in blocks)
    flags = [{"excerpt": frag[:120], "offset": s} for s, _, frag in scan(full_text)]
    src = Source(workspace_id=workspace_id, title=title, lineage_key=key, version=prev + 1, kind="document",
                 filename=filename[:255], mime=ALLOWED[ext], status="pending_review", authority=authority[:120],
                 effective_date=effective_date, page_count=pages, injection_flags=flags, is_synthetic=synthetic)
    db.add(src)
    db.flush()
    for i, b in enumerate(chunk_blocks(blocks)):
        db.add(Chunk(workspace_id=workspace_id, source_id=src.id, ordinal=i, page=b.page, section=b.section, text=b.text))
    log_event(db, workspace_id, role, "knowledge.uploaded", None,
              f"Uploaded “{title}” v{src.version} ({len(blocks)} lines, pending review)",
              {"source_id": src.id, "flags": len(flags)})
    db.commit()
    db.refresh(src)
    return src


def approve_source(db: Session, src: Source, role: str, proposals_to_accept: list[int] | None = None) -> Source:
    if src.status not in ("pending_review",):
        raise DomainError(f"Source is already {src.status}.", 409)
    for old in db.scalars(select(Source).where(Source.workspace_id == src.workspace_id, Source.lineage_key == src.lineage_key,
                                               Source.status == "approved", Source.id != src.id)):
        old.status = "superseded"
    src.status = "approved"
    src.approved_at = now()
    created = 0
    if proposals_to_accept:
        props = propose_rules(src.chunks)
        for idx in proposals_to_accept:
            if 0 <= idx < len(props):
                p = props[idx]
                db.add(Term(workspace_id=src.workspace_id, source_id=src.id, kind=p["kind"], term=p["term"],
                            replacement=p["replacement"], variants=p["variants"],
                            category="compliance" if p["kind"] == "forbidden_claim" else "terminology",
                            severity="high" if p["kind"] == "forbidden_claim" else "medium",
                            explanation=f"Extracted from “{src.title}”: {p['excerpt']}", page=p["page"],
                            section=p["section"], status="approved"))
                created += 1
    log_event(db, src.workspace_id, role, "knowledge.approved", None,
              f"Approved “{src.title}” v{src.version} as authoritative ({len(src.chunks)} sections indexed, {created} rule(s) created)",
              {"source_id": src.id})
    db.commit()
    return src


def compare_versions(old: Source, new: Source) -> dict:
    def sections(s: Source) -> dict[str, str]:
        out: dict[str, str] = {}
        for c in s.chunks:
            k = c.section or "(untitled)"
            out[k] = (out.get(k, "") + " " + c.text).strip()
        return out
    a, b = sections(old), sections(new)
    changes = []
    for k in sorted(set(a) | set(b)):
        if k not in a:
            changes.append({"section": k, "change": "added", "new": b[k][:600]})
        elif k not in b:
            changes.append({"section": k, "change": "removed", "old": a[k][:600]})
        elif a[k] != b[k]:
            diff = list(difflib.unified_diff(a[k].split(". "), b[k].split(". "), lineterm="", n=0))[2:]
            changes.append({"section": k, "change": "modified", "old": a[k][:600], "new": b[k][:600], "diff": diff[:20]})
    return {"old": {"id": old.id, "version": old.version}, "new": {"id": new.id, "version": new.version}, "changes": changes}
