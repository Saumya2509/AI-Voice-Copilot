// Charts for the Analytics screen. Recharts for pie, bar and line; plain SVG for the heatmap and the
// scatter. Theme colours only, ordered by meaning; thin axes, light gridlines, tabular figures, no
// shadows or gradients. Each chart animates once on load and transitions on filter change.
import { useState, type ReactNode } from "react";
import { Area, Bar, BarChart, Cell, ComposedChart, Line, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis,
  CartesianGrid } from "recharts";
import { CLASS_COLOR, CLASS_LABEL, CLASS_PLURAL, num, pct, rupees } from "@/lib/format";
import { useMotionPref } from "@/lib/motion";
import type { ItemClass, ScatterItem } from "@/lib/types";

/** Category palette: theme colours in a fixed order, then ink tints. */
export const SERIES = ["--indigo", "--plow", "--leaf", "--haldi", "--plum", "--chilli", "--muted"];
export const colorAt = (i: number) => (i < SERIES.length ? `rgb(var(${SERIES[i]}))` : `rgb(var(--ink) / ${Math.max(0.15, 0.5 - (i - SERIES.length) * 0.08)})`);
export const classColor = (c: ItemClass) => `rgb(var(--${CLASS_COLOR[c]}))`;
const axis = { fontSize: 12, fill: "rgb(var(--muted))" };
const tooltipStyle = { background: "rgb(var(--card))", border: "1px solid rgb(var(--ink) / 0.2)", borderRadius: 2, fontSize: 13 };

