"""Prompt-injection heuristics. Content and documents are always treated as data; this module only
surfaces suspicious embedded instructions so humans can see them."""
from __future__ import annotations

import re

from .findings import FindingDraft
from .text_utils import split_sentences

INJECTION_PATTERNS = [
    r"ignore\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above|earlier)\s+(?:instructions|rules|prompts?)",
    r"disregard\s+(?:all\s+)?(?:the\s+)?(?:previous|prior|above|system)\s+(?:instructions|rules|prompts?)",
    r"(?:you\s+are\s+now|act\s+as)\s+(?:an?\s+)?(?:unrestricted|different|new)\s+(?:ai|assistant|model)",
    r"(?:mark|approve|treat)\s+(?:this|the)\s+(?:content|submission|document|text)\s+as\s+(?:approved|compliant|verified)",
    r"(?:reveal|print|show)\s+(?:the\s+)?(?:system\s+prompt|hidden\s+instructions|api\s+key)",
    r"override\s+(?:the\s+)?(?:system|brand|safety)\s+(?:rules|prompt|instructions|policy)",
    r"</?\s*(?:system|instructions?)\s*>",
]
_RX = [re.compile(p, re.IGNORECASE) for p in INJECTION_PATTERNS]


def scan(text: str) -> list[tuple[int, int, str]]:
    hits = []
    for rx in _RX:
        for m in rx.finditer(text):
            hits.append((m.start(), m.end(), m.group(0)))
    hits.sort()
    return hits


def injection_findings(text: str) -> list[FindingDraft]:
    out = []
    hits = scan(text)
    sentences = split_sentences(text)
    done: set[int] = set()
    for hs, he, _ in hits:
        sent = next((x for x in sentences if x.start <= hs < x.end), None)
        s, e = (sent.start, sent.end) if sent else (hs, he)
        if s in done:
            continue
        done.add(s)
        frag = text[s:e]
        out.append(FindingDraft(
            rule_id="SEC-EMBEDDED-INSTRUCTION", rule_label="Embedded instruction", category="security", severity="medium",
            title="Embedded instruction detected", passage=frag, start=s, end=e,
            explanation=("This text reads like an instruction to an AI system. BrandGuard treats submitted content as data, "
                         "so it was not followed and cannot change audit results. Remove it before publishing."),
            evidence_status="security", evidence=[], confidence="medium", suggestion="",
            suggestion_reason="Delete the sentence containing the embedded instruction.", origin="security"))
    return out
