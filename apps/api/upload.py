"""CSV upload for the Analytics flow (improve.md, section 2).

The restaurant menu is built in, so a sales CSV (one row per order line) only brings in sales history:
each row's item is matched to the menu by name or alias, and rows naming a dish that is not on the menu
are rejected. Commit replaces the orders and keeps the menu (calls are kept, with their order link
cleared), then re-runs analytics. If there is no menu at all, items are derived from the CSV instead.
A menu CSV only updates items.
"""
from __future__ import annotations

import csv
import io
import json
import re
import shutil
import sqlite3
import tempfile
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import insert, text
from sqlmodel import Session

import events_bus
import importer
import settings
import settings_store
from models import Category, Item, Order, OrderItem
from pos.service import daypart_for
from revenue import cache

SALES_FIELDS: dict[str, tuple[bool, list[str]]] = {
    "order_ref": (True, ["order_id", "order_no", "bill_no", "invoice_no", "bill_number", "order_number", "ticket"]),
    "ts": (True, ["order_time", "order_time_utc", "timestamp", "date_time", "datetime", "created_at", "bill_date",
                  "date", "time"]),
    "item_name": (True, ["item_name", "item", "dish", "product", "menu_item", "name", "item_description"]),
    "quantity": (True, ["quantity", "qty", "units", "count"]),
    "price": (True, ["price", "unit_price", "rate", "item_price", "selling_price", "mrp"]),
    "category": (False, ["category", "category_name", "group", "menu_group", "section"]),
    "veg": (False, ["veg", "is_veg", "vegetarian", "veg_nonveg", "food_type", "diet", "type", "veg_type"]),
    "food_cost": (False, ["food_cost", "unit_cost", "cost", "cost_price", "cogs", "plate_cost"]),
    "channel": (False, ["channel", "order_type", "source", "service_type", "mode"]),
    "image_url": (False, ["image_url", "image", "photo", "picture", "img"]),
    "customer": (False, ["customer", "customer_name", "guest", "guest_name"]),
}
MENU_FIELDS: dict[str, tuple[bool, list[str]]] = {
    "item_name": (True, ["item_name", "item", "dish", "product", "menu_item", "name"]),
    "price": (True, ["price", "selling_price", "rate", "mrp", "unit_price"]),
    "category": (False, ["category", "category_name", "group", "menu_group", "section", "type"]),
    "veg": (False, ["veg", "is_veg", "vegetarian", "veg_nonveg", "food_type", "diet"]),
    "food_cost": (False, ["food_cost", "cost", "cost_price", "unit_cost", "cogs", "plate_cost"]),
    "description": (False, ["description", "desc", "details", "about"]),
    "spice_level": (False, ["spice_level", "spice", "heat"]),
    "image_url": (False, ["image_url", "image", "photo", "picture", "img"]),
}
TEMPLATES = {
    "sales": ["order_id", "order_time", "item_name", "quantity", "price", "category", "veg", "food_cost",
              "channel", "customer", "image_url"],
    "menu": ["item_name", "category", "price", "food_cost", "veg", "description", "spice_level", "image_url"],
}
NON_VEG_WORDS = ("chicken", "mutton", "lamb", "fish", "prawn", "egg", "keema", "murgh", "gosht", "seekh", "crab",
                 "pork", "beef")
DEFAULT_STATION = importer.DEFAULT_STATION


def template_csv(kind: str) -> str:
    buf = io.StringIO()
    csv.writer(buf).writerow(TEMPLATES[kind])
    return buf.getvalue()


def _kind_for(category: str) -> str:
    known = importer.parse_category(category)
    if known:
        return known
    slug = re.sub(r"[^a-z0-9]+", "_", category.strip().lower()).strip("_")
    return slug or "main"


def _guess_veg(name: str) -> bool:
    low = f" {name.lower()} "
    return not any(w in low for w in NON_VEG_WORDS)


@dataclass
class Parsed:
    columns: list[str]
    mapping: dict[str, str | None]
    missing_required: list[str]
    rows: int = 0
    accepted: int = 0
    duplicates: int = 0
    rejected: list[dict] = field(default_factory=list)  # {row, reason, values}
    items: dict[str, dict] = field(default_factory=dict)  # lower name -> item info
    orders: dict[str, dict] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    needs_food_cost: list[str] = field(default_factory=list)
    uses_menu: bool = False

    def report(self, kind: str) -> dict:
        reasons = Counter(r["reason"] for r in self.rejected)
        ts = [o["ts"] for o in self.orders.values()]
        return {
            "kind": kind, "columns": self.columns, "mapping": self.mapping, "missing_required": self.missing_required,
            "rows": self.rows, "accepted": self.accepted, "rejected": len(self.rejected),
            "duplicates": self.duplicates,
            "rejected_reasons": [{"reason": k, "count": v} for k, v in reasons.most_common()],
            "rejected_rows": self.rejected[:5000],
            "items_found": len(self.items), "orders_found": len(self.orders),
            "date_from": _local_date(min(ts)) if ts else None, "date_to": _local_date(max(ts)) if ts else None,
            "needs_food_cost": self.needs_food_cost,
            "food_cost_message": ("Food cost is missing for some items. Set a default cost percentage by category; "
                                  "margin charts will say Estimated until real costs are added.")
            if self.needs_food_cost else None,
            "warnings": self.warnings,
            "uses_menu": self.uses_menu,
        }


