"""Combo recommendation from association analysis (file 04, section 3)."""
from __future__ import annotations

import hashlib
import warnings
from dataclasses import dataclass

import pandas as pd
from mlxtend.frequent_patterns import apriori, association_rules

from revenue.data import Dataset

MIN_SUPPORT = 0.01
MAX_LEN = 3
MIN_LIFT = 1.2
MIN_CONFIDENCE = 0.15
DISCOUNT_STEPS = (0.12, 0.10, 0.08, 0.05, 0.0)  # largest first
CM_FLOOR = 0.50          # absolute floor for a combo's margin percentage
CM_FLOOR_FACTOR = 0.55   # combo cm_pct must also stay above 0.55 x average menu cm_pct
MIX_BOOST = 1.15         # Puzzle or Star next to a Plowhorse anchor lifts margin, not just volume
MIN_TRIPLE_LIFT = 1.3    # each item of a 3-item combo must be associated with the other two
MIN_IMPROVEMENT = 0.05   # a longer rule must beat the confidence of its shorter sub-rule by this much


def baskets(data: Dataset) -> pd.DataFrame:
    """One-hot basket matrix (orders x item ids), multi-item orders only."""
    pairs = data.lines[["order_id", "item_id"]].drop_duplicates()
    size = pairs.groupby("order_id")["item_id"].transform("count")
    pairs = pairs[size > 1]
    if pairs.empty:
        return pd.DataFrame()
    m = pd.crosstab(pairs["order_id"], pairs["item_id"]).astype(bool)
    m.columns = [int(c) for c in m.columns]
    return m


def mine_rules(basket: pd.DataFrame, max_len: int = MAX_LEN) -> pd.DataFrame:
    """Rules with support, confidence, lift and leverage, filtered by lift and confidence."""
    cols = ["antecedents", "consequents", "support", "confidence", "lift", "leverage",
            "antecedent support", "consequent support"]
    if basket.empty:
        return pd.DataFrame(columns=cols)
    # Apriori returns the same frequent itemsets as FP-Growth; mlxtend's FP-Growth is far slower on
    # menu-sized data (seconds versus a quarter of a second), which matters for cold start.
    itemsets = apriori(basket, min_support=MIN_SUPPORT, use_colnames=True, max_len=max_len)
    if itemsets.empty or itemsets["itemsets"].map(len).max() < 2:
        return pd.DataFrame(columns=cols)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        rules = association_rules(itemsets, metric="lift", min_threshold=MIN_LIFT)
    rules = rules[rules["confidence"] >= MIN_CONFIDENCE]
    return prune_redundant(rules)[cols].reset_index(drop=True)


def prune_redundant(rules: pd.DataFrame) -> pd.DataFrame:
    """Drop rules whose extra antecedent adds nothing: confidence must beat every shorter rule with
    the same consequent by MIN_IMPROVEMENT (Bayardo's minimum improvement)."""
    conf = {(frozenset(r.antecedents), frozenset(r.consequents)): r.confidence for r in rules.itertuples()}
    keep = []
    for r in rules.itertuples():
        ante, cons = frozenset(r.antecedents), frozenset(r.consequents)
        subs = [conf.get((ante - {a}, cons)) for a in ante if len(ante) > 1]
        best_sub = max((c for c in subs if c is not None), default=0.0)
        keep.append(len(ante) == 1 or r.confidence >= best_sub + MIN_IMPROVEMENT)
    return rules[keep]


def combo_id(item_ids) -> str:
    return "c" + hashlib.sha1(",".join(str(i) for i in sorted(item_ids)).encode()).hexdigest()[:8]


def bundle_discount(prices: list[int], costs: list[int], floor_pct: float) -> tuple[float, int]:
    """Largest discount step that keeps the combo margin above the floor. Returns (d, price_paise)."""
    total, cost = sum(prices), sum(costs)
    for d in DISCOUNT_STEPS:
        price = _bundle_price(total * (1 - d))
        if price > cost and (price - cost) / price >= floor_pct:
            return round(1 - price / total, 4), price
    return 0.0, total


