"""The seeded restaurant must contain patterns the revenue engine can discover."""
from __future__ import annotations

import hashlib
import sqlite3
from collections import Counter
from datetime import date

import pandas as pd
import pytest
import yaml

import settings
from revenue.classify import classify_db
from seed.generate import build
from seed.menu import EXPECTED_CLASS, MENU


def _dump_hash(path) -> str:
    con = sqlite3.connect(path)
    h = hashlib.sha256()
    for table in ("categories", "items", "modifier_groups", "modifiers", "orders", "order_items",
                  "ingredients", "recipe_lines"):
        for row in con.execute(f"SELECT * FROM {table} ORDER BY 1, 2"):
            h.update(repr(row).encode())
    con.close()
    return h.hexdigest()


def test_generator_is_deterministic(tmp_path):
    a = build(tmp_path / "a", seed=7, days=10, target_orders=900, end_date=date(2026, 10, 10))
    b = build(tmp_path / "b", seed=7, days=10, target_orders=900, end_date=date(2026, 10, 10))
    c = build(tmp_path / "c", seed=8, days=10, target_orders=900, end_date=date(2026, 10, 10))
    assert _dump_hash(a) == _dump_hash(b)
    assert _dump_hash(a) != _dump_hash(c)
    assert (tmp_path / "a" / "orders.csv").read_bytes() == (tmp_path / "b" / "orders.csv").read_bytes()


def test_menu_shape(seeded_db):
    con = sqlite3.connect(seeded_db)
    n_items, = con.execute("SELECT COUNT(*) FROM items").fetchone()
    kinds = {k for (k,) in con.execute("SELECT kind FROM categories")}
    pcts = [cost / price for price, cost in con.execute("SELECT price_paise, food_cost_paise FROM items")]
    con.close()
    assert 42 <= n_items <= 48
    assert kinds == {"starter", "main", "bread", "rice", "dessert", "beverage", "side"}
    assert all(0.22 <= p <= 0.48 for p in pcts), "food cost must be 22 to 48 percent of price"


@pytest.mark.parametrize("window", [30, 60, 90])
def test_class_counts(seeded_db, window):
    result = classify_db(seeded_db, window)
    counts = Counter(r.cls for r in result)
    assert counts["star"] >= 8
    assert 5 <= counts["puzzle"] <= 6
    assert 5 <= counts["plowhorse"] <= 6
    assert 4 <= counts["dog"] <= 5
    wrong = {r.name: r.cls for r in result if EXPECTED_CLASS.get(r.name, "star") != r.cls}
    assert not wrong, f"items landed in an unexpected class: {wrong}"


@pytest.fixture(scope="module")
def frames(seeded_db):
    con = sqlite3.connect(seeded_db)
    orders = pd.read_sql_query("SELECT * FROM orders", con, parse_dates=["ts"])
    lines = pd.read_sql_query(
        "SELECT oi.*, i.name FROM order_items oi JOIN items i ON i.id = oi.item_id", con)
    con.close()
    return orders, lines


def test_volume_and_channels(frames):
    orders, _ = frames
    assert 11_400 <= len(orders) <= 12_600
    phone = (orders["channel"] == "phone").mean()
    assert 0.15 <= phone <= 0.20
    assert orders["ts"].dt.date.nunique() == 90


def test_money_is_consistent(frames):
    orders, lines = frames
    for col in ("subtotal_paise", "discount_paise", "total_paise"):
        assert pd.api.types.is_integer_dtype(orders[col])
    line_sum = (lines["qty"] * lines["unit_price_paise"]).groupby(lines["order_id"]).sum()
    merged = orders.set_index("id").join(line_sum.rename("line_sum"))
    assert (merged["subtotal_paise"] == merged["line_sum"]).all()
    assert (merged["total_paise"] == merged["subtotal_paise"] - merged["discount_paise"]).all()


def test_time_patterns(frames):
    orders, _ = frames
    local = orders["ts"].dt.tz_localize("UTC").dt.tz_convert(settings.RESTAURANT_TZ)
    hours = local.dt.hour
    assert hours.between(12, 15).mean() > 0.3 and hours.between(19, 23).mean() > 0.4
    per_day = local.dt.date.value_counts()
    dow = pd.Series({d: pd.Timestamp(d).dayofweek for d in per_day.index})
    weekend = per_day[dow[dow >= 5].index].mean()
    weekday = per_day[dow[dow < 4].index].mean()
    assert weekend > weekday * 1.2
    dinner = orders[orders["daypart"] == "dinner"]
    dinner_dow = dinner["ts"].dt.tz_localize("UTC").dt.tz_convert(settings.RESTAURANT_TZ).dt.dayofweek
    per_dow = dinner_dow.value_counts() / (90 / 7)
    assert per_dow[4] > per_dow[3] * 1.3, "Friday evening spike"


def _lift(lines, a: set[str], b: set[str]) -> float:
    baskets = lines.groupby("order_id")["name"].apply(set)
    has_a = baskets.apply(lambda s: bool(s & a))
    has_b = baskets.apply(lambda s: bool(s & b))
    return (has_a & has_b).mean() / (has_a.mean() * has_b.mean())


def test_seeded_affinities(frames):
    _, lines = frames
    curries = {i.name for i in MENU if "curry" in i.tags}
    breads = {i.name for i in MENU if i.category == "bread"}
    chinese = {i.name for i in MENU if "chinese" in i.tags}
    assert _lift(lines, {"Veg Biryani", "Chicken Biryani"}, {"Boondi Raita"}) > 2.0
    assert _lift(lines, curries, breads) > 1.4
    assert _lift(lines, chinese, {"Cold Drink"}) > 1.8
    assert _lift(lines, chinese, {"Veg Manchurian"}) > 1.8
    assert _lift(lines, {"Veg Thali"}, {"Gulab Jamun"}) > 2.5


def test_lexicon_covers_menu():
    aliases = yaml.safe_load((settings.LEXICON_DIR / "aliases.yaml").read_text(encoding="utf-8"))
    assert set(aliases) == {i.name for i in MENU}
    assert all(len(v) >= 3 for v in aliases.values())
    for name in ("numbers", "modifiers", "fillers"):
        assert yaml.safe_load((settings.LEXICON_DIR / f"{name}.yaml").read_text(encoding="utf-8"))
    for pack in ("mr", "gu"):
        data = yaml.safe_load((settings.LEXICON_DIR / "packs" / f"{pack}.yaml").read_text(encoding="utf-8"))
        assert {"language", "aliases", "numbers", "modifiers", "fillers"} <= set(data)
        assert set(data["aliases"]) <= {i.name for i in MENU}


def test_csv_exports(seeded_db):
    out = seeded_db.parent
    items = pd.read_csv(out / "items.csv")
    orders = pd.read_csv(out / "orders.csv")
    assert len(items) == len(MENU)
    con = sqlite3.connect(seeded_db)
    n_lines, = con.execute("SELECT COUNT(*) FROM order_items").fetchone()
    con.close()
    assert len(orders) == n_lines
    assert orders["order_time_utc"].str.endswith("Z").all()
