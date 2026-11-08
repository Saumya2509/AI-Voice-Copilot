"""Tadka API. Base path /api/v1.

Run from apps/api:  uvicorn main:app --reload --port 8000
"""
from __future__ import annotations

import asyncio
import base64
import csv
import io
import json
import logging
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import APIRouter, Depends, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response, StreamingResponse
from sqlalchemy import and_, or_
from sqlmodel import Session, func, select
from starlette.exceptions import HTTPException as StarletteHTTPException

import db
import events_bus
import importer
import settings
from money import rupees
from models import Category, Item, Modifier, ModifierGroup, Order, OrderItem, PosOrder
from pos.mock_pos import MockPosAdapter
from pos.service import DraftOrder, OrderRejected, finalize_and_push, retry_order
from revenue import cache
from revenue.engine import get_engine
from routes_calls import router as calls_router, ws_router
from routes_data import router as data_router
from routes_revenue import ApiError, router as revenue_router

log = logging.getLogger("tadka")
NL = chr(10)


def error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


@asynccontextmanager
async def lifespan(_app: FastAPI):
    if not settings.DB_PATH.exists():
        log.warning("No database at %s. Creating it with the built-in menu and no orders.", settings.DB_PATH)
    db.init_db()
    if settings.PRELOAD_MENU:
        from seed.generate import install_menu

        if install_menu(settings.DB_PATH):
            log.info("Loaded the built-in menu into %s.", settings.DB_PATH)
    # Precompute analytics, upsell rules and the NLU so a live call only reads them.
    from dialogue.services import services_for
    from nlu.intent import load_model

    get_engine().warm()
    load_model()
    from tts import get_tts

    get_tts().warm()
    services_for(str(settings.DB_PATH)).parser
    yield
    db.dispose()


app = FastAPI(title="Tadka API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ApiError)
async def _api_error(_req: Request, exc: ApiError):
    return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status)


@app.exception_handler(OrderRejected)
async def _order_rejected(_req: Request, exc: OrderRejected):
    return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=422)


@app.exception_handler(RequestValidationError)
async def _validation(_req: Request, exc: RequestValidationError):
    return JSONResponse(error_body("invalid_request", "Some fields are missing or have the wrong type. "
                                   "Check the details and send again.", {"errors": exc.errors()}),
                        status_code=422)


@app.exception_handler(StarletteHTTPException)
async def _http(_req: Request, exc: StarletteHTTPException):
    code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
    message = {404: "There is nothing at this address. Check the path against /docs.",
               405: "This path does not accept that method. Check /docs for the right one."}.get(
        exc.status_code, str(exc.detail))
    return JSONResponse(error_body(code, message), status_code=exc.status_code)


@app.exception_handler(Exception)
async def _unhandled(_req: Request, exc: Exception):
    log.exception("Unhandled error", exc_info=exc)
    return JSONResponse(error_body("internal_error", "Something went wrong on the server. Retry; if it keeps "
                                   "happening, check the API log.", {"type": type(exc).__name__}), status_code=500)


api = APIRouter(prefix="/api/v1")


def get_adapter() -> MockPosAdapter:
    return MockPosAdapter(db.get_engine())


# ----- health and menu ---------------------------------------------------------------


@api.get("/health")
def health(session: Session = Depends(db.get_session)):
    items = session.exec(select(func.count()).select_from(Item)).one()
    orders = session.exec(select(func.count()).select_from(Order)).one()
    first, last = session.exec(select(func.min(Order.ts), func.max(Order.ts))).one()
    return {
        "status": "ok",
        "items": items,
        "orders": orders,
        "data_from": first.isoformat() + "Z" if first else None,
        "data_to": last.isoformat() + "Z" if last else None,
        "analytics_version": cache.version(),
    }


