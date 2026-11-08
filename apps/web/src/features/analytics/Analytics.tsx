// Analytics (improve.md, section 2). Empty until data exists; then every figure comes from
// /analytics/* and follows the shared filter bar. Clicking a slice, a channel or a heatmap cell filters
// the rest of the page; active filters show as removable chips.
import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { Sheet } from "@/components/Sheet";
import { ClassTag, ErrorState, Loading, Segmented, Tabs } from "@/components/ui";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { CHANNEL_LABEL, CLASS_LABEL, CLASS_PLURAL, num, pct, rupees } from "@/lib/format";
import { useLive } from "@/lib/live";
import type { AnalyticsFilters, ItemClass } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { ItemSheet } from "../menu-field/ItemSheet";
import { ChannelBar, ChartCard, classColor, colorAt, Donut, HBars, Heatmap, Scatter, TrendChart } from "./charts";

const WEEKDAY = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];

export default function Analytics() {
  const [f, setF] = useState<AnalyticsFilters>({});
  const [grain, setGrain] = useState<"day" | "week">("day");
  const [item, setItem] = useState<number | null>(null);
  const [list, setList] = useState<"puzzles" | "plowhorse_risk" | "underperformers">("puzzles");
  const dataVersion = useLive((s) => s.dataVersion);
  const key = JSON.stringify(f) + dataVersion;

  const ov = useApi(() => api.analytics.overview(f), [key]);
  const cats = useApi(() => api.analytics.categoryShare(f), [key]);
  const veg = useApi(() => api.analytics.vegSplit(f), [key]);
  const cls = useApi(() => api.analytics.classSplit(f), [key]);
  const topU = useApi(() => api.analytics.topItems(f, "units"), [key]);
  const topP = useApi(() => api.analytics.topItems(f, "profit"), [key]);
  const trend = useApi(() => api.analytics.trend(f, grain), [key, grain]);
  const heat = useApi(() => api.analytics.heatmap(f), [key]);
  const chan = useApi(() => api.analytics.channelMix(f), [key]);
  const scatter = useApi(() => api.analytics.items(f), [key]);
  const lists = useApi(() => api.analytics.list(list, f), [key, list]);

  const set = useCallback((patch: Partial<AnalyticsFilters>) => setF((cur) => {
    const next = { ...cur, ...patch };
    (Object.keys(next) as (keyof AnalyticsFilters)[]).forEach((k) => next[k] === undefined && delete next[k]);
    return next;
  }), []);
  const toggle = <K extends keyof AnalyticsFilters>(k: K, v: AnalyticsFilters[K]) => set({ [k]: f[k] === v ? undefined : v } as Partial<AnalyticsFilters>);

  if (ov.loading && !ov.data) return <div className="mx-auto max-w-[1600px] px-6 py-8"><Loading label="Reading your sales" /></div>;
  if (ov.error) return <div className="mx-auto max-w-[1600px] px-6 py-8"><ErrorState message={ov.error} onRetry={ov.reload} /></div>;
  const o = ov.data!;
  if (!o.data_from) return <EmptyAnalytics />;

  const est = o.estimated;
  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6">
      <div className="title-rule flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-xl">Analytics</h1>
        <p className="text-sm text-muted">{num(o.sample_size)} orders from {fmtDate(o.from)} to {fmtDate(o.to)}{est ? ". Margins are estimated from default food costs" : ""}.</p>
      </div>

      <FilterBar f={f} set={set} dataFrom={o.data_from} dataTo={o.data_to} categories={cats.data?.categories.map((c) => c.category) ?? []} />

      <section aria-label="Totals" className="mb-8 grid grid-cols-2 gap-x-6 gap-y-4 border-b border-ink/15 pb-6 sm:grid-cols-3 lg:grid-cols-6">
        <Kpi label="Revenue" value={rupees(o.revenue)} />
        <Kpi label="Orders" value={num(o.orders)} />
        <Kpi label="Average order" value={rupees(o.aov)} />
        <Kpi label="Items sold" value={num(o.items_sold)} />
        <Kpi label={`Gross margin${est ? " (estimated)" : ""}`} value={o.gross_margin_pct === null ? "—" : pct(o.gross_margin_pct, 1)} />
        <Kpi label="Busiest hour" value={o.busiest_hour === null ? "—" : `${o.busiest_hour}:00 to ${o.busiest_hour + 1}:00`} />
      </section>

      <div className="grid gap-x-10 gap-y-10 lg:grid-cols-3">
        <ChartCard title="Revenue by category" table={{ head: ["Category", "Revenue", "Share"],
          rows: (cats.data?.categories ?? []).map((c) => [c.category, rupees(c.revenue), pct(c.share)]) }}>
          <Donut center={rupees(o.revenue)} centerLabel="total" selected={f.category} onSelect={(k) => toggle("category", k)}
            slices={(cats.data?.categories ?? []).map((c, i) => ({ key: c.category, label: c.category, value: Number(c.revenue), color: colorAt(i) }))} />
        </ChartCard>
        <ChartCard title="Veg and non-veg" table={{ head: ["Type", "Revenue", "Share"],
          rows: (veg.data?.slices ?? []).map((s) => [s.key === "veg" ? "Veg" : "Non-veg", rupees(s.revenue), pct(s.share)]) }}>
          <Donut pie selected={f.veg} onSelect={(k) => toggle("veg", k as "veg" | "non_veg")}
            slices={(veg.data?.slices ?? []).map((s) => ({ key: s.key, label: s.key === "veg" ? "Veg" : "Non-veg", value: Number(s.revenue),
              color: s.key === "veg" ? "rgb(var(--leaf))" : "rgb(var(--chilli))", detail: rupees(s.revenue) }))} />
        </ChartCard>
        <ChartCard title="Menu classes" estimated={est} note="Popularity and margin against each item's own category (menu engineering)."
          table={{ head: ["Class", "Items"], rows: (cls.data?.classes ?? []).map((c) => [CLASS_PLURAL[c.class], c.count]) }}>
          <Donut center={num((cls.data?.classes ?? []).reduce((s, c) => s + c.count, 0))} centerLabel="items"
            slices={(cls.data?.classes ?? []).map((c) => ({ key: c.class, label: CLASS_PLURAL[c.class], value: c.count,
              color: classColor(c.class) }))} />
        </ChartCard>

        <ChartCard title="Top 10 by units" className="lg:col-span-1"
          table={{ head: ["Item", "Units"], rows: (topU.data?.items ?? []).map((i) => [i.name, num(i.units)]) }}>
          <HBars color="rgb(var(--indigo))" format={num} onSelect={(k) => setItem(Number(k))}
            rows={(topU.data?.items ?? []).map((i) => ({ key: i.item_id, label: i.name, value: i.units }))} />
        </ChartCard>
        <ChartCard title="Top 10 by profit" estimated={est}
          table={{ head: ["Item", "Profit"], rows: (topP.data?.items ?? []).map((i) => [i.name, rupees(i.profit)]) }}>
          <HBars color="rgb(var(--leaf))" format={(n) => rupees(n)} onSelect={(k) => setItem(Number(k))}
            rows={(topP.data?.items ?? []).map((i) => ({ key: i.item_id, label: i.name, value: Number(i.profit) }))} />
        </ChartCard>
        <ChartCard title="Channels" table={{ head: ["Channel", "Revenue", "Orders", "Average order"],
          rows: (chan.data?.channels ?? []).map((c) => [CHANNEL_LABEL[c.channel] ?? c.channel, rupees(c.revenue), num(c.orders), rupees(c.aov)]) }}>
          <ChannelBar channels={(chan.data?.channels ?? []).map((c) => ({ ...c, revenue: Number(c.revenue), aov: Number(c.aov) }))}
            labels={CHANNEL_LABEL} selected={f.channel} onSelect={(c) => toggle("channel", c as AnalyticsFilters["channel"])} />
        </ChartCard>

        <ChartCard title="Revenue and orders over time" className="lg:col-span-2"
          note={<span>Area: revenue. Thin Haldi line: average order value.</span>}
          table={{ head: [grain === "week" ? "Week of" : "Day", "Revenue", "Orders", "Average order"],
            rows: (trend.data?.points ?? []).map((p) => [p.period, rupees(p.revenue), num(p.orders), rupees(p.aov)]) }}>
          <div className="mb-2 flex justify-end">
            <Segmented label="Grain" value={grain} onChange={setGrain} options={[{ value: "day", label: "Daily" }, { value: "week", label: "Weekly" }]} />
          </div>
          <TrendChart grain={grain} points={(trend.data?.points ?? []).map((p) => ({ ...p, revenue: Number(p.revenue), aov: Number(p.aov) }))} />
        </ChartCard>
        <ChartCard title="Busy hours" table={{ head: ["Day", "Hour", "Orders", "Revenue"],
          rows: (heat.data?.cells ?? []).map((c) => [heat.data!.weekdays[c.weekday], `${c.hour}:00`, num(c.orders), rupees(c.revenue)]) }}>
          <Heatmap cells={(heat.data?.cells ?? []).map((c) => ({ ...c, revenue: Number(c.revenue) }))} weekdays={heat.data?.weekdays ?? []}
            max={heat.data?.max_orders ?? 0} selected={{ weekday: f.weekday, hour: f.hour }}
            onSelect={(w, h) => (f.weekday === w && f.hour === h ? set({ weekday: undefined, hour: undefined }) : set({ weekday: w, hour: h }))} />
        </ChartCard>

        <ChartCard title="Margin against popularity" className="lg:col-span-2" estimated={est}
          table={{ head: ["Item", "Class", "Units", "Profit"], rows: (scatter.data?.items ?? []).filter((i) => i.units > 0)
            .map((i) => [i.name, CLASS_LABEL[i.class], num(i.units), rupees(i.profit)]) }}>
          <Scatter items={(scatter.data?.items ?? []).map((i) => ({ ...i, profit: Number(i.profit) }))} onSelect={setItem} />
        </ChartCard>
        <section aria-label="Lists" className="min-w-0 lg:col-span-1">
          <Tabs label="Lists" value={list} onChange={setList} tabs={[
            { value: "puzzles", label: "High margin, low selling" },
            { value: "plowhorse_risk", label: "Low margin, high volume" },
            { value: "underperformers", label: "Underperformers" },
          ]} />
          <ListTable rows={lists.data?.items ?? []} kind={list} onOpen={setItem} loading={lists.loading} />
          {lists.data && <p className="mt-2 text-xs text-muted">{lists.data.assumption}</p>}
        </section>
      </div>

      <ItemPanel id={item} onClose={() => setItem(null)} />
    </div>
  );
}

