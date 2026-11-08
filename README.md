# Tadka

Tadka reads a restaurant's PoS history to find where money is being left on the table, then uses those findings live on the phone: it takes orders in English, Hindi or Hinglish, offers upsells backed by data, and sends a clean order and KOT to the PoS.

Everything runs locally. Tadka makes no calls to hosted AI services. Its models are rules, statistics and a small scikit-learn classifier.

The product spec is in [md/](md/), files `00` to `09`, with [md/improve.md](md/improve.md) applied on top (it overrides earlier files where they conflict).

## What works today

Files `00` to `09` and `improve.md` are built. The web app has the improve.md identity, top navbar, landing page and public menu; the call desk has the menu panel and the bottom ticket tray; analytics come from CSV upload; orders are live; combos are text only; transcripts display in English; calls can be recorded.

| Area | Where |
|---|---|
| Web app: Landing, Menu, Call desk, Analytics, Upload, Combos, Orders, Recordings, Pricing lab, Settings | `apps/web/` |
| Design tokens (improve.md, section 6), light and dark | `apps/web/src/styles/tokens.css` |
| CSV upload: preview, mapping, validation, default food cost, sample restaurant | `apps/api/upload.py`, `apps/web/src/features/upload/` |
| Analytics with filters and cross filtering | `apps/api/revenue/analytics.py`, `apps/web/src/features/analytics/` |
| English display of what the caller said | `apps/api/nlu/gloss_en.py`, `data/lexicon/gloss_en.yaml` |
| Live orders (server-sent events), call recordings | `apps/api/events_bus.py`, `apps/api/routes_calls.py` |
| Offline speech in the browser (Vosk Web Worker), spoken replies (speechSynthesis) | `apps/web/src/lib/stt.ts`, `tts.ts` |
| SQLite schema, seeded restaurant (45 items, 90 days, about 12,000 orders) | `apps/api/models.py`, `apps/api/seed/` |
| Revenue engine: stats, classes, detections, combos, pricing, upsell ranker, signals | `apps/api/revenue/` |
| NLU and dialogue manager (English, Hindi, Hinglish) | `apps/api/nlu/`, `apps/api/dialogue/` |
| PoS adapter, built-in PoS, KOT, idempotent push with retry; CSV import | `apps/api/pos/`, `apps/api/importer.py` |
| Shared JSON Schemas (order, KOT, server events) and TypeScript types | `packages/shared/` |
| Voice test set (84 cases), three sample calls, screenshot script | `apps/api/tests/utterances.yaml`, `data/samples/`, `apps/web/scripts/shots.mjs` |

## Run it

You need Python 3.11 or newer and Node 18 or newer.

```
make install     # Python venv, API and web dependencies, shared types, intent model, speech models (about 80 MB)
make seed        # writes the sample restaurant to data/seed (tests and development only)
make dev         # API on :8000 and the web app on http://localhost:5173
make test        # API tests, web tests and the TypeScript check
make train       # retrain the intent model (after menu or template changes)
make eval        # run the voice test set: item and intent accuracy, latency
make simulate    # play the three sample calls in the terminal
make shots       # screenshots of every screen, light and dark, 1440 and 390 px (needs make dev)
                 # also captures the real-UI crops used on the landing page
cd apps/web && npm run test:ui   # improve.md acceptance checks in a browser (needs make dev)
make models      # download the offline speech models again
```

If `make` isn't installed (common on Windows), run `python tasks.py <task>` with the same task names.
- Seed options pass through, for example `python tasks.py seed --end-date 2026-10-10`.
- `python tasks.py simulate --say "ek dal makhani|bas|haan"` plays your own lines, separated by `|`.

**Your data, not sample data.** The app reads and writes `data/tadka.sqlite`. On first start it holds the built-in restaurant menu (45 dishes with aliases, modifiers and recipes) and no orders, so the Call desk works straight away. Orders, Analytics, Recordings and combos show only the sales you upload and the calls you take. To try Analytics, download `data/samples/sample-sales.csv` (also linked on the Upload page as "Download a sample sales CSV"): 3,059 orders, 2 Aug to 30 Sep 2026, every row a dish on the menu. Set `TADKA_PRELOAD_MENU=0` to start with no menu at all. The generated sample restaurant lives separately in `data/seed` and is never shown unless you point the API at it on purpose: `TADKA_DB=data/seed/tadka.sqlite`. Use that for development, and for `make shots` and `npm run test:ui`, which place test orders.

