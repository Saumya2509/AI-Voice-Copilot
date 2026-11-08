"""Call endpoints (file 08): calls, samples, NLU debug, and the live WebSocket."""
from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Optional

import yaml
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, Response
from sqlalchemy import func, or_
from fastapi.concurrency import run_in_threadpool
from pydantic import BaseModel
from sqlmodel import Session, delete, select

import db
import settings
from dialogue import manager as dm
from dialogue.services import drop_session, drop_sessions, get_session, services_for
from models import Call, Item, PosOrder, UpsellEvent, UpsellRule
from nlu.gloss_en import gloss_en
from routes_revenue import ApiError

router = APIRouter(prefix="/api/v1")
ws_router = APIRouter()
_locks: dict[str, asyncio.Lock] = {}
CLIENT_TYPES = {"transcript.partial", "transcript.final", "ui.choice", "ui.offer", "ui.end", "ui.listening",
                "ui.add_combo", "ui.barge_in",
                "ui.add_item", "ui.confirm", "ui.send", "resume"}


def _parse(raw: str) -> dict | None:
    try:
        msg = json.loads(raw)
    except ValueError:
        return None
    return msg if isinstance(msg, dict) else None


class CallBody(BaseModel):
    channel: str = "phone"


@router.post("/calls")
def start_call(body: CallBody | None = None):
    call_id = f"call_{uuid.uuid4().hex[:12]}"
    sess = get_session(call_id)
    sess.channel = (body.channel if body else "phone")
    return {"call_id": call_id, "ws": f"/ws/call/{call_id}"}


RECORDINGS_DIR = settings.DATA_DIR / "recordings"
MAX_RECORDING_BYTES = 60 * 1024 * 1024


def _call_row(c: Call, totals: dict) -> dict:
    t = totals.get(c.order_id, {})
    return {
        "call_id": c.id, "started_at": c.started_at.isoformat() + "Z",
        "ended_at": c.ended_at.isoformat() + "Z" if c.ended_at else None,
        "duration_s": round(c.duration_s if c.duration_s is not None else
                            ((c.ended_at - c.started_at).total_seconds() if c.ended_at else 0), 1),
        "language": c.language, "outcome": c.outcome, "order_id": f"ORD-{c.order_id}" if c.order_id else None,
        "total": t.get("total"), "upsell_added": t.get("added"),
        "upsell_shown": c.upsell_shown, "upsell_accepted": c.upsell_accepted,
        "has_recording": bool(c.recording_path),
    }


@router.get("/calls")
def list_calls(
    limit: int = Query(30, ge=1, le=200),
    q: Optional[str] = Query(None, description="Search call id, order id or transcript text"),
    outcome: Optional[str] = None,
    language: Optional[str] = None,
    has_recording: Optional[bool] = None,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    session: Session = Depends(db.get_session),
):
    from main import local_day_bounds
    stmt = select(Call)
    if outcome:
        stmt = stmt.where(Call.outcome == outcome)
    if language:
        stmt = stmt.where(Call.language == language)
    if has_recording is True:
        stmt = stmt.where(Call.recording_path.is_not(None))
    elif has_recording is False:
        stmt = stmt.where(Call.recording_path.is_(None))
    if date_from:
        stmt = stmt.where(Call.started_at >= local_day_bounds(date_from))
    if date_to:
        stmt = stmt.where(Call.started_at < local_day_bounds(date_to, end=True))
    if q and q.strip():
        like = f"%{q.strip().lower()}%"
        digits = q.strip().upper().removeprefix("ORD-")
        conds = [func.lower(Call.id).like(like), func.lower(Call.transcript_json).like(like)]
        if digits.isdigit():
            conds.append(Call.order_id == int(digits))
        stmt = stmt.where(or_(*conds))
    calls = session.exec(stmt.order_by(Call.started_at.desc()).limit(limit)).all()
    totals = _order_totals(session, [c.order_id for c in calls if c.order_id])
    return {"calls": [_call_row(c, totals) for c in calls]}