export function ChartCard({ title, note, table, children, estimated, className = "" }: {
  title: string; note?: ReactNode; table: { head: string[]; rows: (string | number)[][] }; children: ReactNode;
  estimated?: boolean; className?: string;
}) {
  const [asTable, setAsTable] = useState(false);
  return (
    <section className={`flex min-w-0 flex-col ${className}`} aria-label={title}>
      <div className="mb-2 flex items-baseline justify-between gap-3 border-b border-ink/15 pb-1.5">
        <h2 className="font-display text-xl">
          {title}
          {estimated && <span className="ml-2 align-middle text-xs font-normal text-muted">Estimated</span>}
        </h2>
        <button className="shrink-0 text-xs text-indigo underline-offset-4 hover:underline" onClick={() => setAsTable(!asTable)}
          aria-pressed={asTable}>
          {asTable ? "View as chart" : "View as table"}
        </button>
      </div>
      {asTable ? (
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead><tr className="text-left text-muted">{table.head.map((h, i) => <th key={h} className={`py-1.5 pr-3 font-normal ${i ? "text-right" : ""}`}>{h}</th>)}</tr></thead>
            <tbody>
              {table.rows.map((r, i) => (
                <tr key={i} className="border-t border-ink/10">{r.map((c, j) => <td key={j} className={`num py-1.5 pr-3 ${j ? "text-right" : ""}`}>{c}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : children}
      {note && <p className="mt-2 text-xs text-muted">{note}</p>}
    </section>
  );
}

interface Slice { key: string; label: string; value: number; color: string; detail?: string }

/** Donut or pie with direct labels beside each slice and, for donuts, the total in the centre. */
export function Donut({ slices, center, centerLabel, onSelect, selected, pie = false }: {
  slices: Slice[]; center?: string; centerLabel?: string; onSelect?: (key: string) => void; selected?: string; pie?: boolean;
}) {
  const { reduced } = useMotionPref();
  const total = slices.reduce((s, x) => s + x.value, 0);
  return (
    <div className="grid grid-cols-1 items-center gap-5 sm:grid-cols-[minmax(150px,200px)_1fr]">
      <div className="relative mx-auto aspect-square w-full max-w-[200px]">
        <ResponsiveContainer>
          <PieChart>
            <Pie data={slices} dataKey="value" nameKey="label" innerRadius={pie ? 0 : "62%"} outerRadius="98%" startAngle={90} endAngle={-270}
              stroke="rgb(var(--plate))" strokeWidth={2} isAnimationActive={!reduced} animationDuration={400}
              onClick={(d: { key?: string }) => d.key && onSelect?.(d.key)}>
              {slices.map((s) => (
                <Cell key={s.key} fill={s.color} opacity={selected && selected !== s.key ? 0.35 : 1}
                  style={{ cursor: onSelect ? "pointer" : "default", outline: "none" }} />
              ))}
            </Pie>
          </PieChart>
        </ResponsiveContainer>
        {!pie && center && (
          <div className="pointer-events-none absolute inset-0 grid place-items-center text-center">
            <div>
              <p className="num text-lg font-medium leading-tight">{center}</p>
              {centerLabel && <p className="text-xs text-muted">{centerLabel}</p>}
            </div>
          </div>
        )}
      </div>
      <ul className="flex min-w-0 flex-col gap-1.5">
        {slices.map((s) => (
          <li key={s.key}>
            <button onClick={() => onSelect?.(s.key)} disabled={!onSelect} aria-pressed={selected === s.key}
              className={`flex w-full items-baseline gap-2 text-left text-sm ${selected && selected !== s.key ? "opacity-50" : ""} ${onSelect ? "hover:underline" : "cursor-default"}`}>
              <span className="h-2.5 w-2.5 shrink-0 translate-y-[1px] rounded-[1px]" style={{ background: s.color }} aria-hidden />
              <span className="shrink-0 whitespace-nowrap">{s.label}</span>
              <span className="leader" aria-hidden />
              <span className="num shrink-0">{total ? pct(s.value / total) : "0%"}</span>
              {s.detail && <span className="num hidden w-20 shrink-0 text-right text-muted sm:inline">{s.detail}</span>}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Horizontal bars with item names on the left and the value at the bar end. */
export function HBars({ rows, format, color, onSelect }: {
  rows: { key: number | string; label: string; value: number; color?: string }[];
  format: (n: number) => string; color: string; onSelect?: (key: number | string) => void;
}) {
  const { reduced } = useMotionPref();
  return (
    <div style={{ height: Math.max(120, rows.length * 30 + 10) }}>
      <ResponsiveContainer>
        <BarChart data={rows} layout="vertical" margin={{ left: 0, right: 64, top: 0, bottom: 0 }} barCategoryGap={6}>
          <XAxis type="number" hide domain={[0, "dataMax"]} />
          <YAxis type="category" dataKey="label" width={150} tick={{ ...axis, fill: "rgb(var(--ink))" }} axisLine={false} tickLine={false} interval={0} />
          <Tooltip cursor={{ fill: "rgb(var(--ink) / 0.05)" }} contentStyle={tooltipStyle} formatter={(v: number) => format(v)} />
          <Bar dataKey="value" fill={color} isAnimationActive={!reduced} animationDuration={400}
            label={{ position: "right", formatter: format, fontSize: 12, fill: "rgb(var(--ink))" }}
            onClick={(d: { key?: number | string }) => d.key !== undefined && onSelect?.(d.key)}
            style={{ cursor: onSelect ? "pointer" : "default" }}>
            {rows.map((r) => <Cell key={r.key} fill={r.color ?? color} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Revenue as a line with the area under it, orders as bars-free second series, AOV as a thin line. */
export function TrendChart({ points, grain }: { points: { period: string; revenue: number; orders: number; aov: number }[]; grain: "day" | "week" }) {
  const { reduced } = useMotionPref();
  const label = (p: string) => {
    const d = new Date(p + "T00:00:00");
    return `${d.getDate()} ${d.toLocaleString("en-IN", { month: "short" })}`;
  };
  return (
    <div className="h-64">
      <ResponsiveContainer>
        <ComposedChart data={points} margin={{ left: 0, right: 8, top: 8, bottom: 0 }}>
          <CartesianGrid vertical={false} stroke="rgb(var(--ink) / 0.08)" />
          <XAxis dataKey="period" tickFormatter={label} tick={axis} axisLine={{ stroke: "rgb(var(--ink) / 0.3)" }} tickLine={false}
            minTickGap={24} />
          <YAxis yAxisId="rev" tickFormatter={(v) => rupees(v)} tick={axis} axisLine={false} tickLine={false} width={72} />
          <YAxis yAxisId="aov" orientation="right" tickFormatter={(v) => rupees(v)} tick={axis} axisLine={false} tickLine={false} width={56} />
          <Tooltip contentStyle={tooltipStyle} labelFormatter={(p: string) => (grain === "week" ? `Week of ${label(p)}` : label(p))}
            formatter={(v: number, name: string) => (name === "Orders" ? num(v) : rupees(v))} />
          <Area yAxisId="rev" type="monotone" dataKey="revenue" name="Revenue" stroke="rgb(var(--indigo))" strokeWidth={2}
            fill="rgb(var(--indigo) / 0.10)" isAnimationActive={!reduced} animationDuration={600} />
          <Line yAxisId="aov" type="monotone" dataKey="aov" name="Average order" stroke="rgb(var(--haldi))" strokeWidth={1.5}
            dot={false} isAnimationActive={!reduced} animationDuration={600} />
          <Line yAxisId="rev" dataKey="orders" name="Orders" stroke="transparent" dot={false} legendType="none" activeDot={false} />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  );
}

/** Weekday by hour heatmap in SVG. Click a cell to filter the page to that hour. */
export function Heatmap({ cells, weekdays, max, onSelect, selected }: {
  cells: { weekday: number; hour: number; orders: number; revenue: number }[]; weekdays: string[]; max: number;
  onSelect?: (weekday: number, hour: number) => void; selected?: { weekday?: number; hour?: number };
}) {
  const hours = cells.length ? Array.from(new Set(cells.map((c) => c.hour))).sort((a, b) => a - b) : [];
  const span = hours.length ? Array.from({ length: hours[hours.length - 1] - hours[0] + 1 }, (_, i) => hours[0] + i) : [];
  const at = new Map(cells.map((c) => [`${c.weekday}-${c.hour}`, c]));
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null);
  return (
    <div className="relative">
      <div className="grid grid-cols-[36px_1fr] gap-1">
        <div />
        <div className="grid" style={{ gridTemplateColumns: `repeat(${span.length}, 1fr)` }}>
          {span.map((h) => <span key={h} className="text-center text-[11px] text-muted">{h % 3 === 0 ? `${h}:00` : ""}</span>)}
        </div>
        {weekdays.map((wd, w) => (
          <div key={wd} className="contents">
            <span className="self-center text-xs text-muted">{wd}</span>
            <div className="grid gap-[2px]" style={{ gridTemplateColumns: `repeat(${span.length}, 1fr)` }}>
              {span.map((h) => {
                const c = at.get(`${w}-${h}`);
                const v = c ? c.orders / Math.max(1, max) : 0;
                const on = selected?.weekday === w && selected?.hour === h;
                return (
                  <button key={h} aria-label={`${wd} ${h}:00, ${c?.orders ?? 0} orders, ${rupees(c?.revenue ?? 0)}`}
                    onClick={() => onSelect?.(w, h)}
                    onMouseEnter={(e) => setTip({ x: (e.currentTarget as HTMLElement).offsetLeft, y: w, text: `${wd} ${h}:00 · ${num(c?.orders ?? 0)} orders · ${rupees(c?.revenue ?? 0)}` })}
                    onMouseLeave={() => setTip(null)}
                    className={`h-6 rounded-[1px] ${on ? "outline outline-2 outline-indigo" : ""}`}
                    style={{ background: v ? `rgb(var(--indigo) / ${0.08 + v * 0.92})` : "rgb(var(--ink) / 0.04)" }} />
                );
              })}
            </div>
          </div>
        ))}
      </div>
      {tip && <p className="mt-2 text-xs" role="status">{tip.text}</p>}
      {!tip && <p className="mt-2 text-xs text-muted">Darker is busier. Click an hour to filter the page.</p>}
    </div>
  );
}

/** Margin against popularity, relative to each item's own category thresholds (lines at 1). */
export function Scatter({ items, onSelect }: { items: ScatterItem[]; onSelect: (id: number) => void }) {
  const w = 560, h = 320, pad = { l: 40, r: 12, t: 12, b: 28 };
  const xs = items.filter((i) => i.units > 0);
  const xmax = Math.max(2, ...xs.map((i) => i.x)) * 1.1;
  const ymin = Math.min(0.6, ...xs.map((i) => i.y)) - 0.05;
  const ymax = Math.max(1.4, ...xs.map((i) => i.y)) + 0.05;
  const lx = (x: number) => pad.l + (Math.log(Math.max(0.05, x) / 0.05) / Math.log(xmax / 0.05)) * (w - pad.l - pad.r);
  const ly = (y: number) => h - pad.b - ((y - ymin) / (ymax - ymin)) * (h - pad.t - pad.b);
  const maxP = Math.max(1, ...xs.map((i) => Math.abs(i.profit)));
  const [hover, setHover] = useState<ScatterItem | null>(null);
  const quad = (cls: ItemClass, x: number, y: number, anchor: "start" | "end") => (
    <text x={x} y={y} textAnchor={anchor} fontSize={12} fill={classColor(cls)}>{CLASS_PLURAL[cls]}</text>
  );
  return (
    <div className="relative">
      <svg viewBox={`0 0 ${w} ${h}`} className="w-full max-w-[680px]" role="group" aria-label="Margin against popularity">
        <line x1={lx(1)} x2={lx(1)} y1={pad.t} y2={h - pad.b} stroke="rgb(var(--ink) / 0.35)" strokeDasharray="3 4" />
        <line x1={pad.l} x2={w - pad.r} y1={ly(1)} y2={ly(1)} stroke="rgb(var(--ink) / 0.35)" strokeDasharray="3 4" />
        {quad("puzzle", pad.l + 6, pad.t + 14, "start")}
        {quad("star", w - pad.r - 6, pad.t + 14, "end")}
        {quad("dog", pad.l + 6, h - pad.b - 8, "start")}
        {quad("plowhorse", w - pad.r - 6, h - pad.b - 8, "end")}
        <text x={w - pad.r} y={h - 6} textAnchor="end" fontSize={11} fill="rgb(var(--muted))">More popular in its category</text>
        <text x={10} y={pad.t + 4} fontSize={11} fill="rgb(var(--muted))" transform={`rotate(90 10 ${pad.t + 4})`}>Higher margin</text>
        {xs.map((i) => (
          <circle key={i.item_id} cx={lx(i.x)} cy={ly(i.y)} r={4 + 10 * Math.sqrt(Math.abs(i.profit) / maxP)}
            fill={classColor(i.class)} fillOpacity={0.75} stroke="rgb(var(--plate))" strokeWidth={1}
            tabIndex={0} role="button" aria-label={`${i.name}, ${CLASS_LABEL[i.class]}, ${rupees(i.profit)} profit`}
            onClick={() => onSelect(i.item_id)} onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && onSelect(i.item_id)}
            onMouseEnter={() => setHover(i)} onMouseLeave={() => setHover(null)} onFocus={() => setHover(i)} onBlur={() => setHover(null)}
            style={{ cursor: "pointer" }} />
        ))}
      </svg>
      <p className="mt-1 text-xs" role="status">{hover ? `${hover.name} · ${CLASS_LABEL[hover.class]} · ${num(hover.units)} sold · ${rupees(hover.profit)} profit` : "Dot size is profit. Click a dot to see the item."}</p>
    </div>
  );
}

/** One stacked bar of revenue by channel, with orders and average order value beside it. */
export function ChannelBar({ channels, labels, onSelect, selected }: {
  channels: { channel: string; orders: number; revenue: number; aov: number }[]; labels: Record<string, string>;
  onSelect?: (channel: string) => void; selected?: string;
}) {
  const total = channels.reduce((s, c) => s + c.revenue, 0);
  const colors: Record<string, string> = { dine_in: "rgb(var(--indigo))", phone: "rgb(var(--haldi))", takeaway: "rgb(var(--plow))" };
  return (
    <div>
      <div className="flex h-8 w-full overflow-hidden rounded-sm" role="img" aria-label="Revenue by channel">
        {channels.map((c) => (
          <button key={c.channel} title={labels[c.channel] ?? c.channel} onClick={() => onSelect?.(c.channel)}
            style={{ width: `${total ? (c.revenue / total) * 100 : 0}%`, background: colors[c.channel] ?? "rgb(var(--muted))",
              opacity: selected && selected !== c.channel ? 0.35 : 1 }} className="h-full transition-[width] duration-layout" />
        ))}
      </div>
      <table className="mt-3 w-full text-sm">
        <thead><tr className="text-left text-muted"><th className="py-1 font-normal">Channel</th><th className="py-1 text-right font-normal">Share</th>
          <th className="py-1 text-right font-normal">Orders</th><th className="py-1 text-right font-normal">Average order</th></tr></thead>
        <tbody>
          {channels.map((c) => (
            <tr key={c.channel} className="border-t border-ink/10">
              <td className="py-1.5"><button onClick={() => onSelect?.(c.channel)} className="flex items-center gap-2 hover:underline">
                <span className="h-2.5 w-2.5 rounded-[1px]" style={{ background: colors[c.channel] }} />{labels[c.channel] ?? c.channel}</button></td>
              <td className="num py-1.5 text-right">{total ? pct(c.revenue / total) : "0%"}</td>
              <td className="num py-1.5 text-right">{num(c.orders)}</td>
              <td className="num py-1.5 text-right">{rupees(c.aov)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