If the database or intent model is missing when the API starts, the API creates it (an empty database). Without the speech models, the call desk still works with Typed input and sample calls, and says so.

## Current results (seed 42)

- **Voice test set:** 100% item accuracy and 100% intent accuracy on 84 cases. The English display matches exactly on 95% of them. Parse time p95 is about 5 ms.
- **Intent model:** 98% on its held-out template set.
- **Server turn latency:** p95 about 40 ms across the sample calls, excluding the built-in PoS's simulated network delay.
- **All three sample calls finish with a KOT:**
  - the Hinglish call has one clarification and one accepted offer;
  - the Hindi call removes an item, changes the spice level, and declines an offer;
  - the English call has one clarification and accepts a combo that completes a set.
- **Seed classes:** 28 stars, 6 plowhorses, 6 puzzles and 5 dogs. Biryani plus raita and dal plus bread appear in the top combos.
- **Imports:** a 53,000-line sales CSV imports in about 2.5 s. Loading the sample restaurant takes about 8 s.
- **Live orders:** a new order appears in Orders about 1.1 s after it is placed, most of which is the built-in PoS's simulated delay. The order event itself arrives in under 0.2 s.

## The seeded restaurant

The seed is a North Indian and Indo-Chinese restaurant. The same `--seed` and `--end-date` always produce the same database.
- **Classes:** the menu is designed so the classifier finds the class listed for each item in `seed/menu.py`, on the 30, 60 and 90 day windows.
- **Affinities:** biryani with raita, curries with their usual breads (dal makhani with butter naan, dal tadka with roti and rice), Indo-Chinese with Manchurian and a cold drink, and thali followed by gulab jamun.
- **Time patterns:** lunch and dinner peaks, a weekend uplift, a Friday-evening spike, daily noise, slow popularity drift for a few items, and a few stock-out days.
- **Inventory:** paneer stock is high (a push signal) and mango pulp is low (a hold signal).

## Live calls over WebSocket

1. `POST /api/v1/calls` returns a `call_id`.
2. Open `WS /ws/call/{call_id}`. The server sends `state.changed` and a greeting.
3. Send `transcript.final` messages. Typed input uses the same message.
4. The server answers with `nlu.result`, `cart.updated`, `clarify.ask`, `upsell.offer`, `reply.say`, `order.finalized`, `pos.sent` and `pos.ack`. Each event carries an increasing `seq`.
5. Buttons send `ui.choice` and `ui.offer`. `ui.end` ends the call.
6. After speaking a reply, the client sends `ui.listening`, which restarts the silence timer: a reprompt after 6 s and the call abandoned after 20 s.
7. On reconnect, the client sends `{"type": "resume", "last_seq": n}` to replay what it missed.

`GET /api/v1/calls/{id}` returns the stored transcript and events for replay. Phone numbers are masked before anything is stored.

## Choices made where the spec left room

**Data and money**
- Money is stored as integer paise, in columns ending in `_paise`. API responses and the order JSON use rupees.
- Columns added beyond file 03:
  - `orders.external_ref` (the order id from an imported export);
  - `calls.transcript_json` and `calls.events_json`;
  - `pos_orders.order_id`, `kot_json` and `attempts`.
- New tables: `app_settings` and `price_changes`.
- Older databases gain the new columns automatically at startup.
- Analytics windows end at the newest order in the database, not at today's date.

**Combos**
- Itemsets come from mlxtend's apriori, not FP-Growth. Both return the same frequent itemsets, but mlxtend's FP-Growth took 7 to 16 seconds per run on this data, against 0.25 s for apriori. That matters for the 5-second cold start.
- Redundant rules are pruned (minimum confidence improvement of 0.05).
- A 3-item combo must have every item associated with the other two (conditional lift of at least 1.3), so a passenger item can't ride along.
- Combos containing a Dog are never offered.
- Bundle prices end in 9.
- Until the owner chooses, the top three combos form the offer pool.

