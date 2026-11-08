"""Price recommendations with a constant-elasticity model (file 04, section 4).

new_units    = units * (1 + dp) ** elasticity
new_profit   = (new_price - cost) * new_units
delta_profit = new_profit - old_profit

Elasticities are assumptions by class unless the item's own price history allows a measurement.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from revenue.data import Dataset

ASSUMED_ELASTICITY = {"star": -0.6, "plowhorse": -0.8, "puzzle": -1.2, "dog": -1.5}
ELASTICITY_BAND = 0.3
MAX_CHANGE = 0.10
ROUND_TO_PAISE = 500  # nearest ₹5
CATEGORY_FLOOR_FACTOR = 0.9  # never push cm_pct below 90 percent of the category's average cm_pct
MIN_DAYS_PER_PRICE = 14
UNGUARDED_CAP = 0.30  # the raw model has no upper limit for inelastic items; shown capped

# Suggested change by class (fraction). Puzzles are promoted first; Dogs are reworked, not repriced.
SUGGESTED_CHANGE = {"star": 0.03, "plowhorse": 0.05, "puzzle": 0.0, "dog": 0.0}
CLASS_ADVICE = {
    "star": "Hold, or test a rise of 2 to 3 percent.",
    "plowhorse": "Raise 3 to 7 percent, or trim portion cost.",
    "puzzle": "Promote and reposition first. Lower the price slightly only if sales stay low.",
    "dog": "Rework or remove rather than reprice.",
}


def predict(units: float, price_paise: int, cost_paise: int, new_price_paise: int, elasticity: float) -> dict:
    """Pure formula. Units and profit for the same period as `units`."""
    dp = new_price_paise / price_paise - 1
    new_units = units * (1 + dp) ** elasticity
    old_profit = (price_paise - cost_paise) * units
    new_profit = (new_price_paise - cost_paise) * new_units
    return {"dp": dp, "new_units": new_units, "old_profit": old_profit, "new_profit": new_profit,
            "delta_profit": new_profit - old_profit}


def round_price(paise: float) -> int:
    return int(round(paise / ROUND_TO_PAISE) * ROUND_TO_PAISE)


def measured_elasticity(data: Dataset, item_id: int) -> float | None:
    """Log-log slope of daily units on base price, when the item sold at two or more prices
    for at least two weeks each. Lines with modifiers are left out so add-ons do not count as price changes."""
    lines = data.lines[(data.lines["item_id"] == item_id) & (data.lines["modifiers_json"].isin(["[]", "", None]))]
    if lines.empty:
        return None
    daily = (lines.assign(day=lines["ts"].dt.normalize())
             .groupby("day").agg(units=("qty", "sum"), price=("unit_price_paise", "median")))
    days_per_price = daily.groupby("price").size()
    if (days_per_price >= MIN_DAYS_PER_PRICE).sum() < 2:
        return None
    daily = daily[daily["price"].isin(days_per_price[days_per_price >= MIN_DAYS_PER_PRICE].index)]
    slope = np.polyfit(np.log(daily["price"]), np.log(daily["units"].clip(lower=0.5)), 1)[0]
    return float(np.clip(slope, -3.0, -0.1))


@dataclass
class PricePreview:
    item_id: int
    price_paise: int
    new_price_paise: int
    elasticity: float
    elasticity_source: str  # Measured | Assumed
    units: float            # monthly
    new_units: float
    profit_paise: float
    new_profit_paise: float
    delta_profit_paise: float
    delta_low_paise: float
    delta_high_paise: float
    cm_pct_after: float
    warnings: list[str]


def preview(row: pd.Series, new_price_paise: int, elasticity: float, source: str,
            category_cm_pct: float, window: int) -> PricePreview:
    monthly_units = float(row["units"]) * 30 / window
    price, cost = int(row["price_paise"]), int(row["food_cost_paise"])
    mid = predict(monthly_units, price, cost, new_price_paise, elasticity)
    lo = predict(monthly_units, price, cost, new_price_paise, elasticity - ELASTICITY_BAND)
    hi = predict(monthly_units, price, cost, new_price_paise, elasticity + ELASTICITY_BAND)
    warnings = []
    if abs(mid["dp"]) > MAX_CHANGE + 1e-9:
        warnings.append("This is more than a 10 percent change. The estimate is less reliable that far out.")
    cm_after = (new_price_paise - cost) / new_price_paise if new_price_paise else 0.0
    if cm_after < CATEGORY_FLOOR_FACTOR * category_cm_pct:
        warnings.append("Margin would fall below the floor for this category.")
    return PricePreview(
        item_id=int(row["item_id"]), price_paise=price, new_price_paise=new_price_paise, elasticity=elasticity,
        elasticity_source=source, units=round(monthly_units, 1), new_units=round(mid["new_units"], 1),
        profit_paise=round(mid["old_profit"]), new_profit_paise=round(mid["new_profit"]),
        delta_profit_paise=round(mid["delta_profit"]),
        delta_low_paise=round(min(lo["delta_profit"], hi["delta_profit"])),
        delta_high_paise=round(max(lo["delta_profit"], hi["delta_profit"])),
        cm_pct_after=round(cm_after, 4), warnings=warnings,
    )


def elasticity_for(data: Dataset, row: pd.Series) -> tuple[float, str]:
    measured = measured_elasticity(data, int(row["item_id"]))
    if measured is not None:
        return measured, "Measured"
    return ASSUMED_ELASTICITY[row["class"]], "Assumed"


def category_cm_pct(classes: pd.DataFrame) -> dict[str, float]:
    g = classes.assign(rev=classes["price_paise"] * classes["units"], cm=classes["cm_paise"] * classes["units"])
    agg = g.groupby("category")[["rev", "cm"]].sum()
    return {c: float(r.cm / r.rev) if r.rev else 0.0 for c, r in agg.iterrows()}


def recommendations(data: Dataset, classes: pd.DataFrame, window: int) -> list[dict]:
    floors = category_cm_pct(classes)
    out = []
    for _, row in classes.iterrows():
        cls = row["class"]
        elasticity, source = elasticity_for(data, row)
        change = SUGGESTED_CHANGE[cls]
        price = int(row["price_paise"])
        cost = int(row["food_cost_paise"])
        target = round_price(price * (1 + max(-MAX_CHANGE, min(MAX_CHANGE, change))))
        # Guardrail: never push margin below the category floor.
        floor = CATEGORY_FLOOR_FACTOR * floors.get(row["category"], 0)
        while target < price and target > cost and (target - cost) / target < floor:
            target += ROUND_TO_PAISE
        p = preview(row, target, elasticity, source, floors.get(row["category"], 0), window)
        action = "raise" if target > price else "lower" if target < price else ("rework" if cls == "dog" else "hold")
        if action == "raise" and p.delta_profit_paise <= 0:
            target, action = price, "hold"
            p = preview(row, price, elasticity, source, floors.get(row["category"], 0), window)
        confidence = "high" if source == "Measured" else ("medium" if row["units"] >= 60 else "low")
        raw_price, raw_note = unguarded_price(price, cost, elasticity)
        raw = preview(row, raw_price, elasticity, source, floors.get(row["category"], 0), window)
        out.append({
            "item_id": int(row["item_id"]), "name": row["name"], "category": row["category"], "class": cls,
            "action": action, "advice": CLASS_ADVICE[cls], "price_paise": price, "suggested_price_paise": target,
            "elasticity": round(elasticity, 2), "elasticity_source": source,
            "elasticity_range": [round(elasticity - ELASTICITY_BAND, 2), round(elasticity + ELASTICITY_BAND, 2)],
            "monthly_units": p.units, "predicted_monthly_units": p.new_units,
            "delta_profit_paise": p.delta_profit_paise,
            "delta_range_paise": [p.delta_low_paise, p.delta_high_paise],
            "confidence": confidence,
            "unguarded_price_paise": raw_price, "unguarded_delta_profit_paise": raw.delta_profit_paise,
            "unguarded_note": raw_note, "guardrail_notes": guardrail_notes(price, raw_price, cost, target, floors.get(
                row["category"], 0), cls),
        })
    out.sort(key=lambda r: r["delta_profit_paise"], reverse=True)
    return out


def unguarded_price(price: int, cost: int, elasticity: float) -> tuple[int, str]:
    """Profit-maximising price under the model with no guardrails. For elastic items (e < -1) this is
    cost * e / (1 + e). Inelastic items have no maximum in this model, so the price is capped."""
    if elasticity < -1:
        best = cost * elasticity / (1 + elasticity)
        capped = min(max(best, price * (1 - UNGUARDED_CAP)), price * (1 + UNGUARDED_CAP))
        note = "Model optimum." if capped == best else "Model optimum is beyond 30 percent; shown capped."
        return int(round(capped / 100) * 100), note
    return int(round(price * (1 + UNGUARDED_CAP) / 100) * 100), (
        "This model keeps rewarding higher prices for this item, which is not realistic; shown capped at 30 percent.")


def guardrail_notes(price: int, raw: int, cost: int, target: int, cat_cm_pct: float, cls: str) -> list[str]:
    notes = []
    if abs(raw / price - 1) > MAX_CHANGE:
        notes.append("Limited to a 10 percent change.")
    if raw < price and (raw - cost) / raw < CATEGORY_FLOOR_FACTOR * cat_cm_pct:
        notes.append("Kept margin above the category floor.")
    if cls == "puzzle" and raw != price:
        notes.append("Puzzles are promoted before they are repriced.")
    if cls == "dog":
        notes.append("Dogs are reworked or removed, not repriced.")
    if target % ROUND_TO_PAISE == 0 and target != price:
        notes.append("Rounded to the nearest ₹5.")
    return notes


__all__ = ["predict", "preview", "recommendations", "round_price", "measured_elasticity",
           "ASSUMED_ELASTICITY"]
