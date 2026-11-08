"""Contract tests for file 08: routes, money, analytics metadata, errors, WebSocket behaviour,
reproducible replay, and generated artefacts staying in sync with the shared schemas."""
from __future__ import annotations

import json
import re
import shutil

import pytest
from fastapi import APIRouter
from fastapi.testclient import TestClient

import contract
import db
import settings
from dialogue.services import drop_sessions
from dialogue.simulate import load_samples
from schemas._loader import errors

MONEY_KEYS = {
    "price", "food_cost", "cm", "revenue", "profit", "category_avg_cm", "aov", "total", "subtotal", "discount",
    "bundle_price", "list_price", "suggested_price", "unguarded_price", "monthly_profit_change",
    "monthly_profit_change_range", "unguarded_monthly_profit_change", "potential_monthly_gain", "monthly_exposure",
    "monthly_gain_if_removed", "aov_change_per_order", "margin_change_per_order", "monthly", "from_pricing",
    "from_promoting_puzzles", "new_price", "old_price", "monthly_profit", "predicted_monthly_profit",
    "predicted_monthly_profit_change", "unit_price", "price_delta", "upsell_added", "added_revenue", "added_margin",
    "aov_with_upsell", "aov_without_upsell", "expected_gain",
}
MONEY_STRING = re.compile(r"^-?\d+\.\d{2}$")


