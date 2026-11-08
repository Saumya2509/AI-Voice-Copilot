"""Loads the lexicon YAML files and merges any enabled language packs."""
from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import yaml

import settings


@dataclass
class Lexicon:
    aliases: dict[str, list[str]]
    numbers: dict[str, float]
    counters: set[str]
    size: dict[str, list[str]]
    spice: dict[str, list[str]]
    addons: dict[str, list[str]]
    exclusions: dict[str, list[str]]
    fillers: set[str]
    filler_phrases: list[str]
    intents: dict[str, list[str]] = field(default_factory=dict)  # extra phrases from packs
    packs: tuple[str, ...] = ()


def _read(name: str) -> dict:
    path = settings.LEXICON_DIR / name
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


@lru_cache(maxsize=8)
def load(packs: tuple[str, ...] = ()) -> Lexicon:
    aliases = {k: list(v) for k, v in _read("aliases.yaml").items()}
    nums_raw = _read("numbers.yaml")
    numbers: dict[str, float] = {}
    for section in ("english", "roman_hindi", "devanagari", "digits", "fractions"):
        numbers.update({str(k): float(v) for k, v in (nums_raw.get(section) or {}).items()})
    counters = set(nums_raw.get("counters") or [])
    mods = _read("modifiers.yaml")
    fill = _read("fillers.yaml")
    fillers_all = [str(w) for section in fill.values() for w in section]
    lex = Lexicon(
        aliases=aliases, numbers=numbers, counters=counters,
        size={k: list(v) for k, v in mods.get("size", {}).items()},
        spice={k: list(v) for k, v in mods.get("spice", {}).items()},
        addons={k: list(v) for k, v in mods.get("addons", {}).items()},
        exclusions={k: list(v) for k, v in mods.get("exclusions", {}).items()},
        fillers={w for w in fillers_all if " " not in w},
        filler_phrases=[w for w in fillers_all if " " in w],
        packs=packs,
    )
    for code in packs:
        pack = _read(f"packs/{code}.yaml")
        for item, words in (pack.get("aliases") or {}).items():
            lex.aliases.setdefault(item, []).extend(words)
        lex.numbers.update({str(k): float(v) for k, v in (pack.get("numbers") or {}).items()})
        for group, values in (pack.get("modifiers") or {}).items():
            target = getattr(lex, group, None)
            if isinstance(target, dict):
                for value, words in values.items():
                    target.setdefault(value, []).extend(words)
        lex.fillers.update(w for w in pack.get("fillers") or [] if " " not in w)
        for intent, words in (pack.get("intents") or {}).items():
            lex.intents.setdefault(intent, []).extend(words)
    return lex
