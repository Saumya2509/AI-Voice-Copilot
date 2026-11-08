// WebSocket client for /ws/call/{id}. Events carry an increasing `seq`; older ones are ignored.
// On reconnect the client sends the last seq it saw and the server replays what was missed.
import type { ServerEvent } from "./types";

export type ClientMessage =
  | { type: "transcript.partial"; text: string; lang_hint?: string }
  | { type: "transcript.final"; text: string; confidence?: number; lang_hint?: string; alternatives?: string[] }
  | { type: "ui.choice"; clarify_id: string; option_id: number | string }
  | { type: "ui.offer"; offer_id: string; action: "accept" | "decline" }
  | { type: "ui.end" }
  | { type: "ui.add_item"; item_id: number; qty_delta: number }
  | { type: "ui.add_combo"; combo_id: string }
  | { type: "ui.confirm" }
  | { type: "ui.send" }
  | { type: "ui.listening" }
  | { type: "ui.barge_in" };

export interface CallSocketHandlers {
  onEvent: (e: ServerEvent) => void;
  onStatus: (s: "connecting" | "open" | "reconnecting" | "closed") => void;
}

export class CallSocket {
  private ws: WebSocket | null = null;
  private lastSeq = 0;
  private closedByUs = false;
  private retries = 0;
  private queue: ClientMessage[] = [];

  constructor(private callId: string, private h: CallSocketHandlers) {}

  connect() {
    this.h.onStatus(this.lastSeq ? "reconnecting" : "connecting");
    const proto = location.protocol === "https:" ? "wss" : "ws";
    const ws = new WebSocket(`${proto}://${location.host}/ws/call/${this.callId}`);
    this.ws = ws;
    ws.onopen = () => {
      this.retries = 0;
      if (this.lastSeq) ws.send(JSON.stringify({ type: "resume", last_seq: this.lastSeq }));
      this.h.onStatus("open");
      this.queue.splice(0).forEach((m) => ws.send(JSON.stringify(m)));
    };
    ws.onmessage = (msg) => {
      const ev = JSON.parse(msg.data) as ServerEvent;
      if (typeof ev.seq === "number") {
        if (ev.seq <= this.lastSeq) return;
        this.lastSeq = ev.seq;
      }
      this.h.onEvent(ev);
    };
    ws.onclose = () => {
      if (this.closedByUs) return this.h.onStatus("closed");
      this.retries += 1;
      if (this.retries > 6) return this.h.onStatus("closed");
      this.h.onStatus("reconnecting");
      setTimeout(() => this.connect(), Math.min(4000, 300 * 2 ** this.retries));
    };
  }

  send(m: ClientMessage) {
    if (this.ws?.readyState === WebSocket.OPEN) this.ws.send(JSON.stringify(m));
    else this.queue.push(m);
  }

  close() {
    this.closedByUs = true;
    this.ws?.close();
  }
}

/** Keep only events newer than what we have, in order. Exported for tests. */
export function mergeEvents(have: ServerEvent[], incoming: ServerEvent[]): ServerEvent[] {
  const last = have.length ? have[have.length - 1].seq : 0;
  return [...have, ...incoming.filter((e) => e.seq > last).sort((a, b) => a.seq - b.seq)];
}
