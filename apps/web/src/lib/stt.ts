// Speech to text. Default: Vosk running in a Web Worker with local models (no network). Two recognisers
// share the model: an open one, and one restricted to the restaurant's ordering vocabulary (menu names and
// aliases, numbers, spice and size words, yes/no). Each utterance is sent with both transcripts and the
// server keeps the one that matches the menu better.
// Optional: the browser's speech service, off by default, behind a Settings toggle.
// The microphone level is exposed for the waveform through an AnalyserNode.

export type SttLanguage = "en" | "hi" | "hinglish" | "auto";

export interface SttHandlers {
  onPartial: (text: string) => void;
  /** `alternatives`: the menu-biased transcript(s) of the same utterance, when they differ. */
  onFinal: (text: string, alternatives?: string[]) => void;
  onError: (message: string) => void;
}

export interface SttSession {
  analyser: AnalyserNode;
  stream: MediaStream; // the microphone, so the call can be recorded when that is switched on
  stop: () => void;
  /** Push-to-talk: audio is only recognised while the talk key is held. */
  setGate: (open: boolean) => void;
}

export const MODEL_URLS: Record<"en" | "hi", string> = {
  en: "/models/vosk-model-small-en-in-0.4.tar.gz",
  hi: "/models/vosk-model-small-hi-0.22.tar.gz",
};

async function modelAvailable(url: string): Promise<boolean> {
  try {
    const res = await fetch(url, { method: "HEAD" });
    return res.ok && !(res.headers.get("content-type") ?? "").includes("text/html");
  } catch {
    return false;
  }
}

async function openMic(): Promise<{ ctx: AudioContext; source: MediaStreamAudioSourceNode; stream: MediaStream; analyser: AnalyserNode }> {
  const stream = await navigator.mediaDevices.getUserMedia({
    audio: { echoCancellation: true, noiseSuppression: true, channelCount: 1 },
  });
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const analyser = ctx.createAnalyser();
  analyser.fftSize = 1024;
  analyser.smoothingTimeConstant = 0.7;
  source.connect(analyser);
  return { ctx, source, stream, analyser };
}

/** Offline recognition with vosk-browser. Hindi and Hinglish use the Hindi model (which also outputs
 *  Devanagari for spoken Hindi); English uses the Indian English model. */
async function orderingVocabulary(which: "en" | "hi"): Promise<string[] | null> {
  try {
    const res = await fetch(`/api/v1/nlu/vocabulary?lang=${which}`);
    if (!res.ok) return null;
    const body = (await res.json()) as { phrases: string[] };
    return body.phrases.length ? body.phrases : null;
  } catch {
    return null;
  }
}

/** Pairs the open and menu-biased results of one utterance. Both recognisers end an utterance at the same
 *  silence, so the second result follows within a few hundred milliseconds; after 600 ms the pair is sent
 *  with whatever arrived. */
export function utterancePairer(emit: (text: string, alternatives: string[]) => void, waitMs = 600) {
  let open: string | null = null;
  let menu: string | null = null;
  let timer: ReturnType<typeof setTimeout> | null = null;
  const clean = (t: string) => t.split(/\s+/).filter((w) => w && w !== "[unk]").join(" ");
  const flush = () => {
    if (timer) clearTimeout(timer);
    timer = null;
    const o = (open ?? "").trim();
    const m = menu ?? "";
    open = menu = null;
    if (!o && !clean(m)) return;
    if (o) emit(o, clean(m) && clean(m) !== o ? [m] : []);
    else emit(clean(m), []);
  };
  const arrive = () => {
    if (open !== null && menu !== null) flush();
    else if (!timer) timer = setTimeout(flush, waitMs);
  };
  return {
    open: (t: string) => { if (open !== null) flush(); open = t; arrive(); },
    menu: (t: string) => { if (menu !== null) flush(); menu = t; arrive(); },
    flush,
  };
}

