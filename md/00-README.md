# Tadka: Revenue and Voice Copilot for Restaurants

Tadka reads a restaurant's PoS history to find where money is being left on the table, then uses those same findings live on the phone: it takes the order in English, Hindi or Hinglish, offers upsells that are backed by data, and pushes a clean order and KOT into the PoS.

The name comes from the finishing flourish in Indian cooking: a small last step that lifts the whole dish. That is what a good upsell is.

## How to use this md set

Give these files to your coding agent (Claude Code) in order. Each file is self-contained and says what it depends on.

| File | What it defines |
|---|---|
| `00-README.md` | This index, hard rules, repo layout |
| `01-product-concept.md` | What makes Tadka different, users, scope, non-goals |
| `02-architecture-and-stack.md` | Stack, services, data flow, folder structure |
| `03-data-and-pos.md` | Schema, synthetic dataset generator, CSV import, PoS adapter, KOT |
| `04-revenue-engine.md` | Margin, popularity, classification, combos, pricing, upsell scoring |
| `05-voice-copilot.md` | Speech to order pipeline, languages, dialogue manager, JSON output |
| `06-frontend-design-system.md` | Visual identity, tokens, type, layout, copy rules |
| `07-frontend-screens-and-animation.md` | Every screen, component and motion spec |
| `08-api-contracts.md` | REST and WebSocket contracts, JSON schemas |
| `09-build-plan-and-testing.md` | Build phases, test utterances, acceptance checks, agent kickoff prompt |

## Hard rules (apply to every file)

1. **No hosted AI API anywhere.** No LLM, STT or TTS calls to OpenAI, Google, Anthropic, Azure, AWS or similar. Everything runs locally: rules, statistics, small scikit-learn models, offline speech recognition in the browser.
2. **Before writing any UI code, read `.claude/skills/frontend-design/SKILL.md`** and follow it. Files 06 and 07 are already built on it, but the skill wins if there is any conflict about taste or process (plan, review against brief, build, critique).
3. **No real-brand claims.** Do not invent customers, certifications, benchmarks or case studies. Numbers shown in the UI come from the dataset in the database, never hard-coded.
4. **No static or dummy values in the UI.** Every figure on screen is computed from the database or the live call. The synthetic dataset is real data as far as the app is concerned.
5. **Product voice only.** Code, comments, UI copy, README, commit messages, seed data and docs all describe Tadka as a real product used by restaurants, and nothing else.
6. **Language policy.** UI text is English. Voice supports English, Hindi (Devanagari and Roman) and Hinglish, with Marathi and Gujarati as optional language packs.
7. **Quality floor.** Responsive to mobile, visible keyboard focus, `prefers-reduced-motion` respected, contrast at WCAG AA, light and dark theme.

## Repo layout (target)

```
tadka/
  apps/
    web/            # Vite + React + TypeScript frontend
    api/            # FastAPI backend (revenue engine, NLU, PoS adapter)
  packages/
    shared/         # JSON schemas, generated TS types
  data/
    seed/           # generator output (sqlite, csv)
    lexicon/        # item aliases, number words, language packs (yaml)
  docs/             # these md files
```

## Definition of done (short form)

- A person can open the app, press the call button, speak (or play a sample call) and watch a correct ticket build, hear a data-backed upsell, confirm, and see the KOT land in the PoS adapter.
- The menu field, combos and pricing lab all load from the database with no hard-coded numbers.
- Full list in `09-build-plan-and-testing.md`.
