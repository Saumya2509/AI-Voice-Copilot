"""Order finalization and PoS push.

1. Recompute every price from the database (the client total is never trusted).
2. Mask the phone number, build the order JSON and validate it against the shared schema.
3. Push to the PoS with an idempotency key, retrying with exponential backoff.
4. After three failed attempts the order is marked `needs_attention` with the reason.
"""
from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel
from sqlmodel import Session, select

import events_bus
import settings
from models import Item, Modifier, ModifierGroup, Order, OrderItem, PosOrder
from pos.adapter import PosAdapter, PosError
from pos.mock_pos import iso_z, utcnow
from privacy import mask_phone
from schemas import Customer, Modifier as OrderModifier, OrderLine, OrderPayload, UpsellSummary, validate_order

MAX_ATTEMPTS = 3
BACKOFF_BASE_S = 0.25  # waits 0.25 s, then 0.5 s between attempts


class DraftModifier(BaseModel):
    group: str
    name: str


class DraftLine(BaseModel):
    item_id: int
    qty: int
    modifiers: list[DraftModifier] = []
    notes: str = ""
    source: str = "customer"
    upsell_rule_id: Optional[int] = None


class DraftOrder(BaseModel):
    """What the dialogue manager hands over at confirmation. Prices are looked up, not trusted."""
    call_id: Optional[str] = None
    channel: str = "phone"
    language: str = "en"
    customer_name: Optional[str] = None
    customer_phone: Optional[str] = None
    customer_address: Optional[str] = None
    lines: list[DraftLine]
    upsell_shown: int = 0
    discount: int = 0


class OrderRejected(Exception):
    def __init__(self, code: str, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}


@dataclass
class PushResult:
    order_id: str
    status: str
    attempts: int
    kot_no: Optional[str] = None
    error: Optional[str] = None
    duplicate: bool = False
    events: list[dict] = field(default_factory=list)  # pos.sent / pos.ack / error, for the WebSocket


def cart_hash(lines: list[DraftLine]) -> str:
    canon = sorted(
        json.dumps(
            {"i": l.item_id, "q": l.qty, "m": sorted(f"{m.group}:{m.name}" for m in l.modifiers),
             "n": l.notes.strip().lower()},
            sort_keys=True,
        )
        for l in lines
    )
    return hashlib.sha256("|".join(canon).encode()).hexdigest()


def idempotency_key(call_id: str | None, lines: list[DraftLine]) -> str:
    return hashlib.sha256(f"{call_id or ''}:{cart_hash(lines)}".encode()).hexdigest()[:32]


def daypart_for(ts_utc: datetime) -> str:
    local = ts_utc.replace(tzinfo=timezone.utc).astimezone(ZoneInfo(settings.RESTAURANT_TZ))
    h = local.hour + local.minute / 60
    if h < 11:
        return "breakfast"
    if h < 16:
        return "lunch"
    if h < 19:
        return "snack"
    return "dinner"


