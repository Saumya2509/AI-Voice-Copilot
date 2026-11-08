"""Intent recognition (file 05, section 4): high-precision rules first, then a TF-IDF (character
2-5 grams plus word 1-2 grams) logistic regression model trained on templated utterances."""
from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

import joblib

import settings

INTENTS = ["greet", "add_item", "remove_item", "modify_item", "ask_price", "ask_recommendation",
           "ask_availability", "confirm", "deny", "finalize", "repeat_order", "give_name", "give_phone",
           "give_address", "cancel", "unknown"]

STRONG_CONFIRM = {"haan", "han", "ha", "yes", "yeah", "yep", "ok", "okay", "theek", "bilkul", "sure", "chalega",
                  "done", "correct", "sahi", "perfect", "great", "fine", "please", "zaroor", "jarur", "confirm",
                  "absolutely", "chalo", "haanji", "hanji", "ji"}
CONFIRM_FILL = STRONG_CONFIRM | {"hai", "ji", "add", "karo", "kar", "do", "de", "dijiye", "it", "that", "go", "ahead",
                                 "place", "the", "order", "thats", "right", "achha", "accha", "acha", "na", "sir",
                                 "bhaiya", "boss", "one", "also", "dal", "daal", "lo", "le", "lijiye", "yes,",
                                 "is", "good", "sounds", "and", "fine", "with", "me", "theek", "1", "ek"}
DENY_WORDS = {"nahi", "no", "nope", "mat", "rehne", "rahne", "nako", "nahin", "naa", "skip", "dont", "nah"}
REMOVE_WORDS = {"hata", "hatao", "hatado", "remove", "nikal", "nikaal", "nikalo", "delete", "minus", "cancel",
                "drop", "hataiye", "hatana"}
LAST_REFS = {"wo", "woh", "vo", "last", "it", "that", "ye", "yeh", "isko", "usko", "use", "ise", "aakhri", "akhri"}
FINALIZE_PHRASES = ["bas itna hi", "bas itna", "itna hi", "bas yahi", "bas ho gaya", "ho gaya", "thats all",
                    "that is all", "thats it", "that will be all", "nothing else", "aur kuch nahi", "kuch nahi bas",
                    "bas", "done ordering", "bas itna hi hai", "thats everything", "nothing more", "and thats it",
                    "that is it", "that is everything", "thatll be all", "that would be all", "thats about it",
                    "nothing else thanks", "im done", "i am done", "all done", "thats enough", "enough",
                    "bas itna kafi hai", "itna kafi hai", "bas karo", "aur kuch nahi chahiye"]
CANCEL_PHRASES = ["cancel the order", "cancel order", "order cancel", "cancel my order", "order cancel kar do",
                  "rehne do order", "kuch nahi chahiye ab", "cancel kar do sab", "cancel everything", "cancel karo",
                  "cancel it all", "forget it"]
PRICE_WORDS = {"kitne", "kitna", "kitni", "price", "cost", "rate", "daam", "dam", "costs", "much"}
AVAIL_PHRASES = ["available", "milega", "milegi", "mil jayega", "mil jaega", "do you have", "hai kya", "milta",
                 "is there", "have you got", "stock"]
RECO_PHRASES = ["recommend", "suggest", "special", "kya accha hai", "kya acha hai", "kya achha hai", "whats good",
                "what is good", "kya lena chahiye", "kya loon", "best", "famous", "kya mangau", "aapki suggestion"]
REPEAT_PHRASES = ["repeat", "dobara", "phir se batao", "order kya hai", "what did i order", "read back",
                  "summary", "kya kya liya", "mera order batao", "can you repeat", "read it back", "order bata"]
GREET_WORDS = {"hello", "hi", "hey", "namaste", "namaskar", "good", "morning", "evening", "afternoon", "hallo",
               "helo", "ji", "haan", "bolo", "boliye", "sir", "bhaiya"}
NAME_PATTERNS = [r"\bmera naam (\w+(?: \w+)?)", r"\bmy name is (\w+(?: \w+)?)", r"\bname is (\w+(?: \w+)?)",
                 r"\bthis is (\w+(?: \w+)?)", r"\bnaam (\w+(?: \w+)?)", r"\bmain (\w+) bol", r"\bi am (\w+)",
                 r"\bim (\w+)", r"\bname (\w+)"]
NAME_STOP = {"hai", "h", "he", "is", "here", "bol", "raha", "rahi", "speaking", "and", "aur", "please", "ji",
             "number", "the", "sir", "a", "my"}
