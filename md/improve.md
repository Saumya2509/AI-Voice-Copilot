# improve.md: changes to the Tadka build

This file **overrides** the earlier md files wherever they conflict. Read `00` to `09` first, then apply everything here.

Before touching any UI, read `.claude/skills/frontend-design/SKILL.md` again and redo its plan and review steps for the new look defined below. Note in the README what you changed from the plan.

## What changes

| # | Change | Touches |
|---|---|---|
| 1 | Orders history is live data, never static | Orders screen, API, WebSocket |
| 2 | Menu analytics is driven by CSV upload and shows pie charts, bars, lines and a heatmap | New Upload flow, Analytics screen, API |
| 3 | Combos page is text only; the node diagram is removed | Combos screen |
| 4 | Call transcripts and recordings display in English | NLU output, Call desk, Recordings screen |
| 5 | New Call desk layout: call on the left, restaurant menu on the right, printed ticket at the bottom | Call desk |
| 6 | Whole new visual identity and colour theme | Replaces file 06 |
| 7 | Landing page and public restaurant menu section | New screens |
| 8 | Sidebar becomes a top navbar | Navigation |

Superseded: the palette, type and layout concept of `06`; the rail, Call desk, Menu field, Combos and Orders and Insights screens of `07`. Everything else stands (engine, NLU, PoS, API basics).

---

## 1. Orders history is live

- The Orders screen reads from the database through `GET /orders` with server-side paging (cursor), search (order id, item, customer), filters (date range, channel, status, has upsell) and sort. No fixed arrays or sample rows in the front end.
- New orders appear without a refresh: the client subscribes to `GET /orders/stream` (server-sent events). A new row slides in at the top of the list, only when the person is on page one with no sort override; otherwise a small "1 new order" bar offers to jump to it.
- After a CSV import, the list and every total on the page reflect the imported orders.
- Row click opens a drawer with the printed ticket view and the order JSON.
- **Export CSV** of the current filter.
- Loading shows row skeletons; empty shows "No orders yet. Upload a sales CSV or take a call."

## 2. Menu analytics from CSV upload

The old "Menu field" becomes **Analytics**. It is empty until data exists, and then it is fully driven by the data.

### Upload flow (navbar button "Upload CSV" and the Analytics empty state)

1. Drag and drop or choose a file. Accept `.csv`. Offer **Download template** for `menu.csv` and `sales.csv`.
2. Parse the first rows in the browser (Papa Parse) and show a preview of 20 rows.
3. **Column mapping** with auto-detected guesses. Required: item name, price, quantity, order id, date and time. Optional: category, veg or non-veg, food cost, channel, image URL.
4. Validation summary: rows accepted, rows rejected with reasons (bad date, missing price, unknown item), duplicates skipped. Rejected rows can be downloaded as CSV.
5. If food cost is missing, say so plainly and let the person set a default cost percent by category; margin charts are labelled "Estimated" until real costs are supplied.
6. **Import** shows a progress bar, then "Analysed 11,842 orders from 12 Jul to 10 Oct" (real numbers) and opens Analytics.
7. A secondary button **Load sample restaurant** runs the seed generator, clearly labelled as sample data, so the app can be explored without a file.

### Analytics screen: what it shows

All charts read from `/analytics/*` endpoints and respond to the shared filter bar (date range, category, veg or non-veg, channel).

| Visual | Type | Notes |
|---|---|---|
| Totals strip | Numbers | Revenue, orders, average order value, items sold, gross margin percent, busiest hour |
| Revenue by category | Donut with the total in the centre | Direct labels, no legend box |
| Veg and non-veg split | Pie | Two slices, labelled with share and rupees |
| Menu classes | Donut | Stars, Plowhorses, Puzzles, Dogs with counts |
| Top 10 by units | Horizontal bars | Item names on the left, value at the bar end |
| Top 10 by profit | Horizontal bars | Same layout so the two can be compared |
| Revenue and orders over time | Line with area under revenue | Daily, with weekly toggle; AOV as a second thin line |
| Busy hours | Heatmap, weekday by hour | Cell tooltip: orders and revenue |
| Margin against popularity | Scatter | One chart among the others, not the main screen; click a dot to open the item panel |
| Channel mix and AOV by channel | Stacked bar | Dine in, phone, takeaway |
| Lists | Tables | High margin low selling, low margin high volume, underperformers (file 04) |

