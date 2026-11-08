// Call state for the Call desk: one WebSocket per call, speech in and out, the sample player, menu
// highlights, staff additions from the menu, and the optional call recording.
import { create } from "zustand";
import { api } from "@/lib/api";
import * as stt from "@/lib/stt";
import { isBargeIn } from "@/lib/bargein";
import { cancelSpeech, setMuted, setNaturalVoice, speak } from "@/lib/tts";
import type { Cart, CallState, GlossPart, NluMatch, Order, ServerEvent } from "@/lib/types";
import { CallSocket, type ClientMessage } from "@/lib/ws";

export type Engine = "offline" | "typed";
export type Lang = "auto" | "en" | "hi" | "hinglish";
export type Status =
  | "idle" | "connecting" | "listening" | "speaking" | "clarifying" | "offering" | "confirming" | "sending"
  | "done" | "error";

export const STATUS_TEXT: Record<Status, string> = {
  idle: "Ready",
  connecting: "Connecting",
  listening: "Listening",
  speaking: "Assistant speaking",
  clarifying: "Waiting for a choice",
  offering: "Offer made",
  confirming: "Confirming the order",
  sending: "Sending to PoS",
  done: "Call ended",
  error: "Something went wrong",
};

export interface Line {
  id: number;
  speaker: "guest" | "assistant";
  text: string;          // English, what the screen shows
  original: string;      // what was recognised or spoken
  partial?: boolean;
  parts?: GlossPart[];
  matches?: NluMatch[];
  lang?: string;
  interrupted?: boolean; // the caller cut in while the agent said this
}

export interface Clarify {
  clarify_id: string;
  question: string;
  options: { id: number | string; label: string }[];
}

export interface Offer {
  offer_id: string;
  kind: "rule" | "combo";
  item: { id: number; name: string; price: number };
  reason: { headline: string; why: string[]; expected_gain: number };
}

interface CallStore {
  status: Status;
  serverState: CallState | null;
  callId: string | null;
  startedAt: number | null;
  endedAt: number | null;
  engine: Engine;
  lang: Lang;
  pushToTalk: boolean;
  talking: boolean;
  muted: boolean;
  showOriginal: boolean;
  lines: Line[];
  cart: Cart | null;
  clarify: Clarify | null;
  offer: Offer | null;
  order: Order | null;
  kotNo: string | null;
  pos: "none" | "sending" | "acked" | "failed";
  error: string | null;
  suggestTyped: boolean;
  heardLang: string | null;
  highlight: { itemId: number; at: number; kind: "heard" | "staff" } | null;
  recording: boolean;
  analyser: AnalyserNode | null;
  setEngine: (e: Engine) => void;
  setLang: (l: Lang) => void;
  setPushToTalk: (v: boolean) => void;
  setTalking: (v: boolean) => void;
  toggleMute: () => void;
  setShowOriginal: (v: boolean) => void;
  start: (opts?: { manual?: boolean }) => Promise<void>;
  sendText: (text: string, alternatives?: string[]) => void;
  choose: (option: number | string) => void;
  answerOffer: (accept: boolean) => void;
  addItem: (itemId: number, delta: number) => void;
  addCombo: (comboId: string) => void;
  confirmOrder: () => void;
  sendToPos: () => void;
  end: () => void;
  reset: () => void;
}

let socket: CallSocket | null = null;
let starting: Promise<void> | null = null;
let speech: stt.SttSession | null = null;
let recorder: MediaRecorder | null = null;
let chunks: Blob[] = [];
let lineId = 1;
let speaking: Promise<void> = Promise.resolve();
let spokenNow = ""; // the reply being spoken (screen and voice forms), to tell echo from the caller
let bargeInOn = true; // Settings: speech.barge_in
const levelBuf = new Float32Array(1024);

