"""Analytics for the Analytics screen (improve.md, sections 2 and 9). Every function takes the shared
filters (date range, category, veg, channel) and returns its data with `window` and `sample_size`.

Revenue here is item sales (quantity x unit price) before order-level discounts, so category, veg and
item figures add up to the total.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Optional

import numpy as np
import pandas as pd

import settings
from revenue import classify as cls_mod
from revenue.data import Dataset
from revenue.stats import item_stats

WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]


@dataclass(frozen=True)
class Filters:
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    category: Optional[str] = None  # category name
    veg: Optional[str] = None       # "veg" | "non_veg"
    channel: Optional[str] = None
    weekday: Optional[int] = None   # 0 = Monday, restaurant local time
    hour: Optional[int] = None      # 0 to 23, restaurant local time


@dataclass
class View:
    orders: pd.DataFrame
    lines: pd.DataFrame  # with item columns joined and line revenue, cost, profit
    date_from: Optional[date]
    date_to: Optional[date]
    estimated: bool

    @property
    def window(self) -> int:
        if not self.date_from or not self.date_to:
            return 0
        return (self.date_to - self.date_from).days + 1

    def meta(self, f: Filters) -> dict:
        return {
            "window": self.window, "sample_size": int(len(self.orders)),
            "from": self.date_from.isoformat() if self.date_from else None,
            "to": self.date_to.isoformat() if self.date_to else None,
            "filters": {k: v for k, v in f.__dict__.items() if v is not None and v != "" and k not in ("date_from", "date_to")},
            "estimated": self.estimated,
        }


def _local(ts: pd.Series) -> pd.Series:
    return ts.dt.tz_localize("UTC").dt.tz_convert(settings.RESTAURANT_TZ)


def view(data: Dataset, f: Filters) -> View:
    orders = data.orders.copy()
    if orders.empty:
        empty = data.lines.iloc[0:0].copy()
        return View(orders, empty, None, None, False)
    orders["local"] = _local(orders["ts"])
    orders["local_date"] = orders["local"].dt.date
    lo = date.fromisoformat(f.date_from) if f.date_from else orders["local_date"].min()
    hi = date.fromisoformat(f.date_to) if f.date_to else orders["local_date"].max()
    orders = orders[(orders["local_date"] >= lo) & (orders["local_date"] <= hi)]
    if f.channel:
        orders = orders[orders["channel"] == f.channel]
    if f.weekday is not None:
        orders = orders[orders["local"].dt.weekday == f.weekday]
    if f.hour is not None:
        orders = orders[orders["local"].dt.hour == f.hour]
    lines = data.lines[data.lines["order_id"].isin(orders["order_id"])].merge(
        data.items[["item_id", "name", "category", "category_name", "veg", "cost_estimated", "price_paise",
                    "food_cost_paise", "cm_paise"]], on="item_id", how="left")
    if f.category:
        lines = lines[lines["category_name"] == f.category]
    if f.veg in ("veg", "non_veg"):
        lines = lines[lines["veg"] == (f.veg == "veg")]
    if f.category or f.veg:
        orders = orders[orders["order_id"].isin(lines["order_id"])]
    lines = lines.copy()
    lines["revenue_paise"] = lines["qty"] * lines["unit_price_paise"]
    lines["cost_paise"] = lines["qty"] * lines["unit_cost_paise"]
    lines["profit_paise"] = lines["revenue_paise"] - lines["cost_paise"]
    local = orders.set_index("order_id")["local"]
    lines["local"] = lines["order_id"].map(local)
    return View(orders, lines, lo, hi, bool(lines["cost_estimated"].any()) if len(lines) else False)


def overview(v: View) -> dict:
    n = len(v.orders)
    rev = int(v.lines["revenue_paise"].sum()) if len(v.lines) else 0
    cost = int(v.lines["cost_paise"].sum()) if len(v.lines) else 0
    busiest = None
    if n:
        hours = v.orders["local"].dt.hour.value_counts()
        busiest = int(hours.idxmax())
    return {
        "revenue_paise": rev, "orders": n, "aov_paise": round(rev / n) if n else 0,
        "items_sold": int(v.lines["qty"].sum()) if len(v.lines) else 0,
        "gross_margin_pct": round((rev - cost) / rev, 4) if rev else None,
        "busiest_hour": busiest,
    }


def category_share(v: View) -> list[dict]:
    if v.lines.empty:
        return []
    g = v.lines.groupby("category_name").agg(revenue=("revenue_paise", "sum"), units=("qty", "sum"))
    total = g["revenue"].sum()
    g = g.sort_values("revenue", ascending=False)
    return [{"category": c, "revenue_paise": int(r.revenue), "units": int(r.units),
             "share": round(float(r.revenue / total), 4) if total else 0.0} for c, r in g.iterrows()]


def veg_split(v: View) -> list[dict]:
    if v.lines.empty:
        return []
    total = v.lines["revenue_paise"].sum()
    out = []
    for veg, label in ((True, "veg"), (False, "non_veg")):
        part = v.lines[v.lines["veg"] == veg]
        rev = int(part["revenue_paise"].sum())
        out.append({"key": label, "revenue_paise": rev, "units": int(part["qty"].sum()),
                    "share": round(rev / total, 4) if total else 0.0})
    return out


def item_table(v: View, data: Dataset) -> pd.DataFrame:
    """Per item units, revenue and profit in the view, classified per category (file 04)."""
    items = data.items.copy()
    if v.lines.empty:
        items["units"] = 0
        items["revenue_paise"] = 0
        items["profit_paise"] = 0
    else:
        g = v.lines.groupby("item_id").agg(units=("qty", "sum"), revenue_paise=("revenue_paise", "sum"),
                                           profit_paise=("profit_paise", "sum"))
        items = items.merge(g, on="item_id", how="left").fillna({"units": 0, "revenue_paise": 0, "profit_paise": 0})
    items["units"] = items["units"].astype(int)
    if items.empty:
        return items.assign(cls=[], popularity_share=[], category_avg_cm_paise=[])
    classified = cls_mod.classify_frame(items[["item_id", "name", "category", "cm_paise", "units"]].copy())
    items = items.merge(classified[["item_id", "cls", "popularity_share", "popularity_index", "category_avg_cm_paise"]],
                        on="item_id", how="left")
    n_cat = items.groupby("category")["item_id"].transform("count")
    items["x"] = items["popularity_share"] / (cls_mod.POPULARITY_FACTOR / n_cat)
    items["y"] = np.where(items["category_avg_cm_paise"] > 0, items["cm_paise"] / items["category_avg_cm_paise"], 1.0)
    return items


def class_split(items: pd.DataFrame) -> list[dict]:
    counts = items["cls"].value_counts().to_dict() if len(items) else {}
    return [{"class": c, "count": int(counts.get(c, 0))} for c in ("star", "plowhorse", "puzzle", "dog")]


def top_items(items: pd.DataFrame, by: str, limit: int) -> list[dict]:
    col = {"units": "units", "profit": "profit_paise", "revenue": "revenue_paise"}[by]
    top = items[items["units"] > 0].sort_values([col, "units"], ascending=False).head(limit)
    return [{"item_id": int(r.item_id), "name": r.name, "category": r.category_name, "class": r.cls,
             "units": int(r.units), "revenue_paise": int(r.revenue_paise), "profit_paise": int(r.profit_paise)}
            for r in top.itertuples()]


def trend(v: View, grain: str) -> list[dict]:
    if v.orders.empty:
        return []
    o = v.orders.copy()
    rev_by_order = v.lines.groupby("order_id")["revenue_paise"].sum()
    o["revenue_paise"] = o["order_id"].map(rev_by_order).fillna(0)
    if grain == "week":
        o["period"] = o["local_date"].map(lambda d: d - timedelta(days=d.weekday()))
    else:
        o["period"] = o["local_date"]
    g = o.groupby("period").agg(revenue=("revenue_paise", "sum"), orders=("order_id", "count"))
    # Days with no orders still appear, so the line does not skip them.
    if grain == "day" and v.date_from and v.date_to:
        full = pd.date_range(v.date_from, v.date_to, freq="D").date
        g = g.reindex(full, fill_value=0)
    return [{"period": p.isoformat(), "revenue_paise": int(r.revenue), "orders": int(r.orders),
             "aov_paise": round(r.revenue / r.orders) if r.orders else 0} for p, r in g.iterrows()]


def heatmap(v: View) -> dict:
    cells = []
    if not v.orders.empty:
        o = v.orders.copy()
        rev_by_order = v.lines.groupby("order_id")["revenue_paise"].sum()
        o["revenue_paise"] = o["order_id"].map(rev_by_order).fillna(0)
        o["weekday"] = o["local"].dt.weekday
        o["hour"] = o["local"].dt.hour
        g = o.groupby(["weekday", "hour"]).agg(orders=("order_id", "count"), revenue=("revenue_paise", "sum"))
        cells = [{"weekday": int(wd), "hour": int(h), "orders": int(r.orders), "revenue_paise": int(r.revenue)}
                 for (wd, h), r in g.iterrows()]
    return {"weekdays": WEEKDAYS, "cells": cells, "max_orders": max((c["orders"] for c in cells), default=0)}


def channel_mix(v: View) -> list[dict]:
    if v.orders.empty:
        return []
    rev_by_order = v.lines.groupby("order_id")["revenue_paise"].sum()
    o = v.orders.assign(revenue_paise=v.orders["order_id"].map(rev_by_order).fillna(0))
    g = o.groupby("channel").agg(orders=("order_id", "count"), revenue=("revenue_paise", "sum"))
    return [{"channel": ch, "orders": int(r.orders), "revenue_paise": int(r.revenue),
             "aov_paise": round(r.revenue / r.orders) if r.orders else 0}
            for ch, r in g.sort_values("revenue", ascending=False).iterrows()]


def lists(v: View, data: Dataset, kind: str) -> pd.DataFrame:
    """The file 04 lists computed on the filtered view."""
    if v.orders.empty:
        return pd.DataFrame()
    sub = Dataset(data.items, v.orders.drop(columns=["local", "local_date"]), v.lines[data.lines.columns],
                  data.ingredients, data.recipes, v.orders["ts"].max())
    df = cls_mod.classify(item_stats(sub, max(1, v.window)))
    return {"puzzles": cls_mod.puzzles, "underperformers": cls_mod.underperformers,
            "plowhorse_risk": cls_mod.plowhorse_risk}[kind](df)
