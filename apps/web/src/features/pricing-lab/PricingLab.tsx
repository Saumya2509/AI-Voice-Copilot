// Screen 4. Pricing lab: recommendations with ranges and confidence, a summary strip, and a toggle that
// shows what the guardrails prevented.
import { useState } from "react";
import { toast } from "@/components/toast";
import { ClassTag, ErrorState, Loading, NumberTween, Switch } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { num, rupees } from "@/lib/format";
import type { PriceRec } from "@/lib/types";
import { useApi } from "@/lib/useApi";

export default function PricingLab() {
  const recs = useApi(() => api.pricing(30), []);
  const [guardrails, setGuardrails] = useState(true);
  const [applied, setApplied] = useState<Record<number, number>>({});
  const [busy, setBusy] = useState<number | null>(null);

  const rows = recs.data?.recommendations ?? [];
  const actionable = rows.filter((r) => (guardrails ? r.suggested_price !== r.price : r.unguarded_price !== r.price));
  const change = (r: PriceRec) => (guardrails ? r.monthly_profit_change : r.unguarded_monthly_profit_change);
  const pending = actionable.filter((r) => !(r.item_id in applied));
  const upside = pending.reduce((s, r) => s + Math.max(0, change(r)), 0);
  const appliedSum = Object.values(applied).reduce((a, b) => a + b, 0);

  const apply = async (r: PriceRec) => {
    const price = guardrails ? r.suggested_price : r.unguarded_price;
    setBusy(r.item_id);
    try {
      await api.applyPrice(r.item_id, price);
      setApplied((a) => ({ ...a, [r.item_id]: change(r) }));
      toast(`Applied ${rupees(price)} to ${r.name}.`);
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "The price was not applied. Retry.", "error");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6">
      <div className="title-rule">
        <h1 className="font-display text-xl">Pricing lab</h1>
        {recs.data && <p className="mt-1 text-sm text-muted">Based on {num(recs.data.sample_size)} orders in the last 30 days. {recs.data.note}</p>}
      </div>

      <section aria-label="Summary" className="mb-6 flex flex-wrap items-end gap-x-10 gap-y-4 border-y border-line py-5">
        <div>
          <p className="label">Monthly profit upside if all are applied</p>
          <p className="text-2xl font-semibold"><NumberTween value={upside} format={(n) => rupees(n, { sign: true })} /></p>
          <p className="text-sm text-muted">{pending.length} {pending.length === 1 ? "item" : "items"} to change</p>
        </div>
        <div>
          <p className="label">Applied this session</p>
          <p className="text-2xl font-semibold"><NumberTween value={appliedSum} format={(n) => rupees(n, { sign: true })} /></p>
        </div>
        <div className="ml-auto min-w-[260px] max-w-sm">
          <Switch checked={guardrails} onChange={setGuardrails} label="Guardrails"
            description="Limit changes to 10 percent, round to ₹5, keep margin above the category floor." />
        </div>
      </section>

      {recs.loading && !recs.data ? <Loading /> : recs.error ? <ErrorState message={recs.error} onRetry={recs.reload} /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-sm">
            <thead>
              <tr className="text-left text-muted">
                <th className="py-3 pr-4 font-normal">Item</th>
                <th className="py-3 pr-4 font-normal">Class</th>
                <th className="py-3 pr-4 text-right font-normal">Current</th>
                <th className="py-3 pr-4 text-right font-normal">Suggested</th>
                <th className="py-3 pr-4 text-right font-normal">Profit change per month</th>
                <th className="py-3 pr-4 font-normal">Elasticity</th>
                <th className="py-3 font-normal"><span className="sr-only">Action</span></th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => {
                const price = guardrails ? r.suggested_price : r.unguarded_price;
                const delta = change(r);
                const done = r.item_id in applied;
                const range = guardrails ? r.monthly_profit_change_range : null;
                return (
                  <tr key={r.item_id} className={`group border-t border-line align-top row-${r.class}`}>
                    <td className="relative py-3 pr-4">
                      <span className="row-bar absolute -left-3 top-1 bottom-1 w-[3px] rounded-r-sm opacity-0 group-hover:opacity-100" aria-hidden />
                      <span className="font-medium">{r.name}</span>
                      <p className="max-w-xs text-muted">{guardrails ? r.advice : r.unguarded_note}</p>
                      {!guardrails && r.guardrail_notes.length > 0 && (
                        <p className="max-w-xs text-xs text-muted">Guardrails would: {r.guardrail_notes.join(" ").toLowerCase()}</p>
                      )}
                    </td>
                    <td className="py-3 pr-4"><ClassTag cls={r.class} /></td>
                    <td className="num py-3 pr-4 text-right">{rupees(r.price)}</td>
                    <td className="num py-3 pr-4 text-right font-medium">{price === r.price ? "Hold" : rupees(price)}</td>
                    <td className="num py-3 pr-4 text-right">
                      {price === r.price ? <span className="text-muted">—</span> : (
                        <>
                          {rupees(delta, { sign: true })}
                          {range && <span className="block text-xs text-muted">{rupees(range[0], { sign: true })} to {rupees(range[1], { sign: true })}</span>}
                        </>
                      )}
                    </td>
                    <td className="py-3 pr-4">
                      <span className={`inline-flex rounded-sm border px-1.5 py-0.5 text-xs ${r.elasticity_source === "Measured" ? "border-ink" : "border-line text-muted"}`}>
                        {r.elasticity_source}
                      </span>
                      <span className="num ml-2 text-muted">{r.elasticity.toFixed(1)}</span>
                    </td>
                    <td className="py-3 text-right">
                      {price !== r.price && (
                        <button className={done ? "btn-quiet" : "btn-secondary"} disabled={done || busy === r.item_id} onClick={() => apply(r)}>
                          {done ? "Applied" : busy === r.item_id ? "Applying" : "Apply"}
                        </button>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
