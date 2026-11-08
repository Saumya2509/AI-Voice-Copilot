// Spoken replies. Natural voice first: Piper, made on this machine by the API (GET /tts) and played with
// Web Audio, whose real output level drives the waveform. If the natural voice is off, not installed or
// slow to answer, the browser's own speechSynthesis voice speaks instead. Replies play in order; cancelling
// (the caller cut in, or the call ended) stops the current one and drops the queue.

type Listener = (level: number) => void;

let muted = false;
let natural = true; // Settings: speech.voice
let naturalInstalled: boolean | null = null; // from GET /tts/status, asked once
const listeners = new Set<Listener>();
let generation = 0; // bumps on cancel; queued replies from an older generation are dropped
let queue: Promise<void> = Promise.resolve();
let ctx: AudioContext | null = null;
let current: { stop: () => void } | null = null;

/** How long to wait for the natural voice before using the browser's voice for this reply. */
const NATURAL_WAIT_MS = 2500;

export function onSpeechLevel(fn: Listener): () => void {
  listeners.add(fn);
  return () => listeners.delete(fn);
}

function emit(level: number) {
  listeners.forEach((l) => l(level));
}

export function setMuted(m: boolean) {
  muted = m;
  if (m) cancelSpeech();
}

export function setNaturalVoice(on: boolean) {
  natural = on;
}

export const isSupported = () => typeof window !== "undefined" && "speechSynthesis" in window;

async function naturalAvailable(): Promise<boolean> {
  if (naturalInstalled === null) {
    try {
      const res = await fetch("/api/v1/tts/status");
      naturalInstalled = res.ok && Boolean(((await res.json()) as { available: boolean }).available);
    } catch {
      naturalInstalled = false;
    }
  }
  return naturalInstalled;
}

function pickVoice(lang: string): SpeechSynthesisVoice | undefined {
  const voices = window.speechSynthesis.getVoices();
  const want = lang === "en" ? ["en-IN", "en-GB", "en"] : ["hi-IN", "en-IN", "hi"];
  for (const w of want) {
    const v = voices.find((x) => x.lang.toLowerCase().startsWith(w.toLowerCase()));
    if (v) return v;
  }
  return undefined;
}

function speakBrowser(text: string, lang: string): Promise<void> {
  if (!isSupported()) return Promise.resolve();
  return new Promise((resolve) => {
    const u = new SpeechSynthesisUtterance(text);
    const voice = pickVoice(lang);
    if (voice) u.voice = voice;
    u.lang = voice?.lang ?? (lang === "en" ? "en-IN" : "hi-IN");
    u.rate = 1.02;
    let decay: number | undefined;
    let settled = false;
    u.onboundary = () => {
      emit(0.55 + Math.random() * 0.45);
      window.clearTimeout(decay);
      decay = window.setTimeout(() => emit(0.15), 140);
    };
    const done = () => {
      if (settled) return;
      settled = true;
      current = null;
      emit(0);
      resolve();
    };
    u.onend = done;
    u.onerror = done;
    window.setTimeout(done, 1500 + text.length * 90); // safety net: some voices never fire onend
    current = { stop: () => { window.speechSynthesis.cancel(); done(); } };
    emit(0.3);
    window.speechSynthesis.speak(u);
  });
}

async function fetchNatural(text: string, lang: string): Promise<AudioBuffer | null> {
  const ac = new AbortController();
  const timer = window.setTimeout(() => ac.abort(), NATURAL_WAIT_MS);
  try {
    const res = await fetch(`/api/v1/tts?${new URLSearchParams({ text: text.slice(0, 400), lang: lang === "en" ? "en" : "hi" })}`,
      { signal: ac.signal });
    if (!res.ok) return null;
    const data = await res.arrayBuffer();
    ctx ??= new AudioContext();
    if (ctx.state === "suspended") await ctx.resume().catch(() => {});
    return await ctx.decodeAudioData(data);
  } catch {
    return null;
  } finally {
    window.clearTimeout(timer);
  }
}

function play(buffer: AudioBuffer): Promise<void> {
  const audio = ctx!;
  return new Promise((resolve) => {
    const src = audio.createBufferSource();
    src.buffer = buffer;
    const analyser = audio.createAnalyser();
    analyser.fftSize = 512;
    src.connect(analyser).connect(audio.destination);
    const buf = new Float32Array(analyser.fftSize);
    let raf = 0;
    const meter = () => {
      analyser.getFloatTimeDomainData(buf);
      let sum = 0;
      for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
      emit(Math.min(1, Math.sqrt(sum / buf.length) * 5));
      raf = requestAnimationFrame(meter);
    };
    let settled = false;
    const done = () => {
      if (settled) return;
      settled = true;
      cancelAnimationFrame(raf);
      current = null;
      emit(0);
      resolve();
    };
    src.onended = done;
    current = { stop: () => { try { src.stop(); } catch { /* already stopped */ } done(); } };
    src.start();
    meter();
  });
}

async function speakOne(text: string, lang: string, gen: number): Promise<void> {
  if (gen !== generation || muted) return;
  if (natural && (await naturalAvailable())) {
    const buffer = await fetchNatural(text, lang);
    if (gen !== generation || muted) return;
    if (buffer) return play(buffer);
  }
  return speakBrowser(text, lang);
}

/** Speak after any reply already playing; resolves when this reply has finished (or was cancelled).
 *  `lang` is "en" or "hi" (Hindi and Hinglish replies are spoken from their Devanagari form). */
export function speak(text: string, lang: string): Promise<void> {
  if (muted || !text) return Promise.resolve();
  const gen = generation;
  const mine = queue.then(() => speakOne(text, lang, gen));
  queue = mine.catch(() => {});
  return mine.catch(() => {});
}

/** Stop the reply playing now and drop any queued ones. */
export function cancelSpeech() {
  generation++;
  queue = Promise.resolve();
  current?.stop();
  if (isSupported()) window.speechSynthesis.cancel();
  emit(0);
}
