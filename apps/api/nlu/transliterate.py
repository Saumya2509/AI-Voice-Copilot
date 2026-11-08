"""Devanagari to Roman transliteration for matching. The original text is kept for display.

The output follows common Roman Hindi spelling (पनीर -> paneer, मखनी -> makhnee) with schwa
deletion at word ends and between syllables, so Devanagari aliases and spoken Hindi meet the
Roman aliases in the same space.
"""
from __future__ import annotations

import re

CONSONANTS = {
    "क": "k", "ख": "kh", "ग": "g", "घ": "gh", "ङ": "n",
    "च": "ch", "छ": "chh", "ज": "j", "झ": "jh", "ञ": "n",
    "ट": "t", "ठ": "th", "ड": "d", "ढ": "dh", "ण": "n",
    "त": "t", "थ": "th", "द": "d", "ध": "dh", "न": "n",
    "प": "p", "फ": "ph", "ब": "b", "भ": "bh", "म": "m",
    "य": "y", "र": "r", "ल": "l", "ळ": "l", "व": "v",
    "श": "sh", "ष": "sh", "स": "s", "ह": "h",
    # precomposed nukta forms
    "क़": "q", "ख़": "kh", "ग़": "g", "ज़": "z", "ड़": "r", "ढ़": "rh", "फ़": "f", "य़": "y",
}
NUKTA_FORMS = {"क": "q", "ख": "kh", "ग": "g", "ज": "z", "ड": "r", "ढ": "rh", "फ": "f"}
VOWELS = {
    "अ": "a", "आ": "aa", "इ": "i", "ई": "ee", "उ": "u", "ऊ": "oo", "ऋ": "ri",
    "ए": "e", "ऐ": "ai", "ओ": "o", "औ": "au", "ऑ": "o", "ॲ": "e",
}
MATRAS = {
    "ा": "aa", "ि": "i", "ी": "ee", "ु": "u", "ू": "oo", "ृ": "ri",
    "े": "e", "ै": "ai", "ो": "o", "ौ": "au", "ॉ": "o", "ॅ": "e",
}
VIRAMA = "्"
NUKTA = "़"
NASAL = {"ं": "n", "ँ": "n"}
VISARGA = "ः"
DIGITS = {chr(0x0966 + i): str(i) for i in range(10)}

_DEVANAGARI = re.compile(r"[ऀ-ॿ]")


def has_devanagari(text: str) -> bool:
    return bool(_DEVANAGARI.search(text))


def _syllables(word: str) -> list[list[str]]:
    """Split a word into units of [consonant_roman, vowel_roman_or_None_for_schwa, explicit_flag]."""
    units: list[list] = []
    i = 0
    chars = list(word)
    while i < len(chars):
        ch = chars[i]
        nxt = chars[i + 1] if i + 1 < len(chars) else ""
        if ch in CONSONANTS:
            cons = CONSONANTS[ch]
            if nxt == NUKTA:
                cons = NUKTA_FORMS.get(ch, cons)
                i += 1
                nxt = chars[i + 1] if i + 1 < len(chars) else ""
            if nxt in MATRAS:
                units.append([cons, MATRAS[nxt], True])
                i += 2
            elif nxt == VIRAMA:
                units.append([cons, "", True])
                i += 2
            else:
                units.append([cons, None, False])  # inherent schwa, decided later
                i += 1
        elif ch in VOWELS:
            units.append(["", VOWELS[ch], True])
            i += 1
        elif ch in NASAL:
            units.append(["", "n", True])
            i += 1
        elif ch == VISARGA:
            units.append(["", "h", True])
            i += 1
        elif ch in DIGITS:
            units.append([DIGITS[ch], "", True])
            i += 1
        else:
            units.append([ch, "", True])
            i += 1
    return units


def _word(word: str) -> str:
    """Resolve inherent schwas left to right: drop it at the end of a word, and in a
    vowel-consonant_consonant-vowel context (मखनी -> makhnee, not makhanee)."""
    units = _syllables(word)
    n = len(units)

    def is_final(i: int) -> bool:
        return all(u[0] == "" and u[1] == "n" for u in units[i + 1:])

    resolved: list[str] = []
    for idx, (cons, vowel, _explicit) in enumerate(units):
        if vowel is None:
            if n > 1 and is_final(idx):
                vowel = ""
            elif idx > 0 and resolved[idx - 1] != "" and units[idx - 1][0] != "" and idx + 1 < n:
                nxt_cons, nxt_vowel, _ = units[idx + 1]
                next_has_vowel = nxt_cons != "" and (nxt_vowel not in ("", None) or
                                                     (nxt_vowel is None and not is_final(idx + 1)))
                vowel = "" if next_has_vowel else "a"
            else:
                vowel = "a"
        resolved.append(vowel)
    out = "".join(cons + v for (cons, _v, _e), v in zip(units, resolved))
    # Common Roman spelling shortens word-final long vowels: रोटी -> roti, मसाला -> masaala.
    if len(out) > 3 and out.endswith(("aa", "ee")):
        out = out[:-2] + ("a" if out.endswith("aa") else "i")
    return out


def to_roman(text: str) -> str:
    if not has_devanagari(text):
        return text
    return re.sub(r"[ऀ-ॿ]+", lambda m: _word(m.group(0)), text)
