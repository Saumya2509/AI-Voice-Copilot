"""Run the voice test set and report item and intent accuracy.

Usage (from apps/api):  python -m nlu.evaluate [--verbose]
"""
from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import settings
from nlu.menu import MenuIndex, load_menu
from nlu.gloss_en import gloss_en
from nlu.parser import Parser

CASES = settings.API_DIR / "tests" / "utterances.yaml"


@dataclass
class Result:
    total: int = 0
    intent_ok: int = 0
    item_cases: int = 0
    item_ok: int = 0
    failures: list[str] = field(default_factory=list)
    en_cases: int = 0
    en_ok: int = 0
    latencies_ms: list[float] = field(default_factory=list)

    @property
    def intent_accuracy(self) -> float:
        return self.intent_ok / self.total if self.total else 0.0

    @property
    def item_accuracy(self) -> float:
        return self.item_ok / self.item_cases if self.item_cases else 0.0

    @property
    def english_accuracy(self) -> float:
        return self.en_ok / self.en_cases if self.en_cases else 0.0

    @property
    def p95_ms(self) -> float:
        xs = sorted(self.latencies_ms)
        return xs[int(0.95 * (len(xs) - 1))] if xs else 0.0


def _items_match(parse, case, menu: MenuIndex) -> tuple[bool, str]:
    if "clarify" in case:
        clar = [m for m in parse.mentions if m.status == "clarify"]
        if not clar:
            return False, "expected a clarification"
        offered = {c.name for c in clar[0].candidates}
        if not 2 <= len(clar[0].candidates) <= 3:
            return False, f"clarification must offer 2 or 3 options, got {len(clar[0].candidates)}"
        missing = set(case["clarify"]) - offered
        return (not missing), (f"missing options {sorted(missing)}" if missing else "")
    expected = case.get("items") or []
    got = [m for m in parse.mentions if m.status == "accepted"]
    if any(m.status == "clarify" for m in parse.mentions):
        return False, "unexpected clarification"
    if len(got) != len(expected):
        return False, f"expected {len(expected)} items, got {[m.candidates[0].name for m in got]}"
    for exp, m in zip(expected, got):
        name = menu.items[m.item_id].name
        if name != exp["name"]:
            return False, f"expected {exp['name']}, got {name}"
        if float(m.qty or 1) != float(exp.get("qty", 1)):
            return False, f"{name}: expected qty {exp.get('qty', 1)}, got {m.qty or 1}"
        want_mods = sorted(exp.get("modifiers", []))
        got_mods = sorted(f"{g}:{n}" for g, n in m.modifiers)
        if want_mods != got_mods:
            return False, f"{name}: expected modifiers {want_mods}, got {got_mods}"
        if sorted(exp.get("notes", [])) != sorted(m.notes):
            return False, f"{name}: expected notes {exp.get('notes', [])}, got {m.notes}"
    if "problems" in case and sum(len(m.problems) for m in got) != case["problems"]:
        return False, "expected a polite note about an invalid modifier"
    if "loose" in case:
        got_loose = sorted(f"{k}:{v}" for k, v in parse.loose_modifiers)
        if got_loose != sorted(case["loose"]):
            return False, f"expected {case['loose']}, got {got_loose}"
    return True, ""


def evaluate(db_path: Path | str | None = None, cases_path: Path = CASES) -> Result:
    menu = load_menu(db_path or settings.DB_PATH)
    parser = Parser(menu)
    cases = yaml.safe_load(cases_path.read_text(encoding="utf-8"))
    parser.parse("warm up")
    res = Result()
    for case in cases:
        cart = {menu.by_name(n).id for n in case.get("cart_before", [])}
        start = time.perf_counter()
        parse = parser.parse(case["text"], cart)
        res.latencies_ms.append((time.perf_counter() - start) * 1000)
        res.total += 1
        if parse.intent == case["intent"]:
            res.intent_ok += 1
        else:
            res.failures.append(f"intent  {case['text']!r}: expected {case['intent']}, got {parse.intent}")
        if "en" in case:
            res.en_cases += 1
            got = " ".join(gloss_en(parse, menu).text.lower().split())
            want = " ".join(str(case["en"]).lower().split())
            if got == want:
                res.en_ok += 1
            else:
                res.failures.append(f"english {case['text']!r}: expected {case['en']!r}, got {got!r}")
        if any(k in case for k in ("items", "clarify", "loose")):
            res.item_cases += 1
            ok, why = _items_match(parse, case, menu)
            if ok:
                res.item_ok += 1
            else:
                res.failures.append(f"items   {case['text']!r}: {why}")
    return res


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    res = evaluate()
    print(f"Cases: {res.total}")
    print(f"Intent accuracy: {res.intent_accuracy:.1%} ({res.intent_ok}/{res.total})")
    print(f"Item accuracy:   {res.item_accuracy:.1%} ({res.item_ok}/{res.item_cases})")
    print(f"English display: {res.english_accuracy:.1%} ({res.en_ok}/{res.en_cases})")
    print(f"Parse latency p95: {res.p95_ms:.1f} ms")
    if res.failures:
        print("\nFailures:")
        for f in res.failures:
            print("  " + f)
    ok = res.intent_accuracy >= 0.95 and res.item_accuracy >= 0.95 and res.english_accuracy >= 0.90
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
