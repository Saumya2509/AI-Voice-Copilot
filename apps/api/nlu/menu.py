"""In-memory menu used by the NLU and the dialogue manager, loaded from the PoS database."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class ModGroup:
    name: str
    required: bool
    options: dict[str, int]  # option name -> price delta (paise)
    costs: dict[str, int]    # option name -> cost delta (paise)


@dataclass
class MenuItem:
    id: int
    name: str
    category: str
    price_paise: int
    food_cost_paise: int
    veg: bool
    available: bool
    prep_minutes: int
    station: str
    aliases: list[str]
    groups: dict[str, ModGroup] = field(default_factory=dict)

    def group_for(self, kind: str) -> ModGroup | None:
        return self.groups.get(kind)

    @property
    def cm_paise(self) -> int:
        return self.price_paise - self.food_cost_paise


@dataclass
class MenuIndex:
    items: dict[int, MenuItem]

    def by_name(self, name: str) -> MenuItem | None:
        low = name.lower()
        return next((i for i in self.items.values() if i.name.lower() == low), None)


def load_menu(db_path: Path | str) -> MenuIndex:
    con = sqlite3.connect(db_path)
    try:
        items: dict[int, MenuItem] = {}
        for row in con.execute(
            "SELECT i.id, i.name, c.kind, i.price_paise, i.food_cost_paise, i.veg, i.available, i.prep_minutes, "
            "i.station, i.aliases_json FROM items i JOIN categories c ON c.id = i.category_id ORDER BY i.id"
        ):
            items[row[0]] = MenuItem(row[0], row[1], row[2], row[3], row[4], bool(row[5]), bool(row[6]), row[7],
                                     row[8], json.loads(row[9] or "[]"))
        groups = {}
        for gid, item_id, name, required in con.execute(
            "SELECT id, item_id, name, required FROM modifier_groups ORDER BY id"
        ):
            groups[gid] = (item_id, ModGroup(name, bool(required), {}, {}))
        for gid, name, delta, cost in con.execute(
            "SELECT group_id, name, price_delta_paise, cost_delta_paise FROM modifiers ORDER BY id"
        ):
            if gid in groups:
                groups[gid][1].options[name] = delta
                groups[gid][1].costs[name] = cost
        for item_id, g in groups.values():
            if item_id in items:
                items[item_id].groups[g.name] = g
    finally:
        con.close()
    return MenuIndex(items)