def _local_date(ts: datetime) -> str:
    return ts.replace(tzinfo=ZoneInfo("UTC")).astimezone(ZoneInfo(settings.RESTAURANT_TZ)).date().isoformat()


def _money(value: str, what: str) -> int:
    paise = importer.parse_money(value)
    if paise is None or paise <= 0:
        raise ValueError(f"missing {what}")
    return paise


def _norm(name: str) -> str:
    return re.sub(r"\s+", " ", name.strip().lower())


def menu_lookup(session: Session) -> dict[str, tuple[int, str]] | None:
    """Item name and aliases (normalised) -> (item id, menu name). None when there is no menu."""
    rows = session.exec(text("SELECT id, name, aliases_json FROM items")).all()
    if not rows:
        return None
    out: dict[str, tuple[int, str]] = {}
    for item_id, name, aliases in rows:
        for a in json.loads(aliases or "[]"):
            if isinstance(a, str) and a.strip():
                out.setdefault(_norm(a), (item_id, name))
    for item_id, name, _a in rows:  # exact names win over aliases
        out[_norm(name)] = (item_id, name)
    return out


def parse_sales(content: bytes, mapping: dict | None,
                menu: dict[str, tuple[int, str]] | None = None) -> Parsed:
    """Validate a sales CSV. With a menu, rows are matched to it; without one, items come from the file."""
    columns, rows = importer.read_csv(content)
    m, missing = importer._resolve_mapping(columns, SALES_FIELDS, mapping)
    out = Parsed(columns, m, missing, rows=len(rows), uses_menu=menu is not None)
    if missing:
        return out
    seen: set[tuple] = set()
    cost_seen: dict[str, list[int]] = defaultdict(list)
    prices: dict[str, Counter] = defaultdict(Counter)
    veg_votes: dict[str, Counter] = defaultdict(Counter)
    for idx, raw in enumerate(rows, start=2):  # row 1 is the header
        get = lambda f: (raw.get(m[f]) or "").strip() if m.get(f) else ""
        try:
            name = get("item_name")
            if not name:
                raise ValueError("missing item name")
            match = menu.get(_norm(name)) if menu is not None else None
            if menu is not None and match is None:
                raise ValueError("item not on the menu")
            price = _money(get("price"), "price")
            q_raw = get("quantity") or "1"
            try:
                qd = Decimal(q_raw)
            except InvalidOperation:
                raise ValueError("quantity is not a number")
            if qd <= 0 or qd != qd.to_integral_value():
                raise ValueError("quantity is not a whole number above zero")
            ref = get("order_ref")
            if not ref:
                raise ValueError("missing order id")
            try:
                ts = importer.parse_ts(get("ts"))
            except ValueError:
                raise ValueError("bad date")
            channel = importer.parse_channel(get("channel")) if m.get("channel") else "dine_in"
            veg = importer.parse_bool_veg(get("veg")) if m.get("veg") and get("veg") else None
            cost = importer.parse_money(get("food_cost")) if m.get("food_cost") and get("food_cost") else None
        except ValueError as exc:
            out.rejected.append({"row": idx, "reason": str(exc), "values": raw})
            continue
        key = tuple(sorted((k, (v or "").strip()) for k, v in raw.items() if k))  # the whole row repeats
        if key in seen:
            out.duplicates += 1
            continue
        seen.add(key)
        if match is not None:
            low = str(match[0])
            out.items.setdefault(low, {"name": match[1], "item_id": match[0]})
            order = out.orders.setdefault(ref, {"ts": ts, "channel": channel, "lines": [],
                                                "customer": get("customer") or None})
            order["ts"] = min(order["ts"], ts)
            order["lines"].append((low, int(qd), price, cost))
            out.accepted += 1
            continue
        low = name.lower()
        info = out.items.setdefault(low, {"name": name, "category": get("category") or "Menu",
                                          "image_url": get("image_url") or None})
        if get("category"):
            info["category"] = get("category")
        if get("image_url"):
            info["image_url"] = get("image_url")
        prices[low][price] += int(qd)
        if veg is not None:
            veg_votes[low][veg] += 1
        if cost is not None:
            cost_seen[low].append(cost)
        order = out.orders.setdefault(ref, {"ts": ts, "channel": channel, "lines": [],
                                            "customer": get("customer") or None})
        order["ts"] = min(order["ts"], ts)
        order["lines"].append((low, int(qd), price, cost))
        out.accepted += 1

    if not m.get("channel"):
        out.warnings.append("The file has no channel column, so every order is counted as dine-in.")
    if menu is not None:
        return out
    no_cost_cats = set()
    for low, info in out.items.items():
        info["price"] = prices[low].most_common(1)[0][0]
        info["veg"] = veg_votes[low].most_common(1)[0][0] if veg_votes[low] else _guess_veg(info["name"])
        info["veg_guessed"] = not veg_votes[low]
        costs = cost_seen.get(low)
        info["food_cost"] = round(sum(costs) / len(costs)) if costs else None
        info["kind"] = _kind_for(info["category"])
        if info["food_cost"] is None:
            no_cost_cats.add(info["category"])
    out.needs_food_cost = sorted(no_cost_cats)
    if any(i["veg_guessed"] for i in out.items.values()):
        out.warnings.append("Veg and non-veg marks were guessed from item names where the file has no veg column.")
    if not m.get("category"):
        out.warnings.append("The file has no category column, so every item is in one category, Menu.")
    return out


