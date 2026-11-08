"""Restaurant settings kept in the database (`app_settings`), with defaults."""
from __future__ import annotations

import copy
import json
from typing import Any

from sqlmodel import Session, select

from models import AppSetting

DEFAULTS: dict[str, Any] = {
    "restaurant_name": "",  # printed on the ticket header
    "upsell": {
        "enabled": True,
        "max_offers_per_call": 2,
        "daypart_weights": {"breakfast": 1.0, "lunch": 1.0, "snack": 1.0, "dinner": 1.0},
        "slow_prep_minutes": 15,  # suppressed while the kitchen is busy
    },
    "kitchen_busy": False,
    "inventory_signals": True,
    "language_packs": [],  # optional packs: "mr", "gu"
    # voice: "natural" (Piper, offline) or "browser" (speechSynthesis). barge_in: the caller can cut in.
    "speech": {"engine": "offline", "browser_service": False, "voice": "natural", "barge_in": True},
    "combo_pool": None,  # None means "not chosen yet": the top combos are used
    "recording": {"enabled": False},  # call audio is recorded only after the owner turns this on
}

AVAILABLE_PACKS = {"mr": "Marathi", "gu": "Gujarati"}


def _merge(base: dict, patch: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in patch.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _merge(out[k], v)
        else:
            out[k] = v
    return out


def get_all(session: Session) -> dict[str, Any]:
    stored = {r.key: json.loads(r.value_json) for r in session.exec(select(AppSetting))}
    return _merge(DEFAULTS, stored)


def get(session: Session, key: str) -> Any:
    return get_all(session)[key]


def validate(patch: dict) -> list[str]:
    problems = []
    unknown = set(patch) - set(DEFAULTS)
    if unknown:
        problems.append(f"Unknown settings: {', '.join(sorted(unknown))}")
    up = patch.get("upsell", {})
    if "max_offers_per_call" in up and up["max_offers_per_call"] not in (0, 1, 2):
        problems.append("upsell.max_offers_per_call must be 0, 1 or 2")
    for part, w in (up.get("daypart_weights") or {}).items():
        if not isinstance(w, (int, float)) or not 0 <= w <= 2:
            problems.append(f"upsell.daypart_weights.{part} must be between 0 and 2")
    speech = patch.get("speech") or {}
    if speech.get("engine") is not None and speech["engine"] not in ("offline", "typed"):
        problems.append("speech.engine must be offline or typed")
    if speech.get("voice") is not None and speech["voice"] not in ("natural", "browser"):
        problems.append("speech.voice must be natural or browser")
    if speech.get("barge_in") is not None and not isinstance(speech["barge_in"], bool):
        problems.append("speech.barge_in must be true or false")
    if "restaurant_name" in patch and (not isinstance(patch["restaurant_name"], str) or len(patch["restaurant_name"]) > 60):
        problems.append("restaurant_name must be text of 60 characters or fewer")
    for pack in patch.get("language_packs", []) or []:
        if pack not in AVAILABLE_PACKS:
            problems.append(f"Unknown language pack: {pack}")
    return problems


def update(session: Session, patch: dict) -> dict[str, Any]:
    current = get_all(session)
    for key, value in patch.items():
        merged = _merge(current[key], value) if isinstance(value, dict) and isinstance(current[key], dict) else value
        row = session.get(AppSetting, key) or AppSetting(key=key, value_json="null")
        row.value_json = json.dumps(merged)
        session.add(row)
    session.commit()
    return get_all(session)
