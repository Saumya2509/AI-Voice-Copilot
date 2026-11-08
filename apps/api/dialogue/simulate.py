"""Play a scripted sample call through the dialogue manager, without a browser.

Usage (from apps/api):
    python -m dialogue.simulate                       # all samples
    python -m dialogue.simulate 02-hindi-change-of-mind
    python -m dialogue.simulate --say "ek dal makhani aur do naan"  # one-off lines, separated by |
"""
from __future__ import annotations

import argparse
import sys
import uuid
from pathlib import Path

import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import settings
from dialogue.manager import CallSession
from dialogue.services import DbServices


def load_samples() -> list[dict]:
    out = []
    for path in sorted(settings.SAMPLES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        data["file"] = path.stem
        out.append(data)
    return out


def run_script(lines: list[str], services: DbServices, call_id: str | None = None,
               on_event=None) -> CallSession:
    sess = CallSession(call_id or f"call_{uuid.uuid4().hex[:10]}", services)
    services.ensure_call(sess.call_id)
    for ev in sess.start():
        on_event and on_event(ev)
    for text in lines:
        on_event and on_event({"type": "guest", "text": text})
        for ev in sess.handle({"type": "transcript.final", "text": text}):
            on_event and on_event(ev)
    return sess


def _print(ev: dict) -> None:
    t = ev["type"]
    if t == "guest":
        print(f"\n  GUEST     {ev['text']}")
    elif t == "reply.say":
        print(f"  TADKA     {ev['text']}")
    elif t == "state.changed":
        print(f"            [{ev['state']}]")
    elif t == "clarify.ask":
        print(f"            ? {[o['label'] for o in ev['options']]}")
    elif t == "upsell.offer":
        print(f"            offer {ev['item']['name']} ₹{ev['item']['price']}: {'; '.join(ev['reason']['why'])}")
    elif t == "cart.updated":
        c = ev["cart"]
        lines = ", ".join(f"{l['qty']}x {l['name']}" for l in c["lines"])
        print(f"            cart: {lines}  (₹{c['total']}, upsell +₹{c['upsell']['added_revenue']})")
    elif t in ("pos.sent", "pos.ack", "error"):
        print(f"            {t} {ev.get('kot_no', '')} {ev.get('message', '')}")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("sample", nargs="?")
    ap.add_argument("--say")
    args = ap.parse_args(argv)
    db.init_db()
    services = DbServices()
    if args.say:
        run_script([s.strip() for s in args.say.split("|")], services, on_event=_print)
        return
    for sample in load_samples():
        if args.sample and args.sample not in (sample["file"], sample["id"]):
            continue
        print(f"\n=== {sample['title']} ===")
        sess = run_script([u["text"] for u in sample["utterances"]], services, call_id=f"sample_{sample['id']}_{uuid.uuid4().hex[:6]}",
                          on_event=_print)
        print(f"\n  outcome: {sess.outcome}, offers {sess.offers_made} shown / {sess.offers_accepted} accepted")


if __name__ == "__main__":
    main()
