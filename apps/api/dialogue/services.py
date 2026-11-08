"""Side effects for a call: NLU, ranker, persistence and the PoS. The dialogue manager only
talks to this object, which keeps it testable."""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Optional

from sqlmodel import Session, select

import db
import settings
import settings_store
from models import Call, Order, UpsellEvent
from nlu.menu import MenuIndex, load_menu
from nlu.parser import Parser
from pos.mock_pos import MockPosAdapter
from pos.service import DraftOrder, finalize_and_push, daypart_for
from privacy import mask_phones_in_text
from revenue import cache
from revenue.engine import get_engine, rng_for
from revenue.upsell import Offer, Ranker


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class DbServices:
    def __init__(self, db_path: Path | str | None = None, pos_sleep=time.sleep):
        self.db_path = str(db_path or settings.DB_PATH)
        self.engine = get_engine(self.db_path)
        self._pos_sleep = pos_sleep
        self._version = -1
        self._menu: MenuIndex | None = None
        self._parsers: dict[tuple, Parser] = {}
        self._ranker: Ranker | None = None
        self._ranker_at = 0.0
        self._lock = threading.RLock()

    # ----- cached resources ----------------------------------------------------------

    def _check(self) -> None:
        if self._version != cache.version():
            self._menu, self._parsers, self._ranker = None, {}, None
            self._version = cache.version()

    @property
    def menu(self) -> MenuIndex:
        with self._lock:
            self._check()
            if self._menu is None:
                self._menu = load_menu(self.db_path)
            return self._menu

    @property
    def parser(self) -> Parser:
        with self._lock:
            packs = tuple(sorted(self.settings().get("language_packs") or []))
            self._check()
            if packs not in self._parsers:
                self._parsers[packs] = Parser(self.menu, packs)
            return self._parsers[packs]

    def settings(self) -> dict:
        with Session(db.get_engine(self.db_path)) as s:
            return settings_store.get_all(s)

    def ranker(self) -> Ranker:
        """Rebuilt at most every 2 seconds so settings changes (kitchen busy, pool) apply quickly."""
        with self._lock:
            self._check()
            if self._ranker is None or time.monotonic() - self._ranker_at > 2:
                with Session(db.get_engine(self.db_path)) as s:
                    self._ranker = self.engine.ranker(s)
                self._ranker_at = time.monotonic()
            return self._ranker

    def learn(self, rule_id: int, accepted: bool) -> None:
        self.engine.learn(rule_id, accepted)

    def daypart(self) -> str:
        return daypart_for(utcnow())

    def rng_for(self, call_id: str):
        return rng_for(call_id)

    def recommendation(self, exclude: set[int]):
        """When the guest asks what to order with an empty cart: the Puzzle with the most to gain,
        then the best-earning Star."""
        from revenue import classify as cls_mod
        df = self.engine.classes(30)
        ranked = list(cls_mod.puzzles(df)["item_id"]) + list(
            df[df["class"] == "star"].sort_values("profit_paise", ascending=False)["item_id"])
        for item_id in ranked:
            item = self.menu.items.get(int(item_id))
            if item and item.available and item.id not in exclude:
                return item
        return None

    # ----- persistence ---------------------------------------------------------------

    def ensure_call(self, call_id: str, channel: str = "phone") -> None:
        with Session(db.get_engine(self.db_path)) as s:
            if s.get(Call, call_id) is None:
                s.add(Call(id=call_id, started_at=utcnow(), outcome=None))
                s.commit()

    def record_offer(self, call_id: str, offer: Offer) -> Optional[int]:
        self.ensure_call(call_id)
        with Session(db.get_engine(self.db_path)) as s:
            ev = UpsellEvent(call_id=call_id, rule_id=offer.rule_id, item_id=offer.item_id, shown_at=utcnow(),
                             reason_json=json.dumps({**offer.reason, "kind": offer.kind, "combo_id": offer.combo_id,
                                                     "p_accept": offer.p_accept, "score": offer.score},
                                                    ensure_ascii=False))
            s.add(ev)
            s.commit()
            return ev.id

    def record_offer_result(self, event_id: Optional[int], accepted: Optional[bool]) -> None:
        if event_id is None:
            return
        with Session(db.get_engine(self.db_path)) as s:
            ev = s.get(UpsellEvent, event_id)
            if ev:
                ev.accepted = accepted
                s.add(ev)
                s.commit()

    def save_call(self, session) -> None:
        self.ensure_call(session.call_id)
        with Session(db.get_engine(self.db_path)) as s:
            call = s.get(Call, session.call_id)
            call.language = session.language
            call.upsell_shown = session.offers_made
            call.upsell_accepted = session.offers_accepted
            call.outcome = session.outcome
            if session.ended_at and call.ended_at is None:
                call.ended_at = utcnow()
                call.duration_s = round((call.ended_at - call.started_at).total_seconds(), 1)
            if session.order:
                call.order_id = int(session.order["order_id"].removeprefix("ORD-"))
            call.transcript_json = json.dumps(session.transcript, ensure_ascii=False)
            call.events_json = json.dumps([_mask_event(e) for e in session.events], ensure_ascii=False)
            s.add(call)
            s.commit()

    def place(self, draft: DraftOrder):
        adapter = MockPosAdapter(db.get_engine(self.db_path))
        with Session(db.get_engine(self.db_path)) as s:
            return finalize_and_push(s, adapter, draft, sleep=self._pos_sleep)


def _mask_event(ev: dict) -> dict:
    if ev.get("type") == "reply.say":
        return {**ev, "text": mask_phones_in_text(ev["text"])}
    return ev


# ----- call registry -----------------------------------------------------------------

_sessions: dict[str, object] = {}
_reg_lock = threading.Lock()


@lru_cache(maxsize=4)
def services_for(db_path: str) -> DbServices:
    return DbServices(db_path)


def get_session(call_id: str, create: bool = True, db_path: str | None = None):
    from dialogue.manager import CallSession
    with _reg_lock:
        sess = _sessions.get(call_id)
        if sess is None and create:
            svc = services_for(str(db_path or settings.DB_PATH))
            svc.ensure_call(call_id)
            sess = CallSession(call_id, svc)
            _sessions[call_id] = sess
        return sess


def drop_session(call_id: str) -> None:
    with _reg_lock:
        _sessions.pop(call_id, None)


def drop_sessions() -> None:
    with _reg_lock:
        _sessions.clear()
    services_for.cache_clear()
