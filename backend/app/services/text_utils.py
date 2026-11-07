"""Text helpers: offset-preserving sentence splitting, boundary-aware phrase matching, tokenisation."""
from __future__ import annotations

import re
from dataclasses import dataclass

STOPWORDS = set("""a an and are as at be by for from has have in is it its of on or our that the this to was were
will with you your we us they their them can all any more most per than then into over up out not no do does
""".split())

_ABBREV = {"e.g.", "i.e.", "etc.", "vs.", "inc.", "ltd.", "no.", "approx."}


@dataclass
class Sentence:
    text: str
    start: int
    end: int


def split_sentences(text: str) -> list[Sentence]:
    """Split text into sentences, keeping character offsets into the original string."""
    sentences: list[Sentence] = []
    start = 0
    i = 0
    n = len(text)
    while i < n:
        ch = text[i]
        is_break = False
        if ch in ".!?":
            # consume runs like "!!!" or "?!"
            j = i
            while j + 1 < n and text[j + 1] in ".!?":
                j += 1
            nxt = text[j + 1] if j + 1 < n else ""
            if nxt == "" or nxt.isspace():
                word = text[max(0, text.rfind(" ", 0, i) + 1):j + 1].lower()
                prev = text[i - 1] if i > 0 else ""
                if word not in _ABBREV and not (ch == "." and prev.isdigit() and nxt and j + 2 < n and text[j + 2].isdigit()):
                    is_break = True
            i = j
        elif ch == "\n" and i + 1 < n and text[i + 1] == "\n":
            is_break = True
        if is_break:
            seg_end = i + 1
            _push(sentences, text, start, seg_end)
            start = seg_end
        i += 1
    _push(sentences, text, start, n)
    return sentences


def _push(out: list[Sentence], text: str, s: int, e: int) -> None:
    seg = text[s:e]
    stripped = seg.strip()
    if not stripped:
        return
    lead = len(seg) - len(seg.lstrip())
    s2 = s + lead
    out.append(Sentence(text=stripped, start=s2, end=s2 + len(stripped)))


def phrase_pattern(phrase: str, case_sensitive: bool = False) -> re.Pattern[str]:
    """Regex for a phrase with word boundaries that also respects hyphens and flexible whitespace.

    "log in" matches "Log in" and "log  in" but not "blog in" or "log-in-page".
    """
    parts = [re.escape(p) for p in phrase.strip().split()]
    body = r"\s+".join(parts)
    # boundary: not preceded/followed by a word char or hyphen-joined word
    pat = rf"(?<![\w-]){body}(?![\w])(?!-\w)"
    if phrase.strip() and not phrase.strip()[-1].isalnum():
        pat = rf"(?<![\w-]){body}"
    return re.compile(pat, 0 if case_sensitive else re.IGNORECASE)


def find_phrase(text: str, phrase: str, case_sensitive: bool = False) -> list[tuple[int, int]]:
    if not phrase.strip():
        return []
    return [(m.start(), m.end()) for m in phrase_pattern(phrase, case_sensitive).finditer(text)]


_TOKEN = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")


def tokenize(text: str, keep_stopwords: bool = False) -> list[str]:
    toks = _TOKEN.findall(text.lower())
    out = []
    for t in toks:
        if not keep_stopwords and t in STOPWORDS:
            continue
        out.append(stem(t))
    return out


def stem(tok: str) -> str:
    """Very small suffix stripper so 'integrates'/'integrations'/'integration' share a stem."""
    for suf in ("ations", "ation", "ings", "ing", "ies", "es", "s", "ed"):
        if len(tok) > len(suf) + 3 and tok.endswith(suf):
            base = tok[: -len(suf)]
            if suf == "ies":
                base += "y"
            return base
    return tok


def sentence_for(sentences: list[Sentence], pos: int) -> Sentence | None:
    for s in sentences:
        if s.start <= pos < s.end:
            return s
    return None


def normalise_passage(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def trigger_pattern(trigger: str) -> re.Pattern[str]:
    """Admin-defined triggers are plain phrases separated by '|' (never raw regex), so they can't cause
    catastrophic backtracking. Each phrase gets the same boundary-aware matching as terms."""
    phrases = [p.strip() for p in trigger.split("|") if p.strip()][:20]
    if not phrases:
        return re.compile(r"(?!x)x")
    return re.compile("|".join(f"(?:{phrase_pattern(p).pattern})" for p in phrases), re.IGNORECASE)
