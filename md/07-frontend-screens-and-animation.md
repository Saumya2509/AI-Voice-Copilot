# 07. Frontend screens, components and animation

Depends on: `05`, `06`. Read `.claude/skills/frontend-design/SKILL.md` first. All data comes from the API (file 08); no hard-coded numbers.

## Motion principles

- **One orchestrated moment:** the Call Desk start sequence (connect, then the ticket feeds out of its slot). That is the only unprompted motion in the app.
- **Motion that answers an action or live event:** ticket lines appearing as items are heard, bubbles moving when a price slider moves, sheets opening, toasts confirming.
- **No** fade-and-slide-up on every section, no hover animations on every card, no looping decoration.
- Durations: 120 ms (feedback), 220 ms (state change), 420 ms (layout change), 900 ms (ticket feed). Easing `cubic-bezier(.2,.8,.2,1)`; use springs (stiffness 260, damping 28) for bubbles.
- Respect `prefers-reduced-motion` globally with a `useMotionPref()` hook.

## Screen 1. Call desk (the hero)

**Layout:** main column plus a fixed ticket column (360 px).

**Elements**
1. **Call bar:** call button, call timer, language chip (English, Hindi, Hinglish, auto), engine chip (Offline speech, Typed, Sample call). Sample call menu lists three scripted calls: a Hinglish family dinner, a Hindi order with a modifier change, an English order with ambiguity.
2. **Waveform:** canvas drawing live mic level from `AnalyserNode` as a single smooth line; when the assistant speaks it switches to a different amplitude pattern driven by TTS boundary events.
3. **Live transcript:** partial text streams in grey; when final, tokens that matched menu items get a coloured underline in the class colour and a small tooltip with the matched item and confidence. Ambiguous tokens are underlined with a dashed line and open the clarification choices on click.
4. **Clarification chips:** the two or three options appear as large buttons under the transcript; speaking the option or clicking resolves it.
5. **Offer card:** slides in below the transcript only when an upsell is made. It shows the offer headline, price, the reasons from the ranker ("Ordered with Dal Makhani in 38 percent of orders", "Adds ₹54 margin"), and two buttons: **Add to ticket** and **Skip**. Voice yes or no does the same.
6. **Rupee meter:** on the ticket, a counter of added revenue and margin from accepted upsells. Numbers tween with a 500 ms ease, and a thin Haldi bar fills with each accepted offer.

**Start sequence (the single orchestrated moment)**
1. Press call. The call bar changes state and the waveform draws in from a flat line (300 ms).
2. The ticket column shows an empty slot (a dark slit at the top edge of the column).
3. When the first item is recognised, a paper ticket feeds out of the slot (translateY and clip-path, 900 ms) with the header already printed (KOT number, time, channel).
4. Each recognised item prints as a new line: characters type in at about 40 characters per second in the ticket font, then the line price settles right aligned. The ticket grows downward; the column scrolls to keep the newest line visible.
5. Corrections (remove or change) strike a line through with a 160 ms stroke and replace it.
6. On confirmation, the ticket gets a perforated tear edge, slides slightly right, and a stamp-style "Sent to PoS" status line replaces the spinner when `pos.ack` arrives, with the KOT number.

**Ticket anatomy (thermal paper `#F7F9F5`, Share Tech Mono)**
- Header: restaurant name, KOT number, time, channel.
- Lines grouped by station.
- Modifiers indented under each line.
- Total, then the rupee meter row (revenue added, margin added).
- Footer: call language and call id (masked).

**States:** idle, connecting, listening, assistant speaking, clarifying, offering, confirming, sending, done, error. Each has a clear text status in the call bar (not colour only).

## Screen 2. Menu field

