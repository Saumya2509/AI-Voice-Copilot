"""Item statistics over a rolling window (file 04, section 1). Computed per category."""
from __future__ import annotations

from datetime import timedelta

import numpy as np
import pandas as pd

from revenue.data import Dataset

VELOCITY_HALF_LIFE_DAYS = 10
TREND_WEEKS = 6
TREND_THRESHOLD = 0.05  # weekly slope as a share of mean weekly units


def item_stats(data: Dataset, window: int = 30) -> pd.DataFrame:
    """One row per menu item. Money columns are in paise."""
    w = data.window(window)
    items = data.items.copy()
    n_orders = len(w.orders)

    units = w.lines.groupby("item_id")["qty"].sum()
    orders_with = w.lines.groupby("item_id")["order_id"].nunique()
    items["units"] = items["item_id"].map(units).fillna(0).astype(int)
    items["attach_rate"] = items["item_id"].map(orders_with).fillna(0) / n_orders if n_orders else 0.0
    items["cm_pct"] = items["cm_paise"] / items["price_paise"]
    items["revenue_paise"] = items["units"] * items["price_paise"]
    items["profit_paise"] = items["units"] * items["cm_paise"]

    cat_units = items.groupby("category")["units"].transform("sum")
    cat_n = items.groupby("category")["item_id"].transform("count")
    items["n_in_category"] = cat_n
    items["popularity_share"] = np.where(cat_units > 0, items["units"] / cat_units.replace(0, 1), 0.0)
    items["popularity_index"] = items["popularity_share"] * cat_n

    items["velocity"] = _velocity(w, items["item_id"], window)
    trend_slope, trend = _trend(data, items["item_id"])
    items["trend_slope"] = trend_slope
    items["trend"] = trend
    items["window"] = window
    items["sample_size"] = n_orders
    return items


def _velocity(w: Dataset, item_ids: pd.Series, window: int) -> list[float]:
    """Units per day, exponentially weighted so recent days count more (half-life 10 days)."""
    if w.as_of is None or w.lines.empty:
        return [0.0] * len(item_ids)
    end = w.as_of.normalize()
    days = pd.date_range(end - timedelta(days=window - 1), end, freq="D")
    daily = (w.lines.assign(day=w.lines["ts"].dt.normalize())
             .groupby(["item_id", "day"])["qty"].sum().unstack(fill_value=0)
             .reindex(columns=days, fill_value=0))
    ewm = daily.T.ewm(halflife=VELOCITY_HALF_LIFE_DAYS).mean().iloc[-1]
    return [round(float(ewm.get(i, 0.0)), 2) for i in item_ids]


def _trend(data: Dataset, item_ids: pd.Series) -> tuple[list[float], list[str]]:
    """Slope of weekly units over the last six full weeks: up, flat or down."""
    if data.as_of is None or data.lines.empty:
        return [0.0] * len(item_ids), ["flat"] * len(item_ids)
    since = data.as_of - timedelta(weeks=TREND_WEEKS)
    recent = data.lines[data.lines["ts"] > since]
    week = ((recent["ts"] - since) / pd.Timedelta(weeks=1)).astype(int).clip(0, TREND_WEEKS - 1)
    weekly = recent.assign(week=week).groupby(["item_id", "week"])["qty"].sum().unstack(fill_value=0)
    weekly = weekly.reindex(columns=range(TREND_WEEKS), fill_value=0)
    x = np.arange(TREND_WEEKS)
    slopes, labels = [], []
    for i in item_ids:
        y = weekly.loc[i].to_numpy(dtype=float) if i in weekly.index else np.zeros(TREND_WEEKS)
        mean = y.mean()
        slope = float(np.polyfit(x, y, 1)[0]) if mean > 0 else 0.0
        rel = slope / mean if mean > 0 else 0.0
        slopes.append(round(rel, 4))
        labels.append("up" if rel > TREND_THRESHOLD else "down" if rel < -TREND_THRESHOLD else "flat")
    return slopes, labels
