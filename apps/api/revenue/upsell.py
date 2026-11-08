"""Upsell ranker with Thompson sampling (file 04, section 5).

score      = P(accept) * incremental_cm * fit
P(accept)  = a draw from Beta(alpha, beta) of the rule
fit        = daypart_factor * class_boost * freshness (* push signal)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np
import pandas as pd

from revenue.signals import PUSH_FACTOR, Signals

CLASS_BOOST = {"puzzle": 1.25, "star": 1.10, "plowhorse": 0.90, "dog": 0.0}
DAYPART_MATCH = 1.10
SAME_CATEGORY_FRESHNESS = 0.85
PRIOR_STRENGTH = 10


def prior(confidence: float) -> tuple[float, float]:
    return 1 + confidence * PRIOR_STRENGTH, 1 + (1 - confidence) * PRIOR_STRENGTH


@dataclass
class Rule:
    id: int
    anchor_item_id: int
    offer_item_id: int
    daypart: Optional[str]
    alpha: float
    beta: float
    lift: float
    confidence: float
    support: float


@dataclass
class PoolCombo:
    id: str
    item_ids: list[int]
    names: list[str]
    price_paise: int
    list_price_paise: int
    confidence: float


@dataclass
class UpsellContext:
    cart_item_ids: list[int]
    daypart: str
    declined_item_ids: set[int] = field(default_factory=set)
    declined_anchor_ids: set[int] = field(default_factory=set)
    offered_item_ids: set[int] = field(default_factory=set)
    offers_made: int = 0
    max_offers: int = 2
    daypart_weight: float = 1.0
    rng: np.random.Generator = field(default_factory=np.random.default_rng)


@dataclass
class Offer:
    kind: str  # rule | combo
    item_id: int
    name: str
    price_paise: int        # what the guest pays for this addition
    incremental_cm_paise: int
    p_accept: float
    fit: float
    score: float
    anchor_item_id: Optional[int]
    rule_id: Optional[int] = None
    combo_id: Optional[str] = None
    combo_discount_paise: int = 0
    reason: dict = field(default_factory=dict)


def _rupees(paise: float) -> int:
    return int(round(paise / 100))


class Ranker:
    def __init__(self, items: pd.DataFrame, rules: list[Rule], pool: list[PoolCombo], signals: Signals):
        """`items` is the classified item frame (item_id, name, category, price_paise, cm_paise, veg,
        available, prep_minutes, class)."""
        self.items = items.set_index("item_id")
        self.rules = rules
        self.pool = pool
        self.signals = signals

    def _rules_for(self, anchor: int, daypart: str) -> list[Rule]:
        """Overall rules for the anchor, replaced by daypart-specific ones where they exist."""
        live = [r for r in self.rules if r.anchor_item_id == anchor and r.lift >= 1.2 and r.confidence > 0]
        chosen = {r.offer_item_id: r for r in live if r.daypart is None}
        chosen.update({r.offer_item_id: r for r in live if r.daypart == daypart})
        return list(chosen.values())

    def _allowed(self, item_id: int, ctx: UpsellContext, cart_veg: bool) -> bool:
        if item_id not in self.items.index:
            return False
        it = self.items.loc[item_id]
        if not it["available"] or item_id in self.signals.hold:
            return False
        if item_id in ctx.cart_item_ids or item_id in ctx.declined_item_ids or item_id in ctx.offered_item_ids:
            return False
        if cart_veg and not it["veg"]:
            return False
        if self.signals.kitchen_busy and it["prep_minutes"] > self.signals.slow_prep_minutes:
            return False
        if it["category"] == "main" and any(
                self.items.at[i, "category"] == "main" for i in ctx.cart_item_ids if i in self.items.index):
            return False  # a good waiter suggests a side, bread, drink or dessert, not a second curry
        return CLASS_BOOST.get(it["class"], 0) > 0

    def _fit(self, item_id: int, ctx: UpsellContext, daypart_match: bool) -> float:
        it = self.items.loc[item_id]
        cart_cats = {self.items.at[i, "category"] for i in ctx.cart_item_ids if i in self.items.index}
        fit = ctx.daypart_weight * (DAYPART_MATCH if daypart_match else 1.0)
        fit *= CLASS_BOOST[it["class"]]
        fit *= SAME_CATEGORY_FRESHNESS if it["category"] in cart_cats else 1.0
        if item_id in self.signals.push:
            fit *= PUSH_FACTOR
        return fit

    def rank(self, ctx: UpsellContext) -> list[Offer]:
        if ctx.offers_made >= ctx.max_offers or not ctx.cart_item_ids:
            return []
        cart = [i for i in ctx.cart_item_ids if i in self.items.index]
        cart_veg = all(bool(self.items.at[i, "veg"]) for i in cart)
        offers: dict[int, Offer] = {}

        for anchor in dict.fromkeys(cart):
            if anchor in ctx.declined_anchor_ids:
                continue
            for r in self._rules_for(anchor, ctx.daypart):
                oid = r.offer_item_id
                if not self._allowed(oid, ctx, cart_veg):
                    continue
                it = self.items.loc[oid]
                p = float(ctx.rng.beta(r.alpha, r.beta))
                fit = self._fit(oid, ctx, r.daypart == ctx.daypart)
                cm = int(it["cm_paise"])
                score = p * cm * fit
                if oid in offers and offers[oid].score >= score:
                    continue
                why = [f"Ordered with {self.items.at[anchor, 'name']} in {round(r.confidence * 100)}% of orders",
                       f"Adds ₹{_rupees(cm)} margin"]
                why.append(self.signals.push.get(oid, "Pairs with your current cart"))
                offers[oid] = Offer(
                    kind="rule", item_id=oid, name=it["name"], price_paise=int(it["price_paise"]),
                    incremental_cm_paise=cm, p_accept=round(p, 4), fit=round(fit, 4), score=round(score / 100, 3),
                    anchor_item_id=anchor, rule_id=r.id,
                    reason={"headline": f"Add {it['name']}", "why": why, "expected_gain": _rupees(cm)},
                )

        cart_set = set(cart)
        for combo in self.pool:
            missing = [i for i in combo.item_ids if i not in cart_set]
            if len(missing) != 1 or len(combo.item_ids) < 2:
                continue
            oid = missing[0]
            anchors = [i for i in combo.item_ids if i != oid]
            if any(a in ctx.declined_anchor_ids for a in anchors) or not self._allowed(oid, ctx, cart_veg):
                continue
            it = self.items.loc[oid]
            discount = combo.list_price_paise - combo.price_paise
            pay = int(it["price_paise"]) - discount
            incremental = int(it["cm_paise"]) - discount
            if incremental <= 0:
                continue
            a, b = prior(combo.confidence)
            p = float(ctx.rng.beta(a, b))
            fit = self._fit(oid, ctx, False)
            score = p * incremental * fit
            if oid in offers and offers[oid].kind == "combo" and offers[oid].score >= score / 100:
                continue
            names = " + ".join(combo.names)
            offers[oid] = Offer(
                kind="combo", item_id=oid, name=it["name"], price_paise=pay, incremental_cm_paise=incremental,
                p_accept=round(p, 4), fit=round(fit, 4), score=round(score / 100, 3), anchor_item_id=anchors[0],
                combo_id=combo.id, combo_discount_paise=discount,
                reason={"headline": f"Make it a combo: add {it['name']}",
                        "why": [f"Completes the {names} combo for ₹{_rupees(combo.price_paise)}",
                                f"Saves the guest ₹{_rupees(discount)}",
                                f"Adds ₹{_rupees(incremental)} margin"],
                        "expected_gain": _rupees(incremental)},
            )
        # A combo that one more item would complete is offered first (file 05, section 8).
        return sorted(offers.values(), key=lambda o: (o.kind != "combo", -o.score))
