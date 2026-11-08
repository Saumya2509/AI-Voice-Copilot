# 08. API contracts

Depends on: `02`, `03`, `04`, `05`. Base path `/api/v1`. JSON everywhere. The order and event schemas live in `packages/shared` and generate both Pydantic models and TypeScript types.

## Conventions

- Money in rupees as integers (whole rupees) or decimal strings with two places where paise matter.
- Timestamps are ISO 8601 in UTC.
- Errors: `{ "error": { "code": "string", "message": "What happened and what to do", "details": {} } }`.
- Every analytics response includes `window` (days) and `sample_size`.

## REST

### Menu and stats

| Method | Path | Purpose |
|---|---|---|
| GET | `/menu` | Items with modifiers and availability |
| GET | `/stats/items?window=30&category=` | Item stats and class (file 04) |
| GET | `/stats/summary?window=30` | AOV, profit, counts per class, upside estimate |
| GET | `/stats/lists/{kind}` | `puzzles`, `plowhorse_risk`, `underperformers` |

Example item stat:

```json
{
  "item_id": 12, "name": "Paneer Butter Masala", "category": "main",
  "price": 280, "food_cost": 98, "cm": 182, "cm_pct": 0.65,
  "units": 412, "velocity": 13.7, "popularity_index": 1.42,
  "class": "star", "reason": "Earns ₹182 per plate and sells 42 percent more than an average main.",
  "trend": "flat", "window": 30, "sample_size": 3812
}
```

### Combos and pricing

| Method | Path | Purpose |
|---|---|---|
| GET | `/combos?window=30` | Ranked combos with evidence |
| POST | `/combos/{id}/pool` | Add or remove from the offer pool |
| GET | `/pricing/recommendations` | Recommendations with ranges and confidence |
| POST | `/pricing/preview` | Body `{item_id, new_price}`, returns predicted units and profit |
| POST | `/pricing/apply` | Apply a price to the simulated PoS menu and log it |

### Calls and orders

| Method | Path | Purpose |
|---|---|---|
| POST | `/calls` | Start a call, returns `call_id` |
| GET | `/calls/{id}` | Call record, transcript, events (for replay) |
| GET | `/orders?channel=&status=` | Orders list |
| GET | `/orders/{id}` | Order JSON and PoS status |
| POST | `/orders/{id}/retry` | Retry a failed PoS send |
| GET | `/samples` | Sample call scripts |
| POST | `/nlu/parse` | Debug endpoint: parse one utterance with a cart |

### Settings and data

| Method | Path | Purpose |
|---|---|---|
| GET/PUT | `/settings` | Upsell policy, language packs, kitchen busy flag |
| POST | `/import/items`, `/import/orders` | CSV import with mapping |
| DELETE | `/calls` | Delete stored calls |

## WebSocket `/ws/call/{call_id}`

### Client to server

```json
{ "type": "transcript.partial", "text": "mujhe ek paneer", "lang_hint": "hinglish" }
{ "type": "transcript.final", "text": "mujhe ek paneer butter masala chahiye", "confidence": 0.86 }
{ "type": "ui.choice", "clarify_id": "c1", "option_id": 12 }
{ "type": "ui.offer", "offer_id": "o1", "action": "accept" }
{ "type": "ui.end" }
```

### Server to client

```json
{ "type": "state.changed", "state": "TAKING_ORDER" }
{ "type": "nlu.result", "intent": "add_item", "language": "hinglish",
  "matches": [{ "span": [2, 5], "item_id": 12, "score": 0.93 }] }
{ "type": "cart.updated", "cart": { "lines": [ ... ], "subtotal": 280 } }
{ "type": "clarify.ask", "clarify_id": "c1", "question": "...",
  "options": [{ "id": 12, "label": "Paneer Butter Masala" }, { "id": 14, "label": "Paneer Tikka Masala" }] }
{ "type": "upsell.offer", "offer_id": "o1", "item": { "id": 31, "name": "Garlic Naan", "price": 60 },
  "reason": { "headline": "Add Garlic Naan", "why": ["..."], "expected_gain": 54 } }
{ "type": "reply.say", "text": "Garlic naan goes well with that. Add one for ₹60?", "lang": "hinglish" }
{ "type": "order.finalized", "order": { ... } }
{ "type": "pos.sent", "order_id": "ORD-8831" }
{ "type": "pos.ack", "order_id": "ORD-8831", "kot_no": "K-2041" }
{ "type": "error", "code": "pos_unreachable", "message": "..." }
```

Rules: events are ordered, each carries a `seq` integer, and the client ignores events with an older `seq`. On reconnect the client sends the last `seq` and the server replays what was missed.

## Contract tests

- JSON Schema validation for every server event and for the order.
- A recorded sample call replayed through the WebSocket must produce the same event sequence on every run (seed the bandit sampler with a fixed seed in test mode).