**Cross filtering:** clicking a donut slice, a bar or a heatmap cell filters the rest of the page; an active filter shows as a removable chip in the filter bar.

**Chart rules**
- Recharts for pie, bar and line; SVG for the heatmap and scatter.
- Palette limited to the theme colours below, ordered by meaning; no rainbow, no gradients, no 3D, no shadows on charts.
- Thin axes, light gridlines, numbers in tabular figures, rupee format with Indian digit grouping (₹1,24,500).
- Charts animate once on data load (arcs sweep, bars grow in 400 ms, line draws), and on filter change they transition from old values. No loops.
- Every chart has a text alternative: a "View as table" toggle that shows the same data.
- Item panel (right slide-over) keeps the what-if price slider from file 07.

New endpoints: see section 9.

## 3. Combos: text only

- Remove the network graph and any node and edge visuals completely.
- The page is a ranked list written as plain sentences, set like a menu card:

```
Dal Makhani + 2 Garlic Naan + Jeera Rice ............ ₹499
Ordered together in 1 of 6 orders, 2.4 times more often than chance.
Adds about ₹86 margin per order. Bundle discount 8%.        [Add to offers]
```

- Dotted leader between the combo and the price, evidence in one sentence, numbers in plain words (support, confidence and lift are shown only under a "Details" disclosure).
- Filters: by anchor item, by category, by minimum margin. Sort: best margin, most popular, highest order value.
- **Add to offers** puts the combo in the pool the voice copilot uses; the button becomes **In offers**.
- Each combo has a one-line "How it sounds on a call" in English, with Hindi and Hinglish versions behind a small language switch.
- No charts on this page.

## 4. English display for transcripts and recordings

The caller may speak Hindi, Hinglish or English, but **everything shown on screen is English.**

- Store three fields per utterance: `original_text` (what was recognised), `display_text_en` (English for the UI), `lang` (detected).
- Produce `display_text_en` locally with no AI API, in `nlu/gloss_en.py`:
  1. Replace matched item mentions with the English menu item name.
  2. Replace number words and quantities with digits.
  3. Replace modifier phrases with English ones from `modifiers.yaml` (`bina pyaaz` becomes "no onion").
  4. Apply the ordering phrase table `data/lexicon/gloss_en.yaml` (`mujhe ... chahiye` becomes "I want ...", `bas itna hi` becomes "That is all", `haan` becomes "Yes", `nahi` becomes "No", `thoda jaldi` becomes "A bit quickly").
  5. Transliterate Devanagari to Roman for any leftover words, shown in italics so nothing is silently dropped.
- Assistant replies always carry `text_en` next to the spoken text, because every template has an English version.
- The Call desk and Recordings screens show English by default. A small **Show original** switch reveals the recognised text. The detected language is a plain tag ("Heard: Hinglish").
- Be honest in the UI: this gloss covers ordering language. Unusual sentences appear partly in italic Roman text.
- Test: the 60 test utterances must have expected English renderings; at least 90 percent must match exactly after normalizing spaces and case.

### Call recordings

- Optional audio recording using `MediaRecorder`, **off until the person turns it on in Settings**, with a plain consent line shown on the Call desk while recording ("Recording this call").
- Audio is stored on the server in `data/recordings/` and referenced from `calls`; sample calls have no audio and show the transcript only.
- **Recordings screen:** list of calls (time, duration, language heard, outcome, order total, upsell result) with search and filters. Open one to see: audio player, English transcript synced to playback (current line highlighted, click a line to seek), markers for items added, clarifications and offers, the final ticket, and the order JSON.
- Delete recording and delete call are separate buttons; both confirm.

