# 04. Revenue intelligence and menu optimization engine

Depends on: `03`. Everything here runs on the local database. No AI API.

## 1. Item statistics (`revenue/stats.py`)

For each item over a rolling window (default 30 days, configurable):

- `units`: total quantity sold.
- `velocity`: units per day, recency-weighted with an exponentially weighted moving average (half-life 10 days) so recent trends count more.
- `cm` (contribution margin, rupees) = `price - food_cost`.
- `cm_pct` = `cm / price`.
- `revenue` = `units * price`; `profit` = `units * cm`.
- `popularity_share` = item units divided by units in its category.
- `popularity_index` = `popularity_share * n_items_in_category` (1.0 means an average seller for its category).
- `attach_rate` = share of orders containing the item.
- `trend` = slope of weekly units over the last 6 weeks (up, flat, down).

Compute per category, because comparing a beverage to a biryani is meaningless.

## 2. Classification (menu engineering)

Per category, using the classic approach with plain names:

- Popular if `popularity_share >= 0.7 * (1 / n_items_in_category)`.
- High margin if `cm >= weighted_average_cm_of_category` (weighted by units).

| Popularity | Margin | Class | Plain meaning | Default action |
|---|---|---|---|---|
| High | High | **Star** | Sells well and earns well | Protect, feature, test a small price rise |
| High | Low | **Plowhorse** | Sells well, thin margin | Raise price slightly, cut portion cost, pair with high-margin side |
| Low | High | **Puzzle** | Earns well, not ordered enough | Promote, rename, reposition, offer as upsell |
| Low | Low | **Dog** | Neither | Rework or remove, never promote |

Return for each item: class, the two scores, and a one-sentence reason generated from templates, for example: "Earns ₹96 per plate, ordered 31 percent less than an average main."

### Specific detections (explicit lists in the UI)

- **High margin, low selling:** Puzzles ranked by `(cm - category_avg_cm) * (expected_uplift_units)`.
- **Underperforming SKUs reducing profitability:** items in Dog class, and items whose profit share is below their menu-space share, flagged with potential savings if removed.
- **Low margin, high volume risk:** Plowhorses where a 5 percent food-cost rise would wipe out more than 20 percent of the item's profit (sensitivity test).

## 3. Combo recommendation (`revenue/combos.py`)

1. Build baskets from `order_items` (set of item ids per order). Exclude single-item orders for rule mining.
2. Mine frequent itemsets with FP-Growth (`mlxtend`), minimum support 1 percent, maximum itemset size 3.
3. Generate rules and compute `support`, `confidence`, `lift`, `leverage`. Keep rules with `lift >= 1.2` and `confidence >= 0.15`.
4. Score each candidate combo:

```
combo_score = lift * incremental_cm_per_order * (1 - discount_penalty)
incremental_cm_per_order = sum(cm of items) * confidence_of_adoption - discount_cost
```

5. **Bundle pricing:** price = `sum(item_prices) * (1 - d)` where `d` is the largest discount in `{0, 5, 8, 10, 12}` percent that keeps combo `cm_pct >= max(0.55 * avg_menu_cm_pct, floor)`. If no discount keeps the floor, offer the combo with a free small item or no discount.
6. **Prefer combos that include a Puzzle or Star** next to a Plowhorse anchor, because they lift margin, not just volume.
7. Output each combo with: items, bundle price, estimated AOV change, margin change, and the evidence (support, confidence, lift in plain words: "Ordered together in 1 of 6 orders, 2.4 times more often than chance").

## 4. Price optimization (`revenue/pricing.py`)

Use a constant-elasticity model with defaults by class. These are **assumptions** and must be labelled as such in the UI, with the range shown.

| Class | Assumed elasticity | Typical suggestion |
|---|---|---|
| Star | -0.6 | Hold, or test +2 to 3 percent |
| Plowhorse | -0.8 | +3 to 7 percent, or trim portion cost |
| Puzzle | -1.2 | Reposition and promote first; small decrease only if volume stays low |
| Dog | -1.5 | Rework or remove |

For a proposed price change `dp` (fraction):

```
new_units = units * (1 + dp) ** elasticity
new_profit = (new_price - cost) * new_units
delta_profit = new_profit - old_profit
```

Guardrails: change limited to ±10 percent, round to the nearest ₹5, never push `cm_pct` below the category floor, and show a range using elasticity ±0.3.

Where a data-estimated elasticity is possible (the item had real price changes in the history), prefer it and mark it "Measured". Otherwise mark "Assumed".

## 5. Upsell prioritization (`revenue/upsell.py`)

At call time the dialogue manager asks the ranker for the best offer given the cart and context.

**Candidate generation:** offers come from `upsell_rules` (anchor item to offer item) and combo completions (add the one missing item of a combo).

**Hard filters (drop candidates that fail):**
- Item unavailable or out of stock.
- Already in the cart or already declined in this call.
- Veg conflict (veg cart should not be offered non-veg).
- Kitchen load high and `prep_minutes` above threshold (optional signal, see section 6).
- Offer budget used up (two offers per call).

**Score:**

```
score = P(accept) * incremental_cm * fit
P(accept)  = sample from Beta(alpha, beta) of the rule, seeded with confidence prior
incremental_cm = offer.cm (or combo incremental cm)
fit        = daypart_factor * class_boost * freshness
class_boost: Puzzle 1.25, Star 1.10, Plowhorse 0.90, Dog 0
```

**Learning:** after each offer, update the rule: accept adds 1 to `alpha`, decline adds 1 to `beta`. Initial `alpha = 1 + confidence * 10`, `beta = 1 + (1 - confidence) * 10`. This is Thompson sampling; exploration happens naturally.

**Explain every offer** with a `reason` object that the UI displays:

```json
{
  "headline": "Add Garlic Naan",
  "why": ["Ordered with Dal Makhani in 38% of orders", "Adds ₹54 margin", "Pairs with your current cart"],
  "expected_gain": 54
}
```

## 6. Inventory-linked signals (optional, advanced)

If `recipe_lines` and `ingredients` exist:
- **Push signal:** ingredient stock above 2 times reorder level and shelf-life short, boost items using it (small positive factor).
- **Hold signal:** ingredient below reorder level, suppress items that use it.
- **Kitchen load signal:** a simulated or manual "busy" toggle (and later, count of open KOTs) that suppresses slow-prep items.

Show active signals in the Settings screen and in the upsell reason ("Pushed: paneer stock is high").

## 7. Outputs (cached, refreshed on data change)

- `item_stats` table or in-memory frame.
- `classification` per item.
- `combos` list.
- `price_recommendations` list.
- `upsell_rules` table.
- `insights_summary`: current AOV, estimated monthly profit upside if top recommendations are applied, count of Puzzles, Dogs, Plowhorse risks.

Every number must include its window and sample size so the UI can show "based on 3,812 orders in the last 30 days".

## 8. Tests for the engine

- Unit tests for formulas with a tiny hand-calculated menu.
- Seed data must produce at least 5 Puzzles, 5 Plowhorses, 4 Dogs, 8 Stars; assert this in a test so generator changes cannot silently break the story.
- Combo test: the seeded affinities (dal plus bread, biryani plus raita) must appear in the top combos.
- Price test: `new_units` and `delta_profit` match a hand calculation for 3 items.
