"""CSV import for PoS exports: items.csv and orders.csv (one row per order line).

Flow: the client uploads a file with `dry_run=true` to get auto-detected column guesses and a
validation report, adjusts the mapping if needed, then uploads again to commit.
"""
from __future__ import annotations

import csv
import io
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

from sqlmodel import Session, delete, select

import settings
from models import CATEGORY_KINDS, Category, Item, Order, OrderItem, PosOrder
from pos.service import daypart_for

FOOD_COST_MESSAGE = "Add food cost to see margin"

# Target field -> (required, header synonyms). Synonyms are compared after normalizing.
ITEM_FIELDS: dict[str, tuple[bool, list[str]]] = {
    "name": (True, ["item_name", "item", "name", "dish", "product", "menu_item", "item_description"]),
    "category": (True, ["category", "category_name", "group", "menu_group", "section", "type"]),
    "price": (True, ["price", "selling_price", "rate", "mrp", "unit_price", "sale_price"]),
    "food_cost": (False, ["food_cost", "cost", "cost_price", "unit_cost", "cogs", "plate_cost"]),
    "veg": (False, ["veg", "is_veg", "vegetarian", "veg_nonveg", "food_type", "diet"]),
    "station": (False, ["station", "kitchen", "kitchen_station", "section_kitchen"]),
    "prep_minutes": (False, ["prep_minutes", "prep_time", "preparation_time", "cook_time"]),
}
ORDER_FIELDS: dict[str, tuple[bool, list[str]]] = {
    "order_ref": (True, ["order_id", "order_no", "bill_no", "invoice_no", "bill_number", "order_number", "ticket"]),
    "ts": (True, ["order_time_utc", "order_time", "timestamp", "date_time", "datetime", "created_at",
                  "bill_date", "date", "time"]),
    "item_name": (True, ["item_name", "item", "dish", "product", "menu_item", "name"]),
    "qty": (True, ["qty", "quantity", "units", "count"]),
    "unit_price": (False, ["unit_price", "price", "rate", "item_price", "selling_price"]),
    "channel": (False, ["channel", "order_type", "source", "service_type", "mode"]),
    "covers": (False, ["covers", "pax", "guests", "persons"]),
    "discount": (False, ["discount", "bill_discount", "discount_amount"]),
    "unit_cost": (False, ["unit_cost", "food_cost", "cost"]),
}

CATEGORY_SYNONYMS = {
    "starter": ["starter", "starters", "appetizer", "appetizers", "snacks", "tandoor starters", "chinese starters"],
    "main": ["main", "mains", "main course", "curry", "curries", "gravy", "thali"],
    "bread": ["bread", "breads", "roti", "indian breads", "tandoor breads"],
    "rice": ["rice", "rice and noodles", "biryani", "noodles", "rice & noodles", "chinese"],
    "dessert": ["dessert", "desserts", "sweets", "mithai"],
    "beverage": ["beverage", "beverages", "drinks", "cold drinks", "hot drinks", "shakes", "mocktails"],
    "side": ["side", "sides", "accompaniments", "salad", "raita", "extras"],
}
CHANNEL_SYNONYMS = {
    "dine_in": ["dine_in", "dine in", "dinein", "table", "eat in", "restaurant"],
    "phone": ["phone", "call", "telephone", "phone order"],
    "takeaway": ["takeaway", "take away", "pickup", "pick up", "parcel", "takeout", "delivery"],
}
DEFAULT_STATION = {"starter": "tandoor", "main": "curry", "bread": "tandoor", "rice": "curry",
                   "dessert": "dessert", "beverage": "beverage", "side": "cold"}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.strip().lower()).strip("_")


@dataclass
class Rejected:
    row: int  # 1-based data row number, header excluded
    reason: str


