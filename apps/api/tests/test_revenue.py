"""Revenue engine (file 04): formulas on a tiny hand-calculated menu, plus checks on the seed."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from revenue import classify as cls_mod
from revenue import combos as combos_mod
from revenue import pricing as pricing_mod
from revenue.engine import get_engine
from revenue.signals import Signals
from revenue.upsell import CLASS_BOOST, PoolCombo, Ranker, Rule, UpsellContext, prior


# ----- classification -----------------------------------------------------------------

def tiny_menu() -> pd.DataFrame:
    # Category "main": 4 items. Units 50, 30, 15, 5 (total 100). Popular line = 0.7 / 4 = 0.175.
    # cm 100, 60, 120, 40 -> unit-weighted avg = (5000 + 1800 + 1800 + 200) / 100 = 88.
    return pd.DataFrame({
        "item_id": [1, 2, 3, 4], "name": ["A", "B", "C", "D"], "category": ["main"] * 4,
        "cm_paise": [10000, 6000, 12000, 4000], "units": [50, 30, 15, 5],
    })


def test_classification_by_hand():
    df = cls_mod.classify_frame(tiny_menu()).set_index("name")
    assert df.loc["A", "category_avg_cm_paise"] == pytest.approx(8800)
    assert df.loc["A", "popularity_share"] == pytest.approx(0.5)
    assert df.loc["A", "popularity_index"] == pytest.approx(2.0)
    assert df.loc["A", "cls"] == "star"        # share 0.5 >= 0.175, cm 100 >= 88
    assert df.loc["B", "cls"] == "plowhorse"   # share 0.3, cm 60 < 88
    assert df.loc["C", "cls"] == "puzzle"      # share 0.15 < 0.175, cm 120
    assert df.loc["D", "cls"] == "dog"


def test_reason_template():
    row = {"category": "main", "cm_paise": 18200, "popularity_index": 1.42, "units": 412, "window": 30}
    assert cls_mod.reason(row) == "Earns ₹182 per plate and sells 42 percent more than an average main."
    row.update(cm_paise=9600, popularity_index=0.69)
    assert cls_mod.reason(row) == "Earns ₹96 per plate and is ordered 31 percent less than an average main."


def test_plowhorse_sensitivity_by_hand():
    df = pd.DataFrame({"item_id": [1], "class": ["plowhorse"], "food_cost_paise": [8800], "cm_paise": [10200],
                       "units": [300], "window": [30]})
    out = cls_mod.plowhorse_risk(df).iloc[0]
    assert out["profit_drop_pct"] == pytest.approx(0.05 * 88 / 102)       # 4.3 percent
    assert out["monthly_exposure_paise"] == pytest.approx(0.05 * 8800 * 300)
    assert not out["at_risk"]


# ----- pricing ------------------------------------------------------------------------

@pytest.mark.parametrize("units,price,cost,new_price,e,exp_units,exp_delta", [
    # 100 * (300/280) ** -0.6 = 95.9449 ; (300-98) * 95.9449 - (280-98) * 100 = ₹1,180.88
    (100, 28000, 9800, 30000, -0.6, 95.9449, 118088),
    # 400 * (200/190) ** -0.8 = 383.9184 ; (200-88) * 383.9184 - (190-88) * 400 = ₹2,198.86
    (400, 19000, 8800, 20000, -0.8, 383.9184, 219886),
    # 50 * (290/310) ** -1.2 = 54.1660 ; (290-104) * 54.1660 - (310-104) * 50 = -₹225.13
    (50, 31000, 10400, 29000, -1.2, 54.1660, -22513),
])
def test_price_formula_by_hand(units, price, cost, new_price, e, exp_units, exp_delta):
    out = pricing_mod.predict(units, price, cost, new_price, e)
    assert out["new_units"] == pytest.approx(exp_units, abs=1e-3)
    assert out["delta_profit"] == pytest.approx(exp_delta, abs=1)


def test_price_guardrails():
    assert pricing_mod.round_price(28763) == 29000  # nearest ₹5
    assert pricing_mod.round_price(28740) == 28500


def test_recommendations_respect_limits(seeded_db):
    eng = get_engine(seeded_db)
    for rec in eng.pricing(30):
        change = rec["suggested_price_paise"] / rec["price_paise"] - 1
        assert abs(change) <= pricing_mod.MAX_CHANGE + 0.02  # rounding to ₹5 can add a little
        assert rec["suggested_price_paise"] % 500 == 0 or rec["action"] in ("hold", "rework")
        assert rec["elasticity_source"] in ("Assumed", "Measured")
        lo, hi = rec["delta_range_paise"]
        assert lo <= rec["delta_profit_paise"] <= hi
        if rec["class"] == "dog":
            assert rec["action"] == "rework"


# ----- combos -------------------------------------------------------------------------

def test_bundle_discount_picks_largest_step_above_floor():
    # Items ₹200 (cost 70) and ₹100 (cost 30): list ₹300, cost ₹100.
    d, price = combos_mod.bundle_discount([20000, 10000], [7000, 3000], floor_pct=0.5)
    assert price == 25900  # 12 percent off -> ₹264 -> rounded down to ₹259
    assert (price - 10000) / price >= 0.5
    # A high floor forces a smaller discount.
    d2, price2 = combos_mod.bundle_discount([20000, 10000], [7000, 3000], floor_pct=0.64)
    assert price2 > price


def test_evidence_sentence():
    assert combos_mod.plain_evidence(1 / 6, 2.4) == "Ordered together in 1 of 6 orders, 2.4 times more often than chance"


def test_seeded_affinities_in_top_combos(seeded_db):
    combos, meta = get_engine(seeded_db).combos(30)
    assert meta["window"] == 30 and meta["sample_size"] > 3000
    top = [set(c.names) for c in combos[:15]]
    assert any({"Boondi Raita"} <= s and s & {"Veg Biryani", "Chicken Biryani"} for s in top), "biryani + raita"
    dals = {"Dal Makhani", "Dal Tadka"}
    breads = {"Butter Naan", "Garlic Naan", "Lachha Paratha", "Tandoori Roti", "Cheese Naan"}
    assert any(s & dals and s & breads for s in top), "dal + bread"
    for c in combos:
        assert "dog" not in c.classes
        assert c.lift >= combos_mod.MIN_LIFT and c.confidence >= combos_mod.MIN_CONFIDENCE


def test_summary_carries_window_and_sample(seeded_db):
    s = get_engine(seeded_db).summary(30)
    assert s["window"] == 30 and s["sample_size"] > 3000
    assert s["class_counts"] == {"star": 28, "plowhorse": 6, "puzzle": 6, "dog": 5}
    assert s["aov_paise"] > 0 and s["upside"]["monthly_paise"] > 0


# ----- upsell ranker ------------------------------------------------------------------

def ranker_items() -> pd.DataFrame:
    return pd.DataFrame([
        # item_id, name, category, price, cm, veg, available, prep, class
        (1, "Dal Makhani", "main", 24000, 17200, True, True, 10, "star"),
        (2, "Garlic Naan", "bread", 7000, 5000, True, True, 6, "star"),
        (3, "Chicken Tikka", "starter", 32000, 18200, False, True, 18, "star"),
        (4, "Cheese Naan", "bread", 11000, 8000, True, True, 8, "puzzle"),
        (5, "Kulfi", "dessert", 8000, 4200, True, True, 2, "dog"),
        (6, "Jeera Rice", "rice", 17000, 9800, True, False, 10, "plowhorse"),
        (7, "Malai Kofta", "main", 32000, 21600, True, True, 18, "puzzle"),
    ], columns=["item_id", "name", "category", "price_paise", "cm_paise", "veg", "available", "prep_minutes", "class"])


def ranker(signals=None, pool=None) -> Ranker:
    rules = [Rule(i, 1, offer, None, *prior(0.38), 1.6, 0.38, 0.05) for i, offer in enumerate([2, 3, 4, 5, 6, 7], 1)]
    return Ranker(ranker_items(), rules, pool or [], signals or Signals())


def ctx(**kw) -> UpsellContext:
    base = dict(cart_item_ids=[1], daypart="dinner", rng=np.random.default_rng(1))
    base.update(kw)
    return UpsellContext(**base)


def test_hard_filters():
    offers = ranker().rank(ctx())
    ids = {o.item_id for o in offers}
    assert 3 not in ids, "veg cart is never offered a non-veg item"
    assert 5 not in ids, "Dogs are never promoted"
    assert 6 not in ids, "unavailable items are skipped"
    assert 7 not in ids, "no second main"
    assert ids == {2, 4}
    assert ranker().rank(ctx(offers_made=2)) == [], "two offers per call at most"
    assert {o.item_id for o in ranker().rank(ctx(declined_item_ids={2}))} == {4}
    assert ranker().rank(ctx(declined_anchor_ids={1})) == [], "a decline ends upselling for that anchor"
    assert {o.item_id for o in ranker().rank(ctx(cart_item_ids=[1, 3]))} >= {2, 4}


def test_kitchen_busy_and_hold_signals():
    busy = Signals(kitchen_busy=True, slow_prep_minutes=7)
    assert {o.item_id for o in ranker(busy).rank(ctx())} == {2}, "slow-prep Cheese Naan is held while busy"
    hold = Signals(hold={2: "Held: maida stock is low"})
    assert {o.item_id for o in ranker(hold).rank(ctx())} == {4}
    push = Signals(push={4: "Pushed: cheese stock is high"})
    offer = next(o for o in ranker(push).rank(ctx()) if o.item_id == 4)
    assert "Pushed: cheese stock is high" in offer.reason["why"]


def test_score_and_reason():
    offers = ranker().rank(ctx(rng=np.random.default_rng(7)))
    for o in offers:
        assert o.score == pytest.approx(o.p_accept * o.incremental_cm_paise * o.fit / 100, rel=1e-3)
        assert o.reason["headline"] == f"Add {o.name}"
        assert o.reason["why"][0] == "Ordered with Dal Makhani in 38% of orders"
        assert o.reason["expected_gain"] == round(o.incremental_cm_paise / 100)
    puzzle = next(o for o in offers if o.item_id == 4)
    assert puzzle.fit == pytest.approx(CLASS_BOOST["puzzle"])


def test_combo_completion_comes_first():
    pool = [PoolCombo("c1", [1, 2], ["Dal Makhani", "Garlic Naan"], 28900, 31000, 0.4)]
    offers = ranker(pool=pool).rank(ctx())
    assert offers[0].kind == "combo" and offers[0].item_id == 2
    assert offers[0].price_paise == 7000 - 2100 and offers[0].combo_discount_paise == 2100


def test_thompson_sampling_learns(work_db):
    eng = get_engine(work_db)
    rule = next(r for r in eng.rules() if r.lift >= 1.2)
    a, b = rule.alpha, rule.beta
    assert a == pytest.approx(1 + rule.confidence * 10) and b == pytest.approx(1 + (1 - rule.confidence) * 10)
    eng.learn(rule.id, True)
    eng.learn(rule.id, False)
    eng.learn(rule.id, False)
    again = next(r for r in eng.rules() if r.id == rule.id)
    assert (again.alpha, again.beta) == (a + 1, b + 2)
