"""Text normalization (file 05, section 2).

1. Unicode normalize, lowercase, collapse whitespace.
2. Transliterate Devanagari to Roman for matching; the original is kept for display.
3. Replace number words with digits.
4. Strip fillers (a separate token list, so intent rules can still see words like "haan").
5. Expand common spelling variants.
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from nlu.lexicon import Lexicon
from nlu.transliterate import has_devanagari, to_roman

SPELLING_VARIANTS = {
    "makhni": "makhani", "makhaani": "makhani", "makhanee": "makhani", "makhnee": "makhani",
    "panir": "paneer", "panner": "paneer", "pneer": "paneer",
    "nan": "naan", "biriyani": "biryani", "briyani": "biryani", "biryaani": "biryani",
    "rotti": "roti", "chiken": "chicken", "chikan": "chicken", "manchuri": "manchurian",
    "lasi": "lassi", "lassee": "lassi", "cofee": "coffee", "coffe": "coffee", "kophi": "coffee", "kophee": "coffee",
    "dhal": "dal", "daal": "dal", "tika": "tikka", "masaala": "masala", "masalla": "masala",
    "naheen": "nahi", "nahin": "nahi", "nahee": "nahi", "nai": "nahi", "nhi": "nahi",
    "thik": "theek", "tik": "theek",
    "chahie": "chahiye", "chaiye": "chahiye", "chahiyee": "chahiye",
    "itana": "itna", "itanaa": "itna", "hee": "hi", "haa": "haan", "haanji": "haan ji",
    "pyaj": "pyaaz", "pyaaj": "pyaaz", "pyaz": "pyaaz", "kold": "cold", "thanks": "thanks",
}

# "do" is two only when it reads as a quantity, not as the imperative ("hata do", "rehne do").
IMPERATIVE_STEMS = {"hata", "de", "bata", "kar", "rakh", "rehne", "rahne", "laga", "bhej", "dikha", "chhod",
                    "likh", "nikal", "jaane", "hone", "pack", "parcel", "bana", "add"}
PRONOUNS_AFTER_DO = {"you", "u", "we", "i", "they", "it", "that"}
STOP_AFTER_A = {"lot", "little", "bit", "few", "minute", "second", "moment"}
MULTIPLIERS = {"dozen": 12.0, "pair": 2.0, "couple": 2.0}

_PUNCT = re.compile(r"[^\w\s.ऀ-ॿ]")
_SPACES = re.compile(r"\s+")


@dataclass
class Normalized:
    original: str
    text: str            # roman, lowercase, numbers as digits, fillers kept
    tokens: list[str]
    clean_tokens: list[str]  # fillers removed
    devanagari: bool
    clean_index: list[int] | None = None  # position of each clean token in `tokens`

    @property
    def clean(self) -> str:
        return " ".join(self.clean_tokens)


def basic(text: str) -> str:
    text = unicodedata.normalize("NFC", text).lower()
    text = to_roman(text)
    text = text.replace("'", "").replace("’", "")
    text = _PUNCT.sub(" ", text)
    text = re.sub(r"(?<!\d)\.|\.(?!\d)", " ", text)
    return _SPACES.sub(" ", text).strip()


def _fmt(n: float) -> str:
    return str(int(n)) if float(n).is_integer() else str(n)


def numbers_to_digits(tokens: list[str], lex: Lexicon) -> list[str]:
    out: list[str] = []
    for i, tok in enumerate(tokens):
        nxt = tokens[i + 1] if i + 1 < len(tokens) else None
        prev = tokens[i - 1] if i > 0 else None
        if tok in MULTIPLIERS and (tok != "couple" or nxt == "of"):
            base = float(out.pop()) if out and _is_num(out[-1]) else 1.0
            out.append(_fmt(base * MULTIPLIERS[tok]))
            continue
        if tok == "of" and prev in MULTIPLIERS:
            continue
        if tok in ("half", "aadha", "adha", "aadhi", "full"):
            out.append(tok)  # sizes, handled as modifiers
            continue
        if tok in lex.numbers:
            if tok == "do" and (nxt is None or nxt in PRONOUNS_AFTER_DO or prev in IMPERATIVE_STEMS):
                out.append(tok)
                continue
            if tok in ("a", "an") and (nxt is None or nxt in STOP_AFTER_A):
                out.append(tok)
                continue
            out.append(_fmt(lex.numbers[tok]))
            continue
        out.append(tok)
    return out


def _is_num(tok: str) -> bool:
    try:
        float(tok)
        return True
    except ValueError:
        return False


def is_number(tok: str) -> bool:
    return _is_num(tok)


def normalize(text: str, lex: Lexicon) -> Normalized:
    base = basic(text)
    tokens = [SPELLING_VARIANTS.get(t, t) for t in base.split()]
    tokens = " ".join(tokens).split()  # variants may expand to two words
    tokens = numbers_to_digits(tokens, lex)
    joined = " " + " ".join(tokens) + " "
    for phrase in sorted(lex.filler_phrases, key=len, reverse=True):
        joined = joined.replace(f" {phrase} ", " ")
    clean = [t for t in joined.split() if t not in lex.fillers]
    index, j = [], 0
    for t in clean:  # clean is a subsequence of tokens
        while j < len(tokens) and tokens[j] != t:
            j += 1
        index.append(j)
        j += 1
    return Normalized(original=text, text=" ".join(tokens), tokens=tokens, clean_tokens=clean,
                      devanagari=has_devanagari(text), clean_index=index)


def normalize_phrase(text: str) -> str:
    """Normalization for lexicon entries (aliases, modifier phrases): no number or filler handling."""
    return " ".join(SPELLING_VARIANTS.get(t, t) for t in basic(text).split())
