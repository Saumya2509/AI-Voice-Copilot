"""Menu-engineering classification per category (file 04, section 2), plain-language reasons,
and the three detection lists.

Popular:     popularity_share >= 0.7 * (1 / n_items_in_category)
High margin: cm >= unit-weighted average cm of the category
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pandas as pd

POPULARITY_FACTOR = 0.7

# Detection assumptions. These are labelled as assumptions wherever they reach the UI.
PROMOTION_GAP_CLOSE = 0.5   # promoting a Puzzle closes half the gap to the popularity line
REMOVAL_SWITCH_RATE = 0.8   # share of a removed item's buyers who switch to another item in the category
FOOD_COST_SHOCK = 0.05      # a 5 percent rise in the item's food cost
PROFIT_LOSS_THRESHOLD = 0.20

CLASS_ACTION = {
    "star": "Protect and feature it. Test a small price rise.",
    "plowhorse": "Raise the price slightly, trim portion cost, or pair it with a high-margin side.",
    "puzzle": "Promote, rename or reposition it, and offer it as an upsell.",
    "dog": "Rework or remove it. Do not promote it.",
}

CATEGORY_NOUN = {
    "starter": "starter", "main": "main", "bread": "bread", "rice": "rice or noodle dish",
    "side": "side", "dessert": "dessert", "beverage": "drink",
}


@dataclass(frozen=True)
class ItemClass:
    item_id: int
    name: str
    category: str
    cm_paise: int
    units: int
    popularity_share: float
    popularity_index: float
    category_avg_cm_paise: float
    popular: bool
    high_margin: bool
    cls: str


def classify_frame(df: pd.DataFrame) -> pd.DataFrame:
    """df needs item_id, name, category, cm_paise, units. Adds class columns per category."""
    if df.empty:
        return df.assign(popularity_share=pd.Series(dtype=float), popularity_index=pd.Series(dtype=float),
                         category_avg_cm_paise=pd.Series(dtype=float), popular=pd.Series(dtype=bool),
                         high_margin=pd.Series(dtype=bool), cls=pd.Series(dtype=str))
    out = []
    for _cat, g in df.groupby("category", sort=False):
        g = g.copy()
        n = len(g)
        total_units = g["units"].sum()
        g["popularity_share"] = g["units"] / total_units if total_units else 0.0
        g["popularity_index"] = g["popularity_share"] * n
        avg_cm = (g["cm_paise"] * g["units"]).sum() / total_units if total_units else g["cm_paise"].mean()
        g["category_avg_cm_paise"] = avg_cm
        g["popular"] = g["popularity_share"] >= POPULARITY_FACTOR / n
        g["high_margin"] = g["cm_paise"] >= avg_cm
        g["cls"] = [
            ("star" if hm else "plowhorse") if pop else ("puzzle" if hm else "dog")
            for pop, hm in zip(g["popular"], g["high_margin"])
        ]
        out.append(g)
    return pd.concat(out).sort_values("item_id") if out else df


def reason(row) -> str:
    noun = CATEGORY_NOUN.get(row["category"], "item")
    cm = int(round(row["cm_paise"] / 100))
    diff = round((row["popularity_index"] - 1) * 100)
    if row["units"] == 0:
        sells = f"has not sold in the last {int(row['window'])} days"
    elif abs(diff) < 3:
        sells = f"sells about as well as an average {noun}"
    elif diff > 0:
        sells = f"sells {diff} percent more than an average {noun}"
    else:
        sells = f"is ordered {-diff} percent less than an average {noun}"
    return f"Earns ₹{cm} per plate and {sells}."


def classify(stats: pd.DataFrame) -> pd.DataFrame:
    """Add class, reason and default action to an item_stats frame."""
    df = classify_frame(stats)
    df["class"] = df["cls"]
    df["reason"] = df.apply(reason, axis=1) if len(df) else pd.Series(dtype=str)
    df["action"] = df["class"].map(CLASS_ACTION)
    return df


# ----- detections ------------------------------------------------------------------


def _monthly(df: pd.DataFrame) -> float:
    return 30 / float(df["window"].iloc[0]) if len(df) else 1.0


def puzzles(df: pd.DataFrame) -> pd.DataFrame:
    """High margin, low selling, ranked by (cm - category avg cm) * expected uplift units."""
    p = df[df["class"] == "puzzle"].copy()
    cat_units = df.groupby("category")["units"].sum()
    line = p["category"].map(cat_units) * POPULARITY_FACTOR / p["n_in_category"]
    p["expected_uplift_units"] = ((line - p["units"]).clip(lower=0) * PROMOTION_GAP_CLOSE).round()
    p["potential_gain_paise"] = ((p["cm_paise"] - p["category_avg_cm_paise"]) * p["expected_uplift_units"]
                                 * _monthly(df)).round()
    return p.sort_values("potential_gain_paise", ascending=False)


def underperformers(df: pd.DataFrame) -> pd.DataFrame:
    """Dogs, plus items whose share of profit is below their share of menu space."""
    if df.empty:
        return df.assign(profit_share=pd.Series(dtype=float), menu_space_share=pd.Series(dtype=float),
                         removal_gain_paise=pd.Series(dtype=float))
    total_profit = df["profit_paise"].sum()
    space = 1 / len(df)
    d = df.copy()
    d["profit_share"] = d["profit_paise"] / total_profit if total_profit else 0.0
    d["menu_space_share"] = space
    d = d[(d["class"] == "dog") | (d["profit_share"] < space * 0.5)].copy()
    # If removed, most buyers switch to another item at the category's average margin.
    d["removal_gain_paise"] = (d["units"] * (REMOVAL_SWITCH_RATE * d["category_avg_cm_paise"] - d["cm_paise"])
                               * _monthly(df)).round()
    return d.sort_values("profit_share")


def plowhorse_risk(df: pd.DataFrame) -> pd.DataFrame:
    """Plowhorses ranked by how much profit a 5 percent food-cost rise would take away."""
    p = df[df["class"] == "plowhorse"].copy()
    p["profit_drop_pct"] = FOOD_COST_SHOCK * p["food_cost_paise"] / p["cm_paise"]
    p["monthly_exposure_paise"] = (FOOD_COST_SHOCK * p["food_cost_paise"] * p["units"] * _monthly(df)).round()
    p["at_risk"] = p["profit_drop_pct"] > PROFIT_LOSS_THRESHOLD
    return p.sort_values("monthly_exposure_paise", ascending=False)


# ----- standalone helper used by the seed tests ---------------------------------


def classify_db(db_path: Path | str, window_days: int = 30) -> list[ItemClass]:
    """Classify every item using the last `window_days` of orders in the database."""
    con = sqlite3.connect(db_path)
    try:
        last_ts = con.execute("SELECT MAX(ts) FROM orders").fetchone()[0]
        items = pd.read_sql_query(
            "SELECT i.id AS item_id, i.name, c.kind AS category, "
            "i.price_paise - i.food_cost_paise AS cm_paise "
            "FROM items i JOIN categories c ON c.id = i.category_id",
            con,
        )
        if last_ts is None:
            units = pd.DataFrame({"item_id": [], "units": []})
        else:
            since = (pd.Timestamp(last_ts) - timedelta(days=window_days)).isoformat(sep=" ")
            units = pd.read_sql_query(
                "SELECT oi.item_id, SUM(oi.qty) AS units FROM order_items oi "
                "JOIN orders o ON o.id = oi.order_id WHERE o.ts > ? GROUP BY oi.item_id",
                con, params=(since,),
            )
    finally:
        con.close()
    df = items.merge(units, on="item_id", how="left").fillna({"units": 0})
    df["units"] = df["units"].astype(int)
    df = classify_frame(df)
    return [
        ItemClass(int(r.item_id), r.name, r.category, int(r.cm_paise), int(r.units),
                  float(r.popularity_share), float(r.popularity_index),
                  float(r.category_avg_cm_paise), bool(r.popular), bool(r.high_margin), r.cls)
        for r in df.itertuples()
    ]
