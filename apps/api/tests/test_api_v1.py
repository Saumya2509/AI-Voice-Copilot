"""Endpoints from file 08 for phases 2 and 3, including the call WebSocket."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import db
import settings
from dialogue.services import drop_sessions
from revenue import pricing as pricing_mod
from schemas._loader import errors


@pytest.fixture
def client(work_db, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", work_db)
    monkeypatch.setattr(settings, "POS_MIN_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "POS_MAX_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "DETERMINISTIC", True)
    drop_sessions()
    import main

    with TestClient(main.app) as c:
        yield c
    drop_sessions()
    db.dispose(work_db)


def test_stats(client):
    s = client.get("/api/v1/stats/summary?window=30").json()
    assert s["window"] == 30 and s["sample_size"] > 3000 and s["class_counts"]["star"] == 28
    items = client.get("/api/v1/stats/items?category=main").json()
    assert len(items["items"]) == 12 and all(i["category"] == "main" for i in items["items"])
    pbm = next(i for i in items["items"] if i["name"] == "Paneer Butter Masala")
    assert pbm["cm"] == 182 and pbm["class"] == "star" and pbm["reason"].startswith("Earns ₹182 per plate")
    for kind in ("puzzles", "underperformers", "plowhorse_risk"):
        out = client.get(f"/api/v1/stats/lists/{kind}").json()
        assert out["items"] and out["assumption"] and out["sample_size"] > 0
    assert client.get("/api/v1/stats/lists/nope").status_code == 404
    assert client.get("/api/v1/stats/items?window=13").json()["error"]["code"] == "invalid_window"


def test_combos_and_pool(client):
    out = client.get("/api/v1/combos?limit=10").json()
    assert out["window"] == 30 and len(out["combos"]) == 10
    first = out["combos"][0]
    assert first["evidence"].startswith("Ordered together in 1 of") and first["pitch"].endswith(f"₹{first['bundle_price']}")
    pooled = [c for c in out["combos"] if c["in_pool"]]
    assert len(pooled) == 3  # top three until the owner chooses
    target = out["combos"][5]["id"]
    r = client.post(f"/api/v1/combos/{target}/pool", json={"in_pool": True}).json()
    assert target in r["pool"]
    again = client.get("/api/v1/combos?limit=10").json()
    assert next(c for c in again["combos"] if c["id"] == target)["in_pool"]


def test_price_preview_matches_formula_and_apply(client):
    items = client.get("/api/v1/stats/items").json()["items"]
    dal = next(i for i in items if i["name"] == "Dal Tadka")
    p = client.post("/api/v1/pricing/preview", json={"item_id": dal["item_id"], "new_price": 200}).json()
    # The client-side formula from the response fields must agree within ₹1.
    units = dal["units"] * 30 / 30
    new_units = units * (200 / dal["price"]) ** p["elasticity"]
    client_delta = (200 - dal["food_cost"]) * new_units - (dal["price"] - dal["food_cost"]) * units
    # Money arrives as an integer or a two-decimal string (file 08).
    delta = float(p["monthly_profit_change"])
    assert abs(client_delta - delta) <= 1
    lo, hi = map(float, p["monthly_profit_change_range"])
    assert lo <= delta <= hi
    recs = client.get("/api/v1/pricing/recommendations").json()
    assert recs["recommendations"] and "Assumed" in recs["note"]
    applied = client.post("/api/v1/pricing/apply", json={"item_id": dal["item_id"], "new_price": 200}).json()
    assert applied["new_price"] == 200
    menu = client.get("/api/v1/menu").json()["items"]
    assert next(i for i in menu if i["id"] == dal["item_id"])["price"] == 200
    after = client.get("/api/v1/stats/items?category=main").json()["items"]
    assert next(i for i in after if i["item_id"] == dal["item_id"])["price"] == 200


def test_settings(client):
    s = client.get("/api/v1/settings").json()
    assert s["upsell"]["max_offers_per_call"] == 2 and s["kitchen_busy"] is False
    assert any(sig["kind"] == "push" for sig in s["active_signals"])
    s = client.put("/api/v1/settings", json={"kitchen_busy": True, "language_packs": ["mr"]}).json()
    assert s["kitchen_busy"] is True and s["language_packs"] == ["mr"]
    assert any(sig["kind"] == "kitchen_busy" for sig in s["active_signals"])
    bad = client.put("/api/v1/settings", json={"upsell": {"max_offers_per_call": 5}})
    assert bad.status_code == 422


def test_nlu_parse_and_samples(client):
    out = client.post("/api/v1/nlu/parse", json={"text": "ek paneer butter masala aur chaar butter naan"}).json()
    assert out["intent"] == "add_item" and [m["qty"] for m in out["matches"]] == [1, 4]
    samples = client.get("/api/v1/samples").json()["samples"]
    assert len(samples) == 3 and all(s["utterances"] for s in samples)


def test_websocket_call_flow_and_resume(client):
    call_id = client.post("/api/v1/calls", json={"channel": "phone"}).json()["call_id"]
    seen = []
    with client.websocket_connect(f"/ws/call/{call_id}") as ws:
        seen += [ws.receive_json(), ws.receive_json()]  # state.changed, reply.say greeting
        assert [e["type"] for e in seen] == ["state.changed", "reply.say"]
        ws.send_json({"type": "transcript.partial", "text": "ek dal"})
        ws.send_json({"type": "transcript.final", "text": "ek dal makhani aur do butter naan"})
        batch = []
        while not any(e["type"] == "reply.say" for e in batch):
            batch.append(ws.receive_json())
        seen += batch
        cart = next(e for e in batch if e["type"] == "cart.updated")["cart"]
        assert {l["name"]: l["qty"] for l in cart["lines"]} == {"Dal Makhani": 1, "Butter Naan": 2}
    # Reconnect and ask for everything after the second event.
    with client.websocket_connect(f"/ws/call/{call_id}") as ws:
        ws.send_json({"type": "resume", "last_seq": 2})
        replay = [ws.receive_json() for _ in range(len(seen) - 2)]
        assert [e["seq"] for e in replay] == [e["seq"] for e in seen[2:]]
    for e in seen:
        assert errors("events", e) == []
    detail = client.get(f"/api/v1/calls/{call_id}").json()
    assert detail["transcript"][0]["speaker"] == "assistant" and detail["events"]
    assert client.delete("/api/v1/calls").json()["deleted"] >= 1
    assert client.get(f"/api/v1/calls/{call_id}").status_code == 404


def test_endpoints_added_for_the_web_app(client):
    items = client.get("/api/v1/stats/items").json()["items"]
    dal = next(i for i in items if i["name"] == "Dal Tadka")
    assert dal["elasticity_source"] == "Assumed" and dal["elasticity"] == -0.8 and dal["n_in_category"] == 12
    trend = client.get(f"/api/v1/stats/items/{dal['item_id']}/trend").json()["series"]
    assert len(trend) == 12 and sum(w["units"] for w in trend) > 0
    graph = client.get("/api/v1/combos/graph").json()
    ids = {n["id"] for n in graph["nodes"]}
    assert graph["edges"] and all(e["source"] in ids and e["target"] in ids and e["lift"] >= 1.2 for e in graph["edges"])
    recs = client.get("/api/v1/pricing/recommendations").json()["recommendations"]
    star = next(r for r in recs if r["class"] == "star")
    # The model keeps rewarding price rises for inelastic items, so the unguarded price is shown capped.
    assert star["unguarded_price"] == round(star["price"] * 1.3) and "capped" in star["unguarded_note"]
    assert client.get("/api/v1/insights").json()["calls_with_orders"] == 0
    assert client.get("/api/v1/calls").json()["calls"] == []
    s = client.put("/api/v1/settings", json={"restaurant_name": "Test Kitchen"}).json()
    assert s["restaurant_name"] == "Test Kitchen"
