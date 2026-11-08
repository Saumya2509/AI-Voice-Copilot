"""Item mapping (file 05, section 5): alias, phonetic key, fuzzy and character TF-IDF scoring
with a small context prior, then accept / clarify / ignore decisions."""
from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from rapidfuzz import fuzz, process
from sklearn.feature_extraction.text import TfidfVectorizer

from nlu.menu import MenuIndex
from nlu.normalize import normalize_phrase
from nlu.phonetic import key as phonetic_key

ACCEPT = 0.85
CLARIFY = 0.60
GAP = 0.08
KEY_SCORE = 0.90
MAX_SPAN = 4
MAX_PRIOR = 0.03
CONTAIN_BASE = 0.70
CONTAIN_RANGE = 0.25
STRONG_SIMILARITY = 0.85
WEAK_PENALTY = 0.20


@dataclass
class Candidate:
    item_id: int
    name: str
    score: float


@dataclass
class Context:
    cart_item_ids: set[int] = field(default_factory=set)
    last_category: str | None = None
    daypart: str | None = None


DAYPART_CATEGORIES = {"snack": {"starter", "beverage"}, "lunch": {"main", "bread", "rice"},
                      "dinner": {"main", "bread", "rice", "dessert"}}


class Matcher:
    def __init__(self, menu: MenuIndex, extra_aliases: dict[str, list[str]] | None = None):
        self.menu = menu
        self.phrases: list[str] = []
        self.phrase_items: list[int] = []
        self.exact: dict[str, set[int]] = {}
        self.keys: dict[str, set[int]] = {}
        for item in menu.items.values():
            words = [item.name, *item.aliases, *((extra_aliases or {}).get(item.name, []))]
            for w in dict.fromkeys(normalize_phrase(x) for x in words):
                if not w:
                    continue
                self.phrases.append(w)
                self.phrase_items.append(item.id)
                self.exact.setdefault(w, set()).add(item.id)
                k = phonetic_key(w)
                if len(k.replace(" ", "")) >= 3:
                    self.keys.setdefault(k, set()).add(item.id)
        self.phrase_keys = [phonetic_key(p) for p in self.phrases]
        self.phrase_tokens = [set(p.split()) for p in self.phrases]
        # An empty menu (fresh install) has nothing to match.
        self.tfidf = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4)).fit(self.phrases) if self.phrases else None
        self.phrase_vecs = self.tfidf.transform(self.phrases) if self.tfidf else None
        self.item_ids = np.array(self.phrase_items)

    def score_spans(self, spans: list[str], ctx: Context | None = None) -> list[list[Candidate]]:
        """Top candidates for each span, best first.

        - exact alias: 1.0
        - phonetic key: 0.9
        - every spoken word is part of the dish name ("naan" in "butter naan"): 0.70 to 0.95 by coverage
        - spelling similarity counts only when high (misspellings); weak similarity is pushed below 0.6
        - character TF-IDF cosine breaks ties
        """
        if not spans:
            return []
        if self.tfidf is None:
            return [[] for _ in spans]
        ts = process.cdist(spans, self.phrases, scorer=fuzz.token_sort_ratio, workers=1) / 100.0
        rt = process.cdist(spans, self.phrases, scorer=fuzz.ratio, workers=1) / 100.0
        span_keys = [phonetic_key(s) for s in spans]
        kr = process.cdist(span_keys, self.phrase_keys, scorer=fuzz.ratio, workers=1) / 100.0
        cos = (self.tfidf.transform(spans) @ self.phrase_vecs.T).toarray()
        out = []
        for si, span in enumerate(spans):
            span_tokens = span.split()
            best: dict[int, float] = {}
            for pi, item_id in enumerate(self.phrase_items):
                ptoks = self.phrase_tokens[pi]
                if set(span_tokens) <= ptoks:
                    s = CONTAIN_BASE + CONTAIN_RANGE * len(span_tokens) / len(ptoks)
                else:
                    r = max(float(rt[si, pi]), float(ts[si, pi]) if len(span_tokens) > 1 else 0.0)
                    s = r if r >= STRONG_SIMILARITY else r - WEAK_PENALTY
                    k = float(kr[si, pi])
                    if k >= 0.9 and len(span_keys[si].replace(" ", "")) >= 3:
                        s = max(s, k * KEY_SCORE)
                s += 0.01 * float(cos[si, pi])
                if s > best.get(item_id, 0.0):
                    best[item_id] = s
            for item_id in self.exact.get(span, ()):
                best[item_id] = max(best.get(item_id, 0.0), 1.0 + 0.01)
            k = span_keys[si]
            for item_id in self.keys.get(k, ()) if len(k.replace(" ", "")) >= 3 else ():
                best[item_id] = max(best.get(item_id, 0.0), KEY_SCORE + 0.01)
            if ctx:
                for item_id in best:
                    best[item_id] += self._prior(item_id, ctx)
            ranked = sorted(best.items(), key=lambda kv: kv[1], reverse=True)[:5]
            out.append([Candidate(i, self.menu.items[i].name, round(s, 4)) for i, s in ranked])
        return out

    def _prior(self, item_id: int, ctx: Context) -> float:
        item = self.menu.items[item_id]
        bonus = 0.0
        if item_id in ctx.cart_item_ids:
            bonus += 0.02
        if ctx.last_category and item.category == ctx.last_category:
            bonus += 0.01
        if ctx.daypart and item.category in DAYPART_CATEGORIES.get(ctx.daypart, ()):
            bonus += 0.005
        return min(bonus, MAX_PRIOR)

    def find(self, tokens: list[str], blocked: set[int], ctx: Context | None = None) -> list[tuple[int, int, list[Candidate]]]:
        """Find item mentions as non-overlapping spans of unblocked tokens.
        Returns (start, end_exclusive, candidates) in token order."""
        segments: list[tuple[int, int]] = []
        start = None
        for i in range(len(tokens) + 1):
            free = i < len(tokens) and i not in blocked
            if free and start is None:
                start = i
            elif not free and start is not None:
                segments.append((start, i))
                start = None
        spans: list[tuple[int, int]] = []
        for a, b in segments:
            for i in range(a, b):
                for j in range(i + 1, min(b, i + MAX_SPAN) + 1):
                    spans.append((i, j))
        texts = [" ".join(tokens[i:j]) for i, j in spans]
        scored = self.score_spans(texts, ctx)
        options = [(spans[k], scored[k]) for k in range(len(spans)) if scored[k] and scored[k][0].score >= CLARIFY]
        options.sort(key=lambda o: (round(o[1][0].score, 2), o[0][1] - o[0][0]), reverse=True)
        taken: set[int] = set()
        chosen = []
        for (i, j), cands in options:
            if any(t in taken for t in range(i, j)):
                continue
            chosen.append((i, j, cands))
            taken.update(range(i, j))
        return sorted(chosen, key=lambda c: c[0])

    @staticmethod
    def decide(cands: list[Candidate]) -> tuple[str, list[Candidate]]:
        """accepted | clarify | none, with the options to offer."""
        if not cands or cands[0].score < CLARIFY:
            return "none", []
        best = cands[0]
        close = [c for c in cands if best.score - c.score < GAP]
        if best.score >= ACCEPT and len(close) == 1:
            return "accepted", [best]
        opts = close[:3]
        if len(opts) < 2 and len(cands) > 1:
            opts = cands[:2]
        return "clarify", opts