@dataclass
class ImportReport:
    kind: str
    columns: list[str]
    mapping: dict[str, str | None]
    missing_required: list[str]
    accepted: int = 0
    rejected: list[Rejected] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    needs_food_cost: list[str] = field(default_factory=list)  # categories without cost data
    committed: bool = False
    sample: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        reasons: dict[str, int] = {}
        for r in self.rejected:
            reasons[r.reason] = reasons.get(r.reason, 0) + 1
        return {
            "kind": self.kind,
            "columns": self.columns,
            "mapping": self.mapping,
            "missing_required": self.missing_required,
            "accepted": self.accepted,
            "rejected": len(self.rejected),
            "rejected_reasons": [{"reason": k, "count": v} for k, v in sorted(reasons.items(), key=lambda x: -x[1])],
            "rejected_rows": [{"row": r.row, "reason": r.reason} for r in self.rejected[:50]],
            "warnings": self.warnings,
            "needs_food_cost": self.needs_food_cost,
            "food_cost_message": FOOD_COST_MESSAGE if self.needs_food_cost else None,
            "committed": self.committed,
            "sample": self.sample,
        }


def guess_mapping(columns: list[str], fields: dict[str, tuple[bool, list[str]]]) -> dict[str, str | None]:
    """Map each target field to the best matching CSV column, never reusing a column."""
    normalized = {c: _norm(c) for c in columns}
    used: set[str] = set()
    mapping: dict[str, str | None] = {}
    for target, (_req, synonyms) in fields.items():
        found = None
        for syn in synonyms:  # exact match first, in synonym priority order
            for col, n in normalized.items():
                if col not in used and n == syn:
                    found = col
                    break
            if found:
                break
        if not found:
            for syn in synonyms:
                for col, n in normalized.items():
                    if col not in used and syn in n.split("_") + [n]:
                        found = col
                        break
                if found:
                    break
        mapping[target] = found
        if found:
            used.add(found)
    return mapping


def read_csv(content: bytes) -> tuple[list[str], list[dict]]:
    text = content.decode("utf-8-sig", errors="replace")
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.DictReader(io.StringIO(text), dialect=dialect)
    rows = [r for r in reader if any((v or "").strip() for v in r.values())]
    return [c for c in (reader.fieldnames or []) if c is not None], rows


def parse_money(value: str | None) -> int | None:
    """'₹1,250.50' -> 125050 paise. Returns None for blank."""
    if value is None or not str(value).strip():
        return None
    cleaned = re.sub(r"[₹,\s]|rs\.?|inr", "", str(value).strip(), flags=re.I)
    try:
        amount = Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"'{value}' is not an amount")
    if amount < 0:
        raise ValueError("amount is negative")
    return int((amount * 100).quantize(Decimal("1")))


def parse_bool_veg(value: str | None) -> bool | None:
    if value is None or not str(value).strip():
        return None
    v = str(value).strip().lower()
    if v in ("yes", "y", "true", "1", "veg", "v", "vegetarian", "pure veg"):
        return True
    if v in ("no", "n", "false", "0", "non-veg", "nonveg", "non veg", "nv", "egg"):
        return False
    raise ValueError(f"'{value}' is not veg or non-veg")


def parse_category(value: str) -> str | None:
    v = value.strip().lower()
    for kind, syns in CATEGORY_SYNONYMS.items():
        if v in syns:
            return kind
    for kind, syns in CATEGORY_SYNONYMS.items():
        if any(s in v for s in syns):
            return kind
    return None


def parse_channel(value: str | None) -> str:
    if not value or not value.strip():
        return "dine_in"
    v = value.strip().lower()
    for ch, syns in CHANNEL_SYNONYMS.items():
        if v in syns or any(s in v for s in syns):
            return ch
    raise ValueError(f"unknown channel '{value}'")


def parse_ts(value: str) -> datetime:
    """Accept ISO 8601 with or without zone, and common Indian PoS formats. Times without a zone
    are taken as restaurant local time. Returns naive UTC."""
    v = value.strip()
    if not v:
        raise ValueError("time is blank")
    dt = None
    try:
        dt = datetime.fromisoformat(v.replace("Z", "+00:00"))
    except ValueError:
        for fmt in ("%d/%m/%Y %H:%M", "%d/%m/%Y %H:%M:%S", "%d-%m-%Y %H:%M", "%d-%m-%Y %H:%M:%S",
                    "%d/%m/%Y %I:%M %p", "%d-%b-%Y %H:%M", "%Y/%m/%d %H:%M"):
            try:
                dt = datetime.strptime(v, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        raise ValueError(f"'{value}' is not a date and time")
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=ZoneInfo(settings.RESTAURANT_TZ))
    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def _resolve_mapping(columns, fields, mapping):
    m = guess_mapping(columns, fields)
    if mapping:
        for k, v in mapping.items():
            if k in fields:
                m[k] = v if v in columns else None
    missing = [k for k, (req, _s) in fields.items() if req and not m.get(k)]
    return m, missing


