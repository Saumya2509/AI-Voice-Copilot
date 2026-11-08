// Recordings (improve.md, section 4): calls with their English transcripts. When a call was recorded
// (only after recording is turned on in Settings), the transcript follows the audio: the current line is
// highlighted and clicking a line seeks to it. Sample and typed calls have no audio.
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { JsonViewer } from "@/components/JsonViewer";
import { PrintedTicket } from "@/components/PrintedTicket";
import { toast } from "@/components/toast";
import { ErrorState, Loading, Switch } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { LANGUAGE_LABEL, num, rupees, time } from "@/lib/format";
import type { CallQuery, Transcript } from "@/lib/types";
import { useApi } from "@/lib/useApi";

const OUTCOME: Record<string, string> = { ordered: "Ordered", abandoned: "No answer", cancelled: "Cancelled", ended: "Ended" };

export default function Recordings() {
  const { id } = useParams();
  return id ? <CallDetail id={id} /> : <CallList />;
}

function CallList() {
  const [q, setQ] = useState<CallQuery>({});
  const [search, setSearch] = useState("");
  useEffect(() => {
    const t = setTimeout(() => setQ((cur) => ({ ...cur, q: search.trim() || undefined })), 300);
    return () => clearTimeout(t);
  }, [search]);
  const calls = useApi(() => api.calls(q), [JSON.stringify(q)]);
  const ins = useApi(() => api.insights(), []);
  const nav = useNavigate();
  const set = (p: Partial<CallQuery>) => setQ((cur) => ({ ...cur, ...p }));

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6">
      <h1 className="title-rule font-display text-xl">Recordings</h1>
      {ins.data && ins.data.calls_with_orders > 0 && (
        <section aria-label="Calls taken by Tadka" className="mb-6 flex flex-wrap gap-x-10 gap-y-3 border-b border-ink/15 pb-5">
          <Kpi label="Phone orders taken" value={num(ins.data.calls_with_orders)} />
          <Kpi label="Average order with offers" value={rupees(ins.data.aov_with_upsell)} />
          <Kpi label="Without the accepted offers" value={rupees(ins.data.aov_without_upsell)} />
          <Kpi label="Offers accepted" value={`${ins.data.offers_accepted} of ${ins.data.offers_shown}`} />
          <Kpi label="Added by offers" value={`${rupees(ins.data.added_revenue)} · ${rupees(ins.data.added_margin)} margin`} />
        </section>
      )}
      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="relative min-w-[14rem] flex-1">
          <span className="sr-only">Search calls</span>
          <Icon name="search" size={18} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input className="field h-10 w-full pl-8" value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search words said, call or order number" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">Outcome
          <select className="field h-10" value={q.outcome ?? ""} onChange={(e) => set({ outcome: e.target.value || undefined })}>
            <option value="">Any</option>{Object.entries(OUTCOME).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select></label>
        <label className="flex flex-col gap-1 text-xs text-muted">Language heard
          <select className="field h-10" value={q.language ?? ""} onChange={(e) => set({ language: e.target.value || undefined })}>
            <option value="">Any</option><option value="en">English</option><option value="hi">Hindi</option><option value="hinglish">Hinglish</option>
          </select></label>
        <label className="flex flex-col gap-1 text-xs text-muted">From
          <input type="date" className="field h-10" value={q.from ?? ""} onChange={(e) => set({ from: e.target.value || undefined })} /></label>
        <label className="flex h-10 items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--indigo))]" checked={q.has_recording === true}
            onChange={(e) => set({ has_recording: e.target.checked ? true : undefined })} />With audio
        </label>
      </div>
      {calls.loading && !calls.data ? <Loading /> : calls.error ? <ErrorState message={calls.error} onRetry={calls.reload} /> :
        !calls.data?.calls.length ? (
          <p className="py-8 text-base">No calls yet. Take a call or play a sample call on the <Link to="/desk" className="text-indigo underline underline-offset-4">Call desk</Link>.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead><tr className="border-b border-ink text-left">
                <th className="py-2 pr-4 font-medium">Time</th><th className="py-2 pr-4 font-medium">Length</th>
                <th className="py-2 pr-4 font-medium">Heard</th><th className="py-2 pr-4 font-medium">Outcome</th>
                <th className="py-2 pr-4 text-right font-medium">Order</th><th className="py-2 pr-4 font-medium">Offers</th>
                <th className="py-2 font-medium">Audio</th></tr></thead>
              <tbody>
                {calls.data.calls.map((c) => (
                  <tr key={c.call_id} className="cursor-pointer border-b border-ink/10 hover:bg-ink/[0.03]" onClick={() => nav(`/recordings/${c.call_id}`)}>
                    <td className="py-2.5 pr-4"><Link to={`/recordings/${c.call_id}`} className="num underline-offset-4 hover:underline" onClick={(e) => e.stopPropagation()}>{time(c.started_at, true)}</Link></td>
                    <td className="num py-2.5 pr-4">{mmss(c.duration_s)}</td>
                    <td className="py-2.5 pr-4">{c.language ? LANGUAGE_LABEL[c.language] ?? c.language : "—"}</td>
                    <td className="py-2.5 pr-4">{c.outcome ? OUTCOME[c.outcome] ?? c.outcome : "In progress"}</td>
                    <td className="num py-2.5 pr-4 text-right">{c.total !== null ? rupees(c.total) : "—"}</td>
                    <td className="py-2.5 pr-4">{c.upsell_shown ? `${c.upsell_accepted} of ${c.upsell_shown} accepted` : "None"}</td>
                    <td className="py-2.5">{c.has_recording ? "Recorded" : <span className="text-muted">Transcript only</span>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
    </div>
  );
}

function mmss(s: number) {
  const t = Math.max(0, Math.round(s));
  return `${Math.floor(t / 60)}:${String(t % 60).padStart(2, "0")}`;
}

function Kpi({ label, value }: { label: string; value: string }) {
  return <div><p className="label">{label}</p><p className="num text-lg font-medium">{value}</p></div>;
}

function CallDetail({ id }: { id: string }) {
  const nav = useNavigate();
  const call = useApi(() => api.call(id), [id]);
  const tr = useApi(() => api.transcript(id), [id]);
  const [original, setOriginal] = useState(false);
  const [now, setNow] = useState(0);
  const [hasAudio, setHasAudio] = useState(true);
  const [confirm, setConfirm] = useState<"recording" | "call" | null>(null);
  const audio = useRef<HTMLAudioElement>(null);
  const orderId = call.data?.order_id ?? null;
  const order = useApi(() => (orderId ? api.order(orderId) : Promise.resolve(null)), [orderId]);
  const lines = tr.data?.lines ?? [];
  const duration = useMemo(() => Math.max(1, ...lines.map((l) => l.at_s), ...(tr.data?.markers ?? []).map((m) => m.at_s)), [lines, tr.data]);
  const current = lines.reduce((acc, l, i) => (l.at_s <= now ? i : acc), -1);

  const seek = (t: number) => {
    setNow(t);
    if (audio.current) {
      audio.current.currentTime = t;
      void audio.current.play().catch(() => {});
    }
  };

  const remove = async (what: "recording" | "call") => {
    try {
      if (what === "recording") {
        await api.deleteRecording(id);
        toast("Recording deleted. The transcript is kept.");
        tr.reload();
      } else {
        await api.deleteCall(id);
        toast("Call deleted.");
        nav("/recordings");
      }
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Not deleted. Retry.", "error");
    }
    setConfirm(null);
  };

  if (call.loading && !call.data) return <div className="px-6 py-8"><Loading /></div>;
  if (call.error) return <div className="px-6 py-8"><ErrorState message={call.error} onRetry={call.reload} /></div>;
  const c = call.data!;
  const recorded = Boolean(tr.data?.has_recording) && hasAudio;
  const markerLabel = { clarify: "Clarification", offer: "Offer", item: "Item heard", sent: "Sent to PoS", interrupted: "Caller cut in" };
  const markerColor = { clarify: "bg-plow", offer: "bg-haldi", item: "bg-ink", sent: "bg-leaf", interrupted: "bg-chilli" };

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6">
      <Link to="/recordings" className="text-sm text-indigo underline-offset-4 hover:underline">All recordings</Link>
      <div className="title-rule mt-2 flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-xl">Call at {time(c.started_at, true)}</h1>
        <p className="text-sm text-muted">
          {c.language ? `Heard: ${LANGUAGE_LABEL[c.language] ?? c.language}` : ""}{c.outcome ? ` · ${OUTCOME[c.outcome] ?? c.outcome}` : ""}
          {c.order_id ? ` · ${c.order_id}` : ""}
        </p>
      </div>

      <div className="grid gap-10 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)]">
        <section aria-label="Transcript" className="min-w-0">
          {recorded ? (
            <audio ref={audio} src={api.recordingUrl(id)} controls className="mb-4 w-full" onTimeUpdate={(e) => setNow(e.currentTarget.currentTime)}
              onError={() => setHasAudio(false)} />
          ) : (
            <p className="mb-4 text-sm text-muted">No audio for this call. Recording is off, or this was a typed or sample call.</p>
          )}
          <div className="relative mb-2 h-6" aria-label="Call timeline">
            <div className="absolute inset-x-0 top-1/2 h-px bg-ink/25" aria-hidden />
            {(tr.data?.markers ?? []).map((m, i) => (
              <button key={i} onClick={() => seek(m.at_s)} title={`${markerLabel[m.kind]}${m.label ? `: ${m.label}` : ""}`}
                aria-label={`${markerLabel[m.kind]} at ${mmss(m.at_s)}${m.label ? `, ${m.label}` : ""}`}
                className={`absolute top-1/2 h-3 w-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-plate ${markerColor[m.kind]}`}
                style={{ left: `${(m.at_s / duration) * 100}%` }} />
            ))}
            <span className="absolute bottom-0 top-0 w-px bg-indigo" style={{ left: `${Math.min(100, (now / duration) * 100)}%` }} aria-hidden />
          </div>
          {!recorded && (
            <input type="range" min={0} max={duration} step={0.1} value={now} onChange={(e) => setNow(Number(e.target.value))}
              className="mb-2 w-full accent-[rgb(var(--indigo))]" aria-label="Move through the call" />
          )}
          <ul className="mb-4 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted">
            {(Object.keys(markerLabel) as (keyof typeof markerLabel)[]).map((k) => (
              <li key={k} className="flex items-center gap-1.5"><span className={`h-2 w-2 rounded-full ${markerColor[k]}`} />{markerLabel[k]}</li>
            ))}
          </ul>
          <div className="mb-2 flex justify-end"><div className="w-44"><Switch checked={original} onChange={setOriginal} label="Show original" /></div></div>
          {tr.loading && !tr.data ? <Loading /> : (
            <ol className="flex flex-col">
              {lines.map((l, i) => (
                <li key={i}>
                  <button onClick={() => seek(l.at_s)} aria-current={i === current ? "true" : undefined}
                    className={`grid w-full grid-cols-[52px_64px_1fr] gap-3 rounded-sm px-2 py-1.5 text-left ${i === current ? "bg-haldi/35" : "hover:bg-ink/5"}`}>
                    <span className="num pt-0.5 text-xs text-muted">{mmss(l.at_s)}</span>
                    <span className="pt-0.5 text-xs text-muted">{l.speaker === "guest" ? "Caller" : "Tadka"}</span>
                    <TranscriptText line={l} original={original} />
                  </button>
                </li>
              ))}
            </ol>
          )}
        </section>

        <aside className="flex min-w-0 flex-col gap-6">
          {order.data?.kot ? <PrintedTicket kot={order.data.kot} /> : <p className="text-sm text-muted">No ticket: this call did not end in an order.</p>}
          {order.data?.order_json && <JsonViewer value={order.data.order_json} />}
          <div className="flex flex-wrap gap-3 border-t border-ink/15 pt-4">
            {tr.data?.has_recording && (confirm === "recording" ? (
              <><button className="btn-danger" onClick={() => remove("recording")}>Delete the recording</button>
                <button className="btn-quiet" onClick={() => setConfirm(null)}>Keep it</button></>
            ) : <button className="btn-secondary" onClick={() => setConfirm("recording")}>Delete recording</button>)}
            {confirm === "call" ? (
              <><button className="btn-danger" onClick={() => remove("call")}>Delete the call and its transcript</button>
                <button className="btn-quiet" onClick={() => setConfirm(null)}>Keep it</button></>
            ) : <button className="btn-secondary" onClick={() => setConfirm("call")}>Delete call</button>}
          </div>
          {c.order_id && <p className="text-sm text-muted">Offers: {c.upsell_accepted} of {c.upsell_shown} accepted.</p>}
        </aside>
      </div>
    </div>
  );
}

function TranscriptText({ line, original }: { line: Transcript["lines"][number]; original: boolean }) {
  if (original) return <span lang={line.lang === "hi" ? "hi" : "en"}>{line.original_text}</span>;
  if (!line.parts) return <span>{line.text}</span>;
  return <span>{line.parts.map((p, i) => <span key={i}>{i > 0 && " "}{p.kind === "unknown" ? <em className="text-ink/70">{p.text}</em> : p.text}</span>)}</span>;
}
