"""Revenue endpoints (file 08): stats, lists, combos, pricing, settings."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlmodel import Session

import db
import settings_store
from money import rupees
from models import Item, PriceChange
from revenue import cache, classify as cls_mod, pricing as pricing_mod
from revenue.engine import get_engine

router = APIRouter(prefix="/api/v1")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


r = rupees  # paise -> whole rupees (int) or a two-decimal string


def _window(window: int) -> int:
    if window not in (7, 14, 30, 60, 90):
        raise ApiError(422, "invalid_window", "window must be one of 7, 14, 30, 60 or 90 days.")
    return window


def item_stat(row) -> dict:
    return {
        "item_id": int(row["item_id"]), "name": row["name"], "category": row["category"],
        "price": r(row["price_paise"]), "food_cost": r(row["food_cost_paise"]), "cm": r(row["cm_paise"]),
        "cm_pct": round(float(row["cm_pct"]), 4), "units": int(row["units"]), "velocity": float(row["velocity"]),
        "popularity_share": round(float(row["popularity_share"]), 4),
        "popularity_index": round(float(row["popularity_index"]), 2), "attach_rate": round(float(row["attach_rate"]), 4),
        "revenue": r(row["revenue_paise"]), "profit": r(row["profit_paise"]),
        "category_avg_cm": r(row["category_avg_cm_paise"]), "class": row["class"], "reason": row["reason"],
        "action": row["action"], "trend": row["trend"], "available": bool(row["available"]), "veg": bool(row["veg"]),
        "window": int(row["window"]), "sample_size": int(row["sample_size"]),
    }


@router.get("/stats/items")
def stats_items(window: int = 30, category: Optional[str] = None):
    eng = get_engine()
    df = eng.classes(_window(window))
    if category:
        df = df[df["category"] == category]
    meta = eng.summary(window)
    el = {x["item_id"]: x for x in eng.pricing(window)}
    items = []
    for _, x in df.iterrows():
        out = item_stat(x)
        rec = el.get(out["item_id"])
        if rec:
            out.update(elasticity=rec["elasticity"], elasticity_source=rec["elasticity_source"],
                       elasticity_range=rec["elasticity_range"])
        out["n_in_category"] = int(x["n_in_category"])
        items.append(out)
    return {"window": window, "sample_size": meta["sample_size"],
            "popularity_factor": cls_mod.POPULARITY_FACTOR, "items": items}


@router.get("/stats/items/{item_id}/trend")
def item_trend(item_id: int, weeks: int = Query(12, ge=2, le=13)):
    series = get_engine().weekly_units(item_id, weeks)
    if not series:
        raise ApiError(404, "not_found", f"There is no sales history for item {item_id}.")
    return {"item_id": item_id, "weeks": weeks, "window": weeks * 7,
            "sample_size": sum(w["units"] for w in series), "series": series}


@router.get("/stats/summary")
def stats_summary(window: int = 30):
    s = get_engine().summary(_window(window))
    return {
        "window": s["window"], "sample_size": s["sample_size"], "aov": r(s["aov_paise"]),
        "revenue": r(s["revenue_paise"]), "profit": r(s["profit_paise"]), "orders_per_day": s["orders_per_day"],
        "class_counts": s["class_counts"], "plowhorse_risk_count": s["plowhorse_risk_count"],
        "upside": {"monthly": r(s["upside"]["monthly_paise"]), "from_pricing": r(s["upside"]["from_pricing_paise"]),
                   "from_promoting_puzzles": r(s["upside"]["from_promoting_puzzles_paise"]),
                   "basis": s["upside"]["basis"]},
    }


LIST_ASSUMPTIONS = {
    "puzzles": f"Assumes promotion closes {int(cls_mod.PROMOTION_GAP_CLOSE * 100)} percent of the gap to the "
               "popularity line.",
    "underperformers": f"Assumes {int(cls_mod.REMOVAL_SWITCH_RATE * 100)} percent of buyers switch to another item "
                       "in the same category at its average margin.",
    "plowhorse_risk": f"Tests a {int(cls_mod.FOOD_COST_SHOCK * 100)} percent rise in food cost. At risk means it "
                      f"would remove more than {int(cls_mod.PROFIT_LOSS_THRESHOLD * 100)} percent of the item's profit.",
}


@router.get("/stats/lists/{kind}")
def stats_list(kind: str, window: int = 30):
    df = get_engine().classes(_window(window))
    sample = int(df["sample_size"].iloc[0]) if len(df) else 0
    if kind == "puzzles":
        rows = [{**item_stat(x), "expected_uplift_units": int(x["expected_uplift_units"]),
                 "potential_monthly_gain": r(x["potential_gain_paise"])} for _, x in cls_mod.puzzles(df).iterrows()]
    elif kind == "underperformers":
        rows = [{**item_stat(x), "profit_share": round(float(x["profit_share"]), 4),
                 "menu_space_share": round(float(x["menu_space_share"]), 4),
                 "monthly_gain_if_removed": r(x["removal_gain_paise"])}
                for _, x in cls_mod.underperformers(df).iterrows()]
    elif kind == "plowhorse_risk":
        rows = [{**item_stat(x), "profit_drop_pct": round(float(x["profit_drop_pct"]), 4),
                 "monthly_exposure": r(x["monthly_exposure_paise"]), "at_risk": bool(x["at_risk"])}
                for _, x in cls_mod.plowhorse_risk(df).iterrows()]
    else:
        raise ApiError(404, "not_found", "List must be puzzles, underperformers or plowhorse_risk.")
    return {"kind": kind, "window": window, "sample_size": sample, "assumption": LIST_ASSUMPTIONS[kind], "items": rows}


# ----- combos ------------------------------------------------------------------------


def _pool_ids(session: Session) -> list[str]:
    chosen = settings_store.get(session, "combo_pool")
    if chosen is None:
        return [c.id for c in get_engine().combos(30)[0][: 3]]
    return list(chosen)


@router.get("/combos")
def combos(window: int = 30, limit: int = Query(30, ge=1, le=200), session: Session = Depends(db.get_session)):
    items, meta = get_engine().combos(_window(window))
    pool = set(_pool_ids(session))
    df = get_engine().classes(30)
    info = df.set_index("item_id") if len(df) else None
    cat = {int(r.item_id): r.category_name for r in get_engine().data().items.itertuples()}
    return {
        **meta,
        "combos": [{
            "id": c.id, "items": [{"id": i, "name": n, "category": cat.get(i)} for i, n in zip(c.item_ids, c.names)],
            "added_margin": r(added_margin(c, info)),
            "pitch_hinglish": pitch_hinglish(c.names, r(c.price_paise)),
            "pitch_hi": pitch_hi(c.names, r(c.price_paise)),
            "anchor_item_ids": c.anchor_ids, "bundle_price": r(c.price_paise), "list_price": r(c.list_price_paise),
            "discount_pct": c.discount_pct, "cm": r(c.cm_paise), "cm_pct": c.cm_pct,
            "support": c.support, "confidence": c.confidence, "lift": c.lift, "score": c.score,
            "aov_change_per_order": r(c.aov_change_paise), "margin_change_per_order": r(c.margin_change_paise),
            "evidence": c.evidence, "classes": c.classes, "in_pool": c.id in pool,
            "pitch": pitch(c.names, r(c.price_paise)),
        } for c in items[:limit]],
    }


def added_margin(c, info) -> int:
    """Margin the rest of the combo adds when a guest already wants the anchor: the other items'
    margin minus the bundle discount (paise)."""
    if info is None:
        return 0
    others = [i for i in c.item_ids if i not in c.anchor_ids]
    return int(sum(int(info.at[i, "cm_paise"]) for i in others if i in info.index) - (c.list_price_paise - c.price_paise))


def _and(names: list[str], word: str) -> str:
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" {word} " + names[-1]


def pitch_hinglish(names: list[str], price) -> str:
    return f"{_and(names, 'aur')} ka combo sirf ₹{price} mein"


def pitch_hi(names: list[str], price) -> str:
    return f"{_and(names, 'और')} का कॉम्बो सिर्फ़ ₹{price} में"


def pitch(names: list[str], price) -> str:
    """How the combo sounds in a call: "Dal Makhani with Butter Naan and Jeera Rice for ₹499"."""
    rest = names[1:]
    tail = " and ".join([", ".join(rest[:-1]), rest[-1]] if len(rest) > 1 else rest)
    return f"{names[0]} with {tail} for ₹{price}" if rest else f"{names[0]} for ₹{price}"


@router.get("/combos/graph")
def combo_graph(window: int = 30):
    return get_engine().graph(_window(window))


class PoolBody(BaseModel):
    in_pool: bool = True


@router.post("/combos/{combo_id}/pool")
def combo_pool(combo_id: str, body: PoolBody, session: Session = Depends(db.get_session)):
    known = {c.id for c in get_engine().combos(30)[0]} | {c.id for c in get_engine().combos(90)[0]}
    if combo_id not in known:
        raise ApiError(404, "not_found", f"There is no combo {combo_id}.")
    pool = [c for c in _pool_ids(session) if c != combo_id]
    if body.in_pool:
        pool.append(combo_id)
    settings_store.update(session, {"combo_pool": pool})
    return {"combo_id": combo_id, "in_pool": body.in_pool, "pool": pool}


# ----- pricing -----------------------------------------------------------------------


def _rec_out(x: dict) -> dict:
    return {
        "item_id": x["item_id"], "name": x["name"], "category": x["category"], "class": x["class"],
        "action": x["action"], "advice": x["advice"], "price": r(x["price_paise"]),
        "suggested_price": r(x["suggested_price_paise"]), "elasticity": x["elasticity"],
        "elasticity_source": x["elasticity_source"], "elasticity_range": x["elasticity_range"],
        "monthly_units": x["monthly_units"], "predicted_monthly_units": x["predicted_monthly_units"],
        "monthly_profit_change": r(x["delta_profit_paise"]),
        "monthly_profit_change_range": [r(v) for v in x["delta_range_paise"]], "confidence": x["confidence"],
        "unguarded_price": r(x["unguarded_price_paise"]),
        "unguarded_monthly_profit_change": r(x["unguarded_delta_profit_paise"]),
        "unguarded_note": x["unguarded_note"], "guardrail_notes": x["guardrail_notes"],
    }


@router.get("/pricing/recommendations")
def pricing_recommendations(window: int = 30):
    recs = get_engine().pricing(_window(window))
    meta = get_engine().summary(window)
    return {"window": window, "sample_size": meta["sample_size"],
            "note": "Elasticities marked Assumed are defaults by class, not measured from your sales.",
            "recommendations": [_rec_out(x) for x in recs]}


class PriceBody(BaseModel):
    item_id: int
    new_price: float = Field(gt=0)
    window: int = 30


def _preview(body: PriceBody):
    eng = get_engine()
    df = eng.classes(_window(body.window))
    rows = df[df["item_id"] == body.item_id]
    if rows.empty:
        raise ApiError(404, "not_found", f"There is no item {body.item_id}.")
    row = rows.iloc[0]
    elasticity, source = pricing_mod.elasticity_for(eng.data(), row)
    floors = pricing_mod.category_cm_pct(df)
    new_paise = int(round(body.new_price * 100))
    return row, pricing_mod.preview(row, new_paise, elasticity, source, floors.get(row["category"], 0), body.window)


@router.post("/pricing/preview")
def pricing_preview(body: PriceBody):
    row, p = _preview(body)
    return {
        "item_id": p.item_id, "name": row["name"], "price": r(p.price_paise), "new_price": r(p.new_price_paise),
        "food_cost": r(row["food_cost_paise"]), "elasticity": round(p.elasticity, 3),
        "elasticity_source": p.elasticity_source,
        "monthly_units": p.units, "predicted_monthly_units": p.new_units,
        "monthly_profit": r(p.profit_paise), "predicted_monthly_profit": r(p.new_profit_paise),
        "monthly_profit_change": r(p.delta_profit_paise),
        "monthly_profit_change_range": [r(p.delta_low_paise), r(p.delta_high_paise)],
        "cm_pct_after": p.cm_pct_after, "warnings": p.warnings,
        "formula": "new_units = units * (new_price / price) ** elasticity; profit = (price - food_cost) * units",
        "window": body.window, "sample_size": int(row["sample_size"]),
    }


@router.post("/pricing/apply")
def pricing_apply(body: PriceBody, session: Session = Depends(db.get_session)):
    _row, p = _preview(body)
    item = session.get(Item, body.item_id)
    old = item.price_paise
    new = int(round(body.new_price * 100))
    if new <= item.food_cost_paise:
        raise ApiError(422, "price_below_cost", "The new price must be higher than the food cost.")
    item.price_paise = new
    session.add(item)
    session.add(PriceChange(item_id=item.id, old_price_paise=old, new_price_paise=new,
                            applied_at=datetime.now(timezone.utc).replace(tzinfo=None)))
    session.commit()
    cache.invalidate()
    return {"item_id": item.id, "name": item.name, "old_price": r(old), "new_price": r(new),
            "predicted_monthly_profit_change": r(p.delta_profit_paise), "warnings": p.warnings}


# ----- settings ----------------------------------------------------------------------


@router.get("/settings")
def get_settings(session: Session = Depends(db.get_session)):
    conf = settings_store.get_all(session)
    sig = get_engine().signals(session)
    return {**conf, "available_packs": [{"code": k, "label": v} for k, v in settings_store.AVAILABLE_PACKS.items()],
            "active_signals": sig.active}


@router.put("/settings")
def put_settings(patch: dict, session: Session = Depends(db.get_session)):
    problems = settings_store.validate(patch)
    if problems:
        raise ApiError(422, "invalid_settings", "; ".join(problems), {"errors": problems})
    settings_store.update(session, patch)
    return get_settings(session)
