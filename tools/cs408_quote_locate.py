"""M4 helper to locate verbatim quotes in CS408 outline source text.

Public functions: build_keymap and locate_quote. Find a verbatim, contiguous
quote_ref for a fuzzy-matched title inside a
source text -- so a node whose B-side match was only confirmed via the
outline normalizer's aggressive normalization (NFKC + casefold + an I/O
OCR fix + whitespace/punctuation stripping) can still cite a real substring
that tools/verify_tree.py's much gentler norm() (whitespace-only stripping)
will actually locate.

Why this is needed: the historical weighted-tree builder established that a node's
2026 title is "present" in the 2022 source B via
``key(title) in key(full_2022_text)`` -- a comparison with all whitespace,
casing and punctuation removed. That is correct for *detecting* a match, but
the matched span is not recoverable by naively passing the raw title through
verify_tree.py's stricter checker, because verify_tree.py does not strip
punctuation or casefold. This module recovers the *actual* substring of the
source text that produced the key-level match, so it can be cited as a real
quote_ref.

Method: build a "keymap" of the source text -- the same character stream
key() would produce (NFKC, casefold, the 1/o -> i/o OCR fix, punctuation and
whitespace dropped) -- paired with, for every kept character, its index in
the original text. Finding key(raw) as a substring of that keymap's string
then gives the original-text span verbatim, punctuation/whitespace and all.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools"))

from cs408_outline_extract import key as base_key  # noqa: E402

# The exact character class the outline normalizer strips, plus whitespace.
_DROP_RE = re.compile(r"[，。；：、,.;:()（）\[\]【】/\\·'\"“”‘’\s　\xa0]")


class SourceTextLengthChangedError(ValueError):
    """Raised if NFKC/casefold changes the source text's character count.

    The keymap position mapping assumes a 1:1 index correspondence between
    the original text and its NFKC-casefolded form. This holds for the CS408
    syllabus texts in practice (verified empirically); if it ever stops
    holding for a new source, this fails loudly instead of silently
    returning wrong offsets.
    """


def build_keymap(source_text: str) -> tuple[str, list[int]]:
    """Return (kept_chars_joined, original_index_of_each_kept_char)."""
    nfkc = unicodedata.normalize("NFKC", source_text)
    if len(nfkc) != len(source_text):
        raise SourceTextLengthChangedError("NFKC normalization changed the source text's length")
    folded = nfkc.casefold()
    if len(folded) != len(source_text):
        raise SourceTextLengthChangedError("casefold() changed the source text's length")
    folded = folded.replace("1/o", "i/o").replace("l/o", "i/o")
    if len(folded) != len(source_text):
        raise SourceTextLengthChangedError("the i/o OCR fix changed the source text's length")
    kept_chars: list[str] = []
    kept_idx: list[int] = []
    for i, c in enumerate(folded):
        if _DROP_RE.match(c):
            continue
        kept_chars.append(c)
        kept_idx.append(i)
    return "".join(kept_chars), kept_idx


def locate_quote(raw_text: str, source_text: str, keymap: tuple[str, list[int]]) -> str | None:
    """Return the verbatim substring of source_text matching raw_text at the
    key() normalization level, or None if no such substring exists."""
    kstr, kidx = keymap
    rk = base_key(raw_text)
    if not rk:
        return None
    pos = kstr.find(rk)
    if pos == -1:
        return None
    start = kidx[pos]
    end = kidx[pos + len(rk) - 1] + 1
    return source_text[start:end]
