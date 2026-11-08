# 03. Data model, seed data and PoS integration

Depends on: `02`.

## Schema (SQLite)

```sql
categories(id, name, kind)                      -- kind: starter|main|bread|rice|dessert|beverage|side
items(id, category_id, name, price, food_cost, veg BOOLEAN, spice_level, prep_minutes,
      available BOOLEAN, station, aliases_json)
modifier_groups(id, item_id, name, required, min_select, max_select)   -- Size, Spice, Add-ons
modifiers(id, group_id, name, price_delta, cost_delta)
orders(id, ts, channel, subtotal, discount, total, covers, daypart)    -- channel: dine_in|phone|takeaway
order_items(id, order_id, item_id, qty, unit_price, unit_cost, modifiers_json)
ingredients(id, name, unit, stock, reorder_level)                      -- optional
recipe_lines(item_id, ingredient_id, qty)                              -- optional
calls(id, started_at, ended_at, language, outcome, order_id, upsell_shown, upsell_accepted)
upsell_events(id, call_id, rule_id, item_id, shown_at, accepted, reason_json)
upsell_rules(id, anchor_item_id, offer_item_id, daypart, alpha, beta, lift, confidence, support)
pos_orders(id, idempotency_key, payload_json, status, kot_no, sent_at, ack_at, error)
```

Indexes on `orders(ts)`, `order_items(order_id)`, `order_items(item_id)`.

## Synthetic dataset generator (`seed/generate.py`)

Purpose: give the app a realistic restaurant without real data. It must produce patterns the engine can discover, so the results are meaningful, not random.

**Menu:** about 45 items across 7 categories of a North Indian and Indo-Chinese restaurant (paneer, dal, biryani, tandoor breads, rice, noodles, desserts, beverages). Each item has price in rupees and a food cost percentage between 22 and 48 percent.

**Orders:** 90 days, about 12,000 orders, with these built-in behaviours:
- Lunch and dinner peaks, weekend uplift, a Friday-evening spike.
- Baskets driven by affinities, for example main dish plus bread, biryani plus raita, pizza or burger plus a cold drink, dessert after a thali.
- 5 to 6 **puzzle** items: high margin, rarely ordered.
- 5 to 6 **plowhorse** items: very popular, thin margin.
- 4 to 5 **dog** items: low margin, low sales.
- 8 or more **stars**.
- 15 to 20 percent of orders on the `phone` channel.
- Day-to-day noise, a slow drift in popularity for a few items, and a few stock-out days.

Make the generator deterministic with a seed argument (`--seed 42`) and write `data/seed/tadka.sqlite` plus CSV exports.

## Lexicon files (`data/lexicon/`)

- `aliases.yaml`: per item, English, Hindi (Devanagari), Roman Hindi spellings and common mishearings. Example: `Paneer Butter Masala: [paneer butter masala, पनीर बटर मसाला, paneer makhani, butter paneer, paneer butter]`.
- `numbers.yaml`: Hindi and English number words, including Roman Hindi (`ek, do, teen, char, paanch...`), Devanagari (`एक, दो, तीन`), and fractions (`aadha, dedh, dhai`).
- `modifiers.yaml`: size, spice, add-on and exclusion vocabulary in all supported languages.
- `fillers.yaml`: words to strip (`um, uh, haan, matlab, please, bhaiya, sir`).
- `packs/mr.yaml`, `packs/gu.yaml`: optional Marathi and Gujarati additions with the same structure.

## CSV import

Screen: Settings, then Import data. Accept `items.csv` and `orders.csv` (or one combined export).

- Show a column-mapping step with auto-detected guesses.
- Validate rows and show a count of accepted and rejected rows with reasons.
- Food cost is required for margin. If it is missing, show a clear message: "Add food cost to see margin" and let the person set a default cost percentage per category.
- Re-run analytics after import and refresh the UI.

## PoS adapter interface

```python
class PosAdapter(Protocol):
    def get_menu(self) -> list[MenuItem]: ...
    def create_order(self, order: OrderPayload, idempotency_key: str) -> PosAck: ...
    def create_kot(self, order_id: str) -> KotAck: ...
    def get_order_status(self, pos_order_id: str) -> PosStatus: ...
```

- `MockPosAdapter` stores to `pos_orders`, assigns a KOT number, simulates 200 to 800 ms latency and a configurable failure rate for testing retry.
- `VendorAdapter` is a stub with the same interface and a mapping layer (item id mapping, modifier mapping, tax fields). Do not name or claim integration with any specific vendor until real credentials and docs exist.
- **Idempotency:** `idempotency_key = hash(call_id + final_cart_hash)`. Retrying never creates a duplicate KOT.
- **Retry:** exponential backoff, three attempts, then status `needs_attention` with the reason shown in the Orders screen.

## KOT format

```json
{
  "kot_no": "K-2041",
  "order_id": "ORD-8831",
  "channel": "phone",
  "created_at": "2026-10-11T13:42:10Z",
  "customer": { "name": "Rohan", "phone": "98XXXXXX10" },
  "lines": [
    { "item": "Paneer Butter Masala", "qty": 1, "mods": ["Medium spicy"], "station": "curry" },
    { "item": "Butter Naan", "qty": 4, "mods": [], "station": "tandoor" }
  ],
  "notes": "No onion in paneer",
  "total": 740
}
```

Group lines by `station` in the KOT so the kitchen sees tandoor, curry and beverage lines separately.

## Data hygiene rules

- Never store a customer's full phone number in logs; mask the middle digits.
- Money is stored as integer paise or as `Decimal`, never floats.
- Order totals are recomputed on the server; the client total is never trusted.