ADDRESS_WORDS = {"address", "pata", "flat", "road", "sector", "nagar", "colony", "street", "apartment", "society"}


def phrase_in(text: str, phrases) -> bool:
    padded = f" {text} "
    return any(f" {p} " in padded for p in phrases)


def extract_name(text: str) -> str | None:
    for pat in NAME_PATTERNS:
        m = re.search(pat, text)
        if m:
            words = [w for w in m.group(1).split() if w not in NAME_STOP and w.isalpha()]
            if words:
                return " ".join(w.capitalize() for w in words[:2])
    return None


def extract_phone(tokens: list[str]) -> str | None:
    digits = "".join(t for t in tokens if t.isdigit())
    if len(digits) >= 12 and digits.startswith("91"):
        digits = digits[2:]
    if len(digits) == 11 and digits.startswith("0"):
        digits = digits[1:]
    return digits if len(digits) == 10 and digits[0] in "6789" else (digits if len(digits) >= 10 else None)


def rule_intent(text: str, tokens: list[str], has_items: bool, has_mods: bool, extra: dict | None = None) -> str | None:
    """High-precision rules. `text`/`tokens` keep fillers so "haan" still counts."""
    toks = set(tokens)
    extra = extra or {}
    digits = sum(len(t) for t in tokens if t.isdigit())
    if digits >= 10 and not has_items:
        return "give_phone"
    if extract_name(text) and not has_items:
        return "give_name"
    if not has_items and (toks & ADDRESS_WORDS) and len(tokens) >= 3:
        return "give_address"
    if not has_items and phrase_in(text, FINALIZE_PHRASES + extra.get("finalize", [])):
        return "finalize"
    if phrase_in(text, CANCEL_PHRASES) or (not has_items and toks == {"cancel"}):
        return "cancel"
    if toks & REMOVE_WORDS and (has_items or toks & LAST_REFS or "do" in toks or len(tokens) <= 3):
        return "remove_item"
    if phrase_in(text, extra.get("confirm", [])):
        return "confirm"
    if phrase_in(text, extra.get("deny", [])):
        return "deny"
    if not has_items and not has_mods and toks & DENY_WORDS:
        return "deny"
    if not has_items and not has_mods and toks <= CONFIRM_FILL and toks & STRONG_CONFIRM:
        return "confirm"
    if toks & PRICE_WORDS and (has_items or "bill" in toks or "total" in toks):
        return "ask_price"
    if phrase_in(text, AVAIL_PHRASES):
        return "ask_availability"
    if phrase_in(text, RECO_PHRASES):
        return "ask_recommendation"
    if phrase_in(text, REPEAT_PHRASES):
        return "repeat_order"
    if has_mods and not has_items:
        return "modify_item"
    if not has_items and toks and toks <= GREET_WORDS and toks & {"hello", "hi", "hey", "namaste", "namaskar",
                                                                 "hallo", "helo", "good"}:
        return "greet"
    if has_items:
        return "add_item"
    return None


def model_text(tokens: list[str], item_spans: list[tuple[int, int]]) -> str:
    """Text the model sees: item mentions become `itemx`, quantities `numx`, phone digits `phonex`."""
    out, i = [], 0
    starts = {a: b for a, b in item_spans}
    while i < len(tokens):
        if i in starts:
            out.append("itemx")
            i = starts[i]
            continue
        t = tokens[i]
        if t.replace(".", "").isdigit():
            out.append("phonex" if len(t) >= 5 else "numx")
        else:
            out.append(t)
        i += 1
    return " ".join(out)


@lru_cache(maxsize=2)
def load_model(path: str | None = None):
    p = Path(path or settings.NLU_MODEL_PATH)
    if not p.exists():
        from nlu.train_intent import train
        train(save_to=p, verbose=False)
    return joblib.load(p)


def model_intent(text: str) -> tuple[str, float]:
    model = load_model()
    probs = model.predict_proba([text])[0]
    idx = int(probs.argmax())
    return str(model.classes_[idx]), float(probs[idx])


def classify(text: str, tokens: list[str], item_spans: list[tuple[int, int]], has_mods: bool,
             extra: dict | None = None) -> tuple[str, str, float]:
    """Returns (intent, source, confidence). Source is rule or model."""
    has_items = bool(item_spans)
    rule = rule_intent(text, tokens, has_items, has_mods, extra)
    if rule:
        return rule, "rule", 1.0
    intent, conf = model_intent(model_text(tokens, item_spans))
    if intent == "add_item" and not has_items:
        return "unknown", "model", conf
    if conf < 0.35:
        return "unknown", "model", conf
    return intent, "model", conf