@api.get("/menu")
def menu(session: Session = Depends(db.get_session)):
    cats = {c.id: c for c in session.exec(select(Category))}
    groups: dict[int, list[ModifierGroup]] = {}
    for g in session.exec(select(ModifierGroup).order_by(ModifierGroup.id)):
        groups.setdefault(g.item_id, []).append(g)
    mods: dict[int, list[Modifier]] = {}
    for m in session.exec(select(Modifier).order_by(Modifier.id)):
        mods.setdefault(m.group_id, []).append(m)
    picks, holds = _menu_signals(session)
    items = []
    for i in session.exec(select(Item).order_by(Item.category_id, Item.id)):
        items.append({
            "chefs_pick": i.id in picks,
            "hold_reason": holds.get(i.id),
            "description": i.description,
            "image_url": i.image_url,
            "id": i.id,
            "name": i.name,
            "category": cats[i.category_id].kind,
            "category_name": cats[i.category_id].name,
            "price": rupees(i.price_paise),
            "food_cost": rupees(i.food_cost_paise),
            "veg": i.veg,
            "spice_level": i.spice_level,
            "prep_minutes": i.prep_minutes,
            "available": i.available,
            "station": i.station,
            "aliases": json.loads(i.aliases_json or "[]"),
            "modifier_groups": [
                {
                    "id": g.id, "name": g.name, "required": g.required,
                    "min_select": g.min_select, "max_select": g.max_select,
                    "options": [{"id": m.id, "name": m.name, "price_delta": rupees(m.price_delta_paise)}
                                for m in mods.get(g.id, [])],
                }
                for g in groups.get(i.id, [])
            ],
        })
    categories = [{"id": c.id, "name": c.name, "kind": c.kind} for c in cats.values()]
    return {"categories": categories, "items": items}


def _menu_signals(session: Session) -> tuple[set[int], dict[int, str]]:
    """Chef's pick: a Puzzle or Star whose margin is well above its category's (at most one per category).
    Hold reasons come from the inventory signals."""
    eng = get_engine()
    try:
        df = eng.classes(30)
        sig = eng.signals(session)
    except Exception:  # an empty database has no analytics yet
        return set(), {}
    picks: set[int] = set()
    if len(df):
        cand = df[df["class"].isin(["puzzle", "star"]) & (df["cm_paise"] >= 1.15 * df["category_avg_cm_paise"])
                  & df["available"]].copy()
        cand["ratio"] = cand["cm_paise"] / cand["category_avg_cm_paise"]
        picks = {int(r.item_id) for r in cand.sort_values("ratio", ascending=False).groupby("category").head(1).itertuples()}
    return picks, {int(k): v for k, v in sig.hold.items()}


# ----- orders and PoS ----------------------------------------------------------------


def _order_summary(o: Order, pos: Optional[PosOrder]) -> dict:
    payload = json.loads(pos.payload_json) if pos and pos.payload_json else {}
    return {
        "order_id": f"ORD-{o.id}",
        "ts": o.ts.isoformat() + "Z",
        "channel": o.channel,
        "daypart": o.daypart,
        "covers": o.covers,
        "subtotal": rupees(o.subtotal_paise),
        "discount": rupees(o.discount_paise),
        "total": rupees(o.total_paise),
        "external_ref": o.external_ref,
        "customer_name": o.customer_name,
        "source": "tadka" if pos else "pos_history",
        "upsell_added": payload.get("upsell", {}).get("added_revenue") if payload else None,
        "confirmed_at": payload.get("confirmed_at") if payload else None,
        "pos": None if pos is None else {
            "status": pos.status, "kot_no": pos.kot_no, "attempts": pos.attempts, "error": pos.error,
            "sent_at": pos.sent_at.isoformat() + "Z" if pos.sent_at else None,
            "ack_at": pos.ack_at.isoformat() + "Z" if pos.ack_at else None,
        },
    }


def _with_items(summary: dict, items: list[dict]) -> dict:
    return {**summary, "items": items}


def _parse_order_id(order_id: str) -> int:
    try:
        return int(order_id.upper().removeprefix("ORD-"))
    except ValueError:
        raise ApiError(404, "not_found", f"There is no order {order_id}.")