@router.get("/calls/{call_id}/transcript")
def call_transcript(call_id: str, lang: str = Query("en", pattern="^(en|original)$"),
                    session: Session = Depends(db.get_session)):
    """Transcript lines with seconds from the start of the call. English by default."""
    call = session.get(Call, call_id)
    if call is None:
        raise ApiError(404, "not_found", f"There is no call {call_id}.")
    start = call.started_at.replace(tzinfo=timezone.utc)
    lines, interrupted = [], []
    for ln in json.loads(call.transcript_json or "[]"):
        t = datetime.fromisoformat(ln["t"].replace("Z", "+00:00"))
        english = ln.get("display_text_en") or ln.get("text", "")
        original = ln.get("original_text") or ln.get("text", "")
        at_s = round(max(0.0, (t - start).total_seconds()), 2)
        lines.append({"at_s": at_s, "speaker": ln["speaker"],
                      "text": english if lang == "en" else original, "display_text_en": english,
                      "original_text": original, "lang": ln.get("lang"), "parts": ln.get("parts"),
                      "interrupted": bool(ln.get("interrupted"))})
        if ln.get("interrupted"):
            interrupted.append({"at_s": at_s, "kind": "interrupted", "label": "Caller cut in"})
    markers = interrupted
    for e in json.loads(call.events_json or "[]"):
        at = round(max(0.0, (datetime.fromisoformat(e["ts"].replace("Z", "+00:00")) - start).total_seconds()), 2)
        if e["type"] == "clarify.ask":
            markers.append({"at_s": at, "kind": "clarify", "label": e.get("question_en") or e.get("question")})
        elif e["type"] == "upsell.offer":
            markers.append({"at_s": at, "kind": "offer", "label": e["item"]["name"], "item_id": e["item"]["id"]})
        elif e["type"] == "menu.highlight":
            markers.append({"at_s": at, "kind": "item", "item_id": e["item_id"]})
        elif e["type"] == "pos.ack":
            markers.append({"at_s": at, "kind": "sent", "label": e["kot_no"]})
    return {"call_id": call_id, "lang": lang, "lines": lines, "markers": sorted(markers, key=lambda m: m["at_s"]),
            "has_recording": bool(call.recording_path)}


@router.post("/calls/{call_id}/recording")
async def upload_recording(call_id: str, file: UploadFile = File(...), duration_s: Optional[float] = Form(None),
                           session: Session = Depends(db.get_session)):
    """Store the call audio recorded in the browser (only when recording is on in Settings)."""
    from settings_store import get_all
    if not get_all(session)["recording"]["enabled"]:
        raise ApiError(403, "recording_off", "Call recording is off. Turn it on in Settings first.")
    call = session.get(Call, call_id)
    if call is None:
        raise ApiError(404, "not_found", f"There is no call {call_id}.")
    data = await file.read()
    if not data:
        raise ApiError(422, "empty_recording", "The recording was empty.")
    if len(data) > MAX_RECORDING_BYTES:
        raise ApiError(413, "recording_too_large", "The recording is larger than 60 MB.")
    ext = {"audio/webm": "webm", "audio/ogg": "ogg", "audio/mp4": "m4a", "audio/wav": "wav"}.get(
        (file.content_type or "").split(";")[0], "webm")
    RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
    name = f"{call_id}.{ext}"
    (RECORDINGS_DIR / name).write_bytes(data)
    call.recording_path, call.recording_bytes = name, len(data)
    if duration_s:
        call.duration_s = float(duration_s)
    session.add(call)
    session.commit()
    return {"call_id": call_id, "bytes": len(data), "has_recording": True}


@router.get("/calls/{call_id}/recording")
def get_recording(call_id: str, session: Session = Depends(db.get_session)):
    call = session.get(Call, call_id)
    if call is None or not call.recording_path or not (RECORDINGS_DIR / call.recording_path).exists():
        raise ApiError(404, "not_found", "This call has no recording.")
    path = RECORDINGS_DIR / call.recording_path
    media = {"webm": "audio/webm", "ogg": "audio/ogg", "m4a": "audio/mp4", "wav": "audio/wav"}[path.suffix[1:]]
    return FileResponse(path, media_type=media)


@router.delete("/calls/{call_id}/recording")
def delete_recording(call_id: str, session: Session = Depends(db.get_session)):
    call = session.get(Call, call_id)
    if call is None:
        raise ApiError(404, "not_found", f"There is no call {call_id}.")
    if call.recording_path:
        (RECORDINGS_DIR / call.recording_path).unlink(missing_ok=True)
    call.recording_path = call.recording_bytes = None
    session.add(call)
    session.commit()
    return {"call_id": call_id, "has_recording": False}


@router.delete("/calls/{call_id}")
def delete_call(call_id: str, session: Session = Depends(db.get_session)):
    call = session.get(Call, call_id)
    if call is None:
        raise ApiError(404, "not_found", f"There is no call {call_id}.")
    if call.recording_path:
        (RECORDINGS_DIR / call.recording_path).unlink(missing_ok=True)
    session.exec(delete(UpsellEvent).where(UpsellEvent.call_id == call_id))
    session.delete(call)
    session.commit()
    drop_session(call_id)
    return {"deleted": call_id}