# ----- items ---------------------------------------------------------------------


def import_items(session: Session, content: bytes, mapping: dict | None = None,
                 default_cost_pct: dict[str, float] | None = None, dry_run: bool = True) -> ImportReport:
    """Upsert menu items by name. Items not in the file are left as they are."""
    columns, rows = read_csv(content)
    m, missing = _resolve_mapping(columns, ITEM_FIELDS, mapping)
    report = ImportReport("items", columns, m, missing)
    if missing:
        report.warnings.append("Match these columns before importing: " + ", ".join(missing))
        return report
    default_cost_pct = {k: float(v) for k, v in (default_cost_pct or {}).items()}

    parsed: list[dict] = []
    seen: set[str] = set()
    no_cost_cats: set[str] = set()
    for idx, raw in enumerate(rows, start=1):
        get = lambda f: (raw.get(m[f]) or "").strip() if m.get(f) else ""
        try:
            name = get("name")
            if not name:
                raise ValueError("item name is blank")
            if name.lower() in seen:
                raise ValueError("item appears twice in the file")
            kind = parse_category(get("category"))
            if kind is None:
                raise ValueError(f"category '{get('category')}' does not match {', '.join(CATEGORY_KINDS)}")
            price = parse_money(get("price"))
            if not price:
                raise ValueError("price is blank or zero")
            cost = parse_money(get("food_cost")) if m.get("food_cost") else None
            if cost is None:
                pct = default_cost_pct.get(kind)
                if pct is None:
                    no_cost_cats.add(kind)
                else:
                    if not 0 < pct < 100:
                        raise ValueError(f"default cost for {kind} must be between 0 and 100 percent")
                    cost = round(price * pct / 100)
            elif cost >= price:
                raise ValueError("food cost is not lower than price")
            veg = parse_bool_veg(get("veg")) if m.get("veg") else None
            prep = int(get("prep_minutes")) if m.get("prep_minutes") and get("prep_minutes") else None
        except ValueError as exc:
            report.rejected.append(Rejected(idx, str(exc)))
            continue
        seen.add(name.lower())
        parsed.append({"name": name, "kind": kind, "price": price, "cost": cost, "veg": veg,
                       "station": get("station") or DEFAULT_STATION[kind], "prep": prep})

    report.accepted = len(parsed)
    report.needs_food_cost = sorted(no_cost_cats)
    report.sample = [
        {"name": p["name"], "category": p["kind"], "price": p["price"] / 100,
         "food_cost": None if p["cost"] is None else p["cost"] / 100}
        for p in parsed[:5]
    ]
    if no_cost_cats:
        report.warnings.append(f"{FOOD_COST_MESSAGE}. Set a default cost percentage for: "
                               + ", ".join(sorted(no_cost_cats)) + ".")
    if dry_run or no_cost_cats or not parsed:
        return report

    cats = {c.kind: c for c in session.exec(select(Category))}
    for kind in {p["kind"] for p in parsed} - cats.keys():
        c = Category(name=kind.title(), kind=kind)
        session.add(c)
        session.flush()
        cats[kind] = c
    existing = {i.name.lower(): i for i in session.exec(select(Item))}
    for p in parsed:
        item = existing.get(p["name"].lower())
        if item is None:
            item = Item(category_id=cats[p["kind"]].id, name=p["name"], price_paise=p["price"],
                        food_cost_paise=p["cost"], veg=True if p["veg"] is None else p["veg"],
                        station=p["station"], aliases_json=json.dumps([p["name"].lower()]))
        else:
            item.category_id = cats[p["kind"]].id
            item.price_paise = p["price"]
            item.food_cost_paise = p["cost"]
            if p["veg"] is not None:
                item.veg = p["veg"]
            item.station = p["station"]
        if p["prep"]:
            item.prep_minutes = p["prep"]
        session.add(item)
    session.commit()
    report.committed = True
    return report