function fmtDate(d: string | null) {
  if (!d) return "";
  const x = new Date(d + "T00:00:00");
  return `${x.getDate()} ${x.toLocaleString("en-IN", { month: "short" })}`;
}

function Kpi({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="label">{label}</p>
      <p className="num text-xl font-medium">{value}</p>
    </div>
  );
}

function FilterBar({ f, set, dataFrom, dataTo, categories }: {
  f: AnalyticsFilters; set: (p: Partial<AnalyticsFilters>) => void; dataFrom: string | null; dataTo: string | null; categories: string[];
}) {
  const chips: { label: string; clear: Partial<AnalyticsFilters> }[] = [];
  if (f.category) chips.push({ label: f.category, clear: { category: undefined } });
  if (f.veg) chips.push({ label: f.veg === "veg" ? "Veg" : "Non-veg", clear: { veg: undefined } });
  if (f.channel) chips.push({ label: CHANNEL_LABEL[f.channel], clear: { channel: undefined } });
  if (f.weekday !== undefined) chips.push({ label: `${WEEKDAY[f.weekday]} ${f.hour}:00`, clear: { weekday: undefined, hour: undefined } });
  return (
    <div className="mb-6 flex flex-wrap items-end gap-3">
      <label className="flex flex-col gap-1 text-xs text-muted">From
        <input type="date" className="field h-9" min={dataFrom ?? undefined} max={dataTo ?? undefined} value={f.from ?? ""}
          onChange={(e) => set({ from: e.target.value || undefined })} /></label>
      <label className="flex flex-col gap-1 text-xs text-muted">To
        <input type="date" className="field h-9" min={dataFrom ?? undefined} max={dataTo ?? undefined} value={f.to ?? ""}
          onChange={(e) => set({ to: e.target.value || undefined })} /></label>
      <label className="flex flex-col gap-1 text-xs text-muted">Category
        <select className="field h-9" value={f.category ?? ""} onChange={(e) => set({ category: e.target.value || undefined })}>
          <option value="">All categories</option>
          {categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select></label>
      <label className="flex flex-col gap-1 text-xs text-muted">Veg
        <select className="field h-9" value={f.veg ?? ""} onChange={(e) => set({ veg: (e.target.value || undefined) as AnalyticsFilters["veg"] })}>
          <option value="">Veg and non-veg</option><option value="veg">Veg</option><option value="non_veg">Non-veg</option>
        </select></label>
      <label className="flex flex-col gap-1 text-xs text-muted">Channel
        <select className="field h-9" value={f.channel ?? ""} onChange={(e) => set({ channel: (e.target.value || undefined) as AnalyticsFilters["channel"] })}>
          <option value="">All channels</option>
          {Object.entries(CHANNEL_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </select></label>
      {chips.length > 0 && (
        <div className="flex flex-wrap items-center gap-2 pb-1" aria-label="Active filters">
          {chips.map((c) => (
            <button key={c.label} onClick={() => set(c.clear)} className="flex items-center gap-1 rounded-full bg-indigo px-3 py-1 text-xs text-on-indigo">
              {c.label}<Icon name="close" size={12} /><span className="sr-only">Remove filter</span>
            </button>
          ))}
          {(f.from || f.to || chips.length > 1) && (
            <button className="text-xs text-indigo underline-offset-4 hover:underline" onClick={() => set({ category: undefined, veg: undefined, channel: undefined, weekday: undefined, hour: undefined, from: undefined, to: undefined })}>
              Clear all
            </button>
          )}
        </div>
      )}
    </div>
  );
}

function ListTable({ rows, kind, onOpen, loading }: {
  rows: { item_id: number; name: string; class: ItemClass; units: number; cm: number; value: number; at_risk?: boolean }[];
  kind: string; onOpen: (id: number) => void; loading: boolean;
}) {
  if (loading && !rows.length) return <Loading />;
  if (!rows.length) return <p className="py-6 text-sm text-muted">Nothing on this list for these filters.</p>;
  const head = { puzzles: "Gain a month", plowhorse_risk: "Exposure a month", underperformers: "Gain if removed" }[kind];
  return (
    <table className="mt-2 w-full text-sm">
      <thead><tr className="text-left text-muted"><th className="py-1.5 font-normal">Item</th><th className="py-1.5 font-normal">Class</th>
        <th className="py-1.5 text-right font-normal">{head}</th></tr></thead>
      <tbody>
        {rows.slice(0, 10).map((r) => (
          <tr key={r.item_id} className={`group border-t border-ink/10 row-${r.class}`}>
            <td className="relative py-1.5 pr-2">
              <span className="row-bar absolute -left-3 bottom-1 top-1 w-[3px] opacity-0 group-hover:opacity-100" aria-hidden />
              <button className="text-left hover:underline" onClick={() => onOpen(r.item_id)}>{r.name}</button>
            </td>
            <td className="py-1.5"><ClassTag cls={r.class} /></td>
            <td className="num py-1.5 text-right">{rupees(r.value, { sign: kind !== "plowhorse_risk" })}{r.at_risk ? ", at risk" : ""}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

function ItemPanel({ id, onClose }: { id: number | null; onClose: () => void }) {
  const stats = useCatalog((s) => s.stats);
  const reload = useCatalog((s) => s.load);
  const item = id ? stats[id] : null;
  const total = useMemo(() => Object.values(stats).reduce((s, i) => s + Number(i.profit), 0), [stats]);
  const noop = useCallback(() => {}, []);
  return (
    <Sheet open={!!item} onClose={onClose} title={item?.name ?? ""} width={420}>
      {item && <ItemSheet item={item} totalProfit={total} window={30} onPrice={noop} onApplied={() => { void reload(); onClose(); }} />}
    </Sheet>
  );
}

function EmptyAnalytics() {
  return (
    <div className="mx-auto max-w-[1600px] px-4 py-8 sm:px-6">
      <h1 className="title-rule font-display text-xl">Analytics</h1>
      <div className="max-w-prose">
        <p className="text-lg">No sales yet.</p>
        <p className="mt-2 text-base text-muted">Upload a sales CSV from your PoS and every chart here is drawn from it: revenue by category, busy hours, what earns and what does not.</p>
        <Link to="/upload" className="btn-primary mt-5"><Icon name="upload" size={18} />Upload CSV</Link>
      </div>
    </div>
  );
}
