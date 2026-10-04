"""Verify that a quoted span really appears in the source text.

This is the anti-hallucination guard: the model may only keep a rule if its
quoted_span can be found in the document. We match ignoring whitespace, case
and curly-quote differences, then store the document's OWN characters.
"""
from __future__ import annotations

import unicodedata

from rapidfuzz import fuzz

_REPL = {
    "‘": "'", "’": "'", "“": '"', "”": '"',
    "–": "-", "—": "-", " ": " ", " ": " ", "​": "",
}
MIN_SPAN = 20


def normalize_with_map(raw: str) -> tuple[str, list[int]]:
    """Lowercase, collapse whitespace, unify quotes. idx[i] = raw offset of norm char i."""
    out: list[str] = []
    idx: list[int] = []
    prev_space = True
    for i, ch in enumerate(raw):
        ch = _REPL.get(ch, ch)
        for c in unicodedata.normalize("NFKC", ch):
            if c.isspace():
                if prev_space:
                    continue
                out.append(" ")
                idx.append(i)
                prev_space = True
            else:
                lc = c.lower()
                out.append(lc if len(lc) == 1 else c)
                idx.append(i)
                prev_space = False
    if out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


class Haystack:
    def __init__(self, raw: str):
        self.raw = raw
        self.norm, self.idx = normalize_with_map(raw)

    def locate(self, span: str, fuzzy_threshold: float = 92.0):
        """Return (raw_span, method, score) or (None, None, score)."""
        nspan, _ = normalize_with_map(span or "")
        if len(nspan) < MIN_SPAN:
            return None, None, 0.0
        pos = self.norm.find(nspan)
        if pos >= 0:
            s = self.idx[pos]
            e = self.idx[pos + len(nspan) - 1] + 1
            return self.raw[s:e], "exact", 100.0
        al = fuzz.partial_ratio_alignment(nspan, self.norm)
        if al is not None and al.score >= fuzzy_threshold and al.dest_end > al.dest_start:
            s = self.idx[al.dest_start]
            e = self.idx[al.dest_end - 1] + 1
            cand = self.raw[s:e]
            if len(normalize_with_map(cand)[0]) >= MIN_SPAN:
                return cand, "fuzzy", float(al.score)
        return None, None, float(al.score) if al else 0.0
