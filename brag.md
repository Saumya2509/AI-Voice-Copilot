# brag.md: Project Showcase Videos

Two videos, **no voiceover** in either, only background music (plus light sound effects):

| # | Video | Length | Purpose |
|---|---|---|---|
| 1 | **Full walkthrough** | 2:00 to 3:00 (plan: ~2:40) | Explain the whole project in detail, using on-screen text instead of voice |
| 2 | **Short teaser** | exactly **0:56** | Laptop-opening intro (about 11s), then the website/software on the screen, then the whole project in the remaining 45s |

This plan works for any project. Fill in section 0 first, and every scene below pulls from it.

---

## 0. Project facts (fill this in first)

| Field | Your answer |
|---|---|
| `[PROJECT NAME]` | **Tadka (AI-Voice Copilot)** |
| `[YOUR NAME]` | **Saumya** |
| `[LINK]` (live URL, GitHub, LinkedIn) | **https://github.com/Saumya2509/AI-Voice-Copilot** |
| One-line pitch (what it is, who it's for) | **AI Voice Copilot & Revenue Engine taking restaurant phone orders in English, Hindi, and Hinglish with zero cloud costs.** |
| Problem it solves | **Restaurants lose high-margin sales on phone orders and face multilingual communication barriers and order errors.** |
| Tech stack (3 to 5 items) | **FastAPI, React 18 / Vite, Vosk (Offline STT), Piper (Neural TTS), SQLite** |
| `[BRAND COLOR]` (accent used in captions and glow) | **`#7A1F2B` (Royal Maroon) & `#B8892B` (Antique Gold)** |
| **Feature 1** (your strongest, most visual one) | **Voice Intake & Barge-In (Fluent English/Hindi/Hinglish speech with live interruption & English gloss)** |
| **Feature 2** | **Revenue Engine & Upsell Ranker (Apriori affinity mining & BCG Menu Matrix: Stars, Plowhorses, Puzzles, Dogs)** |
| **Feature 3** | **Instant Kitchen Order Ticket (Thermal KOT generation, idempotent POS dispatch & live SSE updates)** |
| **Feature 4** (add or remove features as needed) | **Dynamic Pricing Lab & Analytics (Elasticity modeling with category margin guardrails & instant CSV ingestion)** |
| Proof points (real numbers only: users, speed, accuracy, scores, results) | **100% item & intent accuracy (84 test cases), ~40ms server latency, p95 5ms parser, 100% offline & local** |

Pick **3 to 5 features**. Rank them by how good they look on screen, because the best one gets the most time in both videos.

---

## 1. Before you record

- [ ] The project runs reliably, with no bugs, console errors or placeholder text visible on screen
- [ ] Use a **production build** or the most stable version, not a half-broken dev environment
- [ ] **Use only real numbers.** Every metric, score, user count or result on screen must be true
- [ ] Add realistic demo data so screens don't look empty
- [ ] Screen: 1920×1080, 60fps, notifications off (Do Not Disturb), clean desktop, and a clean browser (fullscreen, 100% zoom, no bookmarks bar, no extensions, no dev tools unless showing code)
- [ ] Cursor: large, with a subtle highlight ring, moving slowly. Tools: Screen Studio (Mac), Cursorful (Chrome extension), OBS with a cursor-highlight plugin
- [ ] Record **each feature as a separate take**, and repeat any tricky moment until it's smooth
- [ ] Practise each flow first so every click has a purpose (no hesitating, no wandering)
- [ ] If the project is not a website (mobile app, desktop tool, CLI, ML model, hardware), record it in its natural environment (emulator or phone screen, terminal, notebook, camera) and follow the notes in section 4

---

## 2. Shared look and sound

**Visual style**
- Match your project's own branding: use `[BRAND COLOR]` for captions, highlights and glow, on a dark or neutral background
- Fonts: one clean sans for titles and one mono font for labels and captions. Reuse your project's fonts if it has them
- Captions are short (2 to 6 words), in a consistent lower-third position, fading in over 0.3s and holding 2 to 3s
- Transitions: quick **push, cross-zoom or whip-pan** at 0.3 to 0.5s. No cheesy wipes
- Slow **zoom-ins** (100%→110%) on the exact element being explained
- Use arrows, highlight boxes or spotlight dimming to point at details (the audience can't hear you)

**Music**
- Style: modern cinematic or tech ambient that fits your project's mood, 100 to 120 BPM, building gradually
- Free and safe to post: YouTube Audio Library, Pixabay Music, Uppbeat, Mixkit. (Artlist or Epidemic if you have a subscription.) Check the licence and save proof so the video isn't muted or claimed
- Mix: music at about -14 LUFS overall, ducked slightly (about -3 dB) during sound effects
- **Cut on the beat:** put every major transition on a beat or bar line
- SFX (not voice): soft whoosh on transitions, subtle UI clicks on interactions, low rumble and a lid creak for the laptop opening in Video 2

**Export** (both): MP4, H.264, 1920×1080, 60fps (30fps is acceptable), about 16 to 20 Mbps, AAC 192 kbps. Also export Video 2 in **9:16 vertical (1080×1920)** for Reels, Shorts and LinkedIn.

**Editing tools:** DaVinci Resolve (free), CapCut or Premiere Pro.

---

## 3. Video 1: Full walkthrough (~2:40, no voice)

Without narration, **every idea needs a short on-screen caption plus a clear visual**. Show one idea at a time.

| Time | Scene | What's on screen | Caption |
|---|---|---|---|
| 0:00–0:08 | **Cold open** | Dark screen, subtle motion or particles, the project title fades in with a light sweep | `[PROJECT NAME]` / `BY [YOUR NAME]` |
| 0:08–0:22 | **What it is** | Landing page, home screen or dashboard, with a slow scroll or tour of the main layout | One-line pitch, then `THE PROBLEM IT SOLVES` |
| 0:22–0:47 | **Feature 1** | Full demo of your strongest feature with a clear start and finish. Zoom in on the key detail | `FEATURE 1 NAME` → one-line benefit |
| 0:47–1:12 | **Feature 2** | Demo with a zoom on the key detail | `FEATURE 2 NAME` → one-line benefit |
| 1:12–1:37 | **Feature 3** | Demo with a zoom on the key detail | `FEATURE 3 NAME` → one-line benefit |
| 1:37–2:02 | **Feature 4** | Demo with a zoom on the key detail | `FEATURE 4 NAME` → one-line benefit |
| 2:02–2:22 | **Under the hood** | Quick cuts: (1) code editor or architecture diagram, (2) project structure, (3) proof points such as a performance report, test results or analytics, (4) a second device or window size showing it works on mobile or other platforms | `BUILT WITH [STACK]` → `[PROOF POINT]` → `WORKS EVERYWHERE` |
| 2:22–2:40 | **Outro** | Fast montage of the best frame from each feature, then fade to an end card | `[PROJECT NAME]` → `[YOUR NAME]` → `[LINK]` |

**Scaling the time:** each feature gets about **(time between 0:22 and 2:02) ÷ number of features**. With 3 features use about 33s each, and with 5 features about 20s each. Keep the total within 2:00 to 3:00.

**Pacing notes**
- Give your **strongest feature** the best position (Feature 1) and a few extra seconds
- Keep every feature scene shaped the same way: show the **goal**, perform the **action**, show the **result**
- Vary the camera moves (zoom, pan, split-screen) so the features don't feel repetitive
- Leave about 0.5s of breathing room between scenes, and match the music's biggest build to your most impressive feature or the outro

---

## 4. Video 2: 56-second teaser (11s laptop intro + 45s project)

### Timeline

| Time | Duration | Scene | Details |
|---|---|---|---|
| 0:00–0:01 | 1s | **Black** | Dark room, soft particles, low rumble starts |
| 0:01–0:04.5 | 3.5s | **Laptop lid opens** | Closed laptop on a dark desk with a `[BRAND COLOR]` or soft white rim light. The lid opens smoothly (ease-in-out) and light spills across the keyboard |
| 0:04.5–0:07.5 | 3s | **Screen wakes** | Screen flashes on, and **your project appears on the laptop screen**. The camera begins a slow push-in. Add a soft beat or riser |
| 0:07.5–0:11 | 3.5s | **Push into the screen** | The camera pushes in until the screen fills the frame (**match cut** into the full-screen recording). Beat drop at about 0:07.5 |
| 0:11–0:17 | 6s | **Hero: "Meet the project"** | Full-screen first view of the project. Caption: `[PROJECT NAME]` + one-line pitch |
| 0:17–0:27 | 10s | **Feature 1 (signature moment)** | Your best feature, shown start to finish with a zoom on the key detail. Caption: feature name + benefit |
| 0:27–0:34 | 7s | **Feature 2** | Fast cut, one clear action and result |
| 0:34–0:41 | 7s | **Feature 3** | Fast cut, one clear action and result |
| 0:41–0:48 | 7s | **Feature 4** | Fast cut, one clear action and result (or a second look at Feature 1 if you have only three) |
| 0:48–0:53 | 5s | **Tech and proof montage** | 1s each: code editor, stack logos, real proof point, second-device view, a final polish moment. Captions: `BUILT WITH [STACK]`, `[PROOF POINT]` |
| 0:53–0:56 | 3s | **End card** | Hold on the logo. `[PROJECT NAME]`, `[YOUR NAME]`, `[LINK]`. Music resolves or fades out |

Intro is 11s (inside your 10 to 15s request). Project section is 45s. Total **56s**.

**If your project has fewer than 4 features:** add the extra seconds to Feature 1 and the tech montage rather than padding with weak scenes.

**If your project isn't a website** (mobile app, desktop tool, CLI, ML model): the laptop intro still works. Put a desktop recording on the laptop screen (an emulator window, terminal or notebook), or show a phone mockup on the desk beside the laptop. For hardware or physical projects, use the laptop only for the dashboard or software side and cut to real footage for the rest.

### How to make the laptop-opening intro

Pick whichever fits your skills and time. All three end with **your screen recording replacing the laptop's screen** via a corner-pin.

**Option A: Template or mockup (fastest, 20 to 40 minutes)**
- Use an animated device mockup: Canva (Apps → Mockups), CapCut laptop-opening templates, Placeit, or a free "laptop opening" After Effects/Premiere template from Envato or similar
- Drop your 1080p screen recording into the screen placeholder
- Add a particle or light-leak overlay (Screen blend mode) and grade the colours to match `[BRAND COLOR]`

**Option B: Blender (best quality, 2 to 4 hours)**
1. Use a free laptop model (check each model's licence on Sketchfab or BlenderKit)
2. Animate the lid hinge from 0° to about 105° over 3.5s with ease-in-out
3. Make the screen material emissive and apply your screen recording as a video texture
4. Add a rim light, a dark background, particles, depth of field, and a slow camera push-in
5. Render at 1080p, 60fps (Eevee is fast enough)

**Option C: AI video generator, then composite**
Generate the opening clip, then corner-pin your recording over the screen. Prompt:

> *Cinematic macro shot of a closed sleek dark-grey laptop on a black matte desk, dark studio background, soft [BRAND COLOR] rim light, floating dust particles in the air. The lid slowly opens in one smooth motion, a bright screen glows and casts light on the keyboard. The camera slowly pushes in toward the screen. Shallow depth of field, photorealistic, 4K, no text, no people, no logos.*

Tips: ask for a plain black or green screen if the tool lets you, because generated screen content won't be your project. In DaVinci Resolve, Premiere or CapCut, **track and corner-pin** your recording onto the screen. Generate a few takes and keep the best.

**Making the match cut seamless**
- The last intro frame should show the same state as the first frame of your full-screen recording (same screen, same scroll position)
- Blend with a 6 to 8 frame cross-dissolve while scaling the recording up to fill the frame

---

## 5. Editing checklist

- [ ] Place the music first and mark beats, then cut clips to the markers
- [ ] Speed-ramp clips slightly (110% to 125%) in Video 2 so it feels energetic. Keep Video 1 at 100% for clarity
- [ ] One consistent caption style, with nothing on screen longer than about 3s
- [ ] Subtle zoom keyframes on each key element, and a spotlight or arrow wherever the viewer needs to look
- [ ] Colour grade for consistency across all clips
- [ ] Audio: SFX on the laptop open, whooshes on cuts, UI clicks on interactions; no voice
- [ ] Watch with sound **off** (captions alone should explain the project), then with sound on
- [ ] Confirm Video 2 is exactly **0:56**

---

## 6. Posting

- Video 1: YouTube (public or unlisted), linked in your README and portfolio
- Video 2: LinkedIn, Instagram Reels, YouTube Shorts and X (use the vertical 9:16 version where supported)
- Add the project link, GitHub link and tech stack in the description

**Caption template**

> Built **[PROJECT NAME]**: [one-line pitch]. Key features: [Feature 1], [Feature 2], [Feature 3]. Built with [STACK]. 🔗 [LINK]
> #[relevant tag] #[relevant tag] #[relevant tag]

---

## 7. Final checklist

- [ ] Section 0 is fully filled in
- [ ] Video 1 is between 2:00 and 3:00 and covers every feature plus the tech and proof
- [ ] Video 2 is exactly 0:56, opens with the laptop (about 11s), and the remaining 45s explains the project
- [ ] No voiceover in either, only music and light SFX
- [ ] Music is royalty-free and the licence is saved
- [ ] Every number on screen is real
- [ ] Exported 1080p60 (plus a 9:16 version of Video 2)