def _order_totals(session: Session, order_ids: list[int]) -> dict[int, dict]:
    if not order_ids:
        return {}
    rows = session.exec(select(PosOrder).where(PosOrder.order_id.in_(order_ids))).all()
    out = {}
    for r in rows:
        p = json.loads(r.payload_json or "{}")
        out[r.order_id] = {"total": p.get("total"), "added": (p.get("upsell") or {}).get("added_revenue", 0),
                           "margin": (p.get("upsell") or {}).get("added_margin", 0)}
    return out


@router.get("/insights")
def insights(session: Session = Depends(db.get_session)):
    """Upsell results from calls handled by Tadka: AOV with and without the accepted offers,
    offer acceptance by hour, and the offers that work best (from the bandit's counts)."""
    from zoneinfo import ZoneInfo
    calls = session.exec(select(Call).where(Call.order_id.is_not(None))).all()
    totals = _order_totals(session, [c.order_id for c in calls])
    vals = [t for t in totals.values() if t["total"] is not None]
    n = len(vals)
    with_up = sum(t["total"] for t in vals) / n if n else None
    without = sum(t["total"] - (t["added"] or 0) for t in vals) / n if n else None
    tz = ZoneInfo(settings.RESTAURANT_TZ)
    events = session.exec(select(UpsellEvent)).all()
    by_hour: dict[int, dict] = {}
    by_offer: dict[tuple, dict] = {}
    names = {i.id: i.name for i in session.exec(select(Item))}
    rules = {r.id: r for r in session.exec(select(UpsellRule))}
    for e in events:
        h = e.shown_at.replace(tzinfo=timezone.utc).astimezone(tz).hour
        slot = by_hour.setdefault(h, {"hour": h, "shown": 0, "accepted": 0})
        slot["shown"] += 1
        slot["accepted"] += 1 if e.accepted else 0
        rule = rules.get(e.rule_id)
        key = (e.rule_id, e.item_id)
        o = by_offer.setdefault(key, {
            "rule_id": e.rule_id, "offer_item": names.get(e.item_id),
            "anchor_item": names.get(rule.anchor_item_id) if rule else None,
            "kind": "rule" if rule else "combo", "shown": 0, "accepted": 0,
            "alpha": round(rule.alpha, 2) if rule else None, "beta": round(rule.beta, 2) if rule else None,
        })
        o["shown"] += 1
        o["accepted"] += 1 if e.accepted else 0
    top = sorted(by_offer.values(), key=lambda o: (-o["accepted"], -o["shown"]))[:10]
    for o in top:
        o["accept_rate"] = round(o["accepted"] / o["shown"], 3) if o["shown"] else 0
        o["expected_rate"] = round(o["alpha"] / (o["alpha"] + o["beta"]), 3) if o["alpha"] else None
    return {
        # Insights cover every call Tadka has handled; sample_size is the number of phone orders.
        "window": None, "sample_size": n,
        "calls_with_orders": n, "offers_shown": len(events),
        "offers_accepted": sum(1 for e in events if e.accepted),
        "aov_with_upsell": round(with_up) if with_up is not None else None,
        "aov_without_upsell": round(without) if without is not None else None,
        "added_revenue": sum(t["added"] or 0 for t in vals), "added_margin": sum(t["margin"] or 0 for t in vals),
        "by_hour": [by_hour[h] for h in sorted(by_hour)], "top_offers": top,
    }


@router.get("/calls/{call_id}")
def get_call(call_id: str, session: Session = Depends(db.get_session)):
    call = session.get(Call, call_id)
    if call is None:
        raise ApiError(404, "not_found", f"There is no call {call_id}.")
    offers = session.exec(select(UpsellEvent).where(UpsellEvent.call_id == call_id).order_by(UpsellEvent.id)).all()
    live = get_session(call_id, create=False)
    return {
        "call_id": call.id, "started_at": call.started_at.isoformat() + "Z",
        "ended_at": call.ended_at.isoformat() + "Z" if call.ended_at else None, "language": call.language,
        "outcome": call.outcome, "order_id": f"ORD-{call.order_id}" if call.order_id else None,
        "upsell_shown": call.upsell_shown, "upsell_accepted": call.upsell_accepted,
        "transcript": json.loads(call.transcript_json or "[]"), "events": json.loads(call.events_json or "[]"),
        "offers": [{"item_id": o.item_id, "rule_id": o.rule_id, "shown_at": o.shown_at.isoformat() + "Z",
                    "accepted": o.accepted, "reason": json.loads(o.reason_json or "{}")} for o in offers],
        "live": live.snapshot() if live else None,
    }


