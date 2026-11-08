// Item sheet: class and reason, weekly trend, margin, profit share, action, and the what-if price slider.
// The slider moves the bubble live with the client formula and confirms with the server on release.
import { area, curveMonotoneX, line } from "d3-shape";
import { useEffect, useMemo, useRef, useState } from "react";
import { toast } from "@/components/toast";
import { ClassTag, NumberTween } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { predict, predictRange, priceSteps } from "@/lib/elasticity";
import { pct, rupees } from "@/lib/format";
import type { ItemStat, PricePreview } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export function ItemSheet({ item, totalProfit, window: days, onPrice, onApplied }: {
  item: ItemStat; totalProfit: number; window: number;
  onPrice: (price: number | null) => void; onApplied: () => void;
}) {
  const steps = useMemo(() => priceSteps(item.price), [item.price]);
  const [idx, setIdx] = useState(steps.indexOf(item.price));
  const [server, setServer] = useState<PricePreview | null>(null);
  const [busy, setBusy] = useState(false);
  const trend = useApi(() => api.trend(item.item_id), [item.item_id]);
  const timer = useRef<number>();

  useEffect(() => {
    setIdx(steps.indexOf(item.price));
    setServer(null);
  }, [item.item_id, item.price, steps]);
  useEffect(() => () => onPrice(null), [onPrice]);

  const price = steps[idx] ?? item.price;
  const inputs = {
    monthlyUnits: (item.units * 30) / days, price: item.price, foodCost: item.food_cost,
    elasticity: item.elasticity ?? -1,
  };
  const p = predict(inputs, price);
  const [lo, hi] = predictRange(inputs, price);

  const confirm = (value: number) => {
    window_clear(timer.current);
    timer.current = window.setTimeout(async () => {
      try {
        setServer(await api.preview(item.item_id, value, days));
      } catch { /* the local preview stays on screen */ }
    }, 250);
  };

  const apply = async () => {
    setBusy(true);
    try {
      const r = await api.applyPrice(item.item_id, price);
      toast(`Applied ${rupees(r.new_price)} to ${r.name} on the PoS menu.`);
      onApplied();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "The price was not applied. Retry.", "error");
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <ClassTag cls={item.class} />
        <p className="text-base">{item.reason}</p>
      </div>

      <section aria-label="Weekly sales">
        <h3 className="label mb-2">Units sold per week, last 12 weeks</h3>
        {trend.data ? <Sparkline values={trend.data.series.map((s) => s.units)} /> : <div className="h-14" />}
      </section>

      <dl className="grid grid-cols-2 gap-x-6 gap-y-4">
        <Stat label="Margin per plate" value={`${rupees(item.cm)} (${pct(item.cm_pct)})`} />
        <Stat label="Profit share" value={pct(totalProfit ? item.profit / totalProfit : 0, 1)} />
        <Stat label={`Units in ${days} days`} value={item.units.toLocaleString("en-IN")} />
        <Stat label="Category average margin" value={rupees(item.category_avg_cm)} />
      </dl>

      <section className="flex flex-col gap-1">
        <h3 className="label">Recommended action</h3>
        <p className="text-base">{item.action}</p>
      </section>

      <section className="flex flex-col gap-4 border-t border-line pt-5" aria-label="What-if price">
        <div className="flex items-baseline justify-between">
          <label htmlFor="price-slider" className="text-base font-medium">What if the price were</label>
          <span className="num text-xl font-semibold">{rupees(price)}</span>
        </div>
        <input
          id="price-slider"
          type="range"
          min={0}
          max={steps.length - 1}
          step={1}
          value={idx}
          aria-valuetext={rupees(price)}
          onChange={(e) => {
            const i = Number(e.target.value);
            setIdx(i);
            onPrice(steps[i] === item.price ? null : steps[i]);
            setServer(null);
          }}
          onPointerUp={() => confirm(price)}
          onKeyUp={() => confirm(price)}
          className="w-full accent-[rgb(var(--ink))]"
        />
        <div className="flex justify-between text-xs text-muted num">
          <span>{rupees(steps[0])}</span>
          <span>Now {rupees(item.price)}</span>
          <span>{rupees(steps[steps.length - 1])}</span>
        </div>
        <div className="rounded-md bg-surface p-4">
          <p className="label">Predicted profit per month</p>
          <p className="mt-1 text-xl font-semibold">
            <NumberTween value={p.newProfit} duration={0.22} />{" "}
            <span className={`text-base font-medium ${p.delta >= 0 ? "" : "text-muted"}`}>
              (<NumberTween value={p.delta} duration={0.22} format={(n) => rupees(n, { sign: true })} />)
            </span>
          </p>
          <p className="mt-1 text-sm text-muted num">
            Range {rupees(lo, { sign: true })} to {rupees(hi, { sign: true })}. Elasticity {item.elasticity?.toFixed(1)},{" "}
            {item.elasticity_source === "Measured" ? "measured from your sales" : "assumed for this class"}.
          </p>
          {server && Math.abs(server.monthly_profit_change - p.delta) <= 1 && (
            <p className="mt-1 text-xs text-muted">Confirmed by the server.</p>
          )}
          {server?.warnings.map((w) => <p key={w} className="mt-1 text-sm">{w}</p>)}
        </div>
        <button className="btn-primary self-start" disabled={price === item.price || busy} onClick={apply}>
          {busy ? "Applying" : `Apply price ${rupees(price)}`}
        </button>
      </section>
    </div>
  );
}

function window_clear(id?: number) {
  if (id) window.clearTimeout(id);
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className="num text-md font-medium">{value}</dd>
    </div>
  );
}

function Sparkline({ values }: { values: number[] }) {
  const w = 340, h = 56;
  const max = Math.max(1, ...values);
  const pts = values.map((v, i) => [(i / Math.max(1, values.length - 1)) * w, h - 4 - (v / max) * (h - 8)] as [number, number]);
  const d = line().curve(curveMonotoneX)(pts) ?? "";
  const a = area().curve(curveMonotoneX).y0(h)(pts) ?? "";
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-14 w-full" role="img" aria-label={`Weekly units: ${values.join(", ")}`}>
      <path d={a} fill="rgb(var(--ink) / 0.06)" />
      <path d={d} fill="none" stroke="rgb(var(--ink))" strokeWidth={1.75} />
      <circle cx={pts[pts.length - 1]?.[0]} cy={pts[pts.length - 1]?.[1]} r={3} fill="rgb(var(--ink))" />
    </svg>
  );
}