def price_lines(session: Session, draft: DraftOrder) -> tuple[list[OrderLine], list[tuple[int, int]]]:
    """Return priced order lines and (unit_price_paise, unit_cost_paise) for each line."""
    if not draft.lines:
        raise OrderRejected("empty_order", "Add at least one item before confirming.")
    ids = {l.item_id for l in draft.lines}
    items = {i.id: i for i in session.exec(select(Item).where(Item.id.in_(ids)))}
    groups = session.exec(select(ModifierGroup).where(ModifierGroup.item_id.in_(ids))).all()
    mods = session.exec(select(Modifier).where(Modifier.group_id.in_([g.id for g in groups]))).all() if groups else []
    by_item: dict[int, dict[tuple[str, str], Modifier]] = {}
    required: dict[int, list[str]] = {}
    group_by_id = {g.id: g for g in groups}
    for g in groups:
        if g.required:
            required.setdefault(g.item_id, []).append(g.name)
    for m in mods:
        g = group_by_id[m.group_id]
        by_item.setdefault(g.item_id, {})[(g.name.lower(), m.name.lower())] = m

    out: list[OrderLine] = []
    money: list[tuple[int, int]] = []
    for line in draft.lines:
        item = items.get(line.item_id)
        if item is None:
            raise OrderRejected("unknown_item", f"Item {line.item_id} is not on the menu.")
        if not item.available:
            raise OrderRejected("item_unavailable", f"{item.name} is not available right now.")
        price, cost = item.price_paise, item.food_cost_paise
        chosen: list[OrderModifier] = []
        for dm in line.modifiers:
            m = by_item.get(item.id, {}).get((dm.group.lower(), dm.name.lower()))
            if m is None:
                raise OrderRejected("invalid_modifier", f"{dm.name} is not an option for {item.name}.")
            g = group_by_id[m.group_id]
            price += m.price_delta_paise
            cost += m.cost_delta_paise
            chosen.append(OrderModifier(group=g.name, name=m.name, price_delta=m.price_delta_paise // 100))
        missing = [g for g in required.get(item.id, []) if g.lower() not in {c.group.lower() for c in chosen}]
        if missing:
            raise OrderRejected("missing_choice", f"Choose {', '.join(missing).lower()} for {item.name}.")
        out.append(OrderLine(
            item_id=item.id, name=item.name, qty=line.qty, unit_price=price // 100, modifiers=chosen,
            notes=line.notes.strip(), source=line.source, upsell_rule_id=line.upsell_rule_id,
        ))
        money.append((price, cost))
    return out, money


def _build_payload(order_no: int, draft: DraftOrder, lines: list[OrderLine],
                   money: list[tuple[int, int]], confirmed: datetime) -> OrderPayload:
    subtotal = sum(l.unit_price * l.qty for l in lines)
    discount = max(0, min(draft.discount, subtotal))
    # Offers include combo completions. A combo's saving comes off what the offer added.
    offered = ("upsell", "combo")
    combo_saving = discount if any(l.source == "combo" for l in lines) else 0
    up_rev = max(0, sum(l.unit_price * l.qty for l in lines if l.source in offered) - combo_saving)
    up_margin = sum((p - c) * l.qty for l, (p, c) in zip(lines, money) if l.source in offered) // 100 - combo_saving
    accepted = sum(1 for l in lines if l.source in offered)
    return OrderPayload(
        order_id=f"ORD-{order_no}",
        call_id=draft.call_id,
        channel=draft.channel,
        language=draft.language,
        customer=Customer(name=draft.customer_name, phone=mask_phone(draft.customer_phone),
                          address=draft.customer_address),
        lines=lines,
        subtotal=subtotal,
        discount=discount,
        total=subtotal - discount,
        upsell=UpsellSummary(shown=max(draft.upsell_shown, accepted), accepted=accepted,
                             added_revenue=up_rev, added_margin=up_margin),
        confirmed_at=iso_z(confirmed),
    )


def finalize_order(session: Session, draft: DraftOrder) -> tuple[OrderPayload, str, bool]:
    """Record the order (once per idempotency key) and return (payload, key, already_existed)."""
    key = idempotency_key(draft.call_id, draft.lines)
    existing = session.exec(select(PosOrder).where(PosOrder.idempotency_key == key)).first()
    if existing is not None:
        return OrderPayload.model_validate_json(existing.payload_json), key, True

    lines, money = price_lines(session, draft)
    now = utcnow()
    subtotal_paise = sum(p * l.qty for l, (p, _c) in zip(lines, money))
    discount_paise = max(0, min(draft.discount * 100, subtotal_paise))
    order = Order(ts=now, channel=draft.channel, subtotal_paise=subtotal_paise, discount_paise=discount_paise,
                  total_paise=subtotal_paise - discount_paise, covers=1, daypart=daypart_for(now),
                  customer_name=draft.customer_name)
    session.add(order)
    session.flush()
    payload = _build_payload(order.id, draft, lines, money, now)
    problems = validate_order(payload.to_json_dict())
    if problems:
        session.rollback()
        raise OrderRejected("invalid_order", "The order could not be sent: " + "; ".join(problems),
                            {"errors": problems})
    order.upsell_added_paise = payload.upsell.added_revenue * 100
    session.add(order)
    for l, (p, c) in zip(lines, money):
        session.add(OrderItem(order_id=order.id, item_id=l.item_id, qty=l.qty, unit_price_paise=p,
                              unit_cost_paise=c, modifiers_json=json.dumps([m.model_dump() for m in l.modifiers])))
    session.add(PosOrder(idempotency_key=key, order_id=order.id,
                         payload_json=json.dumps(payload.to_json_dict(), ensure_ascii=False), status="pending"))
    session.commit()
    events_bus.publish("order", {"order_id": payload.order_id, "total": payload.total, "channel": payload.channel})
    return payload, key, False


def push_to_pos(session: Session, adapter: PosAdapter, payload: OrderPayload, key: str,
                sleep: Callable[[float], None] = time.sleep) -> PushResult:
    row = session.exec(select(PosOrder).where(PosOrder.idempotency_key == key)).one()
    if row.status == "acked":
        return PushResult(payload.order_id, "acked", row.attempts, row.kot_no, duplicate=True,
                          events=[{"type": "pos.ack", "order_id": payload.order_id, "kot_no": row.kot_no}])
    events: list[dict] = []
    last_error = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        row.attempts += 1
        session.add(row)
        session.commit()
        try:
            adapter.create_order(payload, key)
            if not any(e["type"] == "pos.sent" for e in events):
                events.append({"type": "pos.sent", "order_id": payload.order_id})
            kot = adapter.create_kot(payload.order_id)
            session.refresh(row)
            events.append({"type": "pos.ack", "order_id": payload.order_id, "kot_no": kot.kot_no})
            events_bus.publish("order.status", {"order_id": payload.order_id, "status": "acked", "kot_no": kot.kot_no})
            return PushResult(payload.order_id, "acked", row.attempts, kot.kot_no, events=events)
        except PosError as exc:
            last_error = exc
            if not exc.retryable:
                break
            if attempt < MAX_ATTEMPTS:
                sleep(BACKOFF_BASE_S * 2 ** (attempt - 1))
    session.refresh(row)
    row.status = "needs_attention"
    row.error = f"{last_error.message} (after {row.attempts} attempts)"
    session.add(row)
    session.commit()
    events.append({"type": "error", "code": last_error.code, "message": row.error})
    events_bus.publish("order.status", {"order_id": payload.order_id, "status": "needs_attention"})
    return PushResult(payload.order_id, "needs_attention", row.attempts, error=row.error, events=events)


def finalize_and_push(session: Session, adapter: PosAdapter, draft: DraftOrder,
                      sleep: Callable[[float], None] = time.sleep) -> tuple[OrderPayload, PushResult]:
    payload, key, existed = finalize_order(session, draft)
    result = push_to_pos(session, adapter, payload, key, sleep=sleep)
    result.duplicate = result.duplicate or existed
    return payload, result


def retry_order(session: Session, adapter: PosAdapter, order_id: int,
                sleep: Callable[[float], None] = time.sleep) -> PushResult:
    row = session.exec(select(PosOrder).where(PosOrder.order_id == order_id)).first()
    if row is None:
        raise OrderRejected("not_found", f"ORD-{order_id} was not sent through Tadka, so there is nothing to retry.")
    payload = OrderPayload.model_validate_json(row.payload_json)
    return push_to_pos(session, adapter, payload, row.idempotency_key, sleep=sleep)
