"""One utterance in, one structured parse out: normalize -> language -> modifiers -> item mentions
-> quantities -> intent."""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from nlu import intent as intent_mod
from nlu.language import detect
from nlu.lexicon import Lexicon, load as load_lexicon
from nlu.matcher import Candidate, Context, Matcher
from nlu.menu import MenuIndex
from nlu.modifiers import find_modifiers, homophone_quantities, nearest, quantity_tokens, validate
from nlu.normalize import Normalized, normalize

# Words that never belong to a dish name. They split the utterance into candidate segments.
STOPWORDS = {
    "aur", "and", "with", "ke", "ki", "ka", "ko", "saath", "sath", "mujhe", "hume", "humein", "chahiye", "dena",
    "dedo", "de", "do", "dijiye", "please", "i", "want", "would", "like", "to", "have", "get", "me", "a", "an",
    "the", "plus", "also", "bhi", "hai", "hain", "kya", "is", "it", "that", "this", "for", "of", "wala", "wali",
    "wale", "order", "karo", "kar", "lena", "lunga", "lungi", "chahta", "chahti", "hoon", "hu", "ho", "tha", "add",
    "some", "more", "extra", "thanda", "garam", "can", "could", "you", "give", "one", "my", "mera", "meri", "ek",
    "aap", "bhaiya", "sir", "ji", "haan", "nahi", "no", "yes", "ok", "okay", "theek", "bas", "itna", "hi",
    "hata", "remove", "wo", "woh", "vo", "ye", "yeh", "isko", "usko", "mein", "me", "se", "par", "pe", "on",
    "side", "bhej", "bhejo", "pack", "parcel", "kitne", "kitna", "price", "available", "milega", "batao",
    "how", "much", "what", "rate", "cancel", "nikal", "mat", "rehne", "or", "ya", "fir", "phir", "then", "naam",
    "name", "number", "thanks", "thank", "aaj", "today", "abhi", "now", "bina", "without", "chalega", "sahi",
    "ruko", "wait", "minute", "kuch", "something", "first", "second", "pehla", "doosra", "dusra", "teesra",
    "make", "change", "karna", "banana", "bana", "kardo", "dal", "lo", "le", "lijiye", "need", "will", "take",
    "rahne", "thats", "all", "everything", "else", "nothing", "done", "gaya", "hua", "sab", "bhai", "yaar",
    "there", "here", "am", "im", "are", "was", "be", "just", "only", "too", "very", "good", "great", "nice",
    "perfect", "sure", "right", "correct", "kaunsa", "kaun", "wala", "one", "ones", "same", "aisa", "waisa",
}
STOPWORDS -= {"dal"}  # dal is a dish word ("dal tadka"); it stays matchable
COUNTERS = {"plate", "plates", "glass", "glasses", "piece", "pieces", "bowl", "bowls", "portion", "portions",
            "bottle", "bottles", "cup", "cups", "pcs", "pc", "nos"}
ORDINALS = {"pehla": 0, "pehle": 0, "pehli": 0, "pahla": 0, "first": 0, "1st": 0, "doosra": 1, "dusra": 1,
            "doosri": 1, "dusri": 1, "second": 1, "2nd": 1, "teesra": 2, "tisra": 2, "third": 2, "3rd": 2,
            "last": -1, "aakhri": -1, "akhri": -1}


@dataclass
class Mention:
    start: int
    end: int
    text: str
    status: str  # accepted | clarify
    candidates: list[Candidate]
    qty: Optional[float] = None
    modifiers: list[tuple[str, str]] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    problems: list[str] = field(default_factory=list)

    @property
    def item_id(self) -> Optional[int]:
        return self.candidates[0].item_id if self.status == "accepted" else None

    @property
    def score(self) -> float:
        return min(self.candidates[0].score, 1.0) if self.candidates else 0.0


@dataclass
class Parse:
    original: str
    normalized: Normalized
    language: str
    intent: str
    intent_source: str
    intent_confidence: float
    mentions: list[Mention]
    loose_modifiers: list[tuple[str, str]]  # modifiers with no item in this utterance: (kind, value)
    loose_qty: Optional[float]
    phone: Optional[str]
    name: Optional[str]
    ordinal: Optional[int]
    refers_to_last: bool
    modifier_spans: list = field(default_factory=list)  # ModPhrase on clean tokens, for the English gloss

    def to_event(self) -> dict:
        return {
            "type": "nlu.result",
            "intent": self.intent,
            "language": self.language,
            "matches": [
                {"span": [m.start, m.end], "text": m.text, "status": m.status,
                 "item_id": m.item_id, "score": round(m.score, 3),
                 "options": [{"id": c.item_id, "label": c.name, "score": round(min(c.score, 1.0), 3)}
                             for c in m.candidates[:3]] if m.status == "clarify" else [],
                 "qty": m.qty, "modifiers": [{"group": g, "name": n} for g, n in m.modifiers],
                 "notes": m.notes, "problems": m.problems}
                for m in self.mentions
            ],
        }


