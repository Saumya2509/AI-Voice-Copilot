"""Inventory-linked signals (file 04, section 6).

Push: ingredient stock above twice its reorder level and short shelf life -> small boost.
Hold: ingredient below reorder level -> suppress items that use it.
Kitchen busy: suppress slow-prep items.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from revenue.data import Dataset

SHORT_SHELF_LIFE = {"paneer", "cream", "milk", "curd", "chicken", "mixed vegetables"}
PUSH_FACTOR = 1.10


@dataclass
class Signals:
    push: dict[int, str] = field(default_factory=dict)   # item_id -> reason text
    hold: dict[int, str] = field(default_factory=dict)
    kitchen_busy: bool = False
    slow_prep_minutes: int = 15
    active: list[dict] = field(default_factory=list)     # for the Settings screen


def compute(data: Dataset, enabled: bool = True, kitchen_busy: bool = False, slow_prep_minutes: int = 15) -> Signals:
    s = Signals(kitchen_busy=kitchen_busy, slow_prep_minutes=slow_prep_minutes)
    if kitchen_busy:
        slow = data.items[data.items["prep_minutes"] > slow_prep_minutes]
        s.active.append({"kind": "kitchen_busy", "text": f"Kitchen busy: holding items that take over "
                         f"{slow_prep_minutes} minutes ({len(slow)} items)."})
    if not enabled or data.ingredients.empty or data.recipes.empty:
        return s
    names = data.items.set_index("item_id")["name"]
    for ing in data.ingredients.itertuples():
        users = data.recipes.loc[data.recipes["ingredient_id"] == ing.ingredient_id, "item_id"].tolist()
        if not users:
            continue
        label = ing.name.lower()
        if ing.stock < ing.reorder_level:
            text = f"Held: {label} stock is low"
            for i in users:
                s.hold[i] = text
            s.active.append({"kind": "hold", "ingredient": ing.name, "text": text,
                             "items": [names[i] for i in users if i in names]})
        elif ing.stock > 2 * ing.reorder_level and label in SHORT_SHELF_LIFE:
            text = f"Pushed: {label} stock is high"
            for i in users:
                s.push.setdefault(i, text)
            s.active.append({"kind": "push", "ingredient": ing.name, "text": text,
                             "items": [names[i] for i in users if i in names]})
    return s
