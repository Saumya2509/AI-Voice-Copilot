// The Call desk's top toolbar: everything that controls the call, in one row under the navbar.
// Left: title, call button, timer and status, a compact live waveform, the language heard.
// Right: language, input (offline speech or typed) and mute.
import { useEffect, useState } from "react";
import { Icon } from "@/components/Icon";
import { duration, LANGUAGE_LABEL } from "@/lib/format";
import { STATUS_TEXT, useCall, type Engine, type Lang } from "./useCall";
import { Waveform } from "./Waveform";

const ENGINES: { value: Engine; label: string; icon: "mic" | "keyboard" }[] = [
  { value: "offline", label: "Offline speech", icon: "mic" },
  { value: "typed", label: "Typed", icon: "keyboard" },
];
const LANGS: { value: Lang; label: string }[] = [
  { value: "auto", label: "Auto" }, { value: "en", label: "English" }, { value: "hi", label: "Hindi" },
  { value: "hinglish", label: "Hinglish" },
];

export function CallBar() {
  const s = useCall();
  const live = !["idle", "done", "error"].includes(s.status);
  const [, tick] = useState(0);

  useEffect(() => {
    if (!live) return;
    const t = setInterval(() => tick((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, [live]);

  const elapsed = s.startedAt ? (s.endedAt ?? Date.now()) - s.startedAt : 0;
  const dot = live ? (s.status === "speaking" ? "bg-haldi" : "bg-leaf") : s.status === "error" ? "bg-chilli" : "bg-ink/30";

  return (
    <div className="sticky top-nav z-20 -mx-4 border-b border-ink/15 bg-plate px-4 py-3 sm:-mx-6 sm:px-6">
      <div className="flex flex-wrap items-center gap-x-5 gap-y-3">
        <h1 className="sr-only font-display text-lg leading-none sm:not-sr-only">Call desk</h1>
        <button onClick={() => (live ? s.end() : void s.start())}
          className={`btn h-11 px-5 text-base ${live ? "bg-chilli text-paper hover:bg-chilli/90" : "bg-indigo text-on-indigo hover:bg-indigo/90"}`}>
          <Icon name={live ? "hangup" : "phone"} />
          {live ? "End call" : "Start call"}
        </button>
        <div className="flex items-baseline gap-3">
          <span className="num text-lg font-medium" aria-label="Call time">{duration(elapsed)}</span>
          <span className="flex items-center gap-2 text-sm" role="status" aria-live="polite">
            <span className={`h-2 w-2 rounded-full ${dot}`} aria-hidden />
            {STATUS_TEXT[s.status]}
          </span>
        </div>
        <div className="hidden w-40 md:block"><Waveform analyser={s.analyser} status={s.status} startedAt={s.startedAt} compact /></div>
        {s.heardLang && <span className="rounded-sm border border-ink/25 px-2 py-0.5 text-xs">Heard: {LANGUAGE_LABEL[s.heardLang] ?? s.heardLang}</span>}
        {s.recording && <span className="flex items-center gap-1.5 text-xs"><span className="h-2 w-2 rounded-full bg-chilli" />Recording this call</span>}

        <div className="flex w-full flex-wrap items-center gap-2 sm:ml-auto sm:w-auto">
          <label className="sr-only" htmlFor="call-lang">Language</label>
          <select id="call-lang" value={s.lang} onChange={(e) => s.setLang(e.target.value as Lang)} disabled={live} className="field h-9 flex-1 pr-8 sm:flex-none">
            {LANGS.map((l) => <option key={l.value} value={l.value}>{l.label}</option>)}
          </select>
          <div role="radiogroup" aria-label="Input" className="inline-flex rounded-sm border border-ink/25 p-0.5">
            {ENGINES.map((e) => (
              <button key={e.value} role="radio" aria-checked={s.engine === e.value} disabled={live} onClick={() => s.setEngine(e.value)}
                className={`flex h-8 items-center gap-1.5 rounded-[2px] px-2.5 text-sm transition-colors duration-fast disabled:cursor-not-allowed ${
                  s.engine === e.value ? "bg-indigo text-on-indigo" : "text-ink/80 hover:bg-ink/5"}`}>
                <Icon name={e.icon} size={16} />
                <span className="hidden lg:inline">{e.label}</span>
                <span className="sr-only lg:hidden">{e.label}</span>
              </button>
            ))}
          </div>
          <button className="btn-quiet h-9 w-9 px-0" onClick={s.toggleMute} aria-pressed={s.muted} title={s.muted ? "Unmute replies" : "Mute replies"}>
            <Icon name={s.muted ? "mute" : "speaker"} size={18} />
            <span className="sr-only">{s.muted ? "Unmute replies" : "Mute replies"}</span>
          </button>
        </div>
      </div>
    </div>
  );
}