class Parser:
    def __init__(self, menu: MenuIndex, packs: tuple[str, ...] = ()):
        self.menu = menu
        self.lex: Lexicon = load_lexicon(tuple(sorted(packs)))
        pack_aliases = {k: v for k, v in self.lex.aliases.items()}
        self.matcher = Matcher(menu, pack_aliases)

    def parse(self, text: str, cart_item_ids: set[int] | None = None, last_category: str | None = None,
              daypart: str | None = None) -> Parse:
        norm = normalize(text, self.lex)
        tokens = norm.clean_tokens
        language = detect(norm.tokens, norm.devanagari)

        mods, mod_used = find_modifiers(tokens, self.lex)
        qtys = quantity_tokens(tokens)
        blocked = set(mod_used) | {i for i, _ in qtys}
        blocked |= {i for i, t in enumerate(tokens) if t in STOPWORDS or t in COUNTERS or t.isdigit()
                    or t in ORDINALS}
        ctx = Context(cart_item_ids or set(), last_category, daypart)
        found = self.matcher.find(tokens, blocked, ctx)

        mentions: list[Mention] = []
        for a, b, cands in found:
            status, opts = Matcher.decide(cands)
            if status == "none":
                continue
            mentions.append(Mention(a, b, " ".join(tokens[a:b]), status, opts if status == "clarify" else cands))
        spans = [(m.start, m.end) for m in mentions]

        loose_qty = None
        for pos, value in qtys:
            idx = nearest(pos, pos + 1, spans, prefer="right") if spans else None
            if idx is None:
                loose_qty = value
            elif mentions[idx].qty is None:
                mentions[idx].qty = value
        # "to butter naan" is "two butter naan" heard by the recogniser; real numbers came first and win.
        ci = norm.clean_index
        raw_spans = [(ci[m.start], ci[m.end - 1] + 1) for m in mentions]
        for idx, value in homophone_quantities(norm.tokens, raw_spans, intent_mod.PRICE_WORDS,
                                                hindi=language != "en"):
            if mentions[idx].qty is None:
                mentions[idx].qty = value

        loose_mods: list[tuple[str, str]] = []
        for mp in mods:
            idx = nearest(mp.start, mp.end, spans, prefer="left") if spans else None
            if idx is None:
                loose_mods.append((mp.kind, mp.value))
                continue
            m = mentions[idx]
            if m.status == "clarify":
                m.notes.append(f"{mp.kind}:{mp.value}")  # applied once the item is chosen
                continue
            mod, note, problem = validate(self.menu.items[m.item_id], mp.kind, mp.value)
            if mod:
                m.modifiers = [x for x in m.modifiers if x[0] != mod[0] or mod[0] == "Add-ons"] + [mod]
            if note:
                m.notes.append(note)
            if problem:
                m.problems.append(problem)

        intent, source, conf = intent_mod.classify(
            norm.text, norm.tokens, spans, bool(mods), self.lex.intents or None)
        if intent == "add_item" and mentions and all(
                m.status == "accepted" and m.item_id in (cart_item_ids or set()) and m.qty is None
                and (m.modifiers or m.notes) for m in mentions):
            intent = "modify_item"  # "kadai paneer kam teekha" changes the dish already on the order
        phone = intent_mod.extract_phone(norm.tokens) if intent == "give_phone" else None
        name = intent_mod.extract_name(norm.text) if intent == "give_name" else None
        ordinal = next((ORDINALS[t] for t in tokens if t in ORDINALS), None)
        refers_to_last = bool(set(norm.tokens) & intent_mod.LAST_REFS)
        return Parse(text, norm, language, intent, source, conf, mentions, loose_mods, loose_qty, phone, name,
                     ordinal, refers_to_last, mods)


def split_fraction(qty: float, has_size: bool) -> list[tuple[int, Optional[str]]]:
    """1.5 plates of a sized item -> one Full and one Half. Other fractions round up."""
    if qty.is_integer():
        return [(int(qty), None)]
    if has_size:
        whole = int(math.floor(qty))
        parts = []
        if whole:
            parts.append((whole, "Full"))
        parts.append((1, "Half"))
        return parts
    return [(int(math.ceil(qty)), None)]
