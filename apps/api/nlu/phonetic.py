"""Indic-aware phonetic keys (file 05, section 5).

Collapses aa/a, ee/i, oo/u, v/w, sh/s, ph/f, th/t, dh/d, aspirates, doubled letters and the
trailing a/h, then keeps the consonant skeleton (first letter, consonants, final vowel), so
makhani, makhni and makhaani share a key, as do butter and batar.
"""
from __future__ import annotations

import re

_PAIRS = [
    ("chh", "c"), ("ch", "c"), ("sh", "s"), ("ph", "f"), ("th", "t"), ("dh", "d"), ("kh", "k"),
    ("gh", "g"), ("bh", "b"), ("jh", "j"), ("rh", "r"), ("ck", "k"), ("aa", "a"), ("ee", "i"),
    ("ii", "i"), ("oo", "u"), ("uu", "u"), ("w", "v"), ("z", "j"), ("q", "k"), ("x", "ks"),
]
_VOWELS = set("aeiouy")


def word_key(word: str) -> str:
    w = re.sub(r"[^a-z]", "", word.lower())
    if not w:
        return ""
    for a, b in _PAIRS:
        w = w.replace(a, b)
    if len(w) > 2 and w[-1] in "ah":
        w = w[:-1]
    w = re.sub(r"(.)\1+", r"\1", w)
    if len(w) <= 2:
        return w
    first, middle, last = w[0], w[1:-1], w[-1]
    skeleton = first + "".join(c for c in middle if c not in _VOWELS) + last
    skeleton = skeleton.replace("y", "i")
    return re.sub(r"(.)\1+", r"\1", skeleton)


def key(phrase: str) -> str:
    return " ".join(k for k in (word_key(w) for w in phrase.split()) if k)
