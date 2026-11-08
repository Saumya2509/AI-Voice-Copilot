"""Dialogue manager (file 05, section 8) and the three sample calls (file 09)."""
from __future__ import annotations

import json
import random

import numpy as np
import pytest
import yaml
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

import db
import settings
from dialogue import manager as dm
from dialogue.services import DbServices, drop_sessions
from dialogue.simulate import load_samples, run_script
from models import Call, PosOrder, UpsellEvent
from revenue.engine import get_engine
from revenue.upsell import UpsellContext
from schemas._loader import errors

no_sleep = lambda _s: None


@pytest.fixture
def svc(work_db, monkeypatch):
    monkeypatch.setattr(settings, "POS_MIN_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "POS_MAX_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "DETERMINISTIC", True)
    return DbServices(work_db, pos_sleep=no_sleep)


def say(sess, *lines):
    out = []
    for text in lines:
        out += sess.handle({"type": "transcript.final", "text": text})
    return out


def types(events):
    return [e["type"] for e in events]


def item_qty(sess) -> dict:
    out = {}
    for l in sess.lines:
        out[l.name] = out.get(l.name, 0) + l.qty
    return out


@pytest.mark.parametrize("sample", load_samples(), ids=lambda s: s["id"])
def test_sample_calls(svc, sample):
    events = []
    sess = run_script([u["text"] for u in sample["utterances"]], svc, call_id=f"t_{sample['id']}",
                      on_event=events.append)
    exp = sample["expect"]
    server = [e for e in events if e["type"] != "guest"]
    assert sess.outcome == exp["outcome"] and sess.state == "FINALIZED"
    assert sess.offers_made == exp["offers_shown"] and sess.offers_accepted == exp["offers_accepted"]
    if "clarifications" in exp:
        assert types(server).count("clarify.ask") == exp["clarifications"]
    got = item_qty(sess)
    for name, qty in exp["items"].items():
        assert got.get(name) == qty, (name, got)
    for name in exp.get("absent", []):
        assert name not in got
    for name, mods in exp.get("modifiers", {}).items():
        line = next(l for l in sess.lines if l.name == name)
        assert sorted(f"{g}:{n}" for g, n in line.modifiers) == sorted(mods)
    if exp.get("combo_accepted"):
        assert any(l.source == "combo" for l in sess.lines)
        assert sess.order["discount"] > 0
    if "customer_items" in exp:
        assert sum(1 for l in sess.lines if l.source == "customer") == exp["customer_items"]
    # Every server event matches the shared schema, in strictly increasing seq order.
    for e in server:
        assert errors("events", e) == [], (e["type"], errors("events", e))
    assert [e["seq"] for e in server] == sorted(e["seq"] for e in server)
    # The order JSON validates and reached the PoS with a KOT.
    assert errors("order", sess.order) == []
    assert any(e["type"] == "pos.ack" for e in server)
    assert sess.order["customer"]["phone"].count("X") == 6


def test_sample_call_is_reproducible(work_db, seeded_db, tmp_path, monkeypatch):
    """Recorded call replayed twice on fresh databases gives the same event sequence."""
    import shutil
    monkeypatch.setattr(settings, "POS_MIN_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "POS_MAX_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "DETERMINISTIC", True)
    sample = load_samples()[0]
    runs = []
    for n in range(2):
        path = tmp_path / f"run{n}.sqlite"
        shutil.copy(seeded_db, path)
        db.init_db(path)
        events = []
        run_script([u["text"] for u in sample["utterances"]], DbServices(path, pos_sleep=no_sleep),
                   call_id="replay_call", on_event=events.append)
        runs.append([(e["type"], e.get("state"), e.get("text"), json.dumps(e.get("item"))) for e in events])
        db.dispose(path)
    assert runs[0] == runs[1]


def test_never_offers_while_clarifying_and_at_most_two(svc):
    sess = dm.CallSession("t_policy", svc)
    sess.start()
    ev = say(sess, "ek paneer masala")
    assert sess.state == "CLARIFYING" and "upsell.offer" not in types(ev)
    ev = say(sess, "bas itna hi")  # moving on drops the question, no offer during clarification
    assert types(ev).count("upsell.offer") <= 1
    say(sess, "nahi")
    say(sess, "nahi")  # change something
    say(sess, "ek dal makhani aur do butter naan", "bas", "nahi", "nahi")
    say(sess, "ek veg biryani", "bas", "nahi")
    assert sess.offers_made <= 2


def test_veg_cart_never_offered_non_veg(work_db):
    eng = get_engine(work_db)
    with Session(db.get_engine(work_db)) as s:
        ranker = eng.ranker(s)
    items = eng.classes(30).set_index("item_id")
    veg_ids = [int(i) for i in items.index if items.at[i, "veg"]]
    rng = random.Random(3)
    for _ in range(300):
        cart = rng.sample(veg_ids, rng.randint(1, 4))
        for offer in ranker.rank(UpsellContext(cart_item_ids=cart, daypart="dinner",
                                               rng=np.random.default_rng(rng.randint(0, 9999)))):
            assert items.at[offer.item_id, "veg"], (cart, offer.name)