## 5. Call desk layout

```
+-----------------------------------------------------------------------------+
| top navbar                                                                  |
+-----------------------------------------+-----------------------------------+
|  CALL DESK (left, ~58%)                 |  RESTAURANT MENU (right, ~42%)    |
|  call bar: call, timer, language heard  |  search, veg toggle, categories   |
|  waveform                               |  list with dotted leaders         |
|  live transcript (English)              |  matched items glow as they are   |
|  clarification buttons                  |  heard; click an item to add it   |
|  offer card with reasons                |  availability and prices live     |
+-----------------------------------------+-----------------------------------+
| TICKET TRAY (bottom, full width)                                            |
| slot ------------------------------------------------------------------    |
| [ printed ticket: lines in columns | total | rupee meter | Send to PoS ]    |
+-----------------------------------------------------------------------------+
```

**Left, Call desk:** as in file 07 but the transcript is English, and the offer card sits directly under the transcript. Keep the screen calm; no decorative panels.

**Right, restaurant menu:**
- Read from `/menu`. Search box, veg only switch, category tabs.
- Items listed like a printed menu card: name, a dotted leader, price. Veg or non-veg shown by the standard square-with-dot mark.
- When the caller says an item, its row highlights for 1.2 seconds and the list scrolls to it; the matched item shows a small "heard" tick. Items in the cart show their quantity.
- Click to add one to the ticket by hand (counts as `source: staff`); a stepper appears for quantity.
- Out-of-stock items are greyed with the reason; items the engine wants to push carry a small "Chef's pick" tag only when they are Puzzles or Stars with high margin (the data decides, not hard-coded).

**Bottom, ticket tray:**
- A fixed dock across the bottom with a visible printer slot (a dark slit with a thin highlight) on its top edge.
- Collapsed height 72 px (slot and total only). It grows as the ticket prints, up to 40 percent of the viewport, then the ticket scrolls inside.
- The ticket is wide, laid out for a landscape tray: header left (KOT number, time, channel), lines in two or three columns grouped by station, totals and rupee meter on the right, and the actions **Confirm order** and **Send to PoS**.
- Printing animation: when the first item is added the ticket rises out of the slot (translateY and clip-path, 900 ms); each new line prints with a typed effect; removals strike through. Confirmation adds a perforated edge and a status stamp when the PoS acknowledges, with the KOT number.
- Reduced motion: the ticket appears without the rise and typing.

**Mobile:** Call desk full screen; menu in a tab beside it; ticket as a bottom sheet that peeks at 72 px.

## 6. New visual identity and colour theme

The first design read as a generic dashboard. The new direction is taken from places a restaurant person already knows: **hand-painted dhaba signboards and printed menu cards**. Bold enamel colour for signage moments, quiet ink-on-paper for working screens.

### Colours

| Name | Light | Dark | Use |
|---|---|---|---|
| Plate | `#F7F6F2` | `#15161B` | App background |
| Card stock | `#FFFFFF` | `#1E2028` | Panels, ticket tray |
| Ink | `#17181C` | `#ECEBE6` | Text, rules |
| Indigo enamel | `#243A8C` | `#8DA2F5` | Primary actions, links, active nav |
| Haldi | `#F5B800` | `#F5B800` | Signage bands, highlights, money gained |
| Chilli | `#D7301F` | `#F2705F` | Warnings, remove, Dogs |
| Leaf | `#2C7A4B` | `#52B67B` | Success, veg mark, Stars |
| Plowhorse blue | `#4A78B8` | `#7FA6DD` | Plowhorses |
| Puzzle plum | `#7A3366` | `#C079AA` | Puzzles |

Large flat areas use Haldi (landing hero band, section dividers) with Ink text. Working screens are mostly Plate and Card stock with Ink rules. No gradients, no glass blur, no purple-blue washes, no glow.

