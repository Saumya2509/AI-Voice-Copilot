# 09. Build plan, testing and kickoff prompt

Depends on: all earlier files.

## Build phases

Do them in order. Each phase ends with something runnable.

**Phase 1. Foundation**
- Monorepo, tooling, SQLite models, shared schemas.
- Seed generator (file 03) with the deterministic seed and the class-count assertions.
- Done when: `make seed` produces the database and the class-count test passes.

**Phase 2. Revenue engine**
- Stats, classification, detections, combos, pricing, upsell ranker (file 04).
- Endpoints for menu, stats, combos, pricing.
- Done when: engine unit tests pass and the seeded affinities appear in the top combos.

**Phase 3. Voice core**
- Lexicon files, normalization, language detection, phonetic keys, matcher, modifiers.
- Intent model training script and rule overrides.
- Dialogue manager with templates, WebSocket events, order JSON, mock PoS and KOT.
- Done when: the test utterance set below passes from the command line with no UI.

**Phase 4. Design system and shell**
- Read the frontend-design skill, confirm the plan in file 06, implement tokens, type, rail, theme switch, empty states.
- Done when: the shell renders in light and dark at desktop and mobile widths.

**Phase 5. Call desk**
- Vosk worker and models, waveform, transcript, clarification chips, offer card, ticket, rupee meter, start sequence (file 07).
- Done when: a sample call and a live microphone call both produce a correct ticket and a KOT.

**Phase 6. Menu field, combos, pricing lab**
- Force-layout field, item sheet with what-if slider, combo graph, pricing table.
- Done when: moving a slider moves a bubble and the predicted profit matches the server preview within rounding.

**Phase 7. Orders, insights, settings, import**
- PoS sync view with retry, call replay, uplift chart, CSV import.
- Done when: a failed PoS send can be retried from the UI and the replay scrubber works.

**Phase 8. Polish and critique**
- Run the quality checklists (files 06 and 07), take screenshots, remove one decorative element per screen, fix accessibility issues, write the README with the exact run commands.

## Test utterances (the voice test set)

Create `tests/utterances.yaml` with at least 60 cases. Each case has `text`, `cart_before`, and the expected `intent`, items, quantities and modifiers. Starter cases:

| Utterance | Expected |
|---|---|
| "ek paneer butter masala aur chaar butter naan" | add PBM x1, Butter Naan x4 |
| "mujhe do dal makhani chahiye medium spicy" | add Dal Makhani x2, spice Medium |
| "paneer masala dena" | clarify between paneer masala variants |
| "पनीर बटर मसाला और दो रोटी" | add PBM x1, Tandoori Roti x2 |
| "one veg biryani with extra raita" | add Veg Biryani x1, Raita add-on |
| "bina pyaaz ke" (after PBM) | modify PBM, exclusion onion |
| "nahi wo hata do" (after last item) | remove last item |
| "bas itna hi" | finalize |
| "haan theek hai" (during offer) | confirm offer |
| "nahi rehne do" (during offer) | deny offer, no re-offer |
| "makhni dal ek" | add Dal Makhani x1 (phonetic) |
| "do glass thanda cold coffee" | add Cold Coffee x2 |

Add noise cases: fillers, repeated words, mixed script, number words ("dedh" for 1.5 where valid), and misspellings.

## Acceptance checks

**Voice**
- Item match accuracy 95 percent or higher on the test set.
- Intent accuracy 95 percent or higher.
- Ambiguous cases ask exactly one question with 2 to 3 options.
- A veg cart is never offered a non-veg item.
- No more than two offers per call; none during clarification.
- Order JSON validates against the schema in 100 percent of finalized calls.
- Idempotent PoS push: retrying never creates a second KOT.
- Server turn latency under 300 ms (p95) on a laptop.

**Revenue**
- Unit tests for every formula in file 04.
- Class counts and seeded affinities as specified.
- Price preview endpoint equals the client-side formula within ₹1.

**Frontend**
- Every number traced to an API field (grep for hard-coded rupee figures in `src`).
- Reduced motion, keyboard, contrast, mobile widths pass the checklists.
- All screens have empty, loading and error states with useful text.

## Sample calls (three scripted, in `data/samples/`)

1. **Hinglish family dinner:** four dishes, one clarification, one accepted upsell, a name and phone number, confirmation.
2. **Hindi with a change of mind:** an item removed, a spice modifier changed, one declined upsell.
3. **English with ambiguity and a combo:** an ambiguous paneer dish, a combo promotion that completes a set, confirmation.

Each script is a list of timed utterances so the player feels like a real call.

## Kickoff prompt for Claude Code

Paste this after placing the md files in `docs/`:

```
Build the project described in docs/00-README.md through docs/09-build-plan-and-testing.md.

Rules:
- Follow the hard rules in 00-README.md exactly. No hosted AI APIs. Keep all code, copy and docs in a plain product voice.
- Before any UI work, read .claude/skills/frontend-design/SKILL.md and follow its plan, review, build and critique process. Use docs/06 and docs/07 as the plan, and note any changes you make to it.
- Work phase by phase as in docs/09. After each phase, run the tests and show me the result before moving on.
- Compute every number in the UI from the API. If something is missing, add it to the API instead of hard-coding it.
- Ask me only when a choice changes the product; otherwise pick a sensible default and write it in the README.
```

## Run commands to document in the repo README

```
make install     # python deps, node deps, download Vosk models
make seed        # generate data/seed/tadka.sqlite
make train       # train the intent model
make dev         # api on :8000, web on :5173
make test        # python and web tests
make shots       # Playwright screenshots for the critique pass
```