# Timestamps are compared in one text form; rows written by different tools differ in precision.
TS_KEY = func.strftime("%Y-%m-%d %H:%M:%f", Order.ts)
ORDER_SORTS = {
    "newest": (TS_KEY, "desc"), "oldest": (TS_KEY, "asc"),
    "total_desc": (Order.total_paise, "desc"), "total_asc": (Order.total_paise, "asc"),
}


def _ts_key(ts: datetime) -> str:
    return f"{ts:%Y-%m-%d %H:%M:%S}.{ts.microsecond // 1000:03d}"


def local_day_bounds(day: str, end: bool = False) -> datetime:
    """Restaurant-local date (YYYY-MM-DD) to a naive UTC bound."""
    try:
        d = date.fromisoformat(day)
    except ValueError:
        raise ApiError(422, "invalid_date", f"'{day}' is not a date. Use YYYY-MM-DD.")
    local = datetime.combine(d + timedelta(days=1) if end else d, time(0), ZoneInfo(settings.RESTAURANT_TZ))
    return local.astimezone(timezone.utc).replace(tzinfo=None)


def _filtered_orders(q, channel, status, has_upsell, date_from, date_to, source):
    stmt = select(Order, PosOrder).join(PosOrder, PosOrder.order_id == Order.id, isouter=True)
    if channel:
        stmt = stmt.where(Order.channel == channel)
    if status:
        stmt = stmt.where(PosOrder.status == status)
    if source == "tadka":
        stmt = stmt.where(PosOrder.id.is_not(None))
    elif source == "pos_history":
        stmt = stmt.where(PosOrder.id.is_(None))
    if has_upsell is True:
        stmt = stmt.where(Order.upsell_added_paise > 0)
    elif has_upsell is False:
        stmt = stmt.where(Order.upsell_added_paise == 0)
    if date_from:
        stmt = stmt.where(Order.ts >= local_day_bounds(date_from))
    if date_to:
        stmt = stmt.where(Order.ts < local_day_bounds(date_to, end=True))
    if q and q.strip():
        term = q.strip()
        digits = term.upper().removeprefix("ORD-").removeprefix("ORD")
        like = f"%{term.lower()}%"
        item_match = select(OrderItem.id).join(Item, Item.id == OrderItem.item_id).where(
            OrderItem.order_id == Order.id, func.lower(Item.name).like(like)).exists()
        conds = [item_match, func.lower(Order.customer_name).like(like), func.lower(Order.external_ref).like(like)]
        if digits.isdigit():
            conds.append(Order.id == int(digits))
        stmt = stmt.where(or_(*conds))
    return stmt


def _cursor_encode(value, oid: int) -> str:
    v = _ts_key(value) if isinstance(value, datetime) else value
    return base64.urlsafe_b64encode(json.dumps([v, oid]).encode()).decode().rstrip("=")


def _cursor_decode(cursor: str, col):
    try:
        v, oid = json.loads(base64.urlsafe_b64decode(cursor + "=" * (-len(cursor) % 4)))
        return (str(v) if col is TS_KEY else int(v)), int(oid)
    except Exception:
        raise ApiError(422, "invalid_cursor", "The page cursor is not valid. Start again from the first page.")