### Type

- **Display:** *Rozha One* for landing headlines and section titles. It has real Devanagari, so Hindi headings stay consistent.
- **Interface and body:** *Mukta* (400, 500, 700), with Devanagari built in. Tabular numerals on money.
- **Ticket only:** *Share Tech Mono*, because the ticket is a printed object.
- Left aligned text; headings are plain sentence case; no all-caps labels, no tiny labels above headings.

### Shape and detail

- Corners small (2 to 4 px) like printed stock; the ticket has a torn edge, not a rounded card.
- **Rules instead of boxes:** a thick-thin double rule under page titles, hairlines between rows, dotted leaders between names and prices. Panels use a 1 px Ink border at 15 percent, not shadows.
- Veg and non-veg marks, a price-tag corner on offers, a round stamp for "Sent to PoS". These come from the domain, so keep them and use them consistently.
- Icons: one consistent line set (Phosphor regular), no emoji, no icons in circles above every heading.
- Imagery: if the menu CSV has image URLs, show them; otherwise show the item name set in Rozha One on a flat tile in the category colour. No stock photos, no generated illustrations.

### What to avoid so it does not read as generated

- Three or four identical feature cards with an icon, a title and two lines.
- Hero with a gradient blob, a floating dashboard screenshot and "Supercharge" or "Transform" copy.
- Everything centred, everything rounded, everything with a soft shadow.
- Placeholder names, fake testimonials, fake logos, invented statistics, "Welcome back" greetings.
- Evenly spaced identical sections. Vary the rhythm: a full-width band, then a two-column section with a deliberately uneven split, then a plain list.

Write copy the way the restaurant trade talks: short, specific, no abstractions.

## 7. Landing page and public menu

### Landing page (`/`)

Public page, same top navbar with a **Open the call desk** button on the right.

1. **Signboard hero:** full-width Haldi band. Headline in Rozha One at large size, left aligned, spanning about two thirds, for example: "Take the order. Sell the extra naan." Below it one sentence and two buttons: **Open the call desk** and **See the menu**. At the right edge, a tilted printed ticket partly overlapping the band, and it prints a short sample order when the page loads (the one entry animation on this page, played once). A rotated sticker reads "Hindi, English, Hinglish".
2. **How a call goes:** a plain three-step sequence (this is a true sequence, so numbering is fine): caller speaks, the ticket prints with the reason for each offer, the kitchen gets the KOT. Each step is a line of text beside a small crop of the real UI taken by the screenshot script, not a mock.
3. **The menu:** a preview of the restaurant's menu, live from the database (see below), with a link to the full menu page.
4. **What the owner sees:** two real charts rendered from the loaded data (revenue by category and busy hours), with one line of text each. If no data has been uploaded, this section shows the upload prompt instead of sample figures.
5. **Languages:** a short list of what is understood, with three example sentences and their English meaning.
6. **Footer:** product name, links, nothing invented.

Scroll motion: elements are not animated on scroll. The only motion is the ticket print in the hero and normal hover and focus states.

### Restaurant menu (`/menu`, also embedded in the landing page)

- Public page reading `GET /public/menu`.
- Layout like a printed menu card: category headings in Rozha One with a double rule, items as name, dotted leader, price; a short description if the CSV has one; veg mark; spice level shown as small chilli marks.
- Category jump links in a sticky row under the navbar; veg only switch; search.
- Two columns on wide screens, one on mobile. Images only when supplied.
- Menu edits from the PoS adapter or CSV import show up here without a rebuild.

## 8. Top navbar (replaces the sidebar)

