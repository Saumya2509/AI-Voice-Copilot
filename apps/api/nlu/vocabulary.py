"""Ordering vocabulary for the offline recogniser.

The Call desk runs a second Vosk recogniser restricted to these phrases (plus "[unk]"), next to the
open one. Restricted to the menu, it hears "dal makhani" where the open model hears "dull mug honey".
The server parses both transcripts and keeps the one that makes more sense (see dialogue.manager).

The English (Indian English) model takes Latin phrases; the Hindi model takes Devanagari. Words the
model does not know are skipped by Vosk.
"""
from __future__ import annotations

import re

from nlu import intent as intent_mod
from nlu.lexicon import Lexicon
from nlu.menu import MenuIndex
from nlu.transliterate import has_devanagari

# Everyday ordering words that are not in the lexicon files.
ORDER_WORDS_EN = [
    "i want", "i would like", "i'd like", "give me", "can i get", "can i have", "could i get", "please", "add",
    "and", "with", "also", "more", "one more", "another", "plate", "plates", "piece", "pieces", "order", "for",
    "to", "the", "a", "of", "me", "my", "is", "it", "that", "this", "what", "how", "much", "do you have",
    "make it", "change", "instead", "only", "just", "thank you", "thanks", "sorry", "wait", "actually",
    "yes", "no", "okay", "right", "correct", "repeat", "cancel", "remove", "delivery", "pickup", "takeaway",
    "zero", "oh", "double",
]
ORDER_WORDS_HI_LATIN = [
    "mujhe", "chahiye", "dena", "de do", "dijiye", "lagao", "laga do", "aur", "ek aur", "bhi", "ke saath",
    "kar do", "karo", "wala", "wali", "plate", "bhaiya", "ji", "accha", "theek hai", "kitne ka", "hai",
]
ORDER_WORDS_HI = [
    "मुझे", "चाहिए", "देना", "दे दो", "दीजिए", "और", "एक और", "भी", "के साथ", "कर दो", "करो", "वाला", "वाली",
    "प्लेट", "भैया", "जी", "अच्छा", "ठीक है", "हाँ", "हां", "नहीं", "बस", "बस इतना ही", "कितने का", "है",
    "हटा दो", "हटाओ", "कैंसल", "ऑर्डर", "धन्यवाद", "शुक्रिया",
]


def _clean(phrase: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s'ऀ-ॿ]", " ", phrase.lower())).strip()


def vocabulary(menu: MenuIndex, lex: Lexicon, script: str) -> list[str]:
    """Phrases for a Vosk grammar. `script` is "latin" (English model) or "devanagari" (Hindi model)."""
    want_dev = script == "devanagari"
    phrases: list[str] = []
    for item in menu.items.values():
        phrases.append(item.name)
        phrases.extend(item.aliases)
    phrases += list(lex.numbers) + list(lex.counters)
    for group in (lex.size, lex.spice, lex.addons, lex.exclusions):
        for words in group.values():
            phrases.extend(words)
    phrases += intent_mod.FINALIZE_PHRASES + intent_mod.CANCEL_PHRASES + intent_mod.AVAIL_PHRASES
    phrases += intent_mod.RECO_PHRASES + intent_mod.REPEAT_PHRASES
    phrases += sorted(intent_mod.STRONG_CONFIRM | intent_mod.DENY_WORDS | intent_mod.REMOVE_WORDS
                      | intent_mod.PRICE_WORDS | intent_mod.GREET_WORDS)
    phrases += ORDER_WORDS_HI if want_dev else ORDER_WORDS_EN + ORDER_WORDS_HI_LATIN

    out: list[str] = []
    seen: set[str] = set()
    for p in phrases:
        p = _clean(str(p))
        if not p or p.isdigit() or has_devanagari(p) != want_dev or p in seen:
            continue
        seen.add(p)
        out.append(p)
    return out
