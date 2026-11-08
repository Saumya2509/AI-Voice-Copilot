"""Train the intent model on templated utterances in English, Hinglish and Hindi.

Usage (from apps/api):  python -m nlu.train_intent
Item names and numbers are filled from the menu, then replaced by `itemx` / `numx` placeholders
exactly as at call time, so the model learns sentence shapes rather than dish names.
"""
from __future__ import annotations

import random
import sys
from pathlib import Path

import joblib
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, classification_report
from sklearn.model_selection import train_test_split
from sklearn.pipeline import FeatureUnion, Pipeline

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings
from nlu.lexicon import load as load_lexicon
from nlu.normalize import normalize

# {item} {n} {name} {phone} {addr} are filled in. Hindi lines are in Devanagari.
TEMPLATES: dict[str, list[str]] = {
    "greet": [
        "hello", "hi", "hello ji", "namaste", "namaste bhaiya", "hi there", "good evening", "good afternoon",
        "hello is this the restaurant", "haan hello", "नमस्ते", "हेलो", "hello order karna tha", "hey",
        "namaskar", "hello sir", "hi good morning", "नमस्कार जी", "hello bhaiya order dena hai",
    ],
    "add_item": [
        "{n} {item}", "{item}", "{n} {item} aur {n} {item}", "mujhe {n} {item} chahiye", "{n} {item} dena",
        "{item} {n}", "i want {n} {item}", "can i get {n} {item}", "i would like {item}", "{n} {item} please",
        "add {n} {item}", "also {n} {item}", "aur ek {item}", "{item} bhi dena", "{n} {item} and {n} {item}",
        "give me {n} {item}", "{n} plate {item}", "mujhe {item} chahiye", "{item} add karo",
        "{n} {item} bhej do", "एक {item} और दो {item}", "मुझे {n} {item} चाहिए", "{item} देना", "{n} {item}",
        "{item} भी देना", "let me have {item}", "one {item} with {item}", "{item} lena hai",
        "{n} {item} pack kar do", "{item} order karna hai", "and {n} {item}", "plus {n} {item}",
        "{n} glass {item}", "{item} bhi add kar do", "ek {item} aur", "{n} {item} lunga",
    ],
    "remove_item": [
        "{item} hata do", "remove the {item}", "nahi wo hata do", "wo hata do", "remove that", "remove it",
        "cancel the {item}", "{item} nahi chahiye hata do", "{item} remove kar do", "last wala hata do",
        "take off the {item}", "{item} nikal do", "वो हटा दो", "{item} हटा दो", "drop the {item}",
        "delete {item}", "{item} cancel karo", "please remove {item}", "isko hata do", "ek {item} kam kar do",
        "{item} mat bhejo", "no {item} remove it", "hatao {item}", "{item} nahi chahiye remove karo",
        "take the {item} out", "scratch the {item}", "{item} wala hata dijiye", "last item remove karo",
    ],
    "modify_item": [
        "bina pyaaz ke", "no onion", "make it spicy", "medium spicy", "kam teekha karna", "{item} medium spicy",
        "make the {item} less spicy", "extra butter", "half kar do", "{item} half", "without garlic",
        "zyada teekha", "बिना प्याज के", "कम तीखा", "change it to full", "{item} mein extra paneer",
        "make it mild", "spicy banana", "no coriander", "jain bana do", "{item} bina pyaaz ke",
    ],
    "ask_price": [
        "{item} kitne ka hai", "how much is {item}", "what is the price of {item}", "{item} ka rate kya hai",
        "{item} कितने का है", "price of {item}", "how much does {item} cost", "{item} kitne ki hai",
        "total kitna hua", "bill kitna hai", "what's the total", "kitna hua total", "{item} ka price batao",
    ],
    "ask_recommendation": [
        "what do you recommend", "kya accha hai", "suggest something", "aaj special kya hai", "what is good here",
        "kya lena chahiye", "aap kya suggest karoge", "what's your best dish", "कुछ suggest करो", "kya famous hai",
        "recommend a dessert", "koi accha starter batao", "what goes well with this", "kuch meetha suggest karo",
        "best kya hai", "your special please",
    ],
    "ask_availability": [
        "{item} milega", "do you have {item}", "is {item} available", "{item} available hai", "{item} hai kya",
        "{item} मिलेगा", "{item} mil jayega", "is there {item}", "have you got {item}", "{item} milta hai kya",
        "aaj {item} hai", "can i get {item} today is it available", "{item} available hai kya aaj",
        "do you have {item} today", "{item} stock mein hai", "kya {item} milega", "{item} ready hai kya",
    ],
    "confirm": [
        "haan", "yes", "haan theek hai", "ok", "okay", "theek hai", "bilkul", "sure", "haan ji", "yes please",
        "haan add karo", "chalega", "हाँ", "हाँ ठीक है", "ठीक है", "yes that's right", "correct", "haan sahi hai",
        "ok go ahead", "place the order", "yes confirm", "haan kar do", "perfect", "sounds good", "ji haan",
        "haan de do", "zaroor", "okay add it", "yeah", "yep",
    ],
    "deny": [
        "nahi", "no", "nahi rehne do", "no thanks", "nahi chahiye", "rehne do", "no thank you", "not now",
        "नहीं", "नहीं रहने दो", "nope", "mat dena", "nahi bhaiya", "skip it", "i dont want it", "nahi ji",
        "no need", "abhi nahi", "उसकी ज़रूरत नहीं", "nah",
    ],
    "finalize": [
        "bas", "bas itna hi", "that's all", "itna hi", "ho gaya", "bas ho gaya", "nothing else", "aur kuch nahi",
        "that's it", "बस इतना ही", "बस", "that will be all", "done", "bas yahi", "thats everything",
        "nothing more thanks", "bas itna hi chahiye", "aur kuch nahi chahiye", "that's all for now",
    ],
    "repeat_order": [
        "repeat my order", "order repeat karo", "what did i order", "mera order kya hai", "read it back",
        "phir se batao", "can you repeat the order", "dobara batao", "kya kya liya maine", "order summary please",
        "मेरा ऑर्डर बताओ", "please read back my order",
    ],
    "give_name": [
        "mera naam {name} hai", "my name is {name}", "{name}", "naam {name}", "this is {name}",
        "मेरा नाम {name} है", "main {name} bol raha hoon", "name is {name}", "i am {name}", "{name} naam hai",
    ],
    "give_phone": [
        "{phone}", "mera number {phone} hai", "my number is {phone}", "phone number {phone}", "{phone} pe call karna",
        "number hai {phone}", "मेरा नंबर {phone}", "you can reach me at {phone}",
    ],
    "give_address": [
        "address hai {addr}", "my address is {addr}", "{addr}", "deliver to {addr}", "pata hai {addr}",
        "flat {n} {addr}", "मेरा पता {addr}",
    ],
    "cancel": [
        "cancel the order", "order cancel kar do", "cancel my order", "rehne do order", "cancel everything",
        "kuch nahi chahiye ab", "ऑर्डर कैंसल कर दो", "forget it cancel", "i want to cancel", "cancel karo sab",
        "please cancel the whole order", "pura order cancel", "i changed my mind cancel it", "order nahi chahiye",
        "cancel the call", "sab cancel kar do",
    ],
    "unknown": [
        "what time do you close", "kitne baje band hota hai", "where are you located", "parking hai kya",
        "is the restaurant open", "aap kahan ho", "hmm", "wait a minute", "ek minute", "ruko", "sorry what",
        "kya bola", "can you hear me", "awaaz nahi aa rahi", "hello hello", "um", "who is this",
        "do you deliver to my area", "delivery kitne time mein hogi", "how long will it take", "kitna time lagega",
        "card chalega kya", "do you take upi", "my food was cold last time", "manager se baat karni hai",
        "table book karna hai", "are you open on sunday", "abhi kitne log hain", "the weather is nice",
        "main baad mein call karta hoon", "one second", "hold on", "ek second ruko", "kaun bol raha hai",
        "aapka address kya hai", "home delivery hai kya", "hmm let me think", "soch ke batata hoon",
    ],
}
NAMES = ["rohan", "priya", "amit", "neha", "suresh", "anjali", "vikram", "kavita", "arjun", "meera", "rahul", "pooja"]
ADDRS = ["sector 21 noida", "mg road bangalore", "andheri west mumbai", "green park colony", "flat 4b sunrise apartment"]