- Height 60 px, Plate background, 2 px Ink rule on the bottom edge.
- Left: wordmark "Tadka" set in Rozha One, linking to the landing page.
- Centre-left links: **Call desk, Menu, Analytics, Combos, Orders, Recordings**. **More** opens a small menu with Pricing lab and Settings.
- Right: **Upload CSV** (secondary button), theme switch, and a small restaurant name chip.
- Active link: a Haldi bar behind the text, like a highlighter, sliding to the new link on route change (220 ms).
- Under 900 px the links collapse into a menu button that opens a full-width drawer from the top; the Call desk link stays visible.
- Keyboard: arrow keys move across links, Escape closes menus, focus ring is a 2 px Indigo outline.
- Remove the old rail, its expand and collapse behaviour and any sidebar code.

## 9. API additions and changes

| Method | Path | Purpose |
|---|---|---|
| GET | `/import/template/{kind}` | CSV templates for `menu` and `sales` |
| POST | `/import/preview` | Parse and validate, returns mapping guess, counts, errors |
| POST | `/import/commit` | Apply the mapping, import, re-run analytics, returns summary |
| POST | `/import/sample` | Generate the sample restaurant |
| GET | `/analytics/overview` | Totals strip |
| GET | `/analytics/category-share` | Donut data |
| GET | `/analytics/veg-split` | Pie data |
| GET | `/analytics/class-split` | Class donut data |
| GET | `/analytics/top-items?by=units|profit&limit=10` | Bar data |
| GET | `/analytics/trend?grain=day|week` | Line data |
| GET | `/analytics/heatmap` | Weekday by hour |
| GET | `/analytics/channel-mix` | Channel bars |
| GET | `/orders` | Cursor paging, search, filters, sort |
| GET | `/orders/stream` | Server-sent events for new orders |
| GET | `/public/menu` | Public menu with categories and availability |
| GET | `/calls` | Recordings list with filters |
| GET | `/calls/{id}/transcript?lang=en` | English transcript with timestamps |
| GET | `/calls/{id}/recording` | Audio stream, if recorded |

All analytics endpoints accept `from`, `to`, `category`, `veg`, `channel` and return `window` and `sample_size`.

Changes to existing events: every `transcript` and `reply.say` event now carries `display_text_en`; the WebSocket also emits `menu.highlight` with the matched `item_id` so the right-hand menu can react.

## 10. Build order for these changes

1. API: import endpoints, analytics endpoints, orders paging and stream, public menu, English gloss, recording storage.
2. Design tokens, fonts, navbar, theme switch. Delete the sidebar.
3. Call desk re-layout with menu panel and ticket tray.
4. Upload flow and Analytics screen with all visuals.
5. Orders live list. Combos text page. Recordings screen.
6. Landing page and public menu.
7. Screenshots in light and dark at 1440 and 390 px; critique pass; remove one decorative element per screen.

## 11. Acceptance checks

- Uploading a valid sales CSV changes every number on Analytics and Orders; uploading a different file changes them again. No chart or table renders values that are not from the API.
- With an empty database, Analytics and the landing owner section show upload prompts, not figures.
- A new order from a call appears in Orders within 2 seconds without refreshing.
- Combos page contains no chart, graph or node element (assert in a UI test).
- Spoken Hindi and Hinglish test calls show English in the transcript and in Recordings; **Show original** reveals the recognised text.
- Call desk matches the layout in section 5 at 1440 px; menu items highlight when heard; the ticket prints from the bottom slot.
- Navbar works by keyboard and collapses under 900 px; no sidebar remains in the code.
- Landing page has no invented logos, quotes or statistics, and no scroll-triggered animations.
- Light and dark pass contrast; reduced motion pass; no horizontal scroll at 390 px.

## 12. Prompt for Claude Code

```
Apply docs/improve.md on top of docs/00 to docs/09. improve.md overrides earlier files where they conflict.

First read .claude/skills/frontend-design/SKILL.md and redo its plan and review for the new identity in improve.md section 6. Then work through section 10 in order, running tests after each step and showing me the result.

Rules: every figure comes from the API, no AI API of any kind, no sidebar, no node diagram on Combos, all displayed transcripts in English, and keep all copy and code in a plain product voice.
```
