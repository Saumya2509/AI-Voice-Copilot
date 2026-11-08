"""HTTP endpoints for phase 1: health, menu, orders, retry and import."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

import db
import settings


@pytest.fixture
def client(work_db, monkeypatch):
    monkeypatch.setattr(settings, "DB_PATH", work_db)
    monkeypatch.setattr(settings, "POS_MIN_LATENCY_MS", 0)
    monkeypatch.setattr(settings, "POS_MAX_LATENCY_MS", 0)
    import main

    with TestClient(main.app) as c:
        yield c
    db.dispose(work_db)


def test_health_and_menu(client):
    h = client.get("/api/v1/health").json()
    assert h["status"] == "ok" and h["items"] == 45 and h["orders"] > 10_000
    menu = client.get("/api/v1/menu").json()
    assert len(menu["items"]) == 45 and len(menu["categories"]) == 7
    tandoori = next(i for i in menu["items"] if i["name"] == "Tandoori Chicken")
    size = next(g for g in tandoori["modifier_groups"] if g["name"] == "Size")
    assert size["required"] and {o["name"] for o in size["options"]} == {"Full", "Half"}


def test_error_format(client):
    r = client.get("/api/v1/orders/ORD-999999")
    assert r.status_code == 404
    assert set(r.json()["error"]) == {"code", "message", "details"}
    r = client.post("/api/v1/orders", json={"lines": "nope"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_request"


def test_order_push_list_and_retry(client):
    menu = client.get("/api/v1/menu").json()["items"]
    dal = next(i for i in menu if i["name"] == "Dal Makhani")
    body = {"call_id": "call_api_1", "customer_phone": "9876543210",
            "lines": [{"item_id": dal["id"], "qty": 2, "notes": "less butter"}]}
    r = client.post("/api/v1/orders", json=body).json()
    assert r["status"] == "acked" and r["order"]["total"] == 2 * dal["price"]
    assert r["order"]["customer"]["phone"] == "98XXXXXX10"
    oid = r["order"]["order_id"]

    listed = client.get("/api/v1/orders", params={"status": "acked"}).json()
    assert listed["total"] == 1 and listed["orders"][0]["order_id"] == oid
    phone = client.get("/api/v1/orders", params={"channel": "phone", "limit": 5}).json()
    assert phone["total"] > 1000 and len(phone["orders"]) == 5

    detail = client.get(f"/api/v1/orders/{oid}").json()
    assert detail["kot"]["kot_no"] == r["kot_no"] and detail["order_json"]["order_id"] == oid

    again = client.post(f"/api/v1/orders/{oid}/retry").json()
    assert again["kot_no"] == r["kot_no"]
    seeded = client.post("/api/v1/orders/ORD-1/retry")
    assert seeded.status_code == 422 and seeded.json()["error"]["code"] == "not_found"


def test_import_dry_run_endpoint(client):
    csv_bytes = b"Dish,Section,Selling Price,Cost\nNew Paneer Roll,Starters,180,60\n"
    r = client.post("/api/v1/import/items", files={"file": ("items.csv", csv_bytes, "text/csv")},
                    data={"dry_run": "true"}).json()
    assert r["mapping"]["name"] == "Dish" and r["mapping"]["food_cost"] == "Cost"
    assert r["accepted"] == 1 and r["committed"] is False
    r = client.post("/api/v1/import/items", files={"file": ("items.csv", csv_bytes, "text/csv")},
                    data={"dry_run": "false"}).json()
    assert r["committed"] is True
    assert client.get("/api/v1/health").json()["items"] == 46