/** Apply the speech settings (voice, barge-in) for the next calls. */
export function configureSpeech(opts: { voice?: "natural" | "browser"; bargeIn?: boolean }) {
  if (opts.voice) setNaturalVoice(opts.voice === "natural");
  if (opts.bargeIn !== undefined) bargeInOn = opts.bargeIn;
}

function statusFor(state: CallState, s: CallStore): Status {
  switch (state) {
    case "CLARIFYING": return "clarifying";
    case "OFFERING": return "offering";
    case "CONFIRMING":
    case "CAPTURING_DETAILS": return "confirming";
    case "FINALIZED": return s.pos === "acked" ? "done" : "sending";
    case "ABANDONED": return "done";
    default: return "listening";
  }
}

export const useCall = create<CallStore>((set, get) => {
  const lastGuestIndex = (lines: Line[]) => {
    for (let i = lines.length - 1; i >= 0; i--) if (lines[i].speaker === "guest") return i;
    return -1;
  };

  const handle = (ev: ServerEvent) => {
    const s = get();
    switch (ev.type) {
      case "state.changed":
        set({ serverState: ev.state, status: statusFor(ev.state, s) });
        if (ev.state !== "CLARIFYING") set({ clarify: null });
        if (ev.state !== "OFFERING") set({ offer: null });
        if (ev.state === "ABANDONED") finish();
        break;
      case "transcript": {
        const lines = [...s.lines];
        const i = lastGuestIndex(lines);
        const line: Line = { id: i >= 0 ? lines[i].id : lineId++, speaker: "guest", text: ev.display_text_en,
          original: ev.original_text, parts: ev.parts, lang: ev.lang };
        if (i >= 0 && !lines[i].parts) lines[i] = { ...lines[i], ...line };
        else lines.push(line);
        set({ lines, heardLang: ev.lang });
        break;
      }
      case "nlu.result": {
        const lines = [...s.lines];
        const i = lastGuestIndex(lines);
        if (i >= 0) lines[i] = { ...lines[i], matches: ev.matches };
        set({ lines });
        break;
      }
      case "menu.highlight":
        set({ highlight: { itemId: ev.item_id, at: Date.now(), kind: ev.kind } });
        break;
      case "cart.updated":
        set({ cart: ev.cart });
        break;
      case "clarify.ask":
        set({ clarify: { clarify_id: ev.clarify_id, question: ev.question_en, options: ev.options } });
        break;
      case "upsell.offer":
        set({ offer: { offer_id: ev.offer_id, kind: ev.kind, item: ev.item, reason: ev.reason } });
        break;
      case "reply.say": {
        set({
          lines: [...get().lines, { id: lineId++, speaker: "assistant", text: ev.display_text_en, original: ev.text, lang: ev.lang }],
          suggestTyped: Boolean(ev.suggest_typed) || get().suggestTyped,
        });
        const prev = get().status;
        const voiceText = ev.speech_text ?? ev.text;
        const voiceLang = ev.speech_lang ?? (ev.lang === "en" ? "en" : "hi");
        // With barge-in the microphone stays open so the caller can cut in; otherwise it closes while
        // the agent speaks, so it does not hear itself.
        if (!canBargeIn()) speech?.setGate(false);
        spokenNow = `${spokenNow} ${ev.text} ${ev.display_text_en} ${voiceText}`;
        set({ status: "speaking" });
        speaking = speak(voiceText, voiceLang).then(() => {
          const now = get();
          if (now.status === "speaking") {
            set({ status: now.serverState ? statusFor(now.serverState, now) : prev });
            spokenNow = "";
          }
          if (!now.pushToTalk) speech?.setGate(true);
          socket?.send({ type: "ui.listening" });
        });
        break;
      }
      case "order.finalized":
        set({ order: ev.order, pos: "sending", status: "sending" });
        break;
      case "pos.sent":
        set({ pos: "sending" });
        break;
      case "pos.ack":
        set({ pos: "acked", kotNo: ev.kot_no });
        void speaking.then(() => set({ status: "done" }));
        finish();
        break;
      case "error":
        set({ pos: get().order ? "failed" : get().pos, error: ev.message });
        break;
    }
  };

  // Staff taps on the menu. The socket exists only once the call is created, so taps that start the call
  // (or land while it connects) are sent after it, in order.
  const staffSend = (msg: ClientMessage) => {
    const live = !["idle", "done", "error"].includes(get().status);
    if (!live && !starting) starting = get().start({ manual: true }).finally(() => { starting = null; });
    if (starting) void starting.then(() => socket?.send(msg));
    else socket?.send(msg);
  };

  const canBargeIn = () => bargeInOn && get().engine === "offline" && !get().pushToTalk && speech !== null;

  const micLevel = () => (speech ? stt.micLevel(speech.analyser, levelBuf) : 0);

  /** The caller spoke over the agent: stop the voice now and listen. */
  const bargeIn = () => {
    cancelSpeech();
    spokenNow = "";
    const lines = [...get().lines];
    for (let i = lines.length - 1; i >= 0; i--) {
      if (lines[i].speaker === "assistant") { lines[i] = { ...lines[i], interrupted: true }; break; }
    }
    const s = get();
    set({ lines, status: s.serverState ? statusFor(s.serverState, s) : "listening" });
    socket?.send({ type: "ui.barge_in" });
  };

  const finish = () => {
    stopRecording();
    speech?.stop();
    speech = null;
    set({ endedAt: get().endedAt ?? Date.now(), analyser: null });
  };

  const startRecording = (stream: MediaStream) => {
    if (typeof MediaRecorder === "undefined") return;
    chunks = [];
    try {
      recorder = new MediaRecorder(stream, MediaRecorder.isTypeSupported("audio/webm") ? { mimeType: "audio/webm" } : undefined);
    } catch {
      return;
    }
    recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
    recorder.start(1000);
    set({ recording: true });
  };

  const stopRecording = () => {
    const rec = recorder;
    const callId = get().callId;
    const started = get().startedAt;
    if (!rec || !callId) return;
    recorder = null;
    rec.onstop = () => {
      const blob = new Blob(chunks, { type: rec.mimeType || "audio/webm" });
      chunks = [];
      set({ recording: false });
      if (blob.size) {
        void api.uploadRecording(callId, blob, started ? (Date.now() - started) / 1000 : 0).catch(() =>
          set({ error: "The recording could not be saved. The transcript is kept." }));
      }
    };
    if (rec.state !== "inactive") rec.stop();
  };

  const startSpeech = async () => {
    const { engine, lang } = get();
    if (engine !== "offline") return;
    const settings = await api.settings().catch(() => null);
    const useBrowser = settings?.speech.browser_service && stt.browserServiceSupported();
    const handlers: stt.SttHandlers = {
      onPartial: (text) => {
        if (get().status === "speaking") {
          // Only real speech from the caller cuts in; the agent's own voice coming back is ignored.
          if (!canBargeIn() || !isBargeIn({ heard: text, spoken: spokenNow, level: micLevel() })) return;
          bargeIn();
        }
        const lines = [...get().lines];
        const last = lines[lines.length - 1];
        if (last?.speaker === "guest" && last.partial) lines[lines.length - 1] = { ...last, text, original: text };
        else lines.push({ id: lineId++, speaker: "guest", text, original: text, partial: true });
        set({ lines });
      },
      onFinal: (text, alternatives) => {
        if (get().status === "speaking") {
          if (!canBargeIn() || !isBargeIn({ heard: text, spoken: spokenNow, level: micLevel(), final: true })) return;
          bargeIn();
        }
        get().sendText(text, alternatives);
      },
      onError: (message) => set({ error: message }),
    };
    try {
      speech = useBrowser ? await stt.startBrowserService(lang, handlers) : await stt.startOffline(lang, handlers);
      speech.setGate(!get().pushToTalk);
      set({ analyser: speech.analyser });
      if (settings?.recording.enabled && speech.stream) startRecording(speech.stream);
    } catch (e) {
      set({ error: e instanceof Error ? e.message : String(e), engine: "typed" });
    }
  };

  return {
    status: "idle",
    serverState: null,
    callId: null,
    startedAt: null,
    endedAt: null,
    engine: "typed",
    lang: "auto",
    pushToTalk: false,
    talking: false,
    muted: false,
    showOriginal: false,
    lines: [],
    cart: null,
    clarify: null,
    offer: null,
    order: null,
    kotNo: null,
    pos: "none",
    error: null,
    suggestTyped: false,
    heardLang: null,
    highlight: null,
    recording: false,
    analyser: null,

    setEngine: (engine) => set({ engine }),
    setLang: (lang) => set({ lang }),
    setPushToTalk: (pushToTalk) => {
      set({ pushToTalk });
      speech?.setGate(!pushToTalk);
    },
    setTalking: (talking) => {
      set({ talking });
      if (get().pushToTalk) speech?.setGate(talking);
    },
    toggleMute: () => {
      const muted = !get().muted;
      setMuted(muted);
      set({ muted });
    },
    setShowOriginal: (showOriginal) => set({ showOriginal }),

    start: async (opts) => {
      get().reset();
      if (opts?.manual) set({ engine: "typed" });
      set({ status: "connecting", startedAt: Date.now() });
      try {
        const { call_id } = await api.startCall();
        set({ callId: call_id });
        socket = new CallSocket(call_id, {
          onEvent: handle,
          onStatus: (st) => {
            if (st === "closed" && get().status !== "done") set({ status: "error", error: "The call connection closed. Start a new call." });
          },
        });
        socket.connect();
        if (!opts?.manual) await startSpeech();
      } catch (e) {
        set({ status: "error", error: e instanceof Error ? e.message : String(e) });
      }
    },

    sendText: (text, alternatives) => {
      const clean = text.trim();
      if (!clean || !socket) return;
      if (get().status === "speaking") bargeIn(); // typing over the agent stops it too
      const lines = [...get().lines];
      const last = lines[lines.length - 1];
      if (last?.speaker === "guest" && last.partial) lines[lines.length - 1] = { ...last, text: clean, original: clean, partial: false };
      else lines.push({ id: lineId++, speaker: "guest", text: clean, original: clean });
      set({ lines });
      const lang = get().lang;
      socket.send({ type: "transcript.final", text: clean, ...(lang !== "auto" ? { lang_hint: lang } : {}),
        ...(alternatives?.length ? { alternatives } : {}) });
    },

    choose: (option) => {
      const c = get().clarify;
      if (c) socket?.send({ type: "ui.choice", clarify_id: c.clarify_id, option_id: option });
    },

    answerOffer: (accept) => {
      const o = get().offer;
      if (o) socket?.send({ type: "ui.offer", offer_id: o.offer_id, action: accept ? "accept" : "decline" });
    },

    addItem: (itemId, delta) => staffSend({ type: "ui.add_item", item_id: itemId, qty_delta: delta }),
    addCombo: (comboId) => staffSend({ type: "ui.add_combo", combo_id: comboId }),

    confirmOrder: () => socket?.send({ type: "ui.confirm" }),
    sendToPos: () => socket?.send({ type: "ui.send" }),

    end: () => {
      socket?.send({ type: "ui.end" });
      cancelSpeech();
      finish();
      if (get().status !== "done") set({ status: "done" });
    },

    reset: () => {
        stopRecording();
      socket?.close();
      socket = null;
      speech?.stop();
      speech = null;
      cancelSpeech();
      set({
        status: "idle", serverState: null, callId: null, startedAt: null, endedAt: null, lines: [], cart: null,
        clarify: null, offer: null, order: null, kotNo: null, pos: "none", error: null, suggestTyped: false,
        analyser: null, heardLang: null, highlight: null, recording: false,
      });
    },
  };
});
