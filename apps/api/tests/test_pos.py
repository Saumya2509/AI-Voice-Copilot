"""Order finalization, PoS push, idempotency, retry and KOT."""
from __future__ import annotations

import random

import pytest
from sqlmodel import Session, func, select

import db
from models import Item, Order, PosOrder
from pos.kot import build_kot, render_text
from pos.mock_pos import MockPosAdapter
from pos.service import DraftLine, DraftModifier, DraftOrder, OrderRejected, finalize_and_push, retry_order
from schemas import validate_kot, validate_order

no_sleep = lambda _s: None


def ids(session, *names):
    rows = {i.name: i for i in session.exec(select(Item).where(Item.name.in_(names)))}
    return [rows[n] for n in names]


def adapter(path, failure_rate=0.0, seed=1):
    return MockPosAdapter(db.get_engine(path), failure_rate=failure_rate, latency_ms=(0, 0),
                          rng=random.Random(seed), sleep=no_sleep)


def draft(session, call_id="call_0001"):
    pbm, naan, garlic = ids(session, "Paneer Butter Masala", "Butter Naan", "Garlic Naan")
    return DraftOrder(
        call_id=call_id, channel="phone", language="hinglish",
        customer_name="Rohan", customer_phone="+91 98123 45610",
        lines=[
            DraftLine(item_id=pbm.id, qty=1, modifiers=[DraftModifier(group="Spice", name="Medium")],
                      notes="no onion"),
            DraftLine(item_id=naan.id, qty=4),
            DraftLine(item_id=garlic.id, qty=2, source="upsell", upsell_rule_id=77),
        ],
        upsell_shown=1,
    )


def test_finalize_push_and_kot(work_db):
    with Session(db.get_engine(work_db)) as s:
        payload, result = finalize_and_push(s, adapter(work_db), draft(s), sleep=no_sleep)
        assert result.status == "acked" and result.kot_no.startswith("K-")
        assert [e["type"] for e in result.events] == ["pos.sent", "pos.ack"]
        data = payload.to_json_dict()
        assert validate_order(data) == []
        # Server prices: 280 + 4 x 60 + 2 x 70
        assert data["subtotal"] == 660 and data["total"] == 660
        assert data["customer"]["phone"] == "98XXXXXX10"
        assert data["upsell"] == {"shown": 1, "accepted": 1, "added_revenue": 140, "added_margin": 100}
        row = s.exec(select(PosOrder)).one()
        assert row.status == "acked" and row.kot_json
        order = s.get(Order, payload_id(payload))
        assert order.total_paise == 66000 and order.channel == "phone"


def payload_id(payload):
    return int(payload.order_id.removeprefix("ORD-"))


def test_retry_never_creates_a_second_kot(work_db):
    with Session(db.get_engine(work_db)) as s:
        a = adapter(work_db)
        p1, r1 = finalize_and_push(s, a, draft(s), sleep=no_sleep)
        p2, r2 = finalize_and_push(s, a, draft(s), sleep=no_sleep)
        assert p1.order_id == p2.order_id and r1.kot_no == r2.kot_no and r2.duplicate
        assert s.exec(select(func.count()).select_from(PosOrder)).one() == 1
        r3 = retry_order(s, a, payload_id(p1), sleep=no_sleep)
        assert r3.kot_no == r1.kot_no
        # A different cart in the same call is a different order.
        d = draft(s)
        d.lines[1].qty = 3
        p4, r4 = finalize_and_push(s, a, d, sleep=no_sleep)
        assert p4.order_id != p1.order_id and r4.kot_no != r1.kot_no


def test_failures_end_in_needs_attention_then_retry_succeeds(work_db):
    with Session(db.get_engine(work_db)) as s:
        waits = []
        payload, result = finalize_and_push(s, adapter(work_db, failure_rate=1.0), draft(s), sleep=waits.append)
        assert result.status == "needs_attention" and result.attempts == 3
        assert waits == [0.25, 0.5], "exponential backoff between the three attempts"
        assert "after 3 attempts" in result.error
        assert result.events[-1]["type"] == "error"
        row = s.exec(select(PosOrder)).one()
        assert row.status == "needs_attention" and row.kot_no is None

        ok = retry_order(s, adapter(work_db), payload_id(payload), sleep=no_sleep)
        assert ok.status == "acked" and ok.kot_no
        again = retry_order(s, adapter(work_db), payload_id(payload), sleep=no_sleep)
        assert again.kot_no == ok.kot_no
        assert s.exec(select(func.count()).select_from(PosOrder).where(PosOrder.kot_no.is_not(None))).one() == 1


def test_flaky_pos_recovers_within_attempts(work_db):
    with Session(db.get_engine(work_db)) as s:
        _p, result = finalize_and_push(s, adapter(work_db, failure_rate=0.5, seed=3), draft(s), sleep=no_sleep)
        assert result.status in ("acked", "needs_attention")
        if result.status == "acked":
            assert s.exec(select(PosOrder)).one().kot_no == result.kot_no


def test_server_rejects_bad_orders(work_db):
    with Session(db.get_engine(work_db)) as s:
        dal, tandoori = ids(s, "Dal Makhani", "Tandoori Chicken")
        with pytest.raises(OrderRejected) as e:
            finalize_and_push(s, adapter(work_db), DraftOrder(lines=[
                DraftLine(item_id=dal.id, qty=1, modifiers=[DraftModifier(group="Add-ons", name="Extra Cheese")])]))
        assert e.value.code == "invalid_modifier"
        with pytest.raises(OrderRejected) as e:
            finalize_and_push(s, adapter(work_db), DraftOrder(lines=[DraftLine(item_id=tandoori.id, qty=1)]))
        assert e.value.code == "missing_choice" and "size" in e.value.message
        with pytest.raises(OrderRejected) as e:
            finalize_and_push(s, adapter(work_db), DraftOrder(lines=[]))
        assert e.value.code == "empty_order"
        _p, r = finalize_and_push(s, adapter(work_db), DraftOrder(call_id="c-half", lines=[
            DraftLine(item_id=tandoori.id, qty=1, modifiers=[DraftModifier(group="size", name="half")])]),
            sleep=no_sleep)
        assert _p.lines[0].unit_price == 380 - 171 and _p.lines[0].modifiers[0].name == "Half"


def test_kot_groups_lines_by_station(work_db):
    with Session(db.get_engine(work_db)) as s:
        payload, result = finalize_and_push(s, adapter(work_db), draft(s), sleep=no_sleep)
        row = s.exec(select(PosOrder)).one()
    import json
    kot = json.loads(row.kot_json)
    assert validate_kot(kot) == []
    assert kot["stations"] == ["tandoor", "curry"]
    assert [l["station"] for l in kot["lines"]] == ["tandoor", "tandoor", "curry"]
    pbm = next(l for l in kot["lines"] if l["item"] == "Paneer Butter Masala")
    assert pbm["mods"] == ["Medium spicy"] and pbm["note"] == "no onion"
    assert kot["notes"] == "Paneer Butter Masala: no onion"
    assert kot["customer"]["phone"] == "98XXXXXX10"


def test_render_text_ticket(work_db):
    with Session(db.get_engine(work_db)) as s:
        payload, _ = finalize_and_push(s, adapter(work_db), draft(s), sleep=no_sleep)
        stations = {i.id: i.station for i in s.exec(select(Item))}
    text = render_text(build_kot(payload, stations, "K-9999", "2026-10-11T13:42:10Z"))
    assert "--- TANDOOR ---" in text and "--- CURRY ---" in text and "NOTE: no onion" in text