@api.get("/orders")
def list_orders(
    q: Optional[str] = Query(None, description="Search order id, item name or customer"),
    channel: Optional[str] = None,
    status: Optional[str] = Query(None, description="PoS status: pending, sent, acked, needs_attention"),
    has_upsell: Optional[bool] = None,
    source: Optional[str] = Query(None, pattern="^(tadka|pos_history)$"),
    date_from: Optional[str] = Query(None, alias="from", description="Restaurant-local date, YYYY-MM-DD"),
    date_to: Optional[str] = Query(None, alias="to"),
    sort: str = Query("newest", pattern="^(newest|oldest|total_desc|total_asc)$"),
    cursor: Optional[str] = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    with_items: bool = Query(False, description="Include each order's dishes (name and quantity)"),
    session: Session = Depends(db.get_session),
):
    """Orders from the database with cursor paging. `next_cursor` is null on the last page."""
    base = _filtered_orders(q, channel, status, has_upsell, date_from, date_to, source)
    sub = base.subquery()
    total, revenue, added = session.exec(select(func.count(), func.coalesce(func.sum(sub.c.total_paise), 0),
                                                func.coalesce(func.sum(sub.c.upsell_added_paise), 0))).one()
    col, direction = ORDER_SORTS[sort]
    stmt = base
    if cursor:
        v, oid = _cursor_decode(cursor, col)
        stmt = stmt.where(or_(col < v, and_(col == v, Order.id < oid)) if direction == "desc"
                          else or_(col > v, and_(col == v, Order.id > oid)))
    order_by = (col.desc(), Order.id.desc()) if direction == "desc" else (col.asc(), Order.id.asc())
    rows = session.exec(stmt.order_by(*order_by).offset(0 if cursor else offset).limit(limit + 1)).all()
    page, more = rows[:limit], len(rows) > limit
    lines: dict[int, list[dict]] = {}
    if with_items and page:
        for oi, name in session.exec(select(OrderItem, Item.name).join(Item, Item.id == OrderItem.item_id)
                                     .where(OrderItem.order_id.in_([o.id for o, _ in page])).order_by(OrderItem.id)):
            lines.setdefault(oi.order_id, []).append({"name": name, "qty": oi.qty})
    last = page[-1][0] if page else None
    key = "ts" if col is TS_KEY else "total_paise"
    next_cursor = _cursor_encode(getattr(last, key), last.id) if more and last else None
    return {
        "total": total, "next_cursor": next_cursor, "sort": sort,
        "summary": {"orders": total, "revenue": rupees(revenue), "upsell_added": rupees(added)},
        "orders": [_with_items(_order_summary(o, p), lines.get(o.id, [])) if with_items else _order_summary(o, p)
                   for o, p in page],
    }


@api.get("/orders/export")
def export_orders(
    q: Optional[str] = None, channel: Optional[str] = None, status: Optional[str] = None,
    has_upsell: Optional[bool] = None, source: Optional[str] = None,
    date_from: Optional[str] = Query(None, alias="from"), date_to: Optional[str] = Query(None, alias="to"),
    sort: str = Query("newest", pattern="^(newest|oldest|total_desc|total_asc)$"),
    session: Session = Depends(db.get_session),
):
    """CSV of every order matching the same filters as the list."""
    col, direction = ORDER_SORTS[sort]
    stmt = _filtered_orders(q, channel, status, has_upsell, date_from, date_to, source)
    rows = session.exec(stmt.order_by(col.desc() if direction == "desc" else col.asc(), Order.id.desc())
                        .limit(200_000)).all()
    ids = [o.id for o, _ in rows]
    lines: dict[int, list[str]] = {}
    for chunk in range(0, len(ids), 900):
        for oi, name in session.exec(select(OrderItem, Item.name).join(Item, Item.id == OrderItem.item_id)
                                     .where(OrderItem.order_id.in_(ids[chunk:chunk + 900]))):
            lines.setdefault(oi.order_id, []).append(f"{oi.qty} x {name}")
    tz = ZoneInfo(settings.RESTAURANT_TZ)
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["order_id", "local_time", "channel", "items", "subtotal", "discount", "total", "upsell_added",
                "status", "kot_no", "customer"])
    for o, p in rows:
        w.writerow([f"ORD-{o.id}", o.ts.replace(tzinfo=timezone.utc).astimezone(tz).strftime("%Y-%m-%d %H:%M"),
                    o.channel, "; ".join(lines.get(o.id, [])), rupees(o.subtotal_paise), rupees(o.discount_paise),
                    rupees(o.total_paise), rupees(o.upsell_added_paise), p.status if p else "pos_history",
                    p.kot_no if p and p.kot_no else "", o.customer_name or ""])
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"Content-Disposition": "attachment; filename=tadka-orders.csv"})


