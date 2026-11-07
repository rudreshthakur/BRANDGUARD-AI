"""Evidence retrieval over APPROVED knowledge only (BM25 lexical ranking, workspace-scoped).

Round 2 uses dependency-free BM25 so the demo is deterministic and works without an embeddings API.
The `Retriever` interface is deliberately small so a pgvector/embedding retriever can be swapped in.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Chunk, Fact, Source
from .text_utils import tokenize


@dataclass
class EvidenceDoc:
    id: str
    type: str  # chunk | fact
    text: str
    document: str
    page: int | None
    section: str | None
    source_id: str | None
    source_version: int | None
    status: str


class BM25:
    def __init__(self, docs: list[EvidenceDoc], k1: float = 1.4, b: float = 0.75):
        self.docs = docs
        self.k1, self.b = k1, b
        self.toks = [tokenize(d.text + " " + (d.section or "")) for d in docs]
        self.tf = [Counter(t) for t in self.toks]
        self.avgdl = (sum(len(t) for t in self.toks) / len(self.toks)) if self.toks else 0.0
        df: Counter[str] = Counter()
        for t in self.toks:
            df.update(set(t))
        n = len(docs)
        self.idf = {w: math.log(1 + (n - f + 0.5) / (f + 0.5)) for w, f in df.items()}

    def search(self, query: str, k: int = 3, min_score: float = 0.0) -> list[tuple[EvidenceDoc, float]]:
        q = tokenize(query)
        if not q or not self.docs:
            return []
        scores = []
        for i, tf in enumerate(self.tf):
            dl = len(self.toks[i]) or 1
            s = 0.0
            for w in q:
                if w not in tf:
                    continue
                f = tf[w]
                s += self.idf.get(w, 0) * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * dl / (self.avgdl or 1)))
            if s > min_score:
                scores.append((self.docs[i], s))
        scores.sort(key=lambda x: -x[1])
        return scores[:k]


class Retriever:
    """Loads the workspace's active approved knowledge and answers evidence queries."""

    def __init__(self, db: Session, workspace_id: str):
        self.workspace_id = workspace_id
        sources = {s.id: s for s in db.scalars(select(Source).where(Source.workspace_id == workspace_id))}
        self.sources = sources
        chunks = db.scalars(select(Chunk).where(Chunk.workspace_id == workspace_id)).all()
        self.chunk_docs = [
            EvidenceDoc(id=c.id, type="chunk", text=c.text, document=sources[c.source_id].title,
                        page=c.page, section=c.section, source_id=c.source_id,
                        source_version=sources[c.source_id].version, status=sources[c.source_id].status)
            for c in chunks if c.source_id in sources and sources[c.source_id].status == "approved"
        ]
        self.facts = db.scalars(select(Fact).where(Fact.workspace_id == workspace_id)).all()
        self.chunk_index = BM25(self.chunk_docs)
        self.by_id: dict[str, EvidenceDoc] = {d.id: d for d in self.chunk_docs}
        for f in self.facts:
            src = sources.get(f.source_id) if f.source_id else None
            self.by_id[f.id] = EvidenceDoc(
                id=f.id, type="fact", text=f.statement, document=src.title if src else "Approved facts register",
                page=f.page, section=f.section, source_id=f.source_id, source_version=src.version if src else None,
                status=f.status)

    def guideline_evidence(self, query: str, k: int = 2, min_score: float = 2.0) -> list[EvidenceDoc]:
        return [d for d, _ in self.chunk_index.search(query, k=k, min_score=min_score)]

    def snapshot(self) -> dict:
        return {
            "approved_sources": sorted(s.title if re.search(r"\bv\d", s.title) else f"{s.title} (version {s.version})"
                                       for s in self.sources.values() if s.status == "approved"),
            "approved_facts": sum(1 for f in self.facts if f.status == "approved"),
            "indexed_chunks": len(self.chunk_docs),
        }
