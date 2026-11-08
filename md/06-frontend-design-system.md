# 06. Frontend design system

Depends on: `01`. **Before writing any UI code, read `.claude/skills/frontend-design/SKILL.md` and follow its process: plan, review against the brief, build, critique.** This file is the result of that process. If you change the plan, redo the review step and note what changed.

## Subject, audience, job

- **Subject:** a restaurant's money and its phone line.
- **Audience:** a restaurant owner or manager at a desk, and a front-desk person with a headset on a busy evening.
- **Primary job:** see what earns money, and take a phone order without mistakes.

The visual world comes from the kitchen: the **pass** (the steel counter where tickets are handed over), **KOT tickets** on a rail, thermal paper, and spice colours used as meaning, not decoration.

## Design plan

### Colour (named, with hex)

| Name | Light | Dark | Role |
|---|---|---|---|
| Steel pass | `#E7ECEF` | `#172126` (Tandoor slate) | App background |
| Counter | `#F4F7F8` | `#1F2D33` | Raised surfaces |
| Ink brine | `#1E2D33` | `#E4ECEF` | Primary text |
| Haldi | `#F0B323` | `#F0B323` | Money gained, upsell highlight, rupee meter |
| Curry leaf | `#2E8B63` | `#47B58A` | High margin, Stars, success |
| Cardamom | `#3E6FA3` | `#6A9BD1` | Plowhorses, neutral data |
| Beetroot | `#8A3B6B` | `#C2679F` | Puzzles (hidden potential) |
| Chilli | `#D9402E` | `#F06A58` | Dogs, errors, risk |
| Thermal paper | `#F7F9F5` | `#F7F9F5` | The KOT ticket only, in both themes |

Quadrant colours mean one thing everywhere: green earns, blue is steady, beetroot is potential, chilli is trouble. Do not use these colours for decoration. No gradient washes.

### Type

- **Interface and headings:** *Familjen Grotesk* (weights 400, 500, 600, 700). Tabular numerals on for all money and counts.
- **Devanagari:** *Hind* as the fallback in the same stack, so Hindi transcripts and replies render cleanly.
- **Ticket only:** *Share Tech Mono*. The ticket is a printed object, so a monospaced, dot-matrix style is the content's real vernacular. Do not use monospace elsewhere.

Scale (rem): 0.75, 0.875, 1, 1.125, 1.375, 1.75, 2.5, 3.5. Body line-height 1.5, headings 1.15. Keep lines under 70 characters. Headings are plain; do not accent a single word in a headline, do not use all caps for labels, do not add small labels above headings.

### Layout concept

Left rail with six destinations, content left aligned, and on the Call Desk a fixed ticket column on the right.

```
+------+--------------------------------------------+-----------------+
| rail |  Call Desk                                  |  KOT ticket     |
|      |  [ caller + waveform ]                      |  (prints here)  |
|  o   |  [ live transcript, items highlighted ]     |  lines          |
|  o   |  [ offer card with its reasons ]            |  total          |
|  o   |                                             |  rupee meter    |
+------+--------------------------------------------+-----------------+
```

```
+------+----------------------------------------------+---------------+
| rail |  Menu field (bubbles on margin x popularity) |  Item sheet   |
|      |                                              |  what-if      |
+------+----------------------------------------------+---------------+
```

Alignment: left aligned text everywhere, numbers right aligned in tables, no centred paragraphs.

### Principles

1. **One memorable thing:** the ticket that prints out of a slot as the order forms, with the rupee meter ticking on it. Everything else stays quiet.
2. **Colour is data.** The same four colours mean the same thing on every screen.
3. **Structure is information.** Borders, dividers and numbering appear only when they encode something. Numbered steps are used only for the KOT status sequence and the call states, which are real sequences.
4. **Always show the reason.** Any recommendation has its evidence beside it.
5. **Calm by default.** Motion answers a person's action or a live event; there are no decorative loops.

## Review of the plan against the brief

Checked against the "generic defaults" list in the skill:

- A first draft used a cream background with a serif display and a clay accent. That is a common generated look and has nothing to do with a restaurant tool, so it was replaced with the steel and slate palette above. Cream survives only on the ticket, where thermal paper makes it correct.
- A first hero idea was a large revenue number with a gradient accent. Replaced with a live call and a printing ticket, which is the most characteristic moment in this product.
- A uniform grid of identical rounded cards was replaced by a field, a rail, a ticket and tables, each with its own shape and radius (radius scale: 4 for inputs and tags, 8 for sheets, 14 for the ticket top edge, 999 for bubbles).
- Eyebrow labels, "WORD, fragment" labels and arrow-suffixed buttons are not used.

## Components to build (design rules)

- **Left rail:** 72 px wide, expands to 220 px on hover or pin. Six items with icon and label: Call desk, Menu field, Combos, Pricing lab, Orders, Insights. Settings sits at the bottom with the theme toggle. The active item is shown by a bar that slides between items, not by a filled pill. Keep it visually quiet; no badges unless there is something to act on.
- **Buttons:** one primary style (Ink brine fill), one secondary (outline), one quiet (text). Primary actions use the exact verb of the result.
- **Tables:** compact, numbers right aligned with tabular numerals, row hover shows a thin left bar in the row's class colour.
- **Tags for classes:** coloured dot plus word (Star, Plowhorse, Puzzle, Dog), sentence case.
- **Toasts:** bottom left, plain sentences, never block the ticket.
- **Empty states:** say what to do ("Press the call button or play a sample call").
- **Theme toggle:** a switch in the rail footer; respects `prefers-color-scheme` on first load, remembers the choice, and swaps tokens with a 200 ms colour transition (no layout shift).

## Tokens (`styles/tokens.css`)

Define all colours, radii, spacing (4 px base), shadows (one soft, one ticket shadow) and durations as CSS variables. Example:

```css
:root {
  --bg: #E7ECEF; --surface: #F4F7F8; --ink: #1E2D33;
  --haldi: #F0B323; --leaf: #2E8B63; --cardamom: #3E6FA3;
  --beet: #8A3B6B; --chilli: #D9402E; --paper: #F7F9F5;
  --r-sm: 4px; --r-md: 8px; --r-lg: 14px;
  --dur-fast: 120ms; --dur-base: 220ms; --ease-out: cubic-bezier(.2,.8,.2,1);
}
[data-theme="dark"] {
  --bg: #172126; --surface: #1F2D33; --ink: #E4ECEF;
  --leaf: #47B58A; --cardamom: #6A9BD1; --beet: #C2679F; --chilli: #F06A58;
}
```

## Copy rules

- Sentence case, plain verbs, active voice. Name things by what the user does.
- Buttons say what happens: "Add to ticket", "Send to PoS", "Apply price". The result message reuses the verb: "Sent to PoS".
- Errors say what happened and what to do, with no apology: "The PoS did not respond. Retry, or keep the order and send later."
- Words appear only when they help. If a label repeats its heading, delete it.

## Accessibility and quality floor

- Visible focus ring (2 px Haldi outline with 2 px offset) on all interactive elements.
- Contrast AA for text and for chart marks against their background; never rely on colour alone, so each class also has a distinct bubble outline pattern and a text tag.
- Live transcript in an `aria-live="polite"` region; the offer card announces itself once.
- `prefers-reduced-motion`: replace motion with instant state changes or short fades; the ticket appears without the feed animation.
- Responsive: rail becomes a bottom bar under 768 px; the ticket becomes a slide-up sheet.
- Critique pass: take screenshots of every screen in light and dark at 1440 and 390 px widths, then remove one decorative element per screen before finishing.
