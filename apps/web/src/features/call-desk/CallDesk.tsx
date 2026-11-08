// Call desk (improve.md, section 5). All call controls sit in one toolbar at the top. Below it, three
// columns: the conversation (with today's confirmed orders under it), the restaurant menu card (the Menu
// section's design, combos first), and the printed ticket in the top-right corner, so nothing covers the
// menu. On phones the three are tabs.
import { useEffect, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { Switch } from "@/components/ui";
import { api } from "@/lib/api";
import { rupees } from "@/lib/format";
import { useMediaQuery } from "@/lib/motion";
import { CallBar } from "./CallBar";
import { ConfirmedOrders } from "./ConfirmedOrders";
import { MenuPanel } from "./MenuPanel";
import { ClarifyChips, OfferCard } from "./Prompts";
import { TicketPanel, useTicketSummary } from "./TicketPanel";
import { Transcript } from "./Transcript";
import { configureSpeech, useCall } from "./useCall";

export default function CallDesk() {
  const s = useCall();
  const narrow = useMediaQuery("(max-width: 1023px)");
  const [tab, setTab] = useState<"call" | "menu" | "ticket">("call");
  const ticket = useTicketSummary();
  const live = !["idle", "done", "error"].includes(s.status);

  useEffect(() => {
    if (useCall.getState().status !== "idle") return;
    api.settings().then((st) => {
      useCall.getState().setEngine(st.speech.engine);
      configureSpeech({ voice: st.speech.voice ?? "natural", bargeIn: st.speech.barge_in ?? true });
    }).catch(() => {});
  }, []);

  const conversation = (
    <section aria-label="Conversation" className="flex min-w-0 flex-col gap-4">
      <div className="flex items-center justify-between gap-x-3 border-b border-ink/15">
        <h2 className="min-w-0 font-display text-xl">Conversation <span className="whitespace-nowrap font-sans text-sm font-normal text-muted">in English</span></h2>
        <div className="shrink-0 whitespace-nowrap [&>label]:gap-3"><Switch checked={s.showOriginal} onChange={s.setShowOriginal} label="Show original" /></div>
      </div>
      {s.error && (
        <p role="alert" className="flex items-start gap-2 text-sm">
          <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-chilli" aria-hidden />{s.error}
        </p>
      )}
      {s.lines.length === 0 ? (live ? (
        <p className="py-6 text-md">Waiting for the caller.</p>
      ) : <ReadyGuide engine={s.engine} />) : <Transcript />}
      {live && (s.engine === "typed" || s.suggestTyped) && <TypedInput />}
      {live && s.engine === "offline" && <TalkControls />}
      {/* Stays in view at the bottom of the screen while it sits under a long transcript. */}
      <div className="sticky bottom-3 z-10 flex flex-col gap-3 bg-plate empty:hidden">
        <ClarifyChips />
        <OfferCard />
      </div>
      <ConfirmedOrders />
    </section>
  );

  return (
    <div className="mx-auto max-w-[1600px] px-4 pb-6 sm:px-6">
      <CallBar />
      <div className="pt-5">
        {narrow ? (
          <>
            <div role="tablist" aria-label="Call desk" className="mb-4 flex gap-1">
              {(["call", "menu", "ticket"] as const).map((t) => (
                <button key={t} role="tab" aria-selected={tab === t} onClick={() => setTab(t)}
                  className={`rounded-sm px-3 py-1.5 text-sm sm:px-4 ${tab === t ? "bg-indigo text-on-indigo" : "border border-ink/25"}`}>
                  {t === "call" ? "Conversation" : t === "menu" ? "Menu" : (
                    <>Ticket{ticket.count > 0 && <span className="num ml-1.5">{ticket.count} · {rupees(ticket.total)}</span>}</>
                  )}
                </button>
              ))}
            </div>
            {tab === "call" ? conversation : (
              <div className="flex h-[calc(100dvh-250px)] min-h-[420px] flex-col">{tab === "menu" ? <MenuPanel /> : <TicketPanel />}</div>
            )}
          </>
        ) : (
          <div className="grid grid-cols-[minmax(0,4fr)_minmax(0,5fr)_300px] gap-6 xl:grid-cols-[minmax(0,4fr)_minmax(0,5fr)_340px] xl:gap-8">
            {conversation}
            <div className="sticky top-[144px] flex h-[calc(100dvh-144px-24px)] flex-col border-l border-ink/15 pl-6 xl:pl-8">
              <MenuPanel />
            </div>
            <div className="sticky top-[144px] flex h-[calc(100dvh-144px-24px)] flex-col border-l border-ink/15 pl-6 xl:pl-8">
              <TicketPanel />
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

const STEPS = [
  { n: "1", title: "Start the call", body: "Press Start call when the phone rings." },
  { n: "2", title: "Take the order", body: "" },
  { n: "3", title: "Check and send", body: "Read the ticket back, then send it to the kitchen." },
];

function ReadyGuide({ engine }: { engine: string }) {
  const take = engine === "typed"
    ? "Type what the caller says, or tap dishes on the menu."
    : "Talk into the microphone, or tap dishes on the menu.";
  return (
    <ol className="grid gap-4 py-4 sm:grid-cols-3 lg:grid-cols-1 2xl:grid-cols-3">
      {STEPS.map((st) => (
        <li key={st.n} className="flex gap-3">
          <span className="num grid h-8 w-8 shrink-0 place-items-center rounded-full border-2 border-ink/80 text-sm font-medium">{st.n}</span>
          <span>
            <span className="block text-md font-medium">{st.title}</span>
            <span className="block text-sm text-muted">{st.body || take}</span>
          </span>
        </li>
      ))}
    </ol>
  );
}

function TypedInput() {
  const [text, setText] = useState("");
  const send = useCall((s) => s.sendText);
  const ref = useRef<HTMLInputElement>(null);
  useEffect(() => ref.current?.focus(), []);
  return (
    <form className="flex gap-2" onSubmit={(e) => { e.preventDefault(); send(text); setText(""); }}>
      <label htmlFor="typed" className="sr-only">What the caller says</label>
      <input id="typed" ref={ref} className="field h-12 min-w-0 flex-1 text-base" autoComplete="off" value={text}
        onChange={(e) => setText(e.target.value)} placeholder="Type what the caller says, for example ek dal makhani aur do butter naan" />
      <button className="btn-primary h-12" disabled={!text.trim()}>Send</button>
    </form>
  );
}

function TalkControls() {
  const { pushToTalk, setPushToTalk, talking, setTalking } = useCall();
  useEffect(() => {
    if (!pushToTalk) return;
    const down = (e: KeyboardEvent) => e.code === "Space" && !e.repeat && (e.target as HTMLElement).tagName !== "INPUT" && (e.preventDefault(), setTalking(true));
    const up = (e: KeyboardEvent) => e.code === "Space" && setTalking(false);
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [pushToTalk, setTalking]);
  return (
    <div className="flex flex-wrap items-center gap-3">
      <div role="radiogroup" aria-label="Microphone mode" className="inline-flex rounded-sm border border-ink/25 p-0.5">
        {[{ v: false, l: "Always listening" }, { v: true, l: "Push to talk" }].map((o) => (
          <button key={o.l} role="radio" aria-checked={pushToTalk === o.v} onClick={() => setPushToTalk(o.v)}
            className={`h-8 rounded-[2px] px-3 text-sm ${pushToTalk === o.v ? "bg-indigo text-on-indigo" : "text-ink/80 hover:bg-ink/5"}`}>{o.l}</button>
        ))}
      </div>
      {pushToTalk && (
        <button className={`btn h-12 px-5 ${talking ? "bg-haldi text-ink" : "btn-secondary"}`} aria-pressed={talking}
          onPointerDown={() => setTalking(true)} onPointerUp={() => setTalking(false)} onPointerLeave={() => talking && setTalking(false)}>
          <Icon name="mic" /> {talking ? "Listening, release to send" : "Hold to talk (or hold Space)"}
        </button>
      )}
    </div>
  );
}
