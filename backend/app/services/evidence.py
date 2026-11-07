"""Evidence Traceability Engine: builds evidence records from the database and validates every reference.

Rule: evidence shown to users is always re-materialised from stored records by ID. Text supplied by
an LLM (or anything else) is never displayed as evidence. Unknown IDs are dropped and logged.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from ..models import Term
from .retrieval import EvidenceDoc, Retriever
from .text_utils import tokenize

UNABLE_TO_VERIFY = "Unable to verify against approved knowledge."

EVIDENCE_STATUS_LABELS = {
    "rule_violation": "Confirmed rule violation",
    "verified_conflict": "Verified conflict with approved fact",
    "outdated": "Matches a superseded (outdated) fact",
    "unsupported": "Unsupported claim — no approved evidence",
    "ambiguous": "Ambiguous evidence",
    "approved": "Approved claim",
    "security": "Security notice",
    "contextual": "Contextual AI observation",
}


TONE_SETTING_LABELS = {
    "flag_repeated_exclamations": "Flag repeated exclamation marks",
    "flag_all_caps": "Flag all-caps emphasis",
    "max_sentence_words": "Maximum words per sentence",
}


def _clip(text: str, limit: int = 600) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    stop = max(cut.rfind(". "), cut.rfind("; "))
    return (cut[:stop + 1] if stop > limit * 0.5 else cut[:cut.rfind(" ")]) + " …"


def doc_to_evidence(doc: EvidenceDoc, role: str = "supports") -> dict:
    return {
        "id": doc.id,
        "type": doc.type,
        "role": role,  # supports | contradicts | current | superseded | policy
        "document": doc.document,
        "version": doc.source_version,
        "page": doc.page,
        "section": doc.section,
        "excerpt": _clip(doc.text),
        "status": doc.status,
    }


def term_to_evidence(term: Term, source_title: str | None, source_version: int | None = None) -> dict:
    kind_label = {
        "prohibited": "Prohibited term", "preferred": "Preferred terminology", "brand_name": "Brand name rule",
        "forbidden_claim": "Forbidden claim", "required_phrase": "Required phrase", "numeric_limit": "Numeric limit",
    }[term.kind]
    rule_text = term.explanation or kind_label
    if term.kind in ("prohibited", "preferred", "brand_name") and term.replacement:
        rule_text = f"{kind_label}: use “{term.replacement}”. {term.explanation}".strip()
    return {
        "id": term.id,
        "type": "term",
        "role": "policy",
        "document": source_title or "Terminology register",
        "version": source_version,
        "page": term.page,
        "section": term.section,
        "excerpt": rule_text,
        "status": term.status,
    }


@dataclass
class ValidationReport:
    kept: list[dict] = field(default_factory=list)
    rejected: list[dict] = field(default_factory=list)


class EvidenceValidator:
    def __init__(self, retriever: Retriever, terms: list[Term], tone_config: dict | None = None,
                 palette: list | None = None):
        self.retriever = retriever
        self.terms = {t.id: t for t in terms}
        self.tone_config = tone_config or {}
        self.palette = {p["hex"].upper(): p for p in (palette or []) if p.get("hex")}

    def materialise(self, evidence_id: str, role: str = "supports") -> dict | None:
        if evidence_id.startswith("SETTING:tone."):
            key = evidence_id.split(".", 1)[1]
            if key not in self.tone_config or not self.tone_config.get(key):
                return None
            label = TONE_SETTING_LABELS.get(key, key)
            return {"id": evidence_id, "type": "setting", "role": "policy", "document": "Workspace tone settings",
                    "version": None, "page": None, "section": "Brand voice", "excerpt": f"{label}: {self.tone_config[key]}",
                    "status": "approved"}
        if evidence_id.startswith("PALETTE:"):
            p = self.palette.get(evidence_id.split(":", 1)[1].upper())
            if not p:
                return None
            return {"id": evidence_id, "type": "palette", "role": "policy",
                    "document": p.get("source", "Brand palette"), "version": None, "page": p.get("page"),
                    "section": "Colour palette", "excerpt": f"{p['name']} {p['hex'].upper()} — {p.get('usage', '')}".strip(" —"),
                    "status": "approved"}
        if evidence_id in self.retriever.by_id:
            return doc_to_evidence(self.retriever.by_id[evidence_id], role)
        if evidence_id in self.terms:
            t = self.terms[evidence_id]
            src = self.retriever.sources.get(t.source_id) if t.source_id else None
            return term_to_evidence(t, src.title if src else None, src.version if src else None)
        return None

    def validate(self, items: list[dict], allowed_ids: set[str] | None = None,
                 claim_text: str | None = None, require_overlap: bool = False) -> ValidationReport:
        """Keep only evidence that exists in this workspace (and, optionally, was actually retrieved and
        shares vocabulary with the claim). Excerpts are rebuilt from the database."""
        rep = ValidationReport()
        seen: set[str] = set()
        for item in items:
            eid = str(item.get("id", "")).strip()
            role = item.get("role", "supports")
            if not eid or eid in seen:
                continue
            seen.add(eid)
            if allowed_ids is not None and eid not in allowed_ids:
                rep.rejected.append({"id": eid, "reason": "not in retrieved evidence set"})
                continue
            ev = self.materialise(eid, role)
            if ev is None:
                rep.rejected.append({"id": eid, "reason": "unknown evidence id"})
                continue
            if ev["status"] in ("rejected", "pending_review", "draft", "disabled", "proposed"):
                rep.rejected.append({"id": eid, "reason": f"evidence not approved ({ev['status']})"})
                continue
            if require_overlap and claim_text:
                overlap = set(tokenize(claim_text)) & set(tokenize(ev["excerpt"] + " " + (ev.get("section") or "")))
                if not overlap:
                    rep.rejected.append({"id": eid, "reason": "evidence does not share terms with the claim"})
                    continue
            rep.kept.append(ev)
        return rep
