"""Cached revenue engine (file 04, section 7). Tables are computed once per data version and
read by API requests and live calls; a call never recomputes analytics."""
from __future__ import annotations

import threading
from pathlib import Path

import numpy as np
import pandas as pd
from sqlmodel import Session, select

import db
import settings
import settings_store
from models import UpsellRule
from revenue import cache, classify as cls_mod, combos as combos_mod, pricing as pricing_mod, signals as signals_mod
from revenue.data import Dataset, load
from revenue.upsell import PoolCombo, Ranker, Rule, prior

RULE_WINDOW = 90
DEFAULT_POOL_SIZE = 3


class Engine:
    def __init__(self, db_path: Path | str):
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        self._version = -1
        self._memo: dict = {}
        self._rules: list[Rule] | None = None

    # ----- cache plumbing ----------------------------------------------------------

    def _check(self) -> None:
        if self._version != cache.version():
            self._memo.clear()
            self._rules = None
            self._version = cache.version()

    def _get(self, key, build):
        with self._lock:
            self._check()
            if key not in self._memo:
                self._memo[key] = build()
            return self._memo[key]

    # ----- tables ------------------------------------------------------------------

    def data(self) -> Dataset:
        return self._get("data", lambda: load(self.db_path))

    def classes(self, window: int = 30) -> pd.DataFrame:
        from revenue.stats import item_stats
        return self._get(("classes", window), lambda: cls_mod.classify(item_stats(self.data(), window)))

    def combos(self, window: int = 30):
        return self._get(("combos", window), lambda: combos_mod.recommend(self.data(), self.classes(window), window))

    def pricing(self, window: int = 30) -> list[dict]:
        return self._get(("pricing", window),
                         lambda: pricing_mod.recommendations(self.data(), self.classes(window), window))

    def graph(self, window: int = 30) -> dict:
        return self._get(("graph", window), lambda: self._graph(window))

    def _graph(self, window: int) -> dict:
        w = self.data().window(window)
        rules = combos_mod.mine_rules(combos_mod.baskets(w), max_len=2)
        df = self.classes(window).set_index("item_id")
        edges: dict[tuple[int, int], dict] = {}
        for r in rules.itertuples():
            a, b = int(next(iter(r.antecedents))), int(next(iter(r.consequents)))
            key = (min(a, b), max(a, b))
            e = edges.setdefault(key, {"source": key[0], "target": key[1], "lift": float(r.lift),
                                       "support": float(r.support), "confidence": 0.0})
            e["confidence"] = max(e["confidence"], float(r.confidence))
        ids = sorted({i for k in edges for i in k})
        nodes = [{"id": i, "name": df.at[i, "name"], "class": df.at[i, "class"], "category": df.at[i, "category"],
                  "units": int(df.at[i, "units"])} for i in ids]
        return {"window": window, "sample_size": int(len(w.orders)), "nodes": nodes,
                "edges": [{**e, "lift": round(e["lift"], 3), "support": round(e["support"], 4),
                           "confidence": round(e["confidence"], 4)} for e in edges.values()]}

    def weekly_units(self, item_id: int, weeks: int = 12) -> list[dict]:
        data = self.data()
        if data.as_of is None:
            return []
        out = []
        lines = data.lines[data.lines["item_id"] == item_id]
        for k in range(weeks, 0, -1):
            end = data.as_of - pd.Timedelta(weeks=k - 1)
            start = end - pd.Timedelta(weeks=1)
            units = int(lines[(lines["ts"] > start) & (lines["ts"] <= end)]["qty"].sum())
            out.append({"week_ending": end.date().isoformat(), "units": units})
        return out

    def summary(self, window: int = 30) -> dict:
        return self._get(("summary", window), lambda: self._summary(window))

    def _summary(self, window: int) -> dict:
        w = self.data().window(window)
        df = self.classes(window)
        n = len(w.orders)
        profit = int(((w.lines["unit_price_paise"] - w.lines["unit_cost_paise"]) * w.lines["qty"]).sum())
        counts = df["class"].value_counts().to_dict()
        price_upside = sum(max(0, r["delta_profit_paise"]) for r in self.pricing(window)[:5])
        puzzle_upside = float(cls_mod.puzzles(df)["potential_gain_paise"].clip(lower=0).sum())
        risk = cls_mod.plowhorse_risk(df)
        return {
            "window": window, "sample_size": n,
            "aov_paise": int(w.orders["total_paise"].mean()) if n else 0,
            "revenue_paise": int(w.orders["total_paise"].sum()),
            "profit_paise": profit,
            "orders_per_day": round(n / window, 1),
            "class_counts": {c: int(counts.get(c, 0)) for c in ("star", "plowhorse", "puzzle", "dog")},
            "plowhorse_risk_count": int(risk["at_risk"].sum()),
            "upside": {
                "monthly_paise": round(price_upside + puzzle_upside),
                "from_pricing_paise": round(price_upside),
                "from_promoting_puzzles_paise": round(puzzle_upside),
                "basis": "Top 5 price recommendations plus promoting Puzzles halfway to the popularity line. "
                         "Elasticities are assumptions unless marked Measured.",
            },
        }

    # ----- upsell rules ------------------------------------------------------------

    def rules(self) -> list[Rule]:
        with self._lock:
            self._check()
            if self._rules is None:
                self._rules = self._sync_rules()
            return self._rules

    def _sync_rules(self) -> list[Rule]:
        mined = combos_mod.pair_rules(self.data(), RULE_WINDOW)
        engine = db.get_engine(self.db_path)
        with Session(engine) as s:
            existing = {(r.anchor_item_id, r.offer_item_id, r.daypart): r for r in s.exec(select(UpsellRule))}
            seen = set()
            for row in mined.itertuples():
                key = (int(row.anchor_item_id), int(row.offer_item_id), row.daypart if row.daypart else None)
                seen.add(key)
                rule = existing.get(key)
                if rule is None:
                    a, b = prior(float(row.confidence))
                    rule = UpsellRule(anchor_item_id=key[0], offer_item_id=key[1], daypart=key[2], alpha=a, beta=b)
                rule.lift, rule.confidence, rule.support = float(row.lift), float(row.confidence), float(row.support)
                s.add(rule)
            for key, rule in existing.items():
                if key not in seen:  # no longer supported by the data; kept for history, never offered
                    rule.lift = rule.confidence = rule.support = 0.0
                    s.add(rule)
            s.commit()
            return [Rule(r.id, r.anchor_item_id, r.offer_item_id, r.daypart, r.alpha, r.beta, r.lift,
                         r.confidence, r.support) for r in s.exec(select(UpsellRule))]

    def learn(self, rule_id: int, accepted: bool) -> None:
        """Thompson sampling update: accept adds 1 to alpha, decline adds 1 to beta."""
        with Session(db.get_engine(self.db_path)) as s:
            row = s.get(UpsellRule, rule_id)
            if row is None:
                return
            if accepted:
                row.alpha += 1
            else:
                row.beta += 1
            s.add(row)
            s.commit()
            a, b = row.alpha, row.beta
        with self._lock:
            for r in self._rules or []:
                if r.id == rule_id:
                    r.alpha, r.beta = a, b

    # ----- combo pool, signals, ranker --------------------------------------------

    def pool(self, session: Session) -> list[PoolCombo]:
        combos, _ = self.combos(30)
        chosen = settings_store.get(session, "combo_pool")
        if chosen is None:
            picked = combos[:DEFAULT_POOL_SIZE]
        else:
            picked = [c for c in combos if c.id in set(chosen)]
        return [PoolCombo(c.id, c.item_ids, c.names, c.price_paise, c.list_price_paise, c.confidence) for c in picked]

    def signals(self, session: Session) -> signals_mod.Signals:
        conf = settings_store.get_all(session)
        return signals_mod.compute(self.data(), conf["inventory_signals"], conf["kitchen_busy"],
                                   conf["upsell"]["slow_prep_minutes"])

    def ranker(self, session: Session) -> Ranker:
        return Ranker(self.classes(30), self.rules(), self.pool(session), self.signals(session))

    def warm(self) -> None:
        self.classes(30)
        self.combos(30)
        self.pricing(30)
        self.rules()


_engines: dict[str, Engine] = {}
_glock = threading.Lock()


def get_engine(db_path: Path | str | None = None) -> Engine:
    path = str(db_path or settings.DB_PATH)
    with _glock:
        if path not in _engines:
            _engines[path] = Engine(path)
        return _engines[path]


def rng_for(call_id: str | None) -> np.random.Generator:
    """Seeded sampler in deterministic mode so recorded calls replay identically."""
    if settings.DETERMINISTIC and call_id:
        import zlib
        return np.random.default_rng(zlib.crc32(call_id.encode()))
    return np.random.default_rng()
