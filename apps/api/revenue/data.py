"""Loads menu and order history from SQLite into pandas frames for the engine."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path

import pandas as pd


@dataclass
class Dataset:
    items: pd.DataFrame        # item_id, name, category, price_paise, food_cost_paise, cm_paise, veg, available, prep_minutes, station
    orders: pd.DataFrame       # order_id, ts, channel, daypart, subtotal_paise, discount_paise, total_paise
    lines: pd.DataFrame        # order_id, item_id, qty, unit_price_paise, unit_cost_paise, modifiers_json, ts, daypart
    ingredients: pd.DataFrame  # ingredient_id, name, unit, stock, reorder_level
    recipes: pd.DataFrame      # item_id, ingredient_id, qty
    as_of: pd.Timestamp | None  # newest order time; windows end here

    def window(self, days: int) -> "Dataset":
        """Orders and lines in the last `days` days up to `as_of`."""
        if self.as_of is None:
            return self
        since = self.as_of - timedelta(days=days)
        o = self.orders[self.orders["ts"] > since]
        l = self.lines[self.lines["ts"] > since]
        return Dataset(self.items, o, l, self.ingredients, self.recipes, self.as_of)


def load(db_path: Path | str) -> Dataset:
    con = sqlite3.connect(db_path)
    try:
        items = pd.read_sql_query(
            "SELECT i.id AS item_id, i.name, c.kind AS category, c.name AS category_name, i.price_paise, "
            "i.food_cost_paise, i.price_paise - i.food_cost_paise AS cm_paise, i.veg, i.available, i.prep_minutes, "
            "i.station, COALESCE(i.cost_estimated, 0) AS cost_estimated "
            "FROM items i JOIN categories c ON c.id = i.category_id ORDER BY i.id", con)
        orders = pd.read_sql_query(
            "SELECT id AS order_id, ts, channel, daypart, subtotal_paise, discount_paise, total_paise FROM orders",
            con, parse_dates=["ts"])
        lines = pd.read_sql_query(
            "SELECT oi.order_id, oi.item_id, oi.qty, oi.unit_price_paise, oi.unit_cost_paise, oi.modifiers_json, "
            "o.ts, o.daypart FROM order_items oi JOIN orders o ON o.id = oi.order_id",
            con, parse_dates=["ts"])
        ingredients = pd.read_sql_query(
            "SELECT id AS ingredient_id, name, unit, stock, reorder_level FROM ingredients", con)
        recipes = pd.read_sql_query("SELECT item_id, ingredient_id, qty FROM recipe_lines", con)
    finally:
        con.close()
    items["veg"] = items["veg"].astype(bool)
    items["available"] = items["available"].astype(bool)
    items["cost_estimated"] = items["cost_estimated"].astype(bool)
    as_of = orders["ts"].max() if len(orders) else None
    return Dataset(items, orders, lines, ingredients, recipes, as_of)
