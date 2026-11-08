// Screen 7. Settings.
import { useEffect, useState, type ReactNode } from "react";
import { ThemeSwitch } from "@/components/ThemeSwitch";
import { toast } from "@/components/toast";
import { ErrorState, Loading, Segmented, Switch } from "@/components/ui";
import { api, ApiError, type ImportReport } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { CATEGORY_LABEL } from "@/lib/format";
import type { Settings } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function SettingsPage() {
  const s = useApi(() => api.settings(), []);
  const reloadCatalog = useCatalog((c) => c.load);

  const save = async (patch: Partial<Settings>, message = "Saved.") => {
    try {
      s.setData(await api.saveSettings(patch));
      toast(message);
      void reloadCatalog();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Not saved. Retry.", "error");
    }
  };

  if (s.loading && !s.data) return <div className="px-8 py-8"><Loading /></div>;
  if (s.error || !s.data) return <div className="px-8 py-8"><ErrorState message={s.error ?? "Settings did not load."} onRetry={s.reload} /></div>;
  const d = s.data;

  return (
    <div className="mx-auto max-w-3xl px-4 py-6 sm:px-6">
      <h1 className="title-rule font-display text-xl">Settings</h1>

      <Group title="Restaurant">
        <NameField value={d.restaurant_name} onSave={(v) => save({ restaurant_name: v }, "Restaurant name saved.")} />
      </Group>

      <Group title="Languages">
        <p className="text-sm text-muted">English, Hindi and Hinglish are always on. Packs add words for more languages; replies use Hinglish until a pack ships its own.</p>
        {d.available_packs.map((p) => (
          <Switch key={p.code} label={p.label} checked={d.language_packs.includes(p.code)}
            onChange={(on) => save({ language_packs: on ? [...d.language_packs, p.code] : d.language_packs.filter((x) => x !== p.code) })}
            description="Without a speech model for this language, it works through typed input and sample calls." />
        ))}
      </Group>

      <Group title="Speech">
        <div className="flex flex-wrap items-center justify-between gap-3 py-3">
          <span className="text-sm font-medium">Default input on the call desk</span>
          <Segmented label="Default input" value={d.speech.engine} onChange={(engine) => save({ speech: { ...d.speech, engine } })}
            options={[{ value: "offline", label: "Offline speech" }, { value: "typed", label: "Typed" }]} />
        </div>
        <div className="flex flex-wrap items-center justify-between gap-3 py-3">
          <span>
            <span className="block text-sm font-medium">Agent's voice</span>
            <span className="mt-0.5 block text-sm text-muted">Natural is made on this computer and sounds like a person, in Hindi and English. Browser uses the system voice.</span>
          </span>
          <Segmented label="Agent's voice" value={d.speech.voice ?? "natural"} onChange={(voice) => save({ speech: { ...d.speech, voice } })}
            options={[{ value: "natural", label: "Natural" }, { value: "browser", label: "Browser" }]} />
        </div>
        <Switch label="Let callers interrupt" checked={d.speech.barge_in ?? true}
          onChange={(v) => save({ speech: { ...d.speech, barge_in: v } })}
          description="With offline speech, the agent stops talking when the caller speaks over it, and listens. Turn it off if your speakers are loud and the agent keeps stopping itself." />
        <Switch label="Record calls" checked={d.recording.enabled}
          onChange={(v) => save({ recording: { enabled: v } }, v ? "Calls on offline speech will be recorded." : "Call recording is off.")}
          description="Off unless you turn it on. While a call is recorded the call desk says so. Audio is kept on this computer, in data/recordings, and can be deleted from Recordings." />
        <Switch label="Browser speech service" checked={d.speech.browser_service}
          onChange={(v) => save({ speech: { ...d.speech, browser_service: v } })}
          description="Uses your browser's speech service. Audio may leave this device." />
      </Group>

      <Group title="Offers">
        <Switch label="Make offers during calls" checked={d.upsell.enabled} onChange={(v) => save({ upsell: { ...d.upsell, enabled: v } })} />
        <div className="flex flex-wrap items-center justify-between gap-3 py-3">
          <span className="text-sm font-medium">Offers per call, at most</span>
          <Segmented label="Offers per call" value={d.upsell.max_offers_per_call}
            onChange={(n) => save({ upsell: { ...d.upsell, max_offers_per_call: n } })}
            options={[0, 1, 2].map((n) => ({ value: n, label: String(n) }))} />
        </div>
        <div className="py-3">
          <p className="text-sm font-medium">Weight by time of day</p>
          <p className="mb-3 text-sm text-muted">1 is normal. Lower makes offers rarer in that part of the day.</p>
          <div className="grid gap-3 sm:grid-cols-2">
            {Object.entries(d.upsell.daypart_weights).map(([part, w]) => (
              <label key={part} className="flex items-center gap-3 text-sm">
                <span className="w-20 capitalize">{part}</span>
                <input type="range" min={0} max={2} step={0.1} defaultValue={w} className="flex-1 accent-[rgb(var(--ink))]"
                  onPointerUp={(e) => save({ upsell: { ...d.upsell, daypart_weights: { ...d.upsell.daypart_weights, [part]: Number((e.target as HTMLInputElement).value) } } })}
                  onKeyUp={(e) => save({ upsell: { ...d.upsell, daypart_weights: { ...d.upsell.daypart_weights, [part]: Number((e.target as HTMLInputElement).value) } } })} />
                <span className="num w-8 text-right">{w.toFixed(1)}</span>
              </label>
            ))}
          </div>
        </div>
      </Group>

      <Group title="Kitchen and stock">
        <Switch label="Kitchen is busy" checked={d.kitchen_busy} onChange={(v) => save({ kitchen_busy: v })}
          description={`Holds offers for items that take longer than ${d.upsell.slow_prep_minutes} minutes.`} />
        <Switch label="Use stock levels" checked={d.inventory_signals} onChange={(v) => save({ inventory_signals: v })}
          description="Push items whose fresh stock is high, and hold items whose stock is low." />
        {d.active_signals.length > 0 && (
          <ul className="mt-1 flex flex-col gap-2 pb-2 text-sm">
            {d.active_signals.map((sig, i) => (
              <li key={i} className="flex gap-2">
                <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${sig.kind === "push" ? "bg-leaf" : sig.kind === "hold" ? "bg-chilli" : "bg-cardamom"}`} aria-hidden />
                <span>{sig.text}{sig.items ? `: ${sig.items.join(", ")}` : ""}</span>
              </li>
            ))}
          </ul>
        )}
      </Group>

      <Group title="Import data">
        <ImportPanel onDone={() => void reloadCatalog()} />
      </Group>

      <Group title="Stored calls">
        <DeleteCalls />
      </Group>

      <Group title="Theme">
        <div className="py-3"><ThemeSwitch /></div>
      </Group>
    </div>
  );
}

function Group({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="border-t border-line py-5">
      <h2 className="mb-2 font-display text-2xl">{title}</h2>
      <div>{children}</div>
    </section>
  );
}

function NameField({ value, onSave }: { value: string; onSave: (v: string) => void }) {
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  return (
    <form className="flex flex-wrap items-end gap-3 py-3" onSubmit={(e) => { e.preventDefault(); onSave(v.trim()); }}>
      <label className="flex flex-1 flex-col gap-1.5 text-sm">
        <span className="font-medium">Name printed on tickets</span>
        <input className="field" value={v} maxLength={60} onChange={(e) => setV(e.target.value)} placeholder="Kitchen order ticket" />
      </label>
      <button className="btn-secondary" disabled={v.trim() === value}>Save name</button>
    </form>
  );
}

function ImportPanel({ onDone }: { onDone: () => void }) {
  const [kind, setKind] = useState<"items" | "orders">("items");
  const [file, setFile] = useState<File | null>(null);
  const [report, setReport] = useState<ImportReport | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [costs, setCosts] = useState<Record<string, string>>({});
  const [mode, setMode] = useState<"replace" | "append">("replace");
  const [busy, setBusy] = useState(false);

  const run = async (dryRun: boolean) => {
    if (!file) return;
    setBusy(true);
    try {
      const opts: Record<string, string> = { dry_run: String(dryRun), mapping: JSON.stringify(mapping) };
      if (kind === "items" && Object.keys(costs).length) {
        opts.default_cost_pct = JSON.stringify(Object.fromEntries(Object.entries(costs).filter(([, v]) => v).map(([k, v]) => [k, Number(v)])));
      }
      if (kind === "orders") opts.mode = mode;
      const r = await api.importCsv(kind, file, opts);
      setReport(r);
      setMapping(r.mapping);
      if (r.committed) {
        toast(`Imported ${r.accepted} rows. Analytics are updated.`);
        onDone();
      }
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "The file was not read. Check it is a CSV.", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-4 py-3">
      <Segmented label="File" value={kind} onChange={(k) => { setKind(k); setReport(null); setMapping({}); }}
        options={[{ value: "items", label: "Items" }, { value: "orders", label: "Orders" }]} />
      <label className="flex flex-col gap-1.5 text-sm">
        <span className="font-medium">{kind === "items" ? "items.csv: name, category, price, food cost" : "orders.csv: one row per order line"}</span>
        <input type="file" accept=".csv,text/csv" className="text-sm file:btn-secondary file:mr-3"
          onChange={(e) => { setFile(e.target.files?.[0] ?? null); setReport(null); setMapping({}); }} />
      </label>
      {kind === "orders" && (
        <Segmented label="Existing orders" value={mode} onChange={setMode}
          options={[{ value: "replace", label: "Replace order history" }, { value: "append", label: "Add to history" }]} />
      )}
      <div className="flex gap-2">
        <button className="btn-secondary" disabled={!file || busy} onClick={() => run(true)}>Check the file</button>
        {report && !report.committed && report.missing_required.length === 0 && (
          <button className="btn-primary" disabled={busy || (kind === "items" && report.needs_food_cost.length > 0 && report.needs_food_cost.some((c) => !costs[c]))}
            onClick={() => run(false)}>
            Import {report.accepted} rows
          </button>
        )}
      </div>

      {report && (
        <div className="panel p-4 text-sm">
          <p className="font-medium">{report.accepted} rows accepted, {report.rejected} rejected.</p>
          {report.rejected_reasons.length > 0 && (
            <ul className="mt-2 text-muted">
              {report.rejected_reasons.map((r) => <li key={r.reason}>{r.count} × {r.reason}</li>)}
            </ul>
          )}
          <h3 className="mt-4 font-medium">Columns</h3>
          <div className="mt-2 grid gap-2 sm:grid-cols-2">
            {Object.entries(mapping).map(([field, col]) => (
              <label key={field} className="flex items-center justify-between gap-3">
                <span className="text-muted">{field.replace(/_/g, " ")}</span>
                <select className="field h-8 w-44" value={col ?? ""} onChange={(e) => setMapping({ ...mapping, [field]: e.target.value || null })}>
                  <option value="">Not in file</option>
                  {report.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                </select>
              </label>
            ))}
          </div>
          {report.food_cost_message && kind === "items" && (
            <div className="mt-4">
              <p className="font-medium">{report.food_cost_message}</p>
              <p className="text-muted">Set a default food cost, as a percentage of price, for each category.</p>
              <div className="mt-2 grid gap-2 sm:grid-cols-2">
                {report.needs_food_cost.map((c) => (
                  <label key={c} className="flex items-center justify-between gap-3">
                    <span>{CATEGORY_LABEL[c] ?? c}</span>
                    <span className="flex items-center gap-1">
                      <input className="field h-8 w-20 text-right" inputMode="decimal" value={costs[c] ?? ""} onChange={(e) => setCosts({ ...costs, [c]: e.target.value })} />%
                    </span>
                  </label>
                ))}
              </div>
            </div>
          )}
          {report.warnings.filter((w) => !w.startsWith(report.food_cost_message ?? "§")).map((w) => <p key={w} className="mt-2 text-muted">{w}</p>)}
        </div>
      )}
    </div>
  );
}

function DeleteCalls() {
  const [confirm, setConfirm] = useState(false);
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 py-3">
      <p className="text-sm text-muted">Transcripts are kept for replay with phone numbers masked. Audio is never stored.</p>
      {confirm ? (
        <div className="flex gap-2">
          <button className="btn-quiet" onClick={() => setConfirm(false)}>Keep calls</button>
          <button className="btn bg-chilli text-paper hover:bg-chilli/90" onClick={async () => {
            try {
              const r = await api.deleteCalls();
              toast(`Deleted ${r.deleted} stored ${r.deleted === 1 ? "call" : "calls"}.`);
            } catch (e) {
              toast(e instanceof ApiError ? e.message : "Calls were not deleted. Retry.", "error");
            }
            setConfirm(false);
          }}>Delete all stored calls</button>
        </div>
      ) : (
        <button className="btn-secondary" onClick={() => setConfirm(true)}>Delete stored calls</button>
      )}
    </div>
  );
}
