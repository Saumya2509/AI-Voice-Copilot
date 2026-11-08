"""CSV import: column guesses, validation reasons, food cost handling and commit."""
from __future__ import annotations

import sqlite3

from sqlmodel import Session, func, select

import db
import importer
from importer import FOOD_COST_MESSAGE, guess_mapping, parse_money, parse_ts
from models import Item, Order


def test_guess_mapping_on_typical_export_headers():
    cols = ["Bill No", "Bill Date", "Item Description", "Quantity", "Rate", "Order Type", "Pax"]
    m = guess_mapping(cols, importer.ORDER_FIELDS)
    assert m["order_ref"] == "Bill No"
    assert m["ts"] == "Bill Date"
    assert m["item_name"] == "Item Description"
    assert m["qty"] == "Quantity"
    assert m["unit_price"] == "Rate"
    assert m["channel"] == "Order Type"
    assert m["covers"] == "Pax"


def test_parsers():
    assert parse_money("₹1,250.50") == 125050
    assert parse_money("Rs. 60") == 6000
    assert parse_money("") is None
    # Local time without a zone is restaurant time (IST, UTC+5:30).
    assert parse_ts("11/10/2026 13:30").isoformat() == "2026-10-11T08:00:00"
    assert parse_ts("2026-10-11T08:00:00Z").isoformat() == "2026-10-11T08:00:00"


ITEMS_NO_COST = b"""Item,Category,Price,Veg
Paneer Butter Masala,Main Course,300,Veg
Kadhai Chicken,Main Course,380,Non-Veg
Masala Chai,Hot Drinks,40,veg
Mystery Box,Combos,199,veg
Free Water,Beverages,0,veg
"""


def test_items_without_food_cost_ask_for_default(work_db):
    with Session(db.get_engine(work_db)) as s:
        report = importer.import_items(s, ITEMS_NO_COST, dry_run=False).to_dict()
        assert report["committed"] is False
        assert report["food_cost_message"] == FOOD_COST_MESSAGE
        assert report["needs_food_cost"] == ["beverage", "main"]
        assert report["accepted"] == 3 and report["rejected"] == 2
        reasons = {r["reason"] for r in report["rejected_rows"]}
        assert any("Combos" in r for r in reasons) and "price is blank or zero" in reasons

        report = importer.import_items(s, ITEMS_NO_COST, default_cost_pct={"main": 35, "beverage": 25},
                                       dry_run=False).to_dict()
        assert report["committed"] is True
        pbm = s.exec(select(Item).where(Item.name == "Paneer Butter Masala")).one()
        assert pbm.price_paise == 30000 and pbm.food_cost_paise == 10500
        chicken = s.exec(select(Item).where(Item.name == "Kadhai Chicken")).one()
        assert chicken.veg is False and chicken.food_cost_paise == 13300


def test_orders_import_reports_reasons_and_replaces_history(work_db):
    csv_bytes = b"""Bill No,Bill Date,Item,Qty,Rate,Order Type
B1,10/10/2026 13:05,Paneer Butter Masala,1,280,Dine In
B1,10/10/2026 13:05,butter naan,3,60,Dine In
B2,10/10/2026 20:15,Dal Makhani,2,,Phone
B3,10/10/2026 21:00,Unknown Dish,1,100,Takeaway
B4,not a date,Dal Tadka,1,190,Takeaway
B5,10/10/2026 21:30,Dal Tadka,0,190,Takeaway
"""
    with Session(db.get_engine(work_db)) as s:
        dry = importer.import_orders(s, csv_bytes, dry_run=True).to_dict()
        assert dry["accepted"] == 3 and dry["rejected"] == 3 and dry["committed"] is False
        reasons = [r["reason"] for r in dry["rejected_rows"]]
        assert "item not on menu: Unknown Dish" in reasons
        assert any("not a date" in r for r in reasons)
        assert "quantity must be a whole number above zero" in reasons
        assert s.exec(select(func.count()).select_from(Order)).one() > 10_000  # dry run changed nothing

        done = importer.import_orders(s, csv_bytes, mode="replace", dry_run=False).to_dict()
        assert done["committed"] is True
        orders = s.exec(select(Order).order_by(Order.id)).all()
        assert [o.external_ref for o in orders] == ["B1", "B2"]
        assert orders[0].total_paise == 280_00 + 3 * 60_00 and orders[0].channel == "dine_in"
        assert orders[1].total_paise == 2 * 240_00 and orders[1].channel == "phone"  # menu price used
        assert orders[0].daypart == "lunch" and orders[1].daypart == "dinner"


def test_seed_export_round_trips_through_importer(work_db, seeded_db):
    content = (seeded_db.parent / "orders.csv").read_bytes()
    with Session(db.get_engine(work_db)) as s:
        report = importer.import_orders(s, content, dry_run=True).to_dict()
    con = sqlite3.connect(seeded_db)
    n_lines, = con.execute("SELECT COUNT(*) FROM order_items").fetchone()
    con.close()
    assert report["rejected"] == 0 and report["accepted"] == n_lines