- Full-bleed field with margin (y) versus popularity (x), quadrant lines drawn from the real category thresholds, quadrant names in plain words (Stars, Plowhorses, Puzzles, Dogs) in the quadrant colours at low opacity.
- Items are bubbles sized by profit, coloured by class, positioned by `d3-force` with collision so they never overlap. On data load they settle in about 1.2 seconds (the settling is the entry motion).
- Category filter chips and a window selector (7, 30, 90 days). Changing the window re-runs the simulation and bubbles glide to new positions.
- **Item sheet (right, opens on click):** name, class tag with the reason sentence, sales trend sparkline, margin, profit share, recommended action, and the **what-if price slider** (±10 percent, ₹5 steps). Moving the slider moves the bubble live using the client-side elasticity formula from file 04, and updates "Predicted profit per month" with the range. Button: **Apply price** (writes to the simulated PoS menu and logs the change).
- Hover shows a quick tooltip; keyboard users move between bubbles with arrow keys in reading order and open the sheet with Enter.
- Lists below the field (tabs): High margin, low selling, Low margin, high volume risk, Underperforming SKUs. Each row links to its bubble, which pulses once to locate it.

## Screen 3. Combos

- Left: association network. Nodes are items (colour by class), edges thickness is lift, opacity is confidence. Selecting a node isolates its neighbours with a 300 ms transition.
- Right: combo list ranked by `combo_score`, each with the evidence sentence, bundle price, margin and AOV estimate. **Create combo** adds it to the offer pool used by the voice copilot; the button state becomes **In offer pool**.
- A preview shows how the offer sounds in the call ("Dal Makhani with two Garlic Naan and a Jeera Rice for ₹499").

## Screen 4. Pricing lab

- Table of recommendations: item, class, current price, suggested price, expected profit change with range, confidence tag (Measured or Assumed), and **Apply**.
- A summary strip on top: total monthly profit upside if all are applied, with a count of items affected. Applying a row animates its numbers into the strip (tween).
- Toggle to include or exclude guardrails (shows what the guardrails prevented).

## Screen 5. Orders and PoS sync

- Table of orders with channel, total, upsell added, status.
- Selecting an order opens a split view: left, the ticket as printed; right, the **JSON viewer** (collapsible, copy button) of the structured order.
- Status timeline with real sequence numbering (Confirmed, Sent to PoS, Acknowledged, KOT printed). Failed sends show the reason and a **Retry** button; a successful retry animates the failed step to done.

## Screen 6. Insights

- Average order value with and without upsell (from calls), accepted offer rate by hour, top performing offers (from the bandit's stats), and a **call replay**: a horizontal timeline of one call with markers for each item added, each clarification and each offer (accepted or declined). Scrubbing moves a cursor and shows the transcript at that moment.
- Charts are simple: a line, a bar and the timeline. No decorative charts.

## Screen 7. Settings

Language packs, speech engine (Offline default, Typed, browser service toggle with the privacy note), upsell policy (offers per call, daypart weights), kitchen busy toggle, inventory signals, import data, delete stored calls, theme.

## Shared components

`Rail`, `CallBar`, `Waveform`, `Transcript`, `ClarifyChips`, `OfferCard`, `Ticket`, `TicketLine`, `RupeeMeter`, `NumberTween`, `MenuField`, `ItemSheet`, `PriceSlider`, `ComboGraph`, `StatusTimeline`, `JsonViewer`, `Toast`, `EmptyState`, `ThemeSwitch`.

## Technical notes

- Use `motion` layout animations for list reorder and the ticket growth; use `useMotionValue` and `animate` for number tweens.
- Render the field in SVG; keep under 100 nodes; run the force simulation in a `requestAnimationFrame` loop that stops when settled.
- The waveform runs on a canvas at 60 fps and pauses when the tab is hidden.
- Keep the ticket's typing effect in plain CSS with `steps()` or a small timer hook, and skip it for reduced motion.
- Debounce API calls from the what-if slider; compute the preview locally and confirm with the server on release.
- Code-split by route; lazy load the Vosk worker and models only when the Call desk opens.
- Add Playwright screenshots for each screen in light and dark, desktop and mobile, for the critique pass in file 06.

## Quality checklist (run before calling the UI done)

- Every number on screen traces to an API field.
- Keyboard: tab order is logical; all actions reachable.
- Reduced motion: the full call flow still works and reads clearly.
- No horizontal scroll at 390 px.
- Light and dark both pass contrast.
- Remove one decorative element per screen.