def commit_sales(session: Session, content: bytes, mapping: dict | None,
                 default_cost_pct: dict[str, float] | None) -> dict:
    menu = menu_lookup(session)
    parsed = parse_sales(content, mapping, menu)
    if parsed.missing_required:
        raise UploadError("missing_columns", "Match these columns before importing: "
                          + ", ".join(parsed.missing_required) + ".")
    if not parsed.orders:
        raise UploadError("no_rows", "No rows could be imported. Check the rejected rows and the column mapping.")
    defaults = {k: float(v) for k, v in (default_cost_pct or {}).items()}
    missing = [c for c in parsed.needs_food_cost if c not in defaults]
    if missing:
        raise UploadError("food_cost_needed", "Set a default food cost percentage for: " + ", ".join(missing) + ".",
                          {"categories": missing})
    for c, pct in defaults.items():
        if not 0 < pct < 100:
            raise UploadError("bad_food_cost", f"The default food cost for {c} must be between 0 and 100 percent.")

    conn = session.connection()
    if menu is not None:
        wipe_orders(conn)
        item_ids = {low: info["item_id"] for low, info in parsed.items.items()}
    else:
        wipe_restaurant(conn)
        item_ids = _insert_items(conn, parsed, defaults)
    order_rows, line_rows = [], []
    for oid, (ref, o) in enumerate(parsed.orders.items(), start=1):
        subtotal = sum(q * p for _l, q, p, _c in o["lines"])
        order_rows.append({"id": oid, "ts": o["ts"], "channel": o["channel"], "subtotal_paise": subtotal,
                           "discount_paise": 0, "total_paise": subtotal, "covers": 1, "daypart": daypart_for(o["ts"]),
                           "external_ref": ref, "customer_name": o["customer"], "upsell_added_paise": 0})
        for low, q, p, c in o["lines"]:
            line_rows.append({"order_id": oid, "item_id": item_ids[low], "qty": q, "unit_price_paise": p,
                              "unit_cost_paise": c, "modifiers_json": "[]"})
    for chunk in range(0, len(order_rows), 5000):
        conn.execute(insert(Order), order_rows[chunk:chunk + 5000])
    # Lines without a cost take the item's cost (real or estimated).
    costs = {r[0]: r[1] for r in conn.execute(text("SELECT id, food_cost_paise FROM items"))}
    for r in line_rows:
        if r["unit_cost_paise"] is None:
            r["unit_cost_paise"] = costs[r["item_id"]]
    for chunk in range(0, len(line_rows), 5000):
        conn.execute(insert(OrderItem), line_rows[chunk:chunk + 5000])
    session.commit()
    return _after_reset(session, "upload")