# ----- orders --------------------------------------------------------------------


def import_orders(session: Session, content: bytes, mapping: dict | None = None, mode: str = "replace",
                  dry_run: bool = True) -> ImportReport:
    """Import order lines grouped by order reference. `replace` clears existing order history first."""
    if mode not in ("replace", "append"):
        raise ValueError("mode must be replace or append")
    columns, rows = read_csv(content)
    m, missing = _resolve_mapping(columns, ORDER_FIELDS, mapping)
    report = ImportReport("orders", columns, m, missing)
    if missing:
        report.warnings.append("Match these columns before importing: " + ", ".join(missing))
        return report

    items = {i.name.lower(): i for i in session.exec(select(Item))}
    for i in list(items.values()):
        for alias in json.loads(i.aliases_json or "[]"):
            items.setdefault(alias.lower(), i)
    no_cost = {i.name for i in items.values() if not i.food_cost_paise}

    orders: dict[str, dict] = {}
    for idx, raw in enumerate(rows, start=1):
        get = lambda f: (raw.get(m[f]) or "").strip() if m.get(f) else ""
        try:
            ref = get("order_ref")
            if not ref:
                raise ValueError("order id is blank")
            item = items.get(get("item_name").lower())
            if item is None:
                raise ValueError(f"item not on menu: {get('item_name') or '(blank)'}")
            qty_raw = get("qty")
            try:
                qty_dec = Decimal(qty_raw)
            except InvalidOperation:
                raise ValueError(f"quantity '{qty_raw}' is not a number")
            if qty_dec <= 0 or qty_dec != qty_dec.to_integral_value():
                raise ValueError("quantity must be a whole number above zero")
            qty = int(qty_dec)
            price = parse_money(get("unit_price")) if m.get("unit_price") else None
            price = item.price_paise if price is None else price
            cost = parse_money(get("unit_cost")) if m.get("unit_cost") else None
            cost = item.food_cost_paise if cost is None else cost
            order = orders.get(ref)
            if order is None:
                ts = parse_ts(get("ts"))
                order = orders[ref] = {
                    "ts": ts, "channel": parse_channel(get("channel")),
                    "covers": int(get("covers")) if get("covers").isdigit() else 1,
                    "discount": parse_money(get("discount")) or 0, "lines": [],
                }
            else:
                extra = parse_money(get("discount")) or 0
                order["discount"] += extra
            order["lines"].append((item.id, qty, price, cost))
        except ValueError as exc:
            report.rejected.append(Rejected(idx, str(exc)))

    report.accepted = sum(len(o["lines"]) for o in orders.values())
    report.sample = [
        {"order_ref": ref, "ts": o["ts"].isoformat() + "Z", "channel": o["channel"], "lines": len(o["lines"])}
        for ref, o in list(orders.items())[:5]
    ]
    if no_cost:
        report.needs_food_cost = ["items"]
        report.warnings.append(f"{FOOD_COST_MESSAGE}: {len(no_cost)} menu items have no food cost.")
    if orders:
        first = min(o["ts"] for o in orders.values())
        last = max(o["ts"] for o in orders.values())
        report.warnings.append(f"{len(orders)} orders from {first.date()} to {last.date()} (UTC).")
    if dry_run or not orders:
        return report

    if mode == "replace":
        session.exec(delete(PosOrder))
        session.exec(delete(OrderItem))
        session.exec(delete(Order))
    for ref, o in orders.items():
        subtotal = sum(q * p for _i, q, p, _c in o["lines"])
        discount = min(o["discount"], subtotal)
        row = Order(ts=o["ts"], channel=o["channel"], subtotal_paise=subtotal, discount_paise=discount,
                    total_paise=subtotal - discount, covers=o["covers"], daypart=daypart_for(o["ts"]),
                    external_ref=ref)
        session.add(row)
        session.flush()
        for item_id, q, p, c in o["lines"]:
            session.add(OrderItem(order_id=row.id, item_id=item_id, qty=q, unit_price_paise=p, unit_cost_paise=c))
    session.commit()
    report.committed = True
    return report