PREFIXES = ["", "", "", "haan", "accha", "bhaiya", "ok", "sir", "ji", "please", "um", "so", "aur"]
SUFFIXES = ["", "", "", "please", "ji", "bhaiya", "na", "yaar", "sir", "thanks"]
NO_AUGMENT = {"confirm", "deny", "greet", "give_phone", "give_name", "unknown"}


def _fill(template: str, rng: random.Random, items: list[str], intent: str = "") -> str:
    out = template
    if intent not in NO_AUGMENT:
        out = f"{rng.choice(PREFIXES)} {out} {rng.choice(SUFFIXES)}".strip()
    while "{item}" in out:
        out = out.replace("{item}", "itemx", 1)
    while "{n}" in out:
        out = out.replace("{n}", rng.choice(["1", "2", "3", "4", "ek", "do", "teen", "one", "two", "char"]), 1)
    out = out.replace("{name}", rng.choice(NAMES))
    out = out.replace("{phone}", rng.choice(["98123 45610", "9876543210", "nine eight seven six five four three two one zero",
                                             "70451 22893", "88 00 12 34 56"]))
    out = out.replace("{addr}", rng.choice(ADDRS))
    return out


def build_dataset(seed: int = 7, per_template: int = 14) -> tuple[list[str], list[str]]:
    rng = random.Random(seed)
    lex = load_lexicon()
    texts, labels = [], []
    for intent, templates in TEMPLATES.items():
        for t in templates:
            seen = set()
            for _ in range(per_template):
                raw = _fill(t, rng, [], intent)
                norm = normalize(raw, lex)
                toks = ["itemx" if w == "itemx" else w for w in norm.tokens]
                text = " ".join(
                    "phonex" if w.isdigit() and len(w) >= 5 else "numx" if w.replace(".", "").isdigit() else w
                    for w in toks
                )
                if intent == "give_phone":
                    text = _collapse_phone(text)
                if text in seen:
                    continue
                seen.add(text)
                texts.append(text)
                labels.append(intent)
    return texts, labels


