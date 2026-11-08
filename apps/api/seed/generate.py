"""Generate the seeded restaurant: menu, modifiers, inventory and 90 days of orders.

Usage (from apps/api):
    python -m seed.generate --seed 42
    python -m seed.generate --seed 42 --days 90 --orders 12000 --end-date 2026-10-10 --out ../../data/seed

Output: `tadka.sqlite` plus `items.csv` and `orders.csv` (one row per order line, the same
shape the CSV importer accepts). The same seed and end date always give the same data.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import yaml

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import db
import settings
from seed.menu import CATEGORIES, DESCRIPTIONS, INGREDIENTS, MENU, RECIPES, MenuItem, modifier_groups_for, photo_urls

LOCAL_TZ = ZoneInfo(settings.RESTAURANT_TZ)

DAYPART_SHARE = {"lunch": 0.40, "snack": 0.12, "dinner": 0.48}
DOW_FACTOR = [0.85, 0.82, 0.88, 0.92, 1.05, 1.28, 1.25]  # Mon..Sun
FRIDAY_DINNER_SPIKE = 1.4
CHANNEL_SHARE = {"dine_in": 0.55, "takeaway": 0.28, "phone": 0.17}


# Which bread goes with which curry. Multiplies the bread's base weight.
BREAD_PREFERENCE: dict[str, dict[str, float]] = {
    "Dal Makhani": {"Butter Naan": 2.6, "Lachha Paratha": 1.8, "Tandoori Roti": 0.6},
    "Paneer Butter Masala": {"Butter Naan": 2.2, "Garlic Naan": 1.4, "Cheese Naan": 1.4, "Tandoori Roti": 0.6},
    "Kadai Paneer": {"Garlic Naan": 1.8, "Lachha Paratha": 1.5, "Tandoori Roti": 0.8},
    "Paneer Tikka Masala": {"Garlic Naan": 2.0, "Butter Naan": 1.3, "Tandoori Roti": 0.7},
    "Shahi Paneer": {"Butter Naan": 1.8, "Cheese Naan": 2.0, "Tandoori Roti": 0.6},
    "Malai Kofta": {"Butter Naan": 1.8, "Cheese Naan": 1.8, "Tandoori Roti": 0.6},
    "Butter Chicken": {"Garlic Naan": 2.6, "Butter Naan": 1.6, "Tandoori Roti": 0.5},
    "Chicken Curry": {"Lachha Paratha": 2.0, "Tandoori Roti": 1.2},
    "Dal Tadka": {"Tandoori Roti": 2.4, "Butter Naan": 0.6},
    "Chana Masala": {"Tandoori Roti": 2.0, "Lachha Paratha": 1.5},
    "Mix Veg": {"Tandoori Roti": 2.2},
}
# Chance of adding plain rice to a curry order.
PLAIN_RICE_CHANCE: dict[str, float] = {"Dal Tadka": 0.6, "Chana Masala": 0.55, "Dal Makhani": 0.4, "Chicken Curry": 0.45}


@dataclass
class Line:
    item: MenuItem
    qty: int
    mods: list[dict]


def load_aliases() -> dict[str, list[str]]:
    path = settings.LEXICON_DIR / "aliases.yaml"
    with path.open(encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


class Generator:
    def __init__(self, seed: int, days: int, target_orders: int, end_date: date):
        self.rng = np.random.default_rng(seed)
        self.days = days
        self.target_orders = target_orders
        self.end_date = end_date
        self.start_date = end_date - timedelta(days=days - 1)
        self.by_cat: dict[str, list[MenuItem]] = {}
        for item in MENU:
            self.by_cat.setdefault(item.category, []).append(item)
        self.mod_groups = {item.name: modifier_groups_for(item) for item in MENU}
        self.stockouts = self._pick_stockouts()

    # ----- calendar -------------------------------------------------------------

    def _pick_stockouts(self) -> set[tuple[str, int]]:
        """A few item-days where the kitchen ran out. Stars are protected by stock planning."""
        candidates = [i.name for i in MENU if i.category in ("main", "starter", "dessert", "rice")]
        out: set[tuple[str, int]] = set()
        for _ in range(7):
            name = candidates[int(self.rng.integers(len(candidates)))]
            out.add((name, int(self.rng.integers(self.days))))
        return out

    def _daily_counts(self) -> list[dict[str, int]]:
        raw = []
        for d in range(self.days):
            day = self.start_date + timedelta(days=d)
            dow = day.weekday()
            noise = float(self.rng.lognormal(0, 0.12))
            parts = {}
            for part, share in DAYPART_SHARE.items():
                f = DOW_FACTOR[dow] * share * noise
                if dow == 4 and part == "dinner":
                    f *= FRIDAY_DINNER_SPIKE
                parts[part] = f
            raw.append(parts)
        total = sum(sum(p.values()) for p in raw)
        scale = self.target_orders / total
        return [{k: int(self.rng.poisson(v * scale)) for k, v in p.items()} for p in raw]

    def _time_for(self, day: date, part: str) -> datetime:
        if part == "lunch":
            minutes = float(np.clip(self.rng.normal(13.5 * 60, 50), 12 * 60, 15.5 * 60))
        elif part == "snack":
            minutes = float(self.rng.uniform(16 * 60, 19 * 60 - 1))
        else:
            minutes = float(np.clip(self.rng.normal(20.75 * 60, 60), 19 * 60, 23.25 * 60))
        seconds = int(minutes * 60 + self.rng.integers(60))
        local = datetime.combine(day, time(0), LOCAL_TZ) + timedelta(seconds=seconds)
        return local.astimezone(timezone.utc).replace(tzinfo=None)

    # ----- choices --------------------------------------------------------------

    def _weights(self, items: list[MenuItem], day_idx: int) -> np.ndarray:
        progress = day_idx / max(self.days - 1, 1)
        w = np.array(
            [
                0.0 if (i.name, day_idx) in self.stockouts else i.weight * (1 + i.drift * progress)
                for i in items
            ]
        )
        return w / w.sum()

    def _pick(self, items: list[MenuItem], day_idx: int, veg_only: bool) -> MenuItem:
        pool = [i for i in items if i.veg or not veg_only]
        if all((i.name, day_idx) in self.stockouts for i in pool):
            # Everything the guest wanted is out today; they pick from the whole category.
            pool = [i for i in self.by_cat[items[0].category] if (i.name, day_idx) not in self.stockouts]
        return pool[int(self.rng.choice(len(pool), p=self._weights(pool, day_idx)))]

    def _pick_from(self, cat: str, day_idx: int, veg_only: bool, tag: str | None = None) -> MenuItem:
        items = self.by_cat[cat]
        if tag:
            items = [i for i in items if tag in i.tags]
        return self._pick(items, day_idx, veg_only)

    def _pick_pref(self, cat: str, day_idx: int, pref: dict[str, float]) -> MenuItem:
        items = [i for i in self.by_cat[cat] if (i.name, day_idx) not in self.stockouts]
        w = self._weights(items, day_idx) * np.array([pref.get(i.name, 1.0) for i in items])
        return items[int(self.rng.choice(len(items), p=w / w.sum()))]

    def _mods(self, item: MenuItem) -> list[dict]:
        chosen = []
        for name, required, _mn, _mx, options in self.mod_groups[item.name]:
            if name == "Size":
                opt = options[1] if self.rng.random() < 0.35 else options[0]
                chosen.append({"group": name, "name": opt[0], "price_delta": opt[1], "cost_delta": opt[2]})
            elif name == "Spice" and self.rng.random() < 0.4:
                opt = options[int(self.rng.choice(3, p=[0.3, 0.45, 0.25]))]
                chosen.append({"group": name, "name": opt[0], "price_delta": 0, "cost_delta": 0})
            elif name == "Add-ons" and self.rng.random() < 0.12:
                opt = options[int(self.rng.integers(len(options)))]
                chosen.append({"group": name, "name": opt[0], "price_delta": opt[1], "cost_delta": opt[2]})
        return chosen

    def _basket(self, day_idx: int, part: str, channel: str, covers: int) -> list[Line]:
        rng = self.rng
        veg_only = rng.random() < 0.45
        lines: list[Line] = []

        def add(item: MenuItem, qty: int = 1) -> None:
            for line in lines:
                if line.item is item and not line.mods:
                    line.qty += qty
                    return
            lines.append(Line(item, qty, self._mods(item)))

        if part == "snack":
            for _ in range(1 + int(rng.random() < 0.35)):
                add(self._pick_from("starter", day_idx, veg_only, "snack"))
            if rng.random() < 0.7:
                add(self._pick_from("beverage", day_idx, veg_only), max(1, covers - int(rng.integers(2))))
            if rng.random() < 0.15:
                add(self._pick_from("dessert", day_idx, veg_only))
            return lines

        # Starters, more likely at dinner and for dine-in groups.
        p_starter = (0.5 if part == "dinner" else 0.25) + (0.1 if channel == "dine_in" else 0)
        if rng.random() < p_starter:
            for _ in range(1 + int(covers >= 4 and rng.random() < 0.5)):
                add(self._pick_from("starter", day_idx, veg_only))

        n_slots = max(1, round(covers * 0.7 + rng.normal(0, 0.4)))
        curry_count = 0
        had_chinese = had_biryani = had_thali = False
        for _ in range(n_slots):
            r = rng.random()
            if r < 0.68:
                item = self._pick_from("main", day_idx, veg_only)
                add(item)
                if "thali" in item.tags:
                    had_thali = True
                else:
                    curry_count += 1
            elif r < 0.86:
                add(self._pick_from("rice", day_idx, veg_only, "biryani"))
                had_biryani = True
            else:
                add(self._pick_from("rice", day_idx, veg_only, "chinese"))
                had_chinese = True

        if curry_count:
            first_curry = next(l.item.name for l in lines if "curry" in l.item.tags)
            # Main dish plus bread: about two breads per person, leaning to the curry's usual bread.
            if rng.random() < 0.88:
                n_bread = max(1, int(round(covers * 1.6 + rng.normal(0, 0.8))))
                for _ in range(max(1, min(3, n_bread // 2))):
                    add(self._pick_pref("bread", day_idx, BREAD_PREFERENCE.get(first_curry, {})),
                        max(1, n_bread // 2))
            if rng.random() < PLAIN_RICE_CHANCE.get(first_curry, 0.32):
                add(self._pick_from("rice", day_idx, veg_only, "plain_rice"))
        if had_biryani and rng.random() < 0.62:
            add(next(i for i in MENU if i.name == "Boondi Raita"), max(1, covers // 2))
        if had_chinese:
            if rng.random() < 0.42:
                add(next(i for i in MENU if i.name == "Veg Manchurian"))
            if rng.random() < 0.5:
                add(next(i for i in MENU if i.name == "Cold Drink"))

        # Sides beyond the raita affinity.
        if rng.random() < 0.3:
            add(self._pick_from("side", day_idx, veg_only))

        # Dessert after a thali, otherwise occasionally after dinner.
        if had_thali and rng.random() < 0.5:
            add(next(i for i in MENU if i.name == "Gulab Jamun"))
        elif rng.random() < (0.2 if part == "dinner" else 0.1):
            add(self._pick_from("dessert", day_idx, veg_only))

        p_bev = 0.32 if part == "lunch" else 0.26
        if rng.random() < p_bev:
            add(self._pick_from("beverage", day_idx, veg_only), max(1, covers - int(rng.integers(2))))
        return lines

    # ----- main loop ------------------------------------------------------------

    def orders(self):
        channels = list(CHANNEL_SHARE)
        channel_p = list(CHANNEL_SHARE.values())
        for d, parts in enumerate(self._daily_counts()):
            day = self.start_date + timedelta(days=d)
            for part, n in parts.items():
                for _ in range(n):
                    channel = channels[int(self.rng.choice(3, p=channel_p))]
                    if channel == "dine_in":
                        covers = int(np.clip(self.rng.poisson(2.6), 1, 8))
                    else:
                        covers = int(np.clip(self.rng.poisson(1.9), 1, 6))
                    if part == "snack":
                        covers = min(covers, 3)
                    lines = self._basket(d, part, channel, covers)
                    yield self._time_for(day, part), part, channel, covers, lines


def build(out_dir: Path, seed: int = 42, days: int = 90, target_orders: int = 12000,
          end_date: date | None = None, db_name: str = "tadka.sqlite") -> Path:
    end_date = end_date or datetime.now(LOCAL_TZ).date() - timedelta(days=1)
    out_dir.mkdir(parents=True, exist_ok=True)
    db_path = out_dir / db_name
    db.dispose(db_path)
    for suffix in ("", "-wal", "-shm"):
        p = Path(str(db_path) + suffix)
        if p.exists():
            p.unlink()
    db.init_db(db_path)
    db.dispose(db_path)

    gen = Generator(seed, days, target_orders, end_date)
    aliases = load_aliases()
    missing = [i.name for i in MENU if i.name not in aliases]
    if missing:
        raise SystemExit(f"aliases.yaml has no entry for: {', '.join(missing)}")

    con = sqlite3.connect(db_path)
    cur = con.cursor()
    item_ids = insert_menu(cur, aliases)

    order_rows = []
    line_rows = []
    order_id = 0
    for ts, part, channel, covers, lines in gen.orders():
        order_id += 1
        subtotal = 0
        for line in lines:
            unit_price = (line.item.price + sum(m["price_delta"] for m in line.mods)) * 100
            unit_cost = (line.item.food_cost + sum(m["cost_delta"] for m in line.mods)) * 100
            subtotal += unit_price * line.qty
            mods = [{"group": m["group"], "name": m["name"], "price_delta": m["price_delta"]} for m in line.mods]
            line_rows.append((order_id, item_ids[line.item.name], line.qty, unit_price, unit_cost,
                              json.dumps(mods)))
        discount = 0
        if gen.rng.random() < 0.04:
            discount = int(round(subtotal * 0.10 / 100)) * 100  # 10 percent, whole rupees
        order_rows.append((order_id, ts.isoformat(sep=" "), channel, subtotal, discount,
                           subtotal - discount, covers, part))

    cur.executemany(
        "INSERT INTO orders(id, ts, channel, subtotal_paise, discount_paise, total_paise, covers, daypart) "
        "VALUES (?,?,?,?,?,?,?,?)", order_rows)
    cur.executemany(
        "INSERT INTO order_items(order_id, item_id, qty, unit_price_paise, unit_cost_paise, modifiers_json) "
        "VALUES (?,?,?,?,?,?)", line_rows)
    con.commit()
    con.close()

    export_csv(db_path, out_dir)
    return db_path


def insert_menu(cur: sqlite3.Cursor, aliases: dict[str, list[str]] | None = None) -> dict[str, int]:
    """Insert the restaurant menu (categories, items, modifiers, ingredients, recipes). Returns item ids."""
    aliases = aliases if aliases is not None else load_aliases()
    photos = photo_urls()
    cat_ids: dict[str, int] = {}
    for name, kind in CATEGORIES:
        cur.execute("INSERT INTO categories(name, kind) VALUES (?, ?)", (name, kind))
        cat_ids[kind] = cur.lastrowid

    item_ids: dict[str, int] = {}
    for i in MENU:
        cur.execute(
            "INSERT INTO items(category_id, name, price_paise, food_cost_paise, veg, spice_level, "
            "prep_minutes, available, station, aliases_json, description, image_url) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (cat_ids[i.category], i.name, i.price * 100, i.food_cost * 100, i.veg, i.spice, i.prep,
             True, i.station, json.dumps(aliases.get(i.name, []), ensure_ascii=False), DESCRIPTIONS.get(i.name),
             photos.get(i.name)),
        )
        item_ids[i.name] = cur.lastrowid
        for gname, required, mn, mx, options in modifier_groups_for(i):
            cur.execute(
                "INSERT INTO modifier_groups(item_id, name, required, min_select, max_select) VALUES (?,?,?,?,?)",
                (item_ids[i.name], gname, required, mn, mx),
            )
            gid = cur.lastrowid
            cur.executemany(
                "INSERT INTO modifiers(group_id, name, price_delta_paise, cost_delta_paise) VALUES (?,?,?,?)",
                [(gid, o[0], o[1] * 100, o[2] * 100) for o in options],
            )

    ing_ids: dict[str, int] = {}
    for name, (unit, stock, reorder) in INGREDIENTS.items():
        cur.execute("INSERT INTO ingredients(name, unit, stock, reorder_level) VALUES (?,?,?,?)",
                    (name, unit, stock, reorder))
        ing_ids[name] = cur.lastrowid
    for item_name, lines in RECIPES.items():
        cur.executemany("INSERT INTO recipe_lines(item_id, ingredient_id, qty) VALUES (?,?,?)",
                        [(item_ids[item_name], ing_ids[ing], qty) for ing, qty in lines])
    return item_ids


def install_menu(db_path: Path) -> bool:
    """Load the restaurant menu into an existing database that has no items yet. Returns True if loaded.
    A database that already has the built-in dishes gets their descriptions and photos where none are set."""
    con = sqlite3.connect(db_path)
    try:
        n, = con.execute("SELECT COUNT(*) FROM items").fetchone()
        if n:
            con.executemany("UPDATE items SET description = ? WHERE name = ? AND description IS NULL",
                            [(d, name) for name, d in DESCRIPTIONS.items()])
            con.executemany("UPDATE items SET image_url = ? WHERE name = ? AND image_url IS NULL",
                            [(url, name) for name, url in photo_urls().items()])
            con.commit()
            return False
        insert_menu(con.cursor())
        con.commit()
        return True
    finally:
        con.close()


def write_sample_sales(path: Path, seed: int = 7, days: int = 60, target_orders: int = 3000,
                       end_date: date = date(2026, 9, 30)) -> int:
    """Write a sales CSV for the built-in menu (one row per order line). Returns the number of orders."""
    gen = Generator(seed, days, target_orders, end_date)
    kind_name = {kind: name for name, kind in CATEGORIES}
    customers = ["Aarav", "Diya", "Kabir", "Meera", "Rohan", "Isha", "Vikram", "Ananya", "Arjun", "Sara",
                 "Nikhil", "Pooja", "Farhan", "Neha", "Siddharth", "Priya"]
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["order_id", "order_time", "item_name", "quantity", "price", "category", "veg", "food_cost",
                    "channel", "customer"])
        for ts, _part, channel, _covers, lines in gen.orders():
            n += 1
            customer = "" if channel == "dine_in" else customers[int(gen.rng.integers(len(customers)))]
            merged: dict[tuple[str, int, int], list] = {}
            for line in lines:
                price = line.item.price + sum(m["price_delta"] for m in line.mods)
                cost = line.item.food_cost + sum(m["cost_delta"] for m in line.mods)
                key = (line.item.name, price, cost)
                if key in merged:
                    merged[key][0] += line.qty
                else:
                    merged[key] = [line.qty, line.item]
            for (name, price, cost), (qty, item) in merged.items():
                local = ts.replace(tzinfo=timezone.utc).astimezone(LOCAL_TZ)
                w.writerow([f"S-{n:05d}", local.strftime("%Y-%m-%d %H:%M"), name, qty, price,
                            kind_name.get(item.category, item.category), "veg" if item.veg else "non-veg",
                            cost, channel, customer])
    return n


def export_csv(db_path: Path, out_dir: Path) -> None:
    """Write items.csv and orders.csv in the format the importer accepts."""
    con = sqlite3.connect(db_path)
    cur = con.cursor()
    with (out_dir / "items.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["item_name", "category", "price", "food_cost", "veg", "station", "prep_minutes"])
        for row in cur.execute(
            "SELECT i.name, c.kind, i.price_paise, i.food_cost_paise, i.veg, i.station, i.prep_minutes "
            "FROM items i JOIN categories c ON c.id = i.category_id ORDER BY i.id"
        ):
            w.writerow([row[0], row[1], _rupees(row[2]), _rupees(row[3]), "yes" if row[4] else "no",
                        row[5], row[6]])
    with (out_dir / "orders.csv").open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["order_id", "order_time_utc", "channel", "covers", "item_name", "qty", "unit_price",
                    "discount"])
        for row in cur.execute(
            "SELECT o.id, o.ts, o.channel, o.covers, i.name, oi.qty, oi.unit_price_paise, o.discount_paise, "
            "oi.id = (SELECT MIN(id) FROM order_items WHERE order_id = o.id) "
            "FROM order_items oi JOIN orders o ON o.id = oi.order_id JOIN items i ON i.id = oi.item_id "
            "ORDER BY o.id, oi.id"
        ):
            # The order discount is written once, on the first line of the order.
            discount = _rupees(row[7]) if row[8] else "0"
            w.writerow([f"ORD-{row[0]:05d}", row[1].replace(" ", "T") + "Z", row[2], row[3], row[4],
                        row[5], _rupees(row[6]), discount])
    con.close()


def _rupees(paise: int) -> str:
    return f"{paise // 100}" if paise % 100 == 0 else f"{paise / 100:.2f}"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Generate the seeded Tadka restaurant database.")
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--orders", type=int, default=12000, help="approximate number of orders")
    ap.add_argument("--end-date", type=date.fromisoformat, default=None,
                    help="last day of data (YYYY-MM-DD, restaurant local date); default yesterday")
    ap.add_argument("--out", type=Path, default=settings.SEED_DIR)
    args = ap.parse_args(argv)
    path = build(args.out, args.seed, args.days, args.orders, args.end_date)
    con = sqlite3.connect(path)
    n_orders, = con.execute("SELECT COUNT(*) FROM orders").fetchone()
    n_lines, = con.execute("SELECT COUNT(*) FROM order_items").fetchone()
    n_items, = con.execute("SELECT COUNT(*) FROM items").fetchone()
    con.close()
    print(f"Wrote {path} with {n_items} items, {n_orders} orders and {n_lines} order lines.")


if __name__ == "__main__":
    main()
