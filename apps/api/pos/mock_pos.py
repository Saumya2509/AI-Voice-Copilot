"""Built-in PoS. Stores to the `pos_orders` table, assigns KOT numbers, and simulates network
latency and a configurable failure rate so retry handling can be exercised."""
from __future__ import annotations

import json
import random
import time
from collections.abc import Callable
from datetime import datetime, timezone

from sqlmodel import Session, func, select

import settings
from models import Item, PosOrder
from pos.adapter import KotAck, PosAck, PosError, PosMenuItem, PosStatus
from pos.kot import build_kot
from schemas import Kot, OrderPayload

KOT_START = 2001


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso_z(dt: datetime) -> str:
    return dt.replace(microsecond=0).isoformat() + "Z"


def order_number(order_id: str) -> int:
    return int(order_id.removeprefix("ORD-"))


class MockPosAdapter:
    def __init__(
        self,
        engine,
        failure_rate: float | None = None,
        latency_ms: tuple[int, int] | None = None,
        rng: random.Random | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.engine = engine
        self.failure_rate = settings.POS_FAILURE_RATE if failure_rate is None else failure_rate
        self.latency_ms = latency_ms or (settings.POS_MIN_LATENCY_MS, settings.POS_MAX_LATENCY_MS)
        self.rng = rng or random.Random()
        self.sleep = sleep

    def _network(self) -> None:
        lo, hi = self.latency_ms
        if hi > 0:
            self.sleep(self.rng.uniform(lo, hi) / 1000)
        if self.rng.random() < self.failure_rate:
            raise PosError("pos_unreachable", "The PoS did not respond. Tadka will try again.")

    def get_menu(self) -> list[PosMenuItem]:
        with Session(self.engine) as s:
            return [
                PosMenuItem(str(i.id), i.name, i.price_paise // 100, i.available)
                for i in s.exec(select(Item).order_by(Item.id))
            ]

    def create_order(self, order: OrderPayload, idempotency_key: str) -> PosAck:
        with Session(self.engine) as s:
            existing = s.exec(select(PosOrder).where(PosOrder.idempotency_key == idempotency_key)).first()
            if existing and existing.status in ("sent", "acked"):
                return PosAck(order.order_id, existing.status, duplicate=True)
        self._network()
        with Session(self.engine) as s:
            row = s.exec(select(PosOrder).where(PosOrder.idempotency_key == idempotency_key)).first()
            if row is None:
                row = PosOrder(idempotency_key=idempotency_key, payload_json="{}")
            row.order_id = order_number(order.order_id)
            row.payload_json = json.dumps(order.to_json_dict(), ensure_ascii=False)
            row.status = "sent"
            row.sent_at = utcnow()
            row.error = None
            s.add(row)
            s.commit()
        return PosAck(order.order_id, "sent")

    def create_kot(self, order_id: str) -> KotAck:
        oid = order_number(order_id)
        with Session(self.engine) as s:
            row = s.exec(select(PosOrder).where(PosOrder.order_id == oid)).first()
            if row is None or row.status not in ("sent", "acked", "needs_attention", "failed"):
                raise PosError("unknown_order", f"The PoS has no order {order_id}.", retryable=False)
            if row.kot_no and row.kot_json:
                return KotAck(row.kot_no, Kot.model_validate_json(row.kot_json), duplicate=True)
        self._network()
        with Session(self.engine) as s:
            row = s.exec(select(PosOrder).where(PosOrder.order_id == oid)).one()
            issued = s.exec(select(func.count()).select_from(PosOrder).where(PosOrder.kot_no.is_not(None))).one()
            kot_no = f"K-{KOT_START + issued}"
            payload = OrderPayload.model_validate_json(row.payload_json)
            ids = [l.item_id for l in payload.lines]
            stations = {i.id: i.station for i in s.exec(select(Item).where(Item.id.in_(ids)))}
            now = utcnow()
            kot = build_kot(payload, stations, kot_no, iso_z(now))
            row.kot_no = kot_no
            row.kot_json = json.dumps(kot.to_json_dict(), ensure_ascii=False)
            row.status = "acked"
            row.ack_at = now
            row.error = None
            s.add(row)
            s.commit()
        return KotAck(kot_no, kot)

    def get_order_status(self, pos_order_id: str) -> PosStatus:
        with Session(self.engine) as s:
            row = s.exec(select(PosOrder).where(PosOrder.order_id == order_number(pos_order_id))).first()
            if row is None:
                raise PosError("unknown_order", f"The PoS has no order {pos_order_id}.", retryable=False)
            return PosStatus(pos_order_id, row.status, row.kot_no, row.error, row.attempts)