def test_decline_learns_and_is_not_repeated(svc, work_db):
    sess = dm.CallSession("t_decline", svc)
    sess.start()
    say(sess, "ek veg biryani")
    ev = say(sess, "bas")
    offer = next(e for e in ev if e["type"] == "upsell.offer")
    with Session(db.get_engine(work_db)) as s:
        rule_id = s.exec(select(UpsellEvent).where(UpsellEvent.call_id == "t_decline")).one().rule_id
    before = next(r for r in get_engine(work_db).rules() if r.id == rule_id).beta
    say(sess, "nahi rehne do")
    assert offer["item"]["id"] in sess.declined_items
    assert next(r for r in get_engine(work_db).rules() if r.id == rule_id).beta == before + 1
    with Session(db.get_engine(work_db)) as s:
        ev_row = s.exec(select(UpsellEvent).where(UpsellEvent.call_id == "t_decline")).one()
        assert ev_row.accepted is False


def test_ui_choice_and_offer_buttons(svc):
    sess = dm.CallSession("t_ui", svc)
    sess.start()
    ev = say(sess, "naan")
    ask = next(e for e in ev if e["type"] == "clarify.ask")
    garlic = next(o for o in ask["options"] if o["label"] == "Garlic Naan")
    sess.handle({"type": "ui.choice", "clarify_id": ask["clarify_id"], "option_id": garlic["id"]})
    assert item_qty(sess) == {"Garlic Naan": 1}
    say(sess, "ek dal makhani")
    ev = say(sess, "bas")
    offer = next((e for e in ev if e["type"] == "upsell.offer"), None)
    if offer:
        ev = sess.handle({"type": "ui.offer", "offer_id": offer["offer_id"], "action": "accept"})
        assert offer["item"]["name"] in item_qty(sess)
    assert sess.state == "CONFIRMING"


def test_required_size_is_asked(svc):
    sess = dm.CallSession("t_size", svc)
    sess.start()
    ev = say(sess, "ek tandoori chicken")
    ask = next(e for e in ev if e["type"] == "clarify.ask")
    assert {o["label"] for o in ask["options"]} == {"Full", "Half"}
    say(sess, "half")
    line = sess.lines[0]
    assert ("Size", "Half") in line.modifiers and sess.state == "TAKING_ORDER"


def test_fraction_splits_into_full_and_half(svc):
    sess = dm.CallSession("t_dedh", svc)
    sess.start()
    say(sess, "dedh plate tandoori chicken")
    mods = sorted(m for l in sess.lines for m in l.modifiers)
    assert mods == [("Size", "Full"), ("Size", "Half")]


def test_unknown_twice_suggests_typing(svc):
    sess = dm.CallSession("t_unknown", svc)
    sess.start()
    say(sess, "parking hai kya")
    ev = say(sess, "kitne baje band hota hai")
    reply = [e for e in ev if e["type"] == "reply.say"][-1]
    assert reply.get("suggest_typed") is True


def test_silence_reprompts_then_abandons(svc, work_db):
    sess = dm.CallSession("t_silent", svc)
    sess.start()
    assert "reply.say" in types(sess.tick(dm.REPROMPT_AFTER_S))
    assert sess.tick(dm.REPROMPT_AFTER_S + 1) == []  # only one reprompt per silence
    sess.tick(dm.ABANDON_AFTER_S)
    assert sess.state == "ABANDONED" and sess.outcome == "abandoned"
    with Session(db.get_engine(work_db)) as s:
        assert s.get(Call, "t_silent").outcome == "abandoned"


def test_transcript_masks_phone_numbers(svc, work_db):
    sess = dm.CallSession("t_mask", svc)
    sess.start()
    say(sess, "mera number 98123 45610 hai")
    with Session(db.get_engine(work_db)) as s:
        call = s.get(Call, "t_mask")
    assert "98123" not in call.transcript_json and "98XXXXXX10" in call.transcript_json
    assert "45610" not in call.events_json


def test_finalize_twice_sends_one_kot(svc, work_db):
    sess = dm.CallSession("t_idem", svc)
    sess.start()
    say(sess, "ek dal makhani", "bas")
    if sess.state == "OFFERING":
        say(sess, "nahi")
    say(sess, "haan", "Rohan", "9812345610")
    assert sess.state == "FINALIZED"
    from pos.service import DraftOrder
    _payload, result = svc.place(DraftOrder(call_id="t_idem", customer_name="Rohan", customer_phone="9812345610",
                                            lines=[{"item_id": sess.lines[0].item_id, "qty": 1}]))
    assert result.duplicate
    with Session(db.get_engine(work_db)) as s:
        assert s.exec(select(func.count()).select_from(PosOrder).where(PosOrder.kot_no.is_not(None))).one() == 1


def test_server_turn_latency_p95(svc):
    import time
    svc.parser, svc.ranker()
    times = []
    for rep in range(3):
        for sample in load_samples():
            sess = dm.CallSession(f"lat_{rep}_{sample['id']}", svc)
            sess.start()
            for u in sample["utterances"]:
                t = time.perf_counter()
                sess.handle({"type": "transcript.final", "text": u["text"]})
                times.append((time.perf_counter() - t) * 1000)
    times.sort()
    assert times[int(0.95 * (len(times) - 1))] < 300


def test_combo_counts_as_an_accepted_offer(svc):
    sample = next(s for s in load_samples() if s["id"] == "english-ambiguity-combo")
    sess = run_script([u["text"] for u in sample["utterances"]], svc, call_id="t_combo_upsell")
    up = sess.order["upsell"]
    assert up["accepted"] == 1 and up["shown"] == 1
    # Tandoori Chicken ₹380 minus the ₹101 combo saving; margin ₹208 minus the saving.
    assert up["added_revenue"] == 380 - sess.order["discount"]
    assert up["added_margin"] == 208 - sess.order["discount"]
