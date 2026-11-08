"""English display text for what the caller said (improve.md, section 4). Local and rule based.

1. Matched item mentions become the English menu name.
2. Number words are already digits (normalize).
3. Modifier phrases become English ("bina pyaaz" -> "no onion").
4. Ordering phrases come from data/lexicon/gloss_en.yaml ("mujhe ... chahiye" -> "I want ...").
5. Leftover non-English words stay as Roman text, marked `unknown` so the UI sets them in italics.

The gloss covers ordering language. Unusual sentences come out partly in italic Roman words.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import yaml

import settings
from nlu.language import ENGLISH_WORDS
from nlu.lexicon import load as load_lexicon
from nlu.menu import MenuIndex

SPICE_EN = {"Mild": "mild", "Medium": "medium spicy", "Spicy": "spicy"}
EXTRA_ENGLISH = {
    "glass", "glasses", "plate", "plates", "piece", "pieces", "bowl", "bottle", "cup", "half", "full", "extra",
    "spicy", "medium", "mild", "hot", "cold", "less", "more", "no", "yes", "okay", "ok", "hello", "hi", "please",
    "thanks", "thank", "sorry", "order", "cancel", "remove", "add", "repeat", "total", "price", "bill", "available",
    "today", "now", "name", "number", "my", "the", "a", "and", "with", "without", "too", "also", "what", "how",
    "much", "is", "are", "it", "that", "this", "i", "we", "you", "me", "want", "like", "would", "could", "can",
    "get", "give", "have", "one", "first", "second", "third", "last", "of", "for", "to", "in", "on", "side",
    "recommend", "suggest", "good", "best", "special", "nothing", "else", "all", "thats", "done", "sure",
    "deliver", "delivery", "time", "open", "close", "there", "do", "does", "will", "be", "some", "any",
}
SOUND_FILLERS = {"um", "umm", "uh", "uhh", "hmm", "er"}
OPEN, CLOSE = "⟦", "⟧"  # wrap words that are already English after a phrase rule


@dataclass
class Gloss:
    text: str
    parts: list[dict] = field(default_factory=list)  # {"text", "kind": plain | item | unknown}


@lru_cache(maxsize=1)
def _table() -> tuple[list[tuple[re.Pattern, str]], dict[str, str]]:
    data = yaml.safe_load((settings.LEXICON_DIR / "gloss_en.yaml").read_text(encoding="utf-8")) or {}
    phrases = sorted((data.get("phrases") or {}).items(), key=lambda kv: -len(kv[0].replace("{x}", "").split()))
    rules = []
    for pattern, english in phrases:
        words = pattern.split()
        rx = r"(?<!\S)" + r"\s+".join(r"(?P<x>.+?)" if w == "{x}" else re.escape(w) for w in words) + r"(?!\S)"
        pieces = english.split("{x}")
        repl = " {x} ".join(f"{OPEN}{p.strip()}{CLOSE}" if p.strip() else "" for p in pieces).strip()
        rules.append((re.compile(rx), repl))
    words = {str(k): ("" if v is None else str(v)) for k, v in (data.get("words") or {}).items()}
    return rules, words


def _modifier_en(kind: str, value: str) -> str:
    if kind == "spice":
        return SPICE_EN.get(value, value.lower())
    if kind == "size":
        return value.lower()
    if kind == "exclusion":
        return f"no {value}"
    if value.lower().startswith("add "):
        return "with " + value[4:].lower()
    return value.lower()


def gloss_en(parse, menu: MenuIndex) -> Gloss:
    norm = parse.normalized
    tokens = norm.tokens
    index = norm.clean_index or list(range(len(norm.clean_tokens)))
    fixed: dict[int, tuple[int, str, str]] = {}  # start token -> (end token, english, kind)
    for m in parse.mentions:
        start, end = index[m.start], index[m.end - 1] + 1
        if m.status == "accepted":
            fixed[start] = (end, menu.items[m.item_id].name, "item")
        else:
            fixed[start] = (end, m.text, "plain")
    for mp in getattr(parse, "modifier_spans", []):
        start, end = index[mp.start], index[mp.end - 1] + 1
        fixed.setdefault(start, (end, _modifier_en(mp.kind, mp.value), "plain"))

    units: list[tuple[str, str]] = []  # (kind, text); kind "word" for words still to gloss
    i = 0
    while i < len(tokens):
        if i in fixed:
            end, english, kind = fixed[i]
            units.append((kind, english))
            i = end
        else:
            units.append(("word", tokens[i]))
            i += 1

    # Phrase rules run over a token string where fixed units are placeholders.
    line = " ".join(t if k == "word" else f"§{n}" for n, (k, t) in enumerate(units))
    rules, words = _table()
    for rx, repl in rules:
        line = rx.sub(lambda mt: repl.replace("{x}", mt.group("x")) if "x" in rx.groupindex else repl, line)

    lex = load_lexicon()
    english_lang = parse.language == "en"
    name_words = set((parse.name or "").lower().split())
    parts: list[dict] = []
    for tok in re.findall(rf"{OPEN}[^{CLOSE}]*{CLOSE}|\S+", line):
        if tok.startswith(OPEN):
            text = tok[1:-1]
            if text:
                parts.append({"text": text, "kind": "plain"})
        elif tok.startswith("§") and tok[1:].isdigit():
            kind, text = units[int(tok[1:])]
            parts.append({"text": text, "kind": kind})
        elif tok in name_words:
            parts.append({"text": tok.capitalize(), "kind": "plain"})
        elif tok == "i":
            parts.append({"text": "I", "kind": "plain"})
        elif tok in words and not english_lang:
            if words[tok]:
                parts.append({"text": words[tok], "kind": "plain"})
        elif tok in lex.fillers and not (english_lang and tok not in SOUND_FILLERS):
            continue
        elif tok.replace(".", "").isdigit() or english_lang or tok in ENGLISH_WORDS or tok in EXTRA_ENGLISH:
            parts.append({"text": tok, "kind": "plain"})
        else:
            parts.append({"text": tok, "kind": "unknown"})
    # Keep digit groups together ("98123 45610") so a spoken phone number is masked as one number.
    merged: list[dict] = []
    for pt in parts:
        if merged and pt["text"].isdigit() and merged[-1]["text"].replace(" ", "").isdigit():
            merged[-1] = {"text": merged[-1]["text"] + " " + pt["text"], "kind": "plain"}
        else:
            merged.append(pt)
    parts = merged
    if parts:
        first = parts[0]["text"]
        parts[0] = {**parts[0], "text": first[:1].upper() + first[1:]}
    return Gloss(" ".join(p["text"] for p in parts), parts)