def _insert_items(conn, parsed: Parsed, defaults: dict[str, float]) -> dict[str, int]:
    """No menu yet: build categories and items from the sales file."""
    cat_ids: dict[str, int] = {}
    for info in parsed.items.values():
        cat = info["category"]
        if cat not in cat_ids:
            res = conn.execute(insert(Category).values(name=cat, kind=info["kind"]))
            cat_ids[cat] = res.inserted_primary_key[0]
    item_ids: dict[str, int] = {}
    for low, info in parsed.items.items():
        estimated = info["food_cost"] is None
        cost = info["food_cost"] if not estimated else round(info["price"] * defaults[info["category"]] / 100)
        res = conn.execute(insert(Item).values(
            category_id=cat_ids[info["category"]], name=info["name"], price_paise=info["price"],
            food_cost_paise=min(cost, info["price"] - 1), veg=info["veg"], spice_level=0, prep_minutes=10,
            available=True, station=DEFAULT_STATION.get(info["kind"], "curry"),
            aliases_json=json.dumps([info["name"].lower()]), image_url=info["image_url"], cost_estimated=estimated))
        item_ids[low] = res.inserted_primary_key[0]
    return item_ids


def commit_menu(session: Session, content: bytes, mapping: dict | None, default_cost_pct: dict | None) -> dict:
    report = importer.import_items(session, content, mapping, default_cost_pct, dry_run=False)
    if not report.committed:
        raise UploadError("not_imported", " ".join(report.warnings) or "No items were imported.",
                          report.to_dict())
    cache.invalidate()
    events_bus.publish("reset", {"reason": "menu"})
    return {"kind": "menu", "items": report.accepted, "message": f"Updated {report.accepted} menu items."}


def load_sample(session: Session, seed: int = 42) -> dict:
    from seed.generate import build

    tmp = Path(tempfile.mkdtemp(prefix="tadka-sample-"))
    try:
        src = build(tmp, seed=seed)
        conn = session.connection()
        wipe_restaurant(conn)
        src_con = sqlite3.connect(src)
        try:
            for table in ("categories", "items", "modifier_groups", "modifiers", "ingredients", "recipe_lines",
                          "orders", "order_items"):
                cols = [r[1] for r in src_con.execute(f"PRAGMA table_info({table})")]
                main_cols = {r[1] for r in conn.exec_driver_sql(f"PRAGMA table_info({table})")}
                shared = [c for c in cols if c in main_cols]
                rows = src_con.execute(f"SELECT {', '.join(shared)} FROM {table}").fetchall()
                sql = f"INSERT INTO {table} ({', '.join(shared)}) VALUES ({', '.join('?' * len(shared))})"
                for chunk in range(0, len(rows), 5000):
                    conn.exec_driver_sql(sql, rows[chunk:chunk + 5000])
        finally:
            src_con.close()
        session.commit()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    return _after_reset(session, "sample")


def wipe_orders(conn) -> None:
    """Remove order data and keep the menu. Calls are kept with their order link cleared."""
    for stmt in ("UPDATE calls SET order_id = NULL", "DELETE FROM upsell_events", "DELETE FROM upsell_rules",
                 "DELETE FROM pos_orders", "DELETE FROM order_items", "DELETE FROM orders"):
        conn.exec_driver_sql(stmt)


def wipe_restaurant(conn) -> None:
    """Remove menu and order data. Calls (and their recordings and transcripts) are kept; their link to an
    order is cleared because the orders are gone. Offer statistics restart with the new data."""
    for stmt in ("UPDATE calls SET order_id = NULL", "DELETE FROM upsell_events", "DELETE FROM upsell_rules",
                 "DELETE FROM pos_orders", "DELETE FROM order_items", "DELETE FROM orders",
                 "DELETE FROM price_changes", "DELETE FROM recipe_lines", "DELETE FROM ingredients",
                 "DELETE FROM modifiers", "DELETE FROM modifier_groups", "DELETE FROM items",
                 "DELETE FROM categories"):
        conn.exec_driver_sql(stmt)


def _after_reset(session: Session, reason: str) -> dict:
    settings_store.update(session, {"combo_pool": None})
    cache.invalidate()
    from dialogue.services import drop_sessions
    drop_sessions()
    first, last, n = session.exec(text("SELECT MIN(ts), MAX(ts), COUNT(*) FROM orders")).one()
    n_items = session.exec(text("SELECT COUNT(*) FROM items")).one()[0]
    n_lines = session.exec(text("SELECT COUNT(*) FROM order_items")).one()[0]
    d_from = _local_date(datetime.fromisoformat(str(first))) if first else None
    d_to = _local_date(datetime.fromisoformat(str(last))) if last else None
    def pretty(d: str | None) -> str:
        if not d:
            return ""
        dd = date.fromisoformat(d)
        return f"{dd.day} {dd:%b}"

    summary = {
        "source": reason, "orders": n, "items": n_items, "lines": n_lines, "date_from": d_from, "date_to": d_to,
        "message": f"Analysed {n:,} orders from {pretty(d_from)} to {pretty(d_to)}" if n else "No orders yet.",
        "sample": reason == "sample",
    }
    events_bus.publish("reset", summary)
    return summary


class UploadError(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code, self.message, self.details = code, message, details or {}