**Detection assumptions** (each is returned with its list)
- Promoting a Puzzle closes half its gap to the popularity line.
- If an item is removed, 80% of its buyers switch to another item in the category.
- The plowhorse risk test is a 5% food-cost rise. With seed margins, no plowhorse crosses the 20% threshold, so the list is ranked by rupee exposure and flags `at_risk`.

**Pricing**
- Suggested moves: Stars +3%, Plowhorses +5%; Puzzles hold; Dogs are reworked, not repriced.
- Margin is never pushed below 90% of the category's margin.
- Elasticity is "Measured" only when an item sold at two or more prices for at least two weeks each.

**Upsell**
- Offers happen when the guest says they're done, or asks for a recommendation.
- A combo that one more item would complete is offered before a single-item offer.
- No second main is offered once a main is on the order.
- An accepted item with a required choice gets the standard option (Full).
- The sampler is seeded from the call id when `TADKA_DETERMINISTIC=1`, so recorded calls replay identically.

**Language**
- Devanagari input is `hi`.
- Roman text with Hindi words is `hinglish`, even when no English words appear. Replies in Roman Hindi suit people who type or speak that way.
- Marathi and Gujarati packs add words, and their replies fall back to Hinglish until the packs ship templates.

**Endpoints and the built-in PoS**
- `POST /orders` is an addition to file 08. It finalizes an order through the same service the dialogue uses.
- The built-in PoS reads `TADKA_POS_FAILURE_RATE` (default 0) and `TADKA_POS_MIN_LATENCY_MS` and `TADKA_POS_MAX_LATENCY_MS` (default 200 and 800).

## Design: heritage fine dining

The whole interface was redesigned at the owner's request to feel classic: like the menu of a grand Indian restaurant.

- **Palette** (`apps/web/src/styles/tokens.css`): ivory paper (`#F7F1E3`), cream panels, deep brown-black text, maroon (`#7A1F2B`) for primary actions, links and the active page, and antique gold (`#B8892B`) for rules, ornaments and highlights. Dark theme: maroon-black with candlelit ivory text, and gold becomes the primary. Token names are unchanged (`indigo` is the maroon primary, `haldi` the gold; `maroon` and `gold` are aliases), so every screen follows the theme. Chart and class colours keep their meanings (green Stars, blue Plowhorses, plum Puzzles, red Dogs).
- **Type:** Cormorant Garamond for headings (lining numerals), Mukta for the interface (it has Devanagari), Share Tech Mono on the kitchen ticket. Hindi in a heading falls back to Rozha One.
- **Detailing:** gold double hairlines under page titles ending in a ❖ ornament, gold double rules above menu sections, gold dotted leaders, a faint laid-paper grain on the background, maroon buttons with a fine gold edge, and cards on cream with a soft warm shadow.
- **Navbar:** ❖ Tadka in Cormorant, maroon links with a sliding gold underline for the active page, gold double hairline beneath.
- **Landing:** a maroon hero framed in gold with corner ornaments, an italic gold second line, gold and ivory buttons; Roman numerals for the steps; screen crops framed like pictures; a maroon footer. The hero and footer stay maroon in both themes, like signage.
- **Checked:** every screen in light and dark at desktop and phone width (`npm run shots`: no page errors, no horizontal scroll); WCAG AA contrast for text (gold is used for ornaments and highlights behind dark text, not for body text on ivory).

## improve.md: what changed and why

**Design process.** improve.md asks for the frontend-design skill's plan and review again. That skill is still not in this repo, so the installed web-design-engineer skill's process was used:
- **Design read:** a working tool for a restaurant, plus a public page.
  - Visual language: hand-painted dhaba signboards and printed menu cards.
  - Dials: variance 6, motion 3, density 6, asset dependence 2, fidelity to the improve.md spec 9.
- **Plan:** the palette, type and shape rules of improve.md section 6, used as written. Rozha One for display, Mukta for the interface, and Share Tech Mono on the ticket.
- **Review against the brief:**
  - No cards with coloured side stripes: the offer card uses a Haldi price-tag corner instead.
  - No gradients or soft shadows on panels: hairline rules and the thick-thin double rule under titles.
  - No identical feature cards on the landing page. The sections vary in rhythm: a full-width band, a numbered sequence, an uneven split, then a plain list.
  - No invented figures, logos or quotes. The hero ticket prints real menu prices. The owner section shows real charts, or an upload prompt when there is no data. The language examples are translated live by Tadka's own gloss.
