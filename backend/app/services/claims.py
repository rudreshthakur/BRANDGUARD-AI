"""Claim extraction and verification against approved facts.

Outcomes per claim:
  approved           – matches a current approved fact (listed as a verified claim, not a finding)
  verified_conflict  – same metric as an approved fact but a different value
  outdated           – matches a superseded fact value; the current fact is shown
  unsupported        – a claim that needs substantiation but no approved evidence exists
                       ("Unable to verify against approved knowledge" — an evidence gap, not proof of falsity)
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from ..models import Fact
from .evidence import UNABLE_TO_VERIFY
from .findings import FindingDraft
from .rules import AuditContext
from .text_utils import Sentence, split_sentences, tokenize

UNIT_MAP = {
    "%": "%", "percent": "%",
    "hour": "hours", "hours": "hours", "hr": "hours", "hrs": "hours", "h": "hours",
    "minute": "minutes", "minutes": "minutes", "min": "minutes", "mins": "minutes",
    "day": "days", "days": "days", "week": "weeks", "weeks": "weeks",
    "x": "x", "×": "x", "times": "x",
    "app": "integrations", "apps": "integrations", "integration": "integrations", "integrations": "integrations",
    "tools": "integrations",
    "language": "languages", "languages": "languages",
    "user": "users", "users": "users", "seats": "users", "members": "users", "teammates": "users", "customers": "customers",
    "teams": "teams", "countries": "countries", "gb": "gb", "tb": "tb",
    "$": "usd", "₹": "inr", "€": "eur", "£": "gbp",
}

NUMBER_WORDS = {"one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
                "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60,
                "ninety": 90, "hundred": 100}
_NUM = r"\d{1,3}(?:,\d{3})+|\d+(?:\.\d+)?|(?:" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")(?=[\s-])"
_UNITS = (r"%|percent\b|hours?\b|hrs?\b|h\b|minutes?\b|mins?\b|days?\b|weeks?\b|x\b|×|times\b|apps?\b|integrations?\b|tools\b|"
          r"languages?\b|users?\b|seats\b|members\b|teammates\b|customers\b|teams\b|countries\b|GB\b|TB\b")
NUMERIC_CLAIM = re.compile(
    rf"(?P<cur>[$₹€£])\s?(?P<mnum>{_NUM})|(?<![\w.])(?P<num>{_NUM})(?P<plus>\+)?\s*(?:-\s*)?(?P<unit>{_UNITS})",
    re.IGNORECASE)
PROMO_CONTEXT = re.compile(r"\b(off|discount|discounted|save|savings|sale|coupon)\b", re.IGNORECASE)

SUPERLATIVES = [
    (re.compile(r"\bthe\s+best\b", re.I), "best", "high"),
    (re.compile(r"\bbest[- ]in[- ]class\b", re.I), "best", "high"),
    (re.compile(r"(?<!\w)(#\s?1|number\s+one|no\.\s?1)\b", re.I), "#1", "high"),
    (re.compile(r"\bworld'?s\s+(?:best|first|leading|fastest|most\s+\w+)\b", re.I), "world's", "high"),
    (re.compile(r"\bthe\s+(?:fastest|smartest|easiest|most\s+(?:advanced|powerful|secure|trusted|reliable))\b", re.I), "most", "high"),
    (re.compile(r"\bthe\s+only\b", re.I), "only", "medium"),
    (re.compile(r"\b(?:industry|market)[- ]leading\b", re.I), "leading", "medium"),
    (re.compile(r"\b(?:unbeatable|unmatched|unrivalled|unrivaled)\b", re.I), "unmatched", "high"),
    (re.compile(r"\bnever\s+(?:fails|miss(?:es)?)\b", re.I), "never", "high"),
    (re.compile(r"\bguarantee[sd]?\b", re.I), "guaranteed", "high"),
]
COMPARATIVE = re.compile(r"\b(?!(?:rather|other|whether|never|ever|under|over|later|sooner)\b)(?:\w+er|more\s+\w+|less\s+\w+)\s+than\b", re.I)
RELATIVE_AFTER = re.compile(r"^\s*(?:longer|more|less|fewer|faster|quicker|better|shorter|higher|lower|cheaper|extra)\b", re.I)
SOFTEN = [
    (re.compile(r"^the\s+best\b", re.I), "a great"),
    (re.compile(r"^best[- ]in[- ]class\b", re.I), "high-quality"),
    (re.compile(r"^(#\s?1|number\s+one|no\.\s?1)\b", re.I), "a popular"),
    (re.compile(r"^the\s+(fastest|smartest|easiest)\b", re.I), lambda m: "a " + {"fastest": "fast", "smartest": "smart", "easiest": "simple"}[m.group(1).lower()]),
    (re.compile(r"^the\s+most\s+(\w+)\b", re.I), lambda m: "a " + m.group(1)),
    (re.compile(r"^(?:industry|market)[- ]leading\b", re.I), "dependable"),
    (re.compile(r"^world'?s\s+\w+(?:\s+\w+)?\b", re.I), "a"),
    (re.compile(r"^guaranteed\s+to\b", re.I), "designed to"),
    (re.compile(r"^guarantee[sd]?\b", re.I), "designed"),
]
COMPARATIVE_TAIL = re.compile(r"\s+(?:in|on)\s+the\s+(?:market|world|industry)\b|\s+(?:ever|anywhere)\b", re.I)


@dataclass
class NumericClaim:
    text: str
    start: int
    end: int
    value: float
    unit: str
    plus: bool
    num_text: str


def parse_numeric_claims(text: str) -> list[NumericClaim]:
    claims = []
    for m in NUMERIC_CLAIM.finditer(text):
        if m.group("cur"):
            num_text, unit = m.group("mnum"), UNIT_MAP[m.group("cur")]
        else:
            num_text, unit = m.group("num"), UNIT_MAP.get(m.group("unit").lower(), m.group("unit").lower())
        if num_text.lower() in NUMBER_WORDS:
            val = float(NUMBER_WORDS[num_text.lower()])
        else:
            try:
                val = float(num_text.replace(",", ""))
            except ValueError:
                continue
        claims.append(NumericClaim(text=m.group(0), start=m.start(), end=m.end(), value=val, unit=unit,
                                   plus=bool(m.groupdict().get("plus")), num_text=num_text))
    return claims


def _window_tokens(text: str, start: int, end: int, sent: Sentence, words: int = 8) -> set[str]:
    left = text[sent.start:start].split()[-words:]
    right = text[end:sent.end].split()[:words]
    return set(tokenize(" ".join(left + right)))


def _fact_tokens(f: Fact) -> tuple[set[str], set[str]]:
    kw = set(tokenize(" ".join(f.keywords or [])))
    subj = set(tokenize(f.subject or ""))
    return kw, subj


def _pretty(f: Fact) -> str:
    metric = (f.metric or "value").replace("_", " ")
    return f"{metric} ({f.subject})" if f.subject else metric


def _fmt(v: float) -> str:
    return f"{v:,.0f}" if float(v).is_integer() else f"{v:g}"


def _replacement_number(claim: NumericClaim, fact: Fact) -> str:
    new_num = _fmt(fact.value)
    plus = "+" if (f"{_fmt(fact.value)}+" in fact.statement or f"{fact.value:g}+" in fact.statement) else ""
    rel = claim.num_text + ("+" if claim.plus else "")
    idx = claim.text.find(rel) if rel in claim.text else claim.text.find(claim.num_text)
    span = len(rel) if rel in claim.text else len(claim.num_text)
    return claim.text[:idx] + new_num + plus + claim.text[idx + span:]


def verify_claims(text: str, ctx: AuditContext) -> tuple[list[FindingDraft], list[dict]]:
    sentences = split_sentences(text)
    findings: list[FindingDraft] = []
    verified: list[dict] = []
    facts = [f for f in ctx.retriever.facts if f.value is not None and f.unit]
    policy = ctx.retriever.guideline_evidence("claims quantified numbers substantiated approved evidence", k=1)
    policy_ev = [ctx.validator.materialise(d.id, "policy") for d in policy]
    policy_ev = [e for e in policy_ev if e]

    for claim in parse_numeric_claims(text):
        sent = next((s for s in sentences if s.start <= claim.start < s.end), None)
        if sent is None:
            continue
        local = _window_tokens(text, claim.start, claim.end, sent)
        # promotional offers (e.g. "40% off") are governed by numeric limits, not fact verification
        after = text[claim.end:claim.end + 25]
        before = text[max(sent.start, claim.start - 25):claim.start]
        if claim.unit == "%" and (PROMO_CONTEXT.search(after) or PROMO_CONTEXT.search(before)):
            continue
        if RELATIVE_AFTER.match(text[claim.end:sent.end]) and not (claim.unit == "%" and re.match(r"^\s*less\s+time", text[claim.end:sent.end], re.I)):
            # relative claims ("10 hours longer than rivals") are comparisons, not specifications; the
            # comparative check below reports them, so don't misread them as fact conflicts
            if not COMPARATIVE.search(text, claim.end, sent.end):
                findings.append(_unsupported_numeric(text, sent, claim, ctx, policy_ev))
            continue
        scored = []
        for f in facts:
            if f.unit != claim.unit:
                continue
            kw, subj = _fact_tokens(f)
            k = len(local & kw)
            if k == 0:
                continue
            scored.append((k + 0.5 * len(local & subj) + (0.25 if f.status == "approved" else 0), f))
        scored.sort(key=lambda x: -x[0])
        if not scored:
            if claim.unit in ("%", "x", "users", "customers", "teams", "integrations", "languages", "countries",
                              "hours", "minutes", "days"):
                findings.append(_unsupported_numeric(text, sent, claim, ctx, policy_ev))
            continue
        metric = scored[0][1].metric
        same_metric = [f for _, f in scored if f.metric == metric]
        current = [f for f in same_metric if f.status == "approved"]
        old = [f for f in same_metric if f.status == "superseded"]
        if any(abs(f.value - claim.value) < 1e-9 for f in current):
            f = next(f for f in current if abs(f.value - claim.value) < 1e-9)
            ev = ctx.validator.materialise(f.id, "supports")
            verified.append({"passage": claim.text, "start": claim.start, "end": claim.end,
                             "status": "approved", "evidence": [ev] if ev else []})
            continue
        stale = next((f for f in old if abs(f.value - claim.value) < 1e-9), None)
        if current:
            cur = current[0]
            ev_cur = ctx.validator.materialise(cur.id, "current")
            evid = [e for e in [ev_cur] if e]
            if stale:
                ev_old = ctx.validator.materialise(stale.id, "superseded")
                if ev_old:
                    ev_old["status"] = "superseded"
                    evid.append(ev_old)
                findings.append(FindingDraft(
                    rule_id=f"OUTDATED-{cur.metric or cur.id}", rule_label=f"Outdated spec: {_pretty(cur)}",
                    category="fact", severity="high", title=f"Outdated specification “{claim.text}”",
                    passage=claim.text, start=claim.start, end=claim.end,
                    explanation=(f"“{claim.text}” matches a superseded specification"
                                 f"{' (effective until ' + cur.effective_date + ')' if cur.effective_date else ''}. "
                                 f"The current approved value is: {cur.statement}"),
                    evidence_status="outdated", evidence=evid, confidence="high",
                    suggestion=_replacement_number(claim, cur),
                    suggestion_reason="Update only the number to the current approved specification.", origin="retrieval"))
            else:
                findings.append(FindingDraft(
                    rule_id=f"CONFLICT-{cur.metric or cur.id}", rule_label=f"Fact conflict: {_pretty(cur)}",
                    category="fact", severity="high", title=f"Conflicts with approved fact: “{claim.text}”",
                    passage=claim.text, start=claim.start, end=claim.end,
                    explanation=f"“{claim.text}” contradicts the approved fact: {cur.statement}",
                    evidence_status="verified_conflict", evidence=evid, confidence="high",
                    suggestion=_replacement_number(claim, cur),
                    suggestion_reason="Replace the value with the approved figure; surrounding wording is preserved.",
                    origin="retrieval"))
        else:
            findings.append(_unsupported_numeric(text, sent, claim, ctx, policy_ev, ambiguous=True))

    q_findings, q_verified = _qualitative_claims(text, sentences, ctx, policy_ev)
    findings.extend(q_findings)
    verified.extend(q_verified)
    return findings, verified


def _alternatives(ctx: AuditContext, claim: NumericClaim) -> str:
    alts = [f.statement for f in ctx.retriever.facts if f.status == "approved" and f.unit == claim.unit][:2]
    return (" Approved claims you could use instead: " + " | ".join(f"“{a}”" for a in alts)) if alts else ""


def _unsupported_numeric(text, sent: Sentence, claim: NumericClaim, ctx, policy_ev, ambiguous=False) -> FindingDraft:
    start, end = claim.start, claim.end
    suggestion = None
    m = re.search(rf"\bby\s+{re.escape(claim.text)}", text[sent.start:sent.end], re.I)
    mx = re.match(r"\s+(faster|quicker|better|easier|more\s+\w+|less\s+\w+)", text[claim.end:sent.end], re.I)
    if m:
        start, end = sent.start + m.start(), sent.start + m.end()
        suggestion = ""
    elif claim.unit == "x" and mx:
        end = claim.end + mx.end()
        suggestion = mx.group(1)
    passage = text[start:end]
    status = "ambiguous" if ambiguous else "unsupported"
    return FindingDraft(
        rule_id=f"UNSUPPORTED-{claim.unit}", rule_label=f"Unverified figure ({claim.unit})",
        category="claim", severity="high",
        title=f"Unsupported numerical claim “{claim.text}”",
        passage=passage, start=start, end=end,
        explanation=(f"{UNABLE_TO_VERIFY} No approved fact substantiates “{claim.text}” in this context. "
                     "This is an evidence gap, not proof that the claim is false."
                     + (" Related facts exist only as superseded versions." if ambiguous else "")),
        evidence_status=status, evidence=list(policy_ev), confidence="medium",
        suggestion=suggestion,
        suggestion_reason=(("Remove the unverified figure and keep the rest of the message." if suggestion is not None
                            else "Replace with an approved figure or attach substantiation for approval.")
                           + _alternatives(ctx, claim)),
        origin="retrieval")


CORE_PHRASES = {
    "best": [r"\bbest\b"], "#1": [r"#\s?1\b", r"\bnumber\s+one\b", r"\bno\.\s?1\b"], "world's": [r"\bworld'?s\b"],
    "most": [r"\bmost\b", r"\bfastest\b", r"\bsmartest\b", r"\beasiest\b"], "only": [r"\bonly\b"],
    "leading": [r"\bleading\b"], "unmatched": [r"\bunmatched\b", r"\bunbeatable\b", r"\bunrivall?ed\b"],
    "never": [r"\bnever\s+fails?\b"], "guaranteed": [r"\bguarantee"],
}


def _support_for(ctx: AuditContext, core: str, sentence: str) -> Fact | None:
    """An approved fact substantiates a superlative only if it contains the same superlative phrase AND
    shares topical keywords with the sentence (excluding the superlative word itself)."""
    pats = [re.compile(p, re.I) for p in CORE_PHRASES.get(core, [re.escape(core)])]
    toks = set(tokenize(sentence)) - set(tokenize(core))
    for f in ctx.retriever.facts:
        if f.status != "approved" or not any(p.search(f.statement) for p in pats):
            continue
        topical = set(tokenize(" ".join(f.keywords or []) + " " + f.subject)) - set(tokenize(core))
        if toks & topical:
            return f
    return None


def _clause_end(text: str, start: int, limit: int) -> int:
    m = re.search(r"[,.;:!?]|\s+(?:and|but|so|because|with)\s+|\s+[-–—]\s+", text[start:limit])
    return start + m.start() if m else limit


def _qualitative_claims(text: str, sentences: list[Sentence], ctx: AuditContext, policy_ev):
    out: list[FindingDraft] = []
    verified: list[dict] = []
    for sent in sentences:
        for rx, core, sev in SUPERLATIVES:
            for m in rx.finditer(text, sent.start, sent.end):
                support = _support_for(ctx, core, sent.text)
                end = _clause_end(text, m.start(), sent.end)
                passage = text[m.start():end].rstrip()
                if len(passage.split()) > 9:
                    passage = " ".join(passage.split()[:9])
                end = m.start() + len(passage)
                if support:
                    ev = ctx.validator.materialise(support.id, "supports")
                    verified.append({"passage": passage, "start": m.start(), "end": end, "status": "approved",
                                     "evidence": [ev] if ev else []})
                    continue
                out.append(FindingDraft(
                    rule_id=f"ABSOLUTE-{core}", rule_label=f"Unverified superlative ({core})", category="claim",
                    severity=sev, title=f"Unsubstantiated absolute claim “{passage}”", passage=passage,
                    start=m.start(), end=end,
                    explanation=(f"{UNABLE_TO_VERIFY} Superlative and absolute statements need approved substantiation "
                                 "(e.g. an independent ranking or approved claim). None was found. "
                                 "This is an evidence gap, not proof that the claim is false."),
                    evidence_status="unsupported", evidence=list(policy_ev), confidence="medium",
                    suggestion=_soften(passage),
                    suggestion_reason="Soften only the absolute wording so the message stays intact, or attach substantiation.",
                    origin="retrieval"))
        for m in COMPARATIVE.finditer(text, sent.start, sent.end):
            end = _clause_end(text, m.end(), sent.end)
            passage = text[m.start():end].rstrip()
            out.append(FindingDraft(
                rule_id="COMPARATIVE", rule_label="Comparative claim", category="claim", severity="medium",
                title=f"Comparative claim “{passage}”", passage=passage, start=m.start(), end=m.start() + len(passage),
                explanation=f"{UNABLE_TO_VERIFY} Comparisons with other products need approved, current substantiation.",
                evidence_status="unsupported", evidence=list(policy_ev), confidence="medium", suggestion=None,
                suggestion_reason="Remove the comparison or link it to an approved comparative claim.", origin="retrieval"))
    return out, verified


def _soften(passage: str) -> str | None:
    for rx, rep in SOFTEN:
        if rx.search(passage):
            new = rx.sub(rep if isinstance(rep, str) else rep, passage, count=1)
            new = COMPARATIVE_TAIL.sub("", new)
            new = re.sub(r"\ba\s+([aeiou])", r"an \1", new, flags=re.I)
            return new.strip()
    return None
