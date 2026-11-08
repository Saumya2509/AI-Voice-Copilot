"""Server side of improve.md: CSV upload, analytics, live orders, public menu, English display,
staff controls and recordings."""
from __future__ import annotations

import json
import threading
import time

import pytest
from fastapi.testclient import TestClient

import db
import settings
from dialogue.services import drop_sessions
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


@pytest.fixture
def empty_client(tmp_path, monkeypatch):
    """A fresh install: the built-in menu is loaded, there are no orders."""
    path = tmp_path / "empty.sqlite"
    monkeypatch.setattr(settings, "DB_PATH", path)
    monkeypatch.setattr(settings, "POS_MIN_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "POS_MAX_LATENCY_MS", 0)
    drop_sessions()
    import main

    with TestClient(main.app) as c:
        yield c
    drop_sessions()
    db.dispose(path)


@pytest.fixture
def bare_client(tmp_path, monkeypatch):
    """No menu at all (menu preloading switched off)."""
    path = tmp_path / "bare.sqlite"
    monkeypatch.setattr(settings, "DB_PATH", path)
    monkeypatch.setattr(settings, "PRELOAD_MENU", False)
    drop_sessions()
    import main

    with TestClient(main.app) as c:
        yield c
    drop_sessions()
    db.dispose(path)


B = "/api/v1"
SALES = (
    "Bill No,Bill Date,Item,Qty,Rate,Category,Type,Order Type,Customer\n"
    "B1,10/10/2026 13:05,Paneer Butter Masala,1,320,Mains,veg,Dine In,Asha\n"
    "B1,10/10/2026 13:05,garlic nan,3,70,Breads,veg,Dine In,Asha\n"
    "B2,10/10/2026 20:15,Butter Chicken,2,420,Mains,non-veg,Phone,\n"
    "B2,10/10/2026 20:15,Garlic Naan,2,70,Breads,veg,Phone,\n"
    "B3,11/10/2026 21:00,Gulab Jamun,2,90,Desserts,veg,Takeaway,Ravi\n"
    "B3,11/10/2026 21:00,Gulab Jamun,2,90,Desserts,veg,Takeaway,Ravi\n"
    "B4,not a date,Garlic Naan,1,70,Breads,veg,Dine In,\n"
    "B5,11/10/2026 21:30,Garlic Naan,1,,Breads,veg,Dine In,\n"
    "B6,11/10/2026 21:40,Unicorn Biryani,1,500,Rice,veg,Dine In,\n"
)


def _upload(c, content=SALES, **data):
    return c.post(B + "/import/" + data.pop("step", "preview"), files={"file": ("sales.csv", content, "text/csv")},
                  data={"kind": "sales", **data})


def test_fresh_install_has_menu_and_no_figures(empty_client):
    c = empty_client
    ov = c.get(B + "/analytics/overview").json()
    assert ov["orders"] == 0 and ov["sample_size"] == 0 and ov["revenue"] == 0
    assert c.get(B + "/analytics/category-share").json()["categories"] == []
    assert c.get(B + "/orders").json()["total"] == 0
    names = [i["name"] for cat in c.get(B + "/public/menu").json()["categories"] for i in cat["items"]]
    assert "Dal Makhani" in names and len(names) == 45
    photos = [i["image_url"] for cat in c.get(B + "/public/menu").json()["categories"] for i in cat["items"]]
    assert all(u and u.startswith("/dishes/") and u.endswith(".webp") for u in photos)  # seed/photos.py
    assert any(i["name"] == "Garlic Naan" for i in c.get(B + "/menu").json()["items"])


def test_templates(client):
    r = client.get(B + "/import/template/sales")
    assert r.status_code == 200 and r.text.startswith("order_id,order_time,item_name,quantity,price")
    assert client.get(B + "/import/template/menu").text.startswith("item_name,category,price")
    assert client.get(B + "/import/template/nope").status_code == 404


def test_sales_upload_keeps_the_menu(client):
    names = lambda: sorted((i["id"], i["name"]) for c in client.get(B + "/public/menu").json()["categories"]
                           for i in c["items"])
    menu_before = names()
    p = _upload(client).json()
    assert p["uses_menu"] is True
    assert p["mapping"]["order_ref"] == "Bill No" and p["mapping"]["veg"] == "Type"
    assert p["accepted"] == 5 and p["duplicates"] == 1 and p["rejected"] == 3
    reasons = {r["reason"] for r in p["rejected_rows"]}
    assert reasons == {"bad date", "missing price", "item not on the menu"}
    assert p["items_found"] == 4 and p["orders_found"] == 3  # "garlic nan" is an alias of Garlic Naan
    assert p["needs_food_cost"] == [] and p["food_cost_message"] is None

    summary = _upload(client, step="commit").json()
    assert summary["orders"] == 3 and summary["items"] == 45 and summary["message"].startswith("Analysed 3 orders")
    ov = client.get(B + "/analytics/overview").json()
    assert ov["orders"] == 3 and ov["revenue"] == 320 + 3 * 70 + 2 * 420 + 2 * 70 + 2 * 90
    assert client.get(B + "/orders").json()["total"] == 3
    assert names() == menu_before  # menu untouched

    # A different file replaces the orders again; rows only for unknown dishes import nothing.
    other = "order_id,order_time,item_name,quantity,price,food_cost\nX1,2026-10-01T12:00:00Z,Masala Dosa,4,150,40\n"
    r = _upload(client, content=other, step="commit")
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_rows"
    other = "order_id,order_time,item_name,quantity,price,food_cost\nX1,2026-10-01T12:00:00Z,Kulfi,4,150,40\n"
    _upload(client, content=other, step="commit")
    ov2 = client.get(B + "/analytics/overview").json()
    assert ov2["orders"] == 1 and ov2["revenue"] == 600


def test_sample_sales_csv_matches_the_menu(empty_client):
    r = empty_client.get(B + "/import/sample-csv")
    assert r.status_code == 200 and r.text.startswith("order_id,order_time,item_name,quantity,price")
    p = _upload(empty_client, content=r.content).json()
    assert p["rejected"] == 0 and p["duplicates"] == 0 and p["orders_found"] > 2000
    summary = _upload(empty_client, content=r.content, step="commit").json()
    assert summary["orders"] == p["orders_found"] and summary["items"] == 45


def test_upload_without_a_menu_builds_items(bare_client):
    c = bare_client
    assert c.get(B + "/public/menu").json()["categories"] == []
    content = SALES.replace("B6,11/10/2026 21:40,Unicorn Biryani,1,500,Rice,veg,Dine In,\n", "")
    p = _upload(c, content=content).json()
    assert p["uses_menu"] is False and p["accepted"] == 5 and p["rejected"] == 2
    assert p["items_found"] == 5  # "garlic nan" and "Garlic Naan" are different items without a menu
    assert set(p["needs_food_cost"]) == {"Mains", "Breads", "Desserts"} and p["food_cost_message"]
    r = _upload(c, content=content, step="commit")
    assert r.status_code == 422 and r.json()["error"]["code"] == "food_cost_needed"
    r = _upload(c, content=content, step="commit",
                default_cost_pct=json.dumps({"Mains": 35, "Breads": 25, "Desserts": 30}))
    assert r.json()["orders"] == 3
    ov = c.get(B + "/analytics/overview").json()
    assert ov["estimated"] is True
    cats = {x["category"]: x["revenue"] for x in c.get(B + "/analytics/category-share").json()["categories"]}
    assert cats == {"Mains": 1160, "Breads": 350, "Desserts": 180}
    veg = {x["key"]: x["revenue"] for x in c.get(B + "/analytics/veg-split").json()["slices"]}
    assert veg == {"veg": 850, "non_veg": 840}


def test_load_sample_restaurant(empty_client):
    r = empty_client.post(B + "/import/sample").json()
    assert r["sample"] is True and r["orders"] > 10_000 and r["message"].startswith("Analysed")
    assert empty_client.get(B + "/analytics/overview").json()["orders"] == r["orders"]


def test_analytics_filters_agree(client):
    ov = client.get(B + "/analytics/overview").json()
    assert ov["window"] == 90 and ov["sample_size"] > 11_000
    cats = client.get(B + "/analytics/category-share").json()["categories"]
    mains = next(c for c in cats if c["category"] == "Mains")
    filtered = client.get(B + "/analytics/overview?category=Mains").json()
    assert filtered["revenue"] == mains["revenue"] and filtered["filters"] == {"category": "Mains"}
    veg = client.get(B + "/analytics/overview?veg=veg").json()
    nonveg = client.get(B + "/analytics/overview?veg=non_veg").json()
    assert int(veg["revenue"]) + int(nonveg["revenue"]) == int(ov["revenue"])
    week = client.get(B + "/analytics/overview?from=2026-10-04&to=2026-10-10").json()
    assert week["window"] == 7 and week["sample_size"] < ov["sample_size"]
    heat = client.get(B + "/analytics/heatmap?channel=phone").json()
    phone = client.get(B + "/analytics/channel-mix").json()["channels"]
    assert sum(c["orders"] for c in heat["cells"]) == next(c for c in phone if c["channel"] == "phone")["orders"]
    trend = client.get(B + "/analytics/trend?grain=day&from=2026-10-01&to=2026-10-10").json()["points"]
    assert len(trend) == 10
    top = client.get(B + "/analytics/top-items?by=profit&limit=5").json()["items"]
    assert len(top) == 5 and int(top[0]["profit"]) >= int(top[-1]["profit"])
    classes = {c["class"]: c["count"] for c in client.get(B + "/analytics/class-split").json()["classes"]}
    assert sum(classes.values()) == 45
    assert client.get(B + "/analytics/items").json()["items"][0]["x"] >= 0
    assert client.get(B + "/analytics/lists/puzzles").json()["items"]
    assert client.get(B + "/analytics/overview?from=bad").status_code == 422


def test_orders_paging_search_and_export(client):
    first = client.get(B + "/orders?limit=25").json()
    assert len(first["orders"]) == 25 and first["next_cursor"]
    second = client.get(B + f"/orders?limit=25&cursor={first['next_cursor']}").json()
    assert not {o["order_id"] for o in first["orders"]} & {o["order_id"] for o in second["orders"]}
    assert first["orders"][-1]["ts"] >= second["orders"][0]["ts"]
    oid = first["orders"][3]["order_id"]
    assert client.get(B + f"/orders?q={oid}").json()["orders"][0]["order_id"] == oid
    hits = client.get(B + "/orders?q=rasmalai&limit=5").json()
    detail = client.get(B + f"/orders/{hits['orders'][0]['order_id']}").json()
    assert any(l["name"] == "Rasmalai" for l in detail["lines"])
    big = client.get(B + "/orders?sort=total_desc&limit=3").json()["orders"]
    assert int(big[0]["total"]) >= int(big[1]["total"]) >= int(big[2]["total"])
    week = client.get(B + "/orders?from=2026-10-04&to=2026-10-10&channel=phone").json()
    csv = client.get(B + "/orders/export?from=2026-10-04&to=2026-10-10&channel=phone")
    assert csv.headers["content-type"].startswith("text/csv")
    assert csv.text.strip().count("\n") == week["total"]
    assert client.get(B + "/orders?has_upsell=true").json()["total"] == 0


def test_new_order_reaches_the_stream(client):
    got: list[str] = []

    def listen():
        with client.stream("GET", B + "/orders/stream?max_events=1") as r:
            for line in r.iter_lines():
                got.append(line)
                if line.startswith("data:"):
                    return

    t = threading.Thread(target=listen, daemon=True)
    t.start()
    time.sleep(0.5)
    start = time.time()
    item = client.get(B + "/menu").json()["items"][0]["id"]
    client.post(B + "/orders", json={"call_id": "stream_test", "lines": [{"item_id": item, "qty": 1}]})
    t.join(timeout=5)
    assert any(l.startswith("event: order") for l in got), got
    assert time.time() - start < 2


def test_staff_menu_marks(client):
    items = client.get(B + "/menu").json()["items"]
    picks = [i for i in items if i["chefs_pick"]]
    assert 1 <= len(picks) <= 7  # at most one per category, decided by the data
    assert any(i["hold_reason"] for i in items)  # mango pulp is low in the sample stock


def test_call_shows_english_and_staff_controls(client):
    events = []
    with client.websocket_connect("/ws/call/improve_call") as ws:
        events += [ws.receive_json(), ws.receive_json()]

        def turn(msg):
            ws.send_json(msg)
            out = []
            while not any(e["type"] in ("reply.say", "cart.updated") for e in out):
                out.append(ws.receive_json())
            return out

        heard = turn({"type": "transcript.final", "text": "दो दाल मखनी और चार बटर नान"})
        while not any(e["type"] == "reply.say" for e in heard):
            heard.append(ws.receive_json())
        events += heard
        tr = next(e for e in heard if e["type"] == "transcript")
        assert tr["display_text_en"] == "2 Dal Makhani and 4 Butter Naan" and tr["original_text"].startswith("दो")
        assert tr["lang"] == "hi"
        assert {e["item_id"] for e in heard if e["type"] == "menu.highlight"}
        reply = next(e for e in heard if e["type"] == "reply.say")
        assert reply["display_text_en"].startswith("Added 2 Dal Makhani and 4 Butter Naan")
        menu = {i["name"]: i["id"] for i in client.get(B + "/menu").json()["items"]}
        staff = turn({"type": "ui.add_item", "item_id": menu["Gulab Jamun"], "qty_delta": 1})
        events += staff
        cart = next(e for e in staff if e["type"] == "cart.updated")["cart"]
        assert any(l["name"] == "Gulab Jamun" and l["source"] == "staff" for l in cart["lines"])
        ws.send_json({"type": "ui.send"})
        sent = []
        while not any(e["type"] in ("pos.ack", "error") for e in sent):
            sent.append(ws.receive_json())
        events += sent
        order = next(e for e in sent if e["type"] == "order.finalized")["order"]
        assert any(l["source"] == "staff" for l in order["lines"]) and errors("order", order) == []
    for e in events:
        assert errors("events", e) == [], (e["type"], errors("events", e))
    tr = client.get(B + "/calls/improve_call/transcript").json()
    assert tr["lines"][1]["text"] == "2 Dal Makhani and 4 Butter Naan"
    original = client.get(B + "/calls/improve_call/transcript?lang=original").json()
    assert original["lines"][1]["text"].startswith("दो")
    assert any(m["kind"] == "sent" for m in tr["markers"])


def test_recordings_need_consent_and_can_be_deleted(client):
    client.post(B + "/calls")
    call_id = client.get(B + "/calls").json()["calls"][0]["call_id"]
    audio = b"\x1aE\xdf\xa3" + b"0" * 2048
    r = client.post(B + f"/calls/{call_id}/recording", files={"file": ("call.webm", audio, "audio/webm")})
    assert r.status_code == 403 and r.json()["error"]["code"] == "recording_off"
    client.put(B + "/settings", json={"recording": {"enabled": True}})
    r = client.post(B + f"/calls/{call_id}/recording", files={"file": ("call.webm", audio, "audio/webm")},
                    data={"duration_s": "12.5"})
    assert r.status_code == 200
    got = client.get(B + f"/calls/{call_id}/recording")
    assert got.status_code == 200 and got.content == audio and got.headers["content-type"] == "audio/webm"
    listed = client.get(B + "/calls?has_recording=true").json()["calls"]
    assert listed[0]["call_id"] == call_id and listed[0]["duration_s"] == 12.5
    assert client.delete(B + f"/calls/{call_id}/recording").json()["has_recording"] is False
    assert client.get(B + f"/calls/{call_id}/recording").status_code == 404
    assert client.delete(B + f"/calls/{call_id}").status_code == 200
    assert client.get(B + f"/calls/{call_id}").status_code == 404


def test_vocabulary_for_the_menu_biased_recogniser(client):
    en = client.get(B + "/nlu/vocabulary?lang=en").json()
    assert {"dal makhani", "butter naan", "two", "thats all", "chahiye"} <= set(en["phrases"])
    assert en["count"] == len(en["phrases"]) == len(set(en["phrases"]))
    hi = client.get(B + "/nlu/vocabulary?lang=hi").json()
    assert hi["phrases"] and all(any("ऀ" <= ch <= "ॿ" for ch in p) for p in hi["phrases"])
    assert "दाल मखनी" in hi["phrases"]
    assert client.get(B + "/nlu/vocabulary?lang=fr").status_code == 422


def _turn(ws, msg, until=("cart.updated",)):
    ws.send_json(msg)
    out = []
    while not any(e["type"] in until for e in out):
        out.append(ws.receive_json())
    return out


def test_menu_biased_transcript_wins_only_when_it_matches_better(client):
    with client.websocket_connect("/ws/call/alt_call") as ws:
        ws.receive_json(), ws.receive_json()
        heard = _turn(ws, {"type": "transcript.final", "text": "one dull mug honey and to butter none",
                           "alternatives": ["one dal makhani and to butter naan [unk]"]})
        cart = next(e for e in heard if e["type"] == "cart.updated")["cart"]
        assert {(l["name"], l["qty"]) for l in cart["lines"]} == {("Dal Makhani", 1), ("Butter Naan", 2)}
        # Equal matches keep the open transcript.
        heard = _turn(ws, {"type": "transcript.final", "text": "one gulab jamun",
                           "alternatives": ["one gulab jamun please"]}, until=("transcript",))
        assert next(e for e in heard if e["type"] == "transcript")["original_text"] == "one gulab jamun"


def _settle(ws, msg):
    """Send a message and read events until the agent has finished reacting: a reply or a state change
    always closes a turn that changed the ticket or asked a question."""
    ws.send_json(msg)
    out = []
    while not out or out[-1]["type"] not in ("reply.say", "state.changed") or (
            out[-1]["type"] == "state.changed" and out[-1]["state"] == "CLARIFYING"):
        out.append(ws.receive_json())
    return out


def test_staff_adds_a_combo_at_the_combo_price(client):
    combo = next(c for c in client.get(B + "/combos").json()["combos"] if c["in_pool"])
    with client.websocket_connect("/ws/call/combo_call") as ws:
        ws.receive_json(), ws.receive_json()
        out = _settle(ws, {"type": "ui.add_combo", "combo_id": combo["id"]})
        cart = [e for e in out if e["type"] == "cart.updated"][-1]["cart"]
        while (ask := next((e for e in out if e["type"] == "clarify.ask"), None)) is not None:
            # A dish with a required choice (Full or Half) asks first; answer with the first option.
            out = _settle(ws, {"type": "ui.choice", "clarify_id": ask["clarify_id"], "option_id": ask["options"][0]["id"]})
            cart = next((e["cart"] for e in reversed(out) if e["type"] == "cart.updated"), cart)
        assert {l["item_id"] for l in cart["lines"]} == {i["id"] for i in combo["items"]}
        assert all(l["source"] == "staff" and l["combo_id"] == combo["id"] for l in cart["lines"])
        assert cart["discount"] == combo["list_price"] - combo["bundle_price"]
        assert cart["upsell"]["added_revenue"] == 0 and cart["upsell"]["accepted"] == 0  # not an offer
        ws.send_json({"type": "ui.send"})
        sent = []
        while not any(e["type"] in ("pos.ack", "error") for e in sent):
            sent.append(ws.receive_json())
        order = next(e for e in sent if e["type"] == "order.finalized")["order"]
        assert order["discount"] == cart["discount"] and order["upsell"]["accepted"] == 0
        assert errors("order", order) == []



def test_unknown_combo_is_an_error(client):
    with client.websocket_connect("/ws/call/combo_err") as ws:
        ws.receive_json(), ws.receive_json()
        err = _turn(ws, {"type": "ui.add_combo", "combo_id": "nope"}, until=("error",))
        assert next(e for e in err if e["type"] == "error")["code"] == "unknown_combo"


def test_orders_can_include_their_dishes(client):
    page = client.get(B + "/orders?limit=3&with_items=true").json()
    assert all(o["items"] and {"name", "qty"} <= set(o["items"][0]) for o in page["orders"])
    assert "items" not in client.get(B + "/orders?limit=1").json()["orders"][0]


def test_replies_carry_what_the_voice_reads(client):
    with client.websocket_connect("/ws/call/voice_call") as ws:
        ws.receive_json()
        hello = ws.receive_json()
        assert hello["type"] == "reply.say" and hello["speech_lang"] in ("en", "hi")
        out = _turn(ws, {"type": "transcript.final", "text": "do butter naan dena"}, until=("reply.say",))
        reply = next(e for e in out if e["type"] == "reply.say")
        assert reply["lang"] == "hinglish" and reply["speech_lang"] == "hi"
        assert "जोड़ दिया" in reply["speech_text"] and "Butter Naan" in reply["speech_text"]  # Devanagari, dish in English
        out = _turn(ws, {"type": "transcript.final", "text": "two garlic naan please"}, until=("reply.say",))
        # The call's language follows the caller; an English reply is read by the English voice.
        reply = next(e for e in out if e["type"] == "reply.say")
        assert (reply["speech_lang"] == "en") == (reply["lang"] == "en")


def test_barge_in_is_recorded_on_the_transcript(client):
    with client.websocket_connect("/ws/call/barge_call") as ws:
        ws.receive_json(), ws.receive_json()
        ws.send_json({"type": "ui.barge_in"})
        _turn(ws, {"type": "transcript.final", "text": "ek dal makhani"}, until=("reply.say",))
    tr = client.get(B + "/calls/barge_call/transcript").json()
    assert tr["lines"][0]["speaker"] == "assistant" and tr["lines"][0]["interrupted"] is True
    assert any(m["kind"] == "interrupted" for m in tr["markers"])
    assert [m["at_s"] for m in tr["markers"]] == sorted(m["at_s"] for m in tr["markers"])


def test_natural_voice_endpoint(client, monkeypatch):
    import tts

    class Fake(tts.Tts):
        def available(self):
            return {"hi": True, "en": False}

        def _voice(self, lang):
            class V:
                def synthesize_wav(self, text, w):
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(b"\0\0" * 160)
            return V()

    monkeypatch.setattr(tts, "_engine", Fake({}))
    assert client.get(B + "/tts/status").json() == {"available": True, "voices": {"hi": True, "en": False}}
    r = client.get(B + "/tts", params={"text": "नमस्ते", "lang": "hi"})
    assert r.status_code == 200 and r.headers["content-type"] == "audio/wav" and r.content[:4] == b"RIFF"
    r = client.get(B + "/tts", params={"text": "Hello", "lang": "en"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "voice_not_installed"
    assert client.get(B + "/tts", params={"text": "x", "lang": "fr"}).status_code == 422

    class Silent(Fake):
        def _voice(self, lang):
            class V:
                def synthesize_wav(self, text, w):
                    pass  # no audio written, as Piper does for punctuation only
            return V()

    monkeypatch.setattr(tts, "_engine", Silent({}))
    r = client.get(B + "/tts", params={"text": "?", "lang": "hi"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "nothing_to_say"


def test_speech_settings_are_validated(client):
    ok = client.put(B + "/settings", json={"speech": {"engine": "offline", "browser_service": False, "voice": "browser", "barge_in": False}})
    assert ok.status_code == 200 and ok.json()["speech"]["voice"] == "browser"
    bad = client.put(B + "/settings", json={"speech": {"voice": "robot"}})
    assert bad.status_code == 422