def _collapse_phone(text: str) -> str:
    out = []
    for w in text.split():
        if w in ("numx", "phonex") and out and out[-1] == "phonex":
            continue
        out.append("phonex" if w in ("numx", "phonex") else w)
    return " ".join(out)


def make_pipeline() -> Pipeline:
    features = FeatureUnion([
        ("chars", TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 5), sublinear_tf=True, min_df=1)),
        ("words", TfidfVectorizer(analyzer="word", ngram_range=(1, 2), sublinear_tf=True, token_pattern=r"\S+")),
    ])
    return Pipeline([("features", features), ("clf", LogisticRegression(C=8.0, max_iter=3000))])


def train(save_to: Path | None = None, verbose: bool = True) -> dict:
    texts, labels = build_dataset()
    x_tr, x_te, y_tr, y_te = train_test_split(texts, labels, test_size=0.2, random_state=42, stratify=labels)
    held = make_pipeline().fit(x_tr, y_tr)
    acc = accuracy_score(y_te, held.predict(x_te))
    if verbose:
        print(f"Templates: {len(texts)} utterances, {len(set(labels))} intents")
        print(f"Held-out accuracy: {acc:.3f}")
        print(classification_report(y_te, held.predict(x_te), zero_division=0))
    model = make_pipeline().fit(texts, labels)
    path = Path(save_to or settings.NLU_MODEL_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, path)
    if verbose:
        print(f"Saved {path}")
    return {"held_out_accuracy": acc, "n": len(texts)}


if __name__ == "__main__":
    train()
