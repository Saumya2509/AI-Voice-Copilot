"""Language detection (file 05, section 3): en, hi or hinglish, with per-call hysteresis."""
from __future__ import annotations

from dataclasses import dataclass

HINDI_WORDS = {
    "hai", "hain", "kya", "mujhe", "chahiye", "aur", "nahi", "dena", "de", "dedo", "dijiye", "wala", "wali",
    "bhi", "ke", "ki", "ka", "ko", "haan", "theek", "bas", "itna", "karo", "kar", "hata", "mera", "meri",
    "naam", "kitne", "kitna", "kuch", "aap", "hum", "bina", "saath", "ji", "thoda", "zyada", "kam", "abhi",
    "wo", "woh", "yeh", "ye", "tha", "rehne", "chalega", "bhaiya", "ek", "do", "teen", "chaar", "paanch",
    "lena", "lunga", "chahta", "chahti", "hoon", "hu", "se", "par", "mein", "liye", "jaldi", "batao",
    "pehla", "doosra", "dusra", "gaya", "ho", "milega", "accha", "achha", "acha", "sab", "phir", "itna",
}
ENGLISH_WORDS = {
    "i", "want", "would", "like", "please", "the", "a", "an", "and", "with", "can", "get", "me", "have",
    "give", "add", "no", "yes", "thats", "all", "is", "it", "of", "my", "name", "what", "how", "much",
    "without", "some", "need", "order", "okay", "ok", "also", "one", "two", "three", "four", "that", "this",
    "for", "you", "do", "make", "remove", "first", "second", "is", "be", "will", "just", "only", "thank",
    "thanks", "sure", "yeah", "nothing", "else", "could", "should", "on", "side", "number", "there", "hello",
}


def detect(tokens: list[str], devanagari: bool) -> str:
    if devanagari:
        return "hi"
    h = sum(1 for t in tokens if t in HINDI_WORDS)
    e = sum(1 for t in tokens if t in ENGLISH_WORDS)
    if h == 0:
        return "en"
    if e > 2 * h:
        return "en"
    return "hinglish"


@dataclass
class CallLanguage:
    """Holds the call language. A new language needs two utterances in a row to take over, so
    one stray word does not flip the replies. Very short utterances never switch it."""
    current: str | None = None
    candidate: str | None = None
    streak: int = 0

    def update(self, detected: str, n_tokens: int) -> str:
        if self.current is None:
            self.current = detected
        elif detected != self.current and n_tokens >= 2:
            if detected == self.candidate:
                self.streak += 1
            else:
                self.candidate, self.streak = detected, 1
            if self.streak >= 2:
                self.current, self.candidate, self.streak = detected, None, 0
        elif detected == self.current:
            self.candidate, self.streak = None, 0
        return self.current