@router.delete("/calls")
def delete_calls(session: Session = Depends(db.get_session)):
    n = len(session.exec(select(Call.id)).all())
    for path in session.exec(select(Call.recording_path).where(Call.recording_path.is_not(None))).all():
        (RECORDINGS_DIR / path).unlink(missing_ok=True)
    session.exec(delete(UpsellEvent))
    session.exec(delete(Call))
    session.commit()
    drop_sessions()
    return {"deleted": n}


@router.get("/samples")
def samples():
    out = []
    for path in sorted(settings.SAMPLES_DIR.glob("*.yaml")):
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
        out.append({k: data.get(k) for k in ("id", "title", "description", "language", "utterances")})
    return {"samples": out}


class ParseBody(BaseModel):
    text: str
    cart_item_ids: list[int] = []


@router.post("/nlu/parse")
def nlu_parse(body: ParseBody):
    svc = services_for(str(settings.DB_PATH))
    p = svc.parser.parse(body.text, set(body.cart_item_ids), None, svc.daypart())
    ev = p.to_event()
    ev.update({"normalized": p.normalized.text, "clean": p.normalized.clean,
               "intent_source": p.intent_source, "intent_confidence": round(p.intent_confidence, 3),
               "loose_modifiers": [{"kind": k, "value": v} for k, v in p.loose_modifiers],
               "phone": None if not p.phone else p.phone[:2] + "X" * (len(p.phone) - 4) + p.phone[-2:],
               "name": p.name, "display_text_en": gloss_en(p, svc.menu).text})
    return ev


@router.get("/tts/status")
def tts_status():
    """Which natural offline voices are installed. Without them the Call desk uses the browser's voice."""
    from tts import get_tts

    voices = get_tts().available()
    return {"available": any(voices.values()), "voices": voices}


@router.get("/tts")
def tts(text: str = Query(..., min_length=1, max_length=400), lang: str = Query("en", pattern="^(en|hi)$")):
    """The agent's reply as speech (WAV), made on this machine by the Piper voice for `lang`."""
    from tts import get_tts

    engine = get_tts()
    if not engine.available().get(lang):
        raise ApiError(503, "voice_not_installed",
                       "The natural voice is not installed. Run python tasks.py models, or use the browser voice.")
    from tts import NothingToSay

    try:
        audio = engine.wav(text, lang)
    except NothingToSay:
        raise ApiError(422, "nothing_to_say", "There is nothing to speak in that text.")
    return Response(audio, media_type="audio/wav", headers={"Cache-Control": "private, max-age=86400"})


@router.get("/nlu/vocabulary")
def nlu_vocabulary(lang: str = Query("en", pattern="^(en|hi)$")):
    """Ordering phrases for the offline recogniser's menu-biased pass: Latin for the English model (en),
    Devanagari for the Hindi model (hi). Built from the menu and the lexicon, so it follows menu edits."""
    from nlu.vocabulary import vocabulary

    svc = services_for(str(settings.DB_PATH))
    parser = svc.parser
    phrases = vocabulary(svc.menu, parser.lex, "devanagari" if lang == "hi" else "latin")
    return {"lang": lang, "count": len(phrases), "phrases": phrases}


@ws_router.websocket("/ws/call/{call_id}")
async def call_socket(ws: WebSocket, call_id: str):
    """Client messages: transcript.partial, transcript.final, ui.choice, ui.offer, ui.end,
    ui.listening (assistant finished speaking; restarts the silence timer) and resume {last_seq}."""
    await ws.accept()
    sess = await run_in_threadpool(get_session, call_id)
    lock = _locks.setdefault(call_id, asyncio.Lock())

    async def send(events):
        for ev in events:
            await ws.send_json(ev)

    if not sess.events:
        async with lock:
            await send(await run_in_threadpool(sess.start))
    last_activity = time.monotonic()
    try:
        while True:
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=1.0)
            except asyncio.TimeoutError:
                silent = time.monotonic() - last_activity
                if silent >= dm.REPROMPT_AFTER_S:
                    async with lock:
                        await send(await run_in_threadpool(sess.tick, silent))
                continue
            msg = _parse(raw)
            if msg is None or msg.get("type") not in CLIENT_TYPES:
                async with lock:
                    what = "not JSON" if msg is None else f"an unknown type: {msg.get('type')!r}"
                    await send(sess.error("bad_message", f"The message was {what}. Send one of: "
                                          + ", ".join(sorted(CLIENT_TYPES)) + "."))
                continue
            kind = msg.get("type")
            if kind == "resume":
                await send(sess.since(int(msg.get("last_seq") or 0)))
                continue
            last_activity = time.monotonic()
            if kind in ("transcript.partial", "ui.listening"):
                continue
            async with lock:
                await send(await run_in_threadpool(sess.handle, msg))
    except WebSocketDisconnect:
        return
