"""Deterministic rule engine. Exact, explainable checks that never depend on an LLM."""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Term, Workspace
from .evidence import EvidenceValidator
from .findings import FindingDraft, match_case
from .retrieval import Retriever
from .text_utils import Sentence, find_phrase, sentence_for, split_sentences

CAPS_ALLOW = {"AES", "HIPAA", "GDPR", "API", "SSO", "USA", "UK", "EU", "CEO", "FAQ", "PDF", "iOS", "AI", "B2B", "SaaS",
              "WCAG", "ISO", "SOC", "USD", "INR"}


@dataclass
class AuditContext:
    workspace: Workspace
    terms: list[Term]
    retriever: Retriever
    validator: EvidenceValidator
    channel: str


def _applies(term: Term, channel: str) -> bool:
    return term.status == "approved" and (not term.channels or channel in term.channels)


def _term_ev(ctx: AuditContext, term: Term) -> list[dict]:
    ev = ctx.validator.materialise(term.id)
    return [ev] if ev else []


def run_rules(text: str, ctx: AuditContext) -> list[FindingDraft]:
    sentences = split_sentences(text)
    out: list[FindingDraft] = []
    for term in ctx.terms:
        if not _applies(term, ctx.channel):
            continue
        handler = _HANDLERS.get(term.kind)
        if handler:
            out.extend(handler(text, sentences, term, ctx))
    out.extend(_tone_checks(text, sentences, ctx))
    return out


def _prohibited(text, sentences, term: Term, ctx):
    res = []
    for s, e in find_phrase(text, term.term):
        found = text[s:e]
        sugg = match_case(found, term.replacement) if term.replacement else None
        res.append(FindingDraft(
            rule_id=term.id, rule_label=f"Prohibited: “{term.term}”", category=term.category,
            severity=term.severity, title=f"Prohibited term “{found}”", passage=found, start=s, end=e,
            explanation=(f"“{found}” is on the approved prohibited-terms list. {term.explanation}").strip(),
            evidence_status="rule_violation", evidence=_term_ev(ctx, term), confidence="high",
            suggestion=sugg,
            suggestion_reason=(f"Replace with the approved alternative “{term.replacement}”; the rest of the sentence is unchanged."
                               if sugg else "No approved alternative is configured — rephrase this word manually."),
        ))
    return res


def _preferred(text, sentences, term: Term, ctx):
    res = []
    for variant in term.variants or []:
        for s, e in find_phrase(text, variant):
            found = text[s:e]
            res.append(FindingDraft(
                rule_id=term.id, rule_label=f"Preferred: “{term.term}”", category=term.category,
                severity=term.severity, title=f"Use preferred term “{term.term}”", passage=found, start=s, end=e,
                explanation=f"The brand's preferred terminology is “{term.term}” instead of “{found}”. {term.explanation}".strip(),
                evidence_status="rule_violation", evidence=_term_ev(ctx, term), confidence="high",
                suggestion=match_case(found, term.term),
                suggestion_reason=f"Swap only the non-preferred wording for “{term.term}”.",
            ))
    return res


def _brand_name(text, sentences, term: Term, ctx):
    res = []
    seen: set[tuple[int, int]] = set()
    for candidate in [term.term, *(term.variants or [])]:
        for s, e in find_phrase(text, candidate):
            found = text[s:e]
            if (s, e) in seen or found == term.term:
                continue
            seen.add((s, e))
            res.append(FindingDraft(
                rule_id=term.id, rule_label=f"Brand name: {term.term}", category="brand_name",
                severity=term.severity, title=f"Incorrect brand/product name “{found}”", passage=found, start=s, end=e,
                explanation=f"The approved name is written exactly as “{term.term}”. {term.explanation}".strip(),
                evidence_status="rule_violation", evidence=_term_ev(ctx, term), confidence="high",
                suggestion=term.term, suggestion_reason="Use the exact approved spelling and capitalisation.",
            ))
    return res


def _forbidden_claim(text, sentences, term: Term, ctx):
    res = []
    for s, e in find_phrase(text, term.term):
        found = text[s:e]
        sugg = match_case(found, term.replacement) if term.replacement else None
        res.append(FindingDraft(
            rule_id=term.id, rule_label=f"Forbidden claim: “{term.term}”", category="compliance",
            severity=term.severity, title=f"Forbidden claim “{found}”", passage=found, start=s, end=e,
            explanation=f"This claim is explicitly forbidden by approved policy. {term.explanation}".strip(),
            evidence_status="rule_violation", evidence=_term_ev(ctx, term), confidence="high",
            suggestion=sugg,
            suggestion_reason=("Replace with approved, substantiated wording." if sugg
                               else "Remove this claim or escalate to legal/compliance for approval."),
        ))
    return res


