from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class FindingDraft:
    rule_id: str
    rule_label: str
    category: str  # terminology|brand_name|claim|fact|tone|clarity|compliance|channel|security|messaging
    severity: str  # critical|high|medium|low
    title: str
    passage: str
    start: int
    end: int
    explanation: str
    evidence_status: str
    evidence: list[dict] = field(default_factory=list)
    confidence: str = "high"
    suggestion: str | None = None
    suggestion_reason: str | None = None
    origin: str = "rule"

    def overlaps(self, other: "FindingDraft") -> bool:
        return self.start < other.end and other.start < self.end

    def as_dict(self) -> dict:
        return asdict(self)


SEVERITY_RANK = {"critical": 0, "high": 1, "medium": 2, "low": 3}


def match_case(original: str, replacement: str) -> str:
    """Carry the capitalisation style of the original passage onto a replacement."""
    if not replacement:
        return replacement
    if original.isupper() and len(original) > 1:
        return replacement.upper()
    if original[:1].isupper() and replacement[:1].islower():
        return replacement[:1].upper() + replacement[1:]
    if original[:1].islower() and replacement[:1].isupper() and not replacement[:2].isupper():
        # keep proper nouns (e.g. brand names) capitalised: only lower generic words
        return replacement
    return replacement