@api.get("/orders/stream")
async def order_stream(request: Request, max_events: Optional[int] = Query(None, ge=1, le=1000)):
    """Server-sent events: `order` when a new order is recorded, `order.status` when the PoS answers,
    and `reset` after a data import. A comment line every 15 seconds keeps the connection open."""
    queue = events_bus.subscribe()

    async def gen():
        sent = 0
        try:
            yield "retry: 3000" + NL + NL
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=15)
                except asyncio.TimeoutError:
                    yield ": keep-alive" + NL + NL
                    continue
                yield f"event: {event}" + NL + f"data: {json.dumps(data)}" + NL + NL
                sent += 1
                if max_events and sent >= max_events:
                    break
        finally:
            events_bus.unsubscribe(queue)

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@api.get("/orders/{order_id}")
def get_order(order_id: str, session: Session = Depends(db.get_session)):
    oid = _parse_order_id(order_id)
    o = session.get(Order, oid)
    if o is None:
        raise ApiError(404, "not_found", f"There is no order {order_id}.")
    pos = session.exec(select(PosOrder).where(PosOrder.order_id == oid)).first()
    lines = session.exec(select(OrderItem, Item).join(Item, Item.id == OrderItem.item_id)
                         .where(OrderItem.order_id == oid).order_by(OrderItem.id)).all()
    out = _order_summary(o, pos)
    out["lines"] = [
        {"item_id": i.id, "name": i.name, "qty": oi.qty, "unit_price": rupees(oi.unit_price_paise),
         "modifiers": json.loads(oi.modifiers_json or "[]")}
        for oi, i in lines
    ]
    out["order_json"] = json.loads(pos.payload_json) if pos else None
    out["kot"] = json.loads(pos.kot_json) if pos and pos.kot_json else None
    return out


@api.post("/orders")
def create_order(draft: DraftOrder, session: Session = Depends(db.get_session),
                 adapter: MockPosAdapter = Depends(get_adapter)):
    """Finalize an order and push it to the PoS. The dialogue manager calls the same service."""
    payload, result = finalize_and_push(session, adapter, draft)
    return {"order": payload.to_json_dict(), "status": result.status, "kot_no": result.kot_no,
            "attempts": result.attempts, "error": result.error, "duplicate": result.duplicate,
            "events": result.events}


@api.post("/orders/{order_id}/retry")
def retry(order_id: str, session: Session = Depends(db.get_session),
          adapter: MockPosAdapter = Depends(get_adapter)):
    result = retry_order(session, adapter, _parse_order_id(order_id))
    return {"order_id": result.order_id, "status": result.status, "kot_no": result.kot_no,
            "attempts": result.attempts, "error": result.error, "events": result.events}


# ----- CSV import --------------------------------------------------------------------


def _json_form(value: Optional[str], field: str) -> dict | None:
    if not value:
        return None
    try:
        data = json.loads(value)
    except json.JSONDecodeError:
        raise ApiError(422, "invalid_request", f"{field} must be a JSON object.")
    if not isinstance(data, dict):
        raise ApiError(422, "invalid_request", f"{field} must be a JSON object.")
    return data


@api.post("/import/items")
async def import_items(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None, description='JSON: {"name": "Item Name", "price": "Rate"}'),
    default_cost_pct: Optional[str] = Form(None, description='JSON: {"main": 35, "beverage": 25}'),
    dry_run: bool = Form(True),
    session: Session = Depends(db.get_session),
):
    report = importer.import_items(session, await file.read(), _json_form(mapping, "mapping"),
                                   _json_form(default_cost_pct, "default_cost_pct"), dry_run=dry_run)
    if report.committed:
        cache.invalidate()
    return report.to_dict()


@api.post("/import/orders")
async def import_orders(
    file: UploadFile = File(...),
    mapping: Optional[str] = Form(None),
    mode: str = Form("replace", description="replace clears existing order history; append adds to it"),
    dry_run: bool = Form(True),
    session: Session = Depends(db.get_session),
):
    if mode not in ("replace", "append"):
        raise ApiError(422, "invalid_request", "mode must be replace or append.")
    report = importer.import_orders(session, await file.read(), _json_form(mapping, "mapping"), mode, dry_run)
    if report.committed:
        cache.invalidate()
    return report.to_dict()


app.include_router(api)
app.include_router(revenue_router)
app.include_router(data_router)
app.include_router(calls_router)
app.include_router(ws_router)