- **Critique pass:** screenshots of every screen in light and dark, at 1440 and 390 px. What was found and fixed:
  - The offer card was hidden by the tray. It now sits just above the tray.
  - The landing crops were unreadable. They are now tight crops of the transcript, the offer card and the order drawer.
  - Analytics overflowed on phones by 36 px.
  - The class and veg legends were truncated.
  - The scatter's labels scaled up too far.
  - The tray's buttons were unreadable on paper in dark mode.
  - The Combos page was too long. It now shows 20 combos with "Show more".

**Decisions where improve.md left room**
- **Dish photos (main Menu only):** each built-in dish has a photo from Wikimedia Commons under a free licence (CC0, public domain, CC BY or CC BY-SA), chosen by hand from search results, cropped to 4:3 and stored in `apps/web/public/dishes` (`python tasks.py photos` downloads them again; the app itself never contacts Wikimedia). Author and licence for each are in `credits.json` and under "Photo credits" on the Menu page. The Call desk menu shows no photos, to stay compact.
- **Built-in menu:** a fresh database gets the restaurant menu at startup (only when it has no dishes), with no orders. Analytics and the landing owner section show upload prompts until a sales CSV is imported.
- **Sample data removed from the UI:** at your request, the "Load sample restaurant" buttons and the scripted sample-call player are gone, so only real uploads and real calls appear. The `/import/sample` and `/samples` endpoints remain for tests and development. `GET /import/sample-csv` serves the sample sales CSV (an addition beyond improve.md).
- **Sales CSV is for Analytics only:** each row is matched to a menu dish by name or alias, ignoring case; rows naming a dish that is not on the menu are rejected with "item not on the menu". The row's price and food cost are used for that line; a missing food cost falls back to the dish's cost. Importing replaces the orders and keeps the menu. If there is no menu (`TADKA_PRELOAD_MENU=0`), the CSV builds the menu as before.
- **Upload replaces orders:** importing a sales CSV replaces the order history. Calls, transcripts and recordings are kept; their link to an order is cleared, and offer statistics restart with the new data.
- **Duplicate rows:** a row counts as a duplicate only if every column repeats.
- **Missing columns:**
  - Without a veg column, veg marks are guessed from item names, and the preview says so.
  - Without a category column, everything goes in one category, Menu.
  - Without a channel column, every order is counted as dine-in.
