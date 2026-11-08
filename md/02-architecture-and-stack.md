# 02. Architecture and stack

Depends on: `00`, `01`.

## Stack

| Layer | Choice | Why |
|---|---|---|
| Frontend | Vite, React 18, TypeScript | Fast dev loop, simple build |
| Styling | Tailwind CSS with CSS variables for tokens | Theme switching and consistent tokens |
| Motion | `motion` (Framer Motion) for layout and gestures, CSS for micro transitions | Layout animation for bubbles and lists |
| Physics | `d3-force` | Bubble field with real collision and drift |
| Charts | `d3` (scales, shapes) rendered in SVG, `recharts` only for simple trends | Full control over the menu field |
| State | Zustand | Small, no boilerplate |
| Audio | Web Audio `AnalyserNode` for the waveform | Live visual of the mic level |
| Offline STT | `vosk-browser` (WASM) with small `en-in` and `hi` models | No API, works offline |
| TTS | Browser `speechSynthesis` (hi-IN, en-IN voices) | Local, no API |
| Backend | Python 3.11, FastAPI, Uvicorn | Strong data and NLP libraries |
| Data | SQLite via SQLModel | Zero setup, portable |
| Analytics | pandas, numpy, mlxtend (FP-Growth), scipy | Association analysis and stats |
| NLU | rapidfuzz, scikit-learn (TF-IDF plus logistic regression), custom Indic phonetic keys | Local, explainable |
| Realtime | WebSocket (FastAPI) | Live transcript, ticket and upsell events |
| Validation | Pydantic on the server, JSON Schema shared with the client | One source of truth for order JSON |

Optional speech engine: browser Web Speech API behind a settings toggle, **off by default**, labelled "Uses your browser's speech service. Audio may leave this device." It exists only as a convenience; the default path stays fully offline.

## Components

```
Browser (apps/web)
  Mic -> Vosk WASM -> partial/final transcript
        |  WebSocket /ws/call/{id}
        v
FastAPI (apps/api)
  /nlu        normalize -> language -> intent -> items -> modifiers
  /dialogue   state machine, clarification, upsell injection, replies
  /revenue    classification, combos, pricing, upsell ranker, bandit
  /pos        adapter interface -> MockPoS (sqlite) | VendorAdapter
        |
        v
SQLite (items, orders, order_items, costs, calls, upsell_events, pos_orders)
```

## Realtime event flow for one call

1. Client opens `WS /ws/call/{call_id}`.
2. Client streams `transcript.partial` and `transcript.final` messages.
3. Server runs NLU on each final transcript and replies with events: `cart.updated`, `clarify.ask`, `upsell.offer`, `reply.say`, `state.changed`.
4. Client renders events and speaks `reply.say` through TTS.
5. On confirmation the server emits `order.finalized` (JSON), then `pos.sent` and `pos.ack`.

Keep each server turn under 300 ms on a laptop. The revenue tables (item stats, rules, upsell candidates) are precomputed and cached in memory; a call only reads them.

## Where telephony would plug in (not built)

A bridge service would receive call audio, run the same STT, and open the same WebSocket. The server contract does not change. Mention this in docs only.

## Folder structure (apps/api)

```
apps/api/
  main.py                # FastAPI app, routers
  db.py, models.py
  seed/generate.py       # synthetic data generator (file 03)
  revenue/
    stats.py             # margin, popularity, velocity
    classify.py          # menu engineering classes
    combos.py            # FP-Growth, lift, combo pricing
    pricing.py           # elasticity based recommendations
    upsell.py            # ranker and Thompson sampling
  nlu/
    normalize.py         # numbers, script, fillers
    language.py
    phonetic.py          # Indic-aware keys
    matcher.py           # alias + phonetic + fuzzy
    modifiers.py
    intent.py            # TF-IDF + LR, plus rules
    train_intent.py
  dialogue/
    manager.py           # state machine
    templates.py         # en / hi / hinglish replies
  pos/
    adapter.py           # interface
    mock_pos.py
    kot.py
  schemas/order.schema.json
```

## Folder structure (apps/web)

```
apps/web/src/
  app/            # routes, layout, theme provider
  features/
    call-desk/    # mic, waveform, transcript, ticket, upsell card, rupee meter
    menu-field/   # bubbles, side sheet, what-if slider
    combos/       # graph and combo builder
    pricing-lab/
    orders/       # PoS sync log and JSON viewer
    insights/     # call replay and uplift
    settings/
  components/     # rail, buttons, toasts, ticket, number-tween
  lib/            # api client, ws client, stt, tts, format
  styles/         # tokens.css, type.css
```

## Non-functional targets

- Cold start of API with seed data under 5 seconds.
- First meaningful paint of the web app under 1.5 seconds on a laptop.
- No network access required after install (models bundled in `public/models`).
- All timestamps stored in UTC, shown in the restaurant's local time.
