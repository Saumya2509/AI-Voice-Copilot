"""Modifiers and quantities (file 05, section 6). Rule-based slot filling: each modifier or
quantity attaches to the nearest item mention, left or right."""
from __future__ import annotations

from dataclasses import dataclass

from nlu.lexicon import Lexicon
from nlu.menu import MenuItem
from nlu.normalize import is_number, normalize_phrase

KIND_PRIORITY = {"exclusion": 0, "spice": 1, "size": 2, "addon": 3}
GROUP_FOR_KIND = {"size": "Size", "spice": "Spice", "addon": "Add-ons"}


@dataclass
class ModPhrase:
    start: int
    end: int  # exclusive
    kind: str  # size | spice | addon | exclusion
    value: str


_TABLES: dict[int, list] = {}


def _phrase_table(lex: Lexicon) -> list[tuple[tuple[str, ...], str, str]]:
    if id(lex) in _TABLES:
        return _TABLES[id(lex)]
    table = []
    for kind, source in (("size", lex.size), ("spice", lex.spice), ("addon", lex.addons),
                         ("exclusion", lex.exclusions)):
        for value, phrases in source.items():
            for p in phrases:
                toks = tuple(normalize_phrase(str(p)).split())
                if toks:
                    table.append((toks, kind, value))
    table.sort(key=lambda t: (-len(t[0]), KIND_PRIORITY[t[1]]))
    _TABLES[id(lex)] = table
    return table


def find_modifiers(tokens: list[str], lex: Lexicon) -> tuple[list[ModPhrase], set[int]]:
    table = _phrase_table(lex)
    used: set[int] = set()
    found: list[ModPhrase] = []
    for toks, kind, value in table:
        n = len(toks)
        for i in range(len(tokens) - n + 1):
            if tuple(tokens[i:i + n]) == toks and not any(j in used for j in range(i, i + n)):
                found.append(ModPhrase(i, i + n, kind, value))
                used.update(range(i, i + n))
    return sorted(found, key=lambda m: m.start), used


def quantity_tokens(tokens: list[str]) -> list[tuple[int, float]]:
    """Positions of quantities. Long digit runs are phone numbers, not quantities."""
    out = []
    for i, t in enumerate(tokens):
        if is_number(t) and len(t.replace(".", "")) <= 3:
            v = float(t)
            if 0 < v <= 50:
                out.append((i, v))
    return out


# Words a speech recogniser writes for a spoken number ("two" heard as "to"). They count as a quantity
# only right next to a dish: before it ("to butter naan", "for garlic naan"), or, for "to", closing the
# utterance or a list item ("jeera rice to and ..."). Never after a price word ("price for dal makhani"),
# and "to" never in Hindi or Hinglish, where it is the filler "toh" ("accha to butter naan").
HOMOPHONES = {"to": 2, "too": 2, "tu": 2, "for": 4, "fore": 4, "won": 1, "wan": 1, "tree": 3}
TRAILING_HOMOPHONES = {"to", "too"}
LIST_BREAKS = {"and", "aur", "plus", "please", "also", "n"}


def homophone_quantities(tokens: list[str], spans: list[tuple[int, int]], price_words: set[str],
                         hindi: bool = False) -> list[tuple[int, float]]:
    """(index into spans, quantity) for each dish with a number homophone beside it. `tokens` are the raw
    tokens (fillers kept, since "to" is also the Hindi filler "toh") and `spans` are raw token spans."""
    numbers = {i for i, t in enumerate(tokens) if is_number(t)}
    starts = {a: k for k, (a, _b) in enumerate(spans)}
    ends = {b: k for k, (_a, b) in enumerate(spans)}
    out: dict[int, float] = {}
    for i, t in enumerate(tokens):
        value = HOMOPHONES.get(t)
        if value is None or (i > 0 and tokens[i - 1] in price_words):
            continue
        if hindi and t in TRAILING_HOMOPHONES:  # in Hindi and Hinglish "to" is "toh" (so, then)
            continue
        if i + 1 in starts:
            if i - 1 not in numbers:  # "2 to butter naan": the real number wins
                out.setdefault(starts[i + 1], float(value))
        elif t in TRAILING_HOMOPHONES and i in ends and (i + 1 == len(tokens) or tokens[i + 1] in LIST_BREAKS):
            out.setdefault(ends[i], float(value))
    return list(out.items())


def nearest(pos_start: int, pos_end: int, spans: list[tuple[int, int]], prefer: str) -> int | None:
    """Index of the closest span. Ties go to the span on the `prefer` side (left or right)."""
    best, best_key = None, None
    for idx, (a, b) in enumerate(spans):
        if pos_end <= a:
            dist, side = a - pos_end + 1, "right"
        elif pos_start >= b:
            dist, side = pos_start - b + 1, "left"
        else:
            dist, side = 0, prefer
        key = (dist, 0 if side == prefer else 1)
        if best_key is None or key < best_key:
            best, best_key = idx, key
    return best


def validate(item: MenuItem, kind: str, value: str) -> tuple[tuple[str, str] | None, str | None, str | None]:
    """Returns (modifier as (group, option), note, problem)."""
    if kind == "exclusion":
        return None, f"no {value}", None
    group = item.group_for(GROUP_FOR_KIND[kind])
    if group and value in group.options:
        return (group.name, value), None, None
    if kind == "size" and value == "Full":
        return None, None, None  # a regular portion needs no modifier
    if kind == "size":
        return None, None, f"{item.name} comes in one size only."
    if kind == "spice":
        return None, None, f"The spice level of {item.name} can't be changed."
    return None, None, f"{value} isn't available with {item.name}."