- **Estimated margins:** charts say "Estimated" when any food cost came from a default percentage.
- **Revenue on Analytics** is item sales before order-level discounts, so category, veg and item figures add up to the total.
- **Analytics filters:** beyond those listed in improve.md, they also take `weekday` and `hour`, so a heatmap cell can filter the page. Clicking a top-item bar opens the item panel, because items are not a filter.
- **English gloss:** it covers ordering language. It scores 95% exact on the 84 test utterances; the target is 90%. The misses are repeated words ("ek ek", "do do"), a misspelling the matcher only partly covers ("masla"), and Hindi word order ("Dal Makhani 1"). Unknown words are shown in italic Roman text.
- **Staff-added items:** added from the menu, they are `source: staff`, a new value in the order schema. The tray's Send to PoS places the order at once, without name or phone. Confirm order runs the normal confirmation, which may make an offer first.
- **Chef's pick:** a Puzzle or Star whose margin is at least 15% above its category average, at most one per category.
- **Insights screen:** its results (order value with and without offers, offers accepted) now head the Recordings screen.
- **Call replay:** it lives in Recordings.
- **Call desk layout:** every call control sits in one toolbar at the top: call button, timer, status, a compact waveform, the language heard, language, input and mute. Below it are three columns: the conversation (with a three-step guide before a call), the restaurant menu, and the ticket in the top-right corner, so the ticket never covers the menu. The ticket is a portrait kitchen order ticket that feeds down from a printer slot; Confirm order and Send to PoS stay pinned at the bottom of its column. On phones the three are tabs, and the Ticket tab shows the item count and total. The menu uses the Menu section's printed-card design: category headings under a double rule, veg mark, spice marks, dotted leader, price and a one-line description, in two columns when the panel is wide. A category bar jumps through the menu and marks the current category; search also matches aliases. Tapping a dish adds it (and starts a call if none is running); a dish on the ticket shows a quantity stepper. Combos come first in the menu: the ones the agent offers on calls (chosen on the Combos page), each with its bundle price against the separate prices. One tap puts every dish on the ticket at the combo price (client message `ui.add_combo`); the lines keep source `staff` with the combo id, so a hand-added combo never counts as an accepted offer.
- **Natural voice:** the agent speaks with Piper, a neural voice that runs on this computer (`GET /tts?text=…&lang=en|hi` returns WAV; nothing leaves the machine). Two voices: Hindi (`hi_IN-priyamvada-medium`) and English (`en_US-lessac-medium`), about 60 MB each in `data/models/piper`, downloaded by `python tasks.py models` (choose others with `TADKA_VOICE_HI` and `TADKA_VOICE_EN`). Hinglish written in Roman letters sounds wrong read by a Hindi voice, so every reply also carries a Devanagari form: `reply.say` has `speech_text` and `speech_lang`, and Hindi and Hinglish calls are spoken from Devanagari, with dish names left in English, which the voice reads the English way. The API loads the voices at startup; a new sentence takes about 0.3 s and repeated sentences come from a cache. If the natural voice is off (Settings: Agent's voice), not installed, or slow to answer (2.5 s), the browser's own voice speaks instead.
- **Caller can cut in (barge-in):** with offline speech the microphone stays open while the agent speaks. When the caller speaks over it, the agent stops at once and listens (`ui.barge_in`), and that reply is marked "(caller cut in)" in the transcript and as a marker on the recording. The agent's own voice coming back through the speakers is not mistaken for the caller: speech that mostly repeats the words being spoken is ignored, a partial result needs two words and a loud enough microphone, and the browser's echo cancellation is on. Typing over the agent stops it too. Turn it off in Settings (Let callers interrupt) if loud speakers make the agent stop itself; push to talk also turns it off.
- **Confirmed orders:** under the conversation, today's orders placed through Tadka (`GET /orders?source=tadka&from=…&with_items=true`), newest first, with KOT number, time, dishes, total and PoS status ("Sending to the PoS", "In the kitchen", or "Not sent" with Send again). It refreshes on the live order stream, so an order appears as soon as it is sent and the current call's order is marked.
- **Listening:** offline speech runs two recognisers on the same Vosk model, an open one and one restricted to the restaurant's ordering vocabulary (`GET /nlu/vocabulary?lang=en|hi`: menu names and aliases, numbers, spice and size words, yes/no, "that's all", in Latin for the English model and Devanagari for the Hindi one). Each utterance is sent with both transcripts (`transcript.final.alternatives`); the server parses both and keeps the menu-biased one only when it finds clearly more (one more dish, or a known intent), never while taking a name, phone or address. The parser also reads recogniser homophones next to a dish ("to butter naan" is 2, "for garlic naan" is 4; not after price words, and "to" never in Hindi or Hinglish where it is "toh"), and knows more ways to finish ("that is it", "I'm done", "bas itna kafi hai"). The voice test set has 12 recogniser-style cases.
- **Recording:** it uses `MediaRecorder` on the same microphone stream as speech recognition, so it only works with Offline speech. It is off until switched on in Settings.

## API contract (file 08)

- **Base path and docs:** the base path is `/api/v1`. Interactive docs are at `/docs`. The OpenAPI document is exported to [packages/shared/openapi.json](packages/shared/openapi.json).
- **Money:** whole rupees as integers, or two-decimal strings where paise matter (`"aov": "928.13"`), never floats. The web client turns those strings into numbers in one place (`src/lib/api.ts`).
- **Timestamps:** ISO 8601 in UTC, for example `2026-10-11T13:42:08Z`. The shared schemas enforce this with a pattern.
- **Errors:** always `{"error": {"code", "message", "details"}}`. This covers 404, 405, 422 and unhandled 500s, and the message says what to do.
- **Analytics responses** carry `window` and `sample_size`. Insights cover every call, so their `window` is `null`.
- **Generated models:** the order and KOT schemas in `packages/shared/schemas` generate both the TypeScript types and the Pydantic models (`apps/api/schemas/generated`), so the server and the client share one source of truth. `make types` regenerates both, plus the OpenAPI export.
- **WebSocket `/ws/call/{call_id}`:**
  - Events are ordered and carry an increasing `seq`.
  - The client sends `{"type": "resume", "last_seq": n}` after reconnecting, and the server replays what was missed.
  - A malformed or unknown message gets an `error` event (`bad_message`) in sequence, and the call carries on.
  - Two client messages are additions, both documented: `ui.listening` restarts the silence timer, and `resume`.
- **improve.md routes:** import (template, preview, commit, sample), `/analytics/*`, `/orders/stream`, `/public/menu`, `/calls` with filters, `/calls/{id}/transcript`, and `/calls/{id}/recording`.
- **Other additions:** `GET /health`, `POST /orders`, `GET /orders/export`, `GET /stats/items/{id}/trend`, `GET /combos/graph`, `GET /insights`, `GET /analytics/items`, `GET /analytics/lists/{kind}`, `POST` and `DELETE /calls/{id}/recording`, and `DELETE /calls/{id}`.
- All routes are listed in `apps/api/contract.py`, and the contract tests fail if an unlisted route appears.
- **New WebSocket messages:**
  - Client: `ui.add_item`, `ui.confirm`, `ui.send`.
  - Server: `transcript` (with `display_text_en`) and `menu.highlight`. `reply.say` and `clarify.ask` now carry English text too.
- **Contract tests** (`apps/api/tests/test_contract.py`) check that:
  - every route in file 08 exists, and nothing else is exposed apart from the listed additions;
  - money formats are correct across the API;
  - analytics responses carry `window` and `sample_size`;
  - the error envelope is used throughout;
  - bad WebSocket messages are handled;
  - the generated models and the OpenAPI export are current;
  - a recorded sample call replayed over the WebSocket gives the same event sequence on every run, with every event valid against the shared schema.

## Web app notes

- **Removed per improve.md:** the sidebar, the force-laid-out Menu field screen, the combo network graph and the Insights screen. The UI acceptance check confirms no sidebar code remains and that Combos has no chart, graph or node element.
- **Ticket before acknowledgement:** it reads "KOT pending", because the PoS assigns the number on acknowledgement. The header prints the restaurant name from Settings, or "Kitchen order ticket" when none is set.
- **Analytics axes:** the scatter plots popularity and margin relative to each item's own category thresholds, so the dashed lines at 1 are the real menu-engineering lines for every category.
- **Guardrails off (Pricing lab):** shows the model's profit-maximising price. For inelastic items the model has no maximum, so the price is shown capped at 30%, with a note saying so.
- **Speech models:** the English model comes from the vosk-browser model mirror. The Hindi model is downloaded from alphacephei.com as a zip and repacked to the tar.gz that vosk-browser loads.
- **Speech engine:** recognition runs on a `ScriptProcessorNode`, which is what vosk-browser expects. Browsers deprecate it but still support it; an AudioWorklet port is a later improvement.
- **Code splitting:** each route is code-split, and the speech engine (5.8 MB with its WASM) loads only when an offline-speech call starts.
- **Live updates:** they use one `EventSource` on `/orders/stream`, shared by every screen. Because that connection stays open, browser tests wait for page load rather than network idle.

## Layout

```
apps/web/        Vite + React + TypeScript web app
  src/features/  landing, public-menu, call-desk, analytics, upload, combos, orders, recordings,
                 pricing-lab, settings
  src/components navbar, sheet, printed ticket, toasts, JSON viewer, status timeline
  src/lib/       API, WebSocket and live-update clients, speech in and out, pricing formula, formatting
  scripts/       shots.mjs (screenshots and landing crops), acceptance.mjs (improve.md checks)
apps/api/        FastAPI backend
  revenue/       stats, classification, combos, pricing, upsell, signals, analytics, engine
  nlu/           transliterate, normalize, language, phonetic, matcher, modifiers, intent, parser, gloss_en
  dialogue/      manager, templates, services, simulate
  pos/           adapter, built-in PoS, KOT, order service
  upload.py      sales and menu CSV upload, sample restaurant
packages/shared/ JSON Schemas, generated TypeScript types, OpenAPI export
data/seed/       generated database and CSV exports (not committed)
data/lexicon/    aliases, numbers, modifiers, fillers, English gloss table, language packs
data/samples/    scripted sample calls
data/recordings/ call audio, only when recording is on (not committed)
md/              product spec and improve.md
```