def _required_phrase(text, sentences: list[Sentence], term: Term, ctx):
    if find_phrase(text, term.term):
        return []
    anchor: Sentence | None = None
    if term.trigger:
        m = re.search(term.trigger, text, re.IGNORECASE)
        if not m:
            return []
        anchor = sentence_for(sentences, m.start())
    elif sentences:
        anchor = sentences[-1]
    if anchor is None:
        return []
    # anchor on the sentence's final word only, so the fix is minimal and doesn't overlap other findings
    last = re.search(r"\S+$", anchor.text)
    a_start = anchor.start + (last.start() if last else 0)
    passage = text[a_start:anchor.end]
    return [FindingDraft(
        rule_id=term.id, rule_label=f"Required phrase: “{term.term}”",
        category="channel" if term.channels else "compliance", severity=term.severity,
        title=f"Missing required phrase “{term.term}”", passage=passage, start=a_start, end=anchor.end,
        explanation=term.explanation or f"Content of this type must include “{term.term}”.",
        evidence_status="rule_violation", evidence=_term_ev(ctx, term), confidence="high",
        suggestion=f"{passage} {term.term}",
        suggestion_reason="Append the required phrase after this sentence; existing wording is preserved.",
    )]


_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*(%|percent\b)", re.IGNORECASE)


def _numeric_limit(text, sentences: list[Sentence], term: Term, ctx):
    res = []
    trig = re.compile(term.trigger or term.term, re.IGNORECASE)
    for sent in sentences:
        if not trig.search(sent.text):
            continue
        for m in _PCT.finditer(sent.text):
            val = float(m.group(1))
            if term.limit_value is not None and val > term.limit_value:
                s, e = sent.start + m.start(), sent.start + m.end()
                limit_txt = f"{term.limit_value:g}{m.group(2) if m.group(2) == '%' else ' percent'}"
                res.append(FindingDraft(
                    rule_id=term.id, rule_label=f"Limit: {term.term}", category="compliance",
                    severity=term.severity, title=f"{m.group(0)} exceeds the approved limit of {term.limit_value:g}%",
                    passage=text[s:e], start=s, end=e,
                    explanation=term.explanation or f"Values above {term.limit_value:g}% are not permitted.",
                    evidence_status="rule_violation", evidence=_term_ev(ctx, term), confidence="high",
                    suggestion=limit_txt, suggestion_reason="Reduce the value to the approved maximum, or obtain an approved exception.",
                ))
    return res


_HANDLERS = {
    "prohibited": _prohibited, "preferred": _preferred, "brand_name": _brand_name,
    "forbidden_claim": _forbidden_claim, "required_phrase": _required_phrase, "numeric_limit": _numeric_limit,
}


def _tone_ev(ctx: AuditContext, key: str, query: str) -> list[dict]:
    ev = [ctx.validator.materialise(f"SETTING:tone.{key}")]
    ev += [ctx.validator.materialise(d.id, "policy") for d in ctx.retriever.guideline_evidence(query, k=1)]
    return [e for e in ev if e]


def _tone_checks(text: str, sentences: list[Sentence], ctx: AuditContext) -> list[FindingDraft]:
    cfg = ctx.workspace.tone_config or {}
    out: list[FindingDraft] = []
    if cfg.get("flag_repeated_exclamations", True):
        for m in re.finditer(r"!{2,}", text):
            out.append(FindingDraft(
                rule_id="TONE-EXCLAMATION", rule_label="Tone: repeated exclamation marks", category="tone",
                severity="low", title="Repeated exclamation marks", passage=m.group(0), start=m.start(), end=m.end(),
                explanation="The brand voice is calm and confident; repeated exclamation marks read as hype.",
                evidence_status="rule_violation", evidence=_tone_ev(ctx, "flag_repeated_exclamations", "exclamation marks voice calm"),
                confidence="high", suggestion=".", suggestion_reason="End the sentence with a single full stop."))
    if cfg.get("flag_all_caps", True):
        for m in re.finditer(r"\b[A-Z]{4,}\b", text):
            w = m.group(0)
            if w in CAPS_ALLOW:
                continue
            out.append(FindingDraft(
                rule_id="TONE-CAPS", rule_label="Tone: all-caps emphasis", category="tone", severity="low",
                title=f"All-caps word “{w}”", passage=w, start=m.start(), end=m.end(),
                explanation="Avoid shouting with capital letters; use sentence case.",
                evidence_status="rule_violation", evidence=_tone_ev(ctx, "flag_all_caps", "capital letters sentence case"),
                confidence="high", suggestion=w.capitalize(), suggestion_reason="Sentence-case the word."))
    max_words = int(cfg.get("max_sentence_words", 0) or 0)
    if max_words:
        for s in sentences:
            n = len(s.text.split())
            if n > max_words:
                out.append(FindingDraft(
                    rule_id="CLARITY-LENGTH", rule_label="Clarity: sentence length", category="clarity", severity="low",
                    title=f"Long sentence ({n} words)", passage=s.text, start=s.start, end=s.end,
                    explanation=f"Sentences over {max_words} words are harder to scan and less accessible.",
                    evidence_status="rule_violation", evidence=_tone_ev(ctx, "max_sentence_words", "short sentences clarity readable"),
                    confidence="medium", suggestion=None, suggestion_reason="Consider splitting this sentence in two."))
    return out
