# 01. Product concept

## The one-line idea

**One brain, two jobs.** The same revenue engine that tells the owner which dishes to push also whispers to the phone assistant what to offer, in the middle of a call, with the reason attached.

Most tools treat menu analytics and voice ordering as separate products. Tadka makes the analytics *act*: every insight becomes a live upsell rule that the voice copilot uses within seconds.

## Users and their jobs

| User | Primary job | What they need to see |
|---|---|---|
| Owner or manager | Understand what makes money and fix what does not | Menu field, pricing lab, combo builder, lift from AI orders |
| Front-desk or call handler | Take phone orders accurately and fast | Call desk with live ticket, clarifications, upsell prompts |
| Kitchen | Receive a correct KOT | Clean KOT with modifiers and notes |

## What makes it different (the six signature ideas)

1. **Upsell with receipts.** Every suggestion shows why: contribution margin in rupees, how often it is ordered with the current cart, and the expected gain. Staff and owners trust what they can read.
2. **Menu field.** Items are living bubbles on a margin-versus-popularity field. Drag a price slider and watch a bubble drift between quadrants with a predicted monthly profit change. No static BCG chart.
3. **Rupee meter.** During a call, a counter shows how much extra revenue and margin this call's accepted upsells added. It makes the value of the AI visible in real time.
4. **Polite upsell policy.** Maximum two offers per call, never while clarifying, stop after a decline, respect veg and non-veg, skip items that are unavailable, and skip slow items when the kitchen is busy. It sells like a good waiter, not like a pop-up.
5. **Self-tuning offers without AI APIs.** Each upsell rule keeps a Beta distribution of accepts and declines (Thompson sampling). The system learns which offers work at lunch versus dinner, with no model hosting.
6. **Voice to kitchen ticket.** The call ends with a ticket that physically prints out of a slot in the UI and a KOT that appears in the PoS sync log. The path from voice to kitchen is visible.

## Scope

**In scope**
- Revenue intelligence: contribution margin, popularity and velocity, classification, high-margin low-selling detection, low-margin high-volume risk, combos by association analysis, price recommendations, upsell prioritization, optional inventory-linked signals.
- Voice copilot: speech to text, intent and item mapping, modifiers, clarification, English/Hindi/Hinglish, live upsell, combo promotion in call flow, confirmation, structured JSON, PoS push and KOT.
- A polished web app with animation (specified in files 06 and 07).
- A synthetic but realistic 90-day dataset so everything works out of the box, plus CSV import for real PoS exports.

**Out of scope**
- Real telephony (SIP, Twilio). The call desk uses the microphone or a sample-call player. A note in `02` shows where a telephony bridge would plug in.
- Payment, delivery aggregators, table management.
- Any hosted AI model.

## Success metrics (measured inside the app)

- Item match accuracy on the test utterances: 95 percent or higher (see file 09).
- Order JSON valid against the schema: 100 percent.
- Average order value uplift on simulated calls with upsell on versus off: shown on the Insights screen.
- Time from end of call to KOT in PoS log: under 2 seconds.

## Tone of the product

Practical and calm, written for a busy restaurant, not for a data team. Plain words: "Offer this next", not "Recommendation engine output". Full copy rules are in file 06.