@pytest.fixture
def client(work_db, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", work_db)
    monkeypatch.setattr(settings, "POS_MIN_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "POS_MAX_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "DETERMINISTIC", True)
    drop_sessions()
    import main

    with TestClient(main.app, raise_server_exceptions=False) as c:
        yield c
    drop_sessions()
    db.dispose(work_db)


def test_every_route_in_file_08_exists():
    import main

    have = {(m, r.path) for r in main.app.routes for m in getattr(r, "methods", None) or []}
    missing = [(m, p) for m, p in contract.REST if (m, contract.BASE + p) not in have]
    assert not missing, missing
    assert any(r.path == contract.WEBSOCKET for r in main.app.routes)
    missing_improve = [(m, p) for m, p in contract.IMPROVE if (m, contract.BASE + p) not in have]
    assert not missing_improve, missing_improve
    documented = {(m, contract.BASE + p) for m, p in contract.REST + contract.IMPROVE + contract.ADDITIONS}
    extra = {(m, p) for m, p in have if p.startswith(contract.BASE) and (m, p) not in documented and m != "HEAD"}
    assert not extra, f"routes not in file 08 or the documented additions: {extra}"


def _walk_money(value, path="") -> list[str]:
    bad = []
    if isinstance(value, dict):
        for k, v in value.items():
            if k in MONEY_KEYS:
                vals = v if isinstance(v, list) else [v]
                for x in vals:
                    if x is not None and not (isinstance(x, int) and not isinstance(x, bool)) and not (
                            isinstance(x, str) and MONEY_STRING.match(x)):
                        bad.append(f"{path}.{k}={x!r}")
            bad += _walk_money(v, f"{path}.{k}")
    elif isinstance(value, list):
        for i, x in enumerate(value[:50]):
            bad += _walk_money(x, f"{path}[{i}]")
    return bad


def test_money_is_integers_or_two_decimal_strings(client):
    items = client.get("/api/v1/stats/items").json()["items"]
    first = items[0]["item_id"]
    client.post("/api/v1/orders", json={"call_id": "money_check", "customer_phone": "9876543210",
                                        "lines": [{"item_id": first, "qty": 1}]})
    responses = {
        "menu": client.get("/api/v1/menu").json(),
        "items": client.get("/api/v1/stats/items").json(),
        "summary": client.get("/api/v1/stats/summary").json(),
        "puzzles": client.get("/api/v1/stats/lists/puzzles").json(),
        "underperformers": client.get("/api/v1/stats/lists/underperformers").json(),
        "plowhorse_risk": client.get("/api/v1/stats/lists/plowhorse_risk").json(),
        "combos": client.get("/api/v1/combos").json(),
        "pricing": client.get("/api/v1/pricing/recommendations").json(),
        "preview": client.post("/api/v1/pricing/preview", json={"item_id": first, "new_price": 263.5}).json(),
        "orders": client.get("/api/v1/orders?limit=5").json(),
        "order": client.get("/api/v1/orders/" + client.get("/api/v1/orders?status=acked").json()["orders"][0]["order_id"]).json(),
        "insights": client.get("/api/v1/insights").json(),
    }
    bad = [b for name, body in responses.items() for b in _walk_money(body, name)]
    assert not bad, bad[:10]
    # Paise really do come through as strings, not floats.
    assert isinstance(responses["summary"]["aov"], (int, str))
    assert any(isinstance(v, str) for v in (responses["preview"]["monthly_profit_change"],
                                            responses["preview"]["predicted_monthly_profit"]))


def test_analytics_responses_carry_window_and_sample_size(client):
    item = client.get("/api/v1/stats/items").json()["items"][0]["item_id"]
    for path in ["/stats/items", "/stats/summary", "/stats/lists/puzzles", "/stats/lists/underperformers",
                 "/stats/lists/plowhorse_risk", "/combos", "/combos/graph", "/pricing/recommendations",
                 f"/stats/items/{item}/trend", "/insights"]:
        body = client.get("/api/v1" + path).json()
        assert "window" in body and "sample_size" in body, path
    body = client.post("/api/v1/pricing/preview", json={"item_id": item, "new_price": 200}).json()
    assert body["window"] == 30 and body["sample_size"] > 0


def test_error_envelope(client):
    import main

    def envelope(r, status, code):
        assert r.status_code == status, r.text
        body = r.json()
        assert set(body) == {"error"} and set(body["error"]) == {"code", "message", "details"}
        assert body["error"]["code"] == code and body["error"]["message"].endswith(".")

    envelope(client.get("/api/v1/nowhere"), 404, "not_found")
    envelope(client.delete("/api/v1/menu"), 405, "method_not_allowed")
    envelope(client.post("/api/v1/pricing/preview", json={"item_id": "x"}), 422, "invalid_request")
    envelope(client.get("/api/v1/orders/ORD-99999999"), 404, "not_found")

    boom = APIRouter()

    @boom.get("/api/v1/_boom")
    def _boom():
        raise RuntimeError("test failure")

    main.app.include_router(boom)
    try:
        envelope(client.get("/api/v1/_boom"), 500, "internal_error")
    finally:
        main.app.router.routes = [r for r in main.app.router.routes if getattr(r, "path", "") != "/api/v1/_boom"]


def test_websocket_answers_bad_messages_and_keeps_the_call(client):
    with client.websocket_connect("/ws/call/contract_bad") as ws:
        first = [ws.receive_json(), ws.receive_json()]
        ws.send_text("this is not json")
        err = ws.receive_json()
        assert err["type"] == "error" and err["code"] == "bad_message" and err["seq"] == first[-1]["seq"] + 1
        ws.send_json({"type": "launch.rocket"})
        err2 = ws.receive_json()
        assert err2["code"] == "bad_message" and "launch.rocket" in err2["message"]
        ws.send_json({"type": "transcript.final", "text": "ek dal makhani"})
        got = []
        while not any(e["type"] == "reply.say" for e in got):
            got.append(ws.receive_json())
        assert any(e["type"] == "cart.updated" for e in got)
        for e in first + [err, err2] + got:
            assert errors("events", e) == [], (e["type"], errors("events", e))


def _play_over_websocket(client, call_id: str, lines: list[str]) -> list[dict]:
    events = []
    with client.websocket_connect(f"/ws/call/{call_id}") as ws:
        events += [ws.receive_json(), ws.receive_json()]
        for text in lines:
            ws.send_json({"type": "transcript.final", "text": text})
            turn = []
            while not any(e["type"] == "reply.say" for e in turn):
                turn.append(ws.receive_json())
            events += turn
    return events


def _without_times(event: dict) -> dict:
    """Events must match exactly apart from wall-clock times."""
    e = {k: v for k, v in event.items() if k != "ts"}
    if "order" in e:
        e["order"] = {k: v for k, v in e["order"].items() if k != "confirmed_at"}
    return e


def test_recorded_call_replays_identically_over_websocket(seeded_db, tmp_path, monkeypatch):
    import main

    monkeypatch.setattr(settings, "POS_MIN_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "POS_MAX_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "DETERMINISTIC", True)
    sample = next(s for s in load_samples() if s["id"] == "hinglish-family-dinner")
    lines = [u["text"] for u in sample["utterances"]]
    runs = []
    for n in range(2):
        path = tmp_path / f"replay{n}.sqlite"
        shutil.copy(seeded_db, path)
        monkeypatch.setattr(settings, "DB_PATH", path)
        drop_sessions()
        with TestClient(main.app) as c:
            events = _play_over_websocket(c, "replay_call", lines)
        db.dispose(path)
        assert [e["seq"] for e in events] == list(range(1, len(events) + 1))
        for e in events:
            assert errors("events", e) == [], (e["type"], errors("events", e))
        runs.append([_without_times(e) for e in events])
    drop_sessions()
    assert runs[0] == runs[1]
    assert any(e["type"] == "pos.ack" for e in runs[0])


def test_generated_pydantic_models_match_the_schemas(tmp_path):
    import sys
    from pathlib import Path

    root = Path(settings.REPO_ROOT)
    sys.path.insert(0, str(root))
    import tasks

    if not (tasks.VENV / ("Scripts" if sys.platform == "win32" else "bin")).exists():
        pytest.skip("generator not installed")
    tasks.pydantic_models(tmp_path)
    for name in tasks.PYDANTIC_FROM:
        committed = (root / "apps/api/schemas/generated" / f"{name}.py").read_text(encoding="utf-8")
        fresh = (tmp_path / f"{name}.py").read_text(encoding="utf-8")
        assert committed == fresh, f"{name}.py is out of date: run make types"


def test_openapi_export_is_current(tmp_path):
    out = tmp_path / "openapi.json"
    contract.export_openapi(out)
    committed = settings.SHARED_SCHEMA_DIR.parent / "openapi.json"
    assert committed.exists(), "run make types"
    assert json.loads(committed.read_text(encoding="utf-8")) == json.loads(out.read_text(encoding="utf-8")), \
        "packages/shared/openapi.json is out of date: run make types"