export async function startOffline(lang: SttLanguage, h: SttHandlers): Promise<SttSession> {
  const which = lang === "en" ? "en" : "hi";
  const url = MODEL_URLS[which];
  if (!(await modelAvailable(url))) {
    throw new Error("The offline speech model is not installed. Run make install, or switch to Typed or a sample call.");
  }
  const { createModel } = await import("vosk-browser");
  const [model, phrases] = await Promise.all([createModel(url), orderingVocabulary(which)]);
  const mic = await openMic();
  const pair = utterancePairer((text, alts) => h.onFinal(text, alts));
  const recognizer = new model.KaldiRecognizer(mic.ctx.sampleRate);
  recognizer.on("partialresult", (m) => {
    const t = (m as { result: { partial: string } }).result.partial;
    if (t) h.onPartial(t);
  });
  const onError = (m: unknown) => h.onError(String((m as { error?: string }).error ?? "Speech recognition failed."));
  recognizer.on("result", (m) => (biased ? pair.open : (t: string) => t && h.onFinal(t))((m as { result: { text: string } }).result.text));
  recognizer.on("error", onError);
  // The menu-biased pass. Without the vocabulary (API unreachable) the open recogniser works alone.
  const biased = phrases ? new model.KaldiRecognizer(mic.ctx.sampleRate, JSON.stringify([...phrases, "[unk]"])) : null;
  biased?.on("result", (m) => pair.menu((m as { result: { text: string } }).result.text));
  biased?.on("error", () => { /* a vocabulary problem must not stop the open recogniser */ });

  let gateOpen = true;
  // ScriptProcessorNode is deprecated but is what vosk-browser expects; an AudioWorklet port can replace it.
  const processor = mic.ctx.createScriptProcessor(4096, 1, 1);
  processor.onaudioprocess = (ev) => {
    if (!gateOpen) return;
    try {
      recognizer.acceptWaveform(ev.inputBuffer);
      biased?.acceptWaveform(ev.inputBuffer);
    } catch (e) {
      h.onError(String(e));
    }
  };
  mic.source.connect(processor);
  processor.connect(mic.ctx.destination);

  return {
    analyser: mic.analyser,
    stream: mic.stream,
    setGate: (open) => {
      if (gateOpen && !open) {
        recognizer.retrieveFinalResult();
        biased?.retrieveFinalResult();
      }
      gateOpen = open;
    },
    stop: () => {
      processor.disconnect();
      mic.source.disconnect();
      mic.stream.getTracks().forEach((t) => t.stop());
      pair.flush();
      recognizer.remove();
      biased?.remove();
      model.terminate();
      void mic.ctx.close();
    },
  };
}

type WebSpeechCtor = new () => {
  lang: string; continuous: boolean; interimResults: boolean;
  onresult: ((e: { resultIndex: number; results: ArrayLike<{ isFinal: boolean; 0: { transcript: string } }> }) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void; stop(): void;
};

export function browserServiceSupported(): boolean {
  const w = window as unknown as { SpeechRecognition?: WebSpeechCtor; webkitSpeechRecognition?: WebSpeechCtor };
  return Boolean(w.SpeechRecognition || w.webkitSpeechRecognition);
}

/** The browser's speech service. Audio may leave the device; only used when switched on in Settings. */
export async function startBrowserService(lang: SttLanguage, h: SttHandlers): Promise<SttSession> {
  const w = window as unknown as { SpeechRecognition?: WebSpeechCtor; webkitSpeechRecognition?: WebSpeechCtor };
  const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
  if (!Ctor) throw new Error("This browser has no speech service. Use offline speech or Typed.");
  const mic = await openMic();
  const rec = new Ctor();
  rec.lang = lang === "en" ? "en-IN" : "hi-IN";
  rec.continuous = true;
  rec.interimResults = true;
  let running = true;
  let gate = true;
  rec.onresult = (e) => {
    if (!gate) return;
    for (let i = e.resultIndex; i < e.results.length; i++) {
      const r = e.results[i];
      if (r.isFinal) h.onFinal(r[0].transcript.trim());
      else h.onPartial(r[0].transcript);
    }
  };
  rec.onerror = (e) => e.error !== "no-speech" && h.onError(`Speech service error: ${e.error}`);
  rec.onend = () => running && rec.start();
  rec.start();
  return {
    analyser: mic.analyser,
    stream: mic.stream,
    setGate: (open) => (gate = open),
    stop: () => {
      running = false;
      rec.stop();
      mic.stream.getTracks().forEach((t) => t.stop());
      void mic.ctx.close();
    },
  };
}

/** Simple energy-based voice activity: RMS of the time-domain signal, 0..1. */
export function micLevel(analyser: AnalyserNode, buf: Float32Array): number {
  analyser.getFloatTimeDomainData(buf);
  let sum = 0;
  for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
  return Math.min(1, Math.sqrt(sum / buf.length) * 6);
}