def _bundle_price(raw_paise: float) -> int:
    """Menu-style price: round down to a price ending in 9 (₹499, ₹289)."""
    rupees = int(raw_paise // 100)
    if rupees >= 100:
        rupees = rupees // 10 * 10 - 1
    return rupees * 100


def plain_evidence(support: float, lift: float) -> str:
    n = max(2, round(1 / support)) if support > 0 else 0
    return f"Ordered together in 1 of {n} orders, {lift:.1f} times more often than chance"


@dataclass
class Combo:
    id: str
    item_ids: list[int]
    names: list[str]
    anchor_ids: list[int]
    price_paise: int
    list_price_paise: int
    discount_pct: float
    cm_paise: int
    cm_pct: float
    support: float
    confidence: float
    lift: float
    incremental_cm_paise: float
    score: float
    aov_change_paise: float
    margin_change_paise: float
    evidence: str
    classes: list[str]


def recommend(data: Dataset, classes: pd.DataFrame, window: int = 30) -> tuple[list[Combo], dict]:
    """Ranked combos plus a meta dict with window and sample size."""
    w = data.window(window)
    basket = baskets(w)
    rules = mine_rules(basket)
    meta = {"window": window, "sample_size": int(len(w.orders)), "baskets": int(len(basket))}
    if rules.empty:
        return [], meta

    info = classes.set_index("item_id")
    avg_cm_pct = float((info["cm_paise"] * info["units"]).sum() / max((info["price_paise"] * info["units"]).sum(), 1))
    floor = max(CM_FLOOR_FACTOR * avg_cm_pct, CM_FLOOR)
    n_orders = max(len(w.orders), 1)
    anchor_freq = {
        frozenset([i]): float(v) for i, v in (w.lines.groupby("item_id")["order_id"].nunique() / n_orders).items()
    }

    best: dict[frozenset, pd.Series] = {}
    for _, r in rules.iterrows():
        key = frozenset(r["antecedents"]) | frozenset(r["consequents"])
        if key not in best or r["confidence"] > best[key]["confidence"]:
            best[key] = r

    combos: list[Combo] = []
    for key, r in best.items():
        ids = sorted(int(i) for i in key)
        if len(ids) == 3 and triple_lift(basket, ids) < MIN_TRIPLE_LIFT:
            continue  # one item is only along for the ride
        cls = [info.at[i, "class"] for i in ids]
        if "dog" in cls or not all(info.at[i, "available"] for i in ids):
            continue  # never promote a Dog
        prices = [int(info.at[i, "price_paise"]) for i in ids]
        costs = [int(info.at[i, "food_cost_paise"]) for i in ids]
        d, price = bundle_discount(prices, costs, floor)
        list_price, cost = sum(prices), sum(costs)
        sum_cm = list_price - cost
        discount_cost = list_price - price
        conf = float(r["confidence"])
        incremental = sum_cm * conf - discount_cost
        score = float(r["lift"]) * incremental * (1 - d)
        if "plowhorse" in cls and ("puzzle" in cls or "star" in cls):
            score *= MIX_BOOST
        anchors = sorted(int(i) for i in r["antecedents"])
        anchor_price = sum(int(info.at[i, "price_paise"]) for i in anchors)
        anchor_cm = sum(int(info.at[i, "cm_paise"]) for i in anchors)
        freq = anchor_freq.get(frozenset(anchors), float(r["antecedent support"]))
        combos.append(Combo(
            id=combo_id(ids), item_ids=ids, names=[info.at[i, "name"] for i in ids], anchor_ids=anchors,
            price_paise=price, list_price_paise=list_price, discount_pct=d, cm_paise=price - cost,
            cm_pct=round((price - cost) / price, 4), support=round(float(r["support"]), 4),
            confidence=round(conf, 4), lift=round(float(r["lift"]), 3),
            incremental_cm_paise=round(incremental), score=round(score / 100, 2),
            # Per order across all orders: anchor orders x adoption x what the combo adds over the anchor.
            aov_change_paise=round(freq * conf * (price - anchor_price)),
            margin_change_paise=round(freq * conf * ((price - cost) - anchor_cm)),
            evidence=plain_evidence(float(r["support"]), float(r["lift"])), classes=cls,
        ))
    combos.sort(key=lambda c: c.score, reverse=True)
    return combos, meta


def triple_lift(basket: pd.DataFrame, ids: list[int]) -> float:
    """min over items c of support(ABC) / (support(AB) * support(c))."""
    cols = basket[ids]
    s_all = cols.all(axis=1).mean()
    out = []
    for c in ids:
        rest = [i for i in ids if i != c]
        denom = cols[rest].all(axis=1).mean() * cols[c].mean()
        out.append(s_all / denom if denom else 0.0)
    return min(out)


def pair_rules(data: Dataset, window: int = 90) -> pd.DataFrame:
    """Single item -> single item rules for the upsell ranker, overall and per daypart."""
    w = data.window(window)
    out = []
    for daypart in [None, "lunch", "snack", "dinner"]:
        sub = w if daypart is None else _daypart(w, daypart)
        rules = mine_rules(baskets(sub), max_len=2)
        if rules.empty:
            continue
        rules = rules[(rules["antecedents"].map(len) == 1) & (rules["consequents"].map(len) == 1)].copy()
        rules["anchor_item_id"] = rules["antecedents"].map(lambda s: int(next(iter(s))))
        rules["offer_item_id"] = rules["consequents"].map(lambda s: int(next(iter(s))))
        rules["daypart"] = daypart
        out.append(rules)
    if not out:
        return pd.DataFrame(columns=["anchor_item_id", "offer_item_id", "daypart", "support", "confidence", "lift"])
    return pd.concat(out, ignore_index=True)[["anchor_item_id", "offer_item_id", "daypart", "support",
                                              "confidence", "lift"]]


def _daypart(w: Dataset, daypart: str) -> Dataset:
    ids = set(w.orders.loc[w.orders["daypart"] == daypart, "order_id"])
    return Dataset(w.items, w.orders[w.orders["order_id"].isin(ids)], w.lines[w.lines["order_id"].isin(ids)],
                   w.ingredients, w.recipes, w.as_of)
