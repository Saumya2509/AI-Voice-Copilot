// Confirmed orders: today's orders placed through Tadka, newest first, from GET /orders (source=tadka).
// It refreshes on every order event from the live stream, so an order appears as soon as it is sent to the
// PoS and its status changes to "In the kitchen" when the PoS acknowledges it. The order from the current
// call is marked. Failed sends can be retried here.
import { useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { api } from "@/lib/api";
import { CHANNEL_LABEL, RESTAURANT_TZ, rupees, time } from "@/lib/format";
import { useLive } from "@/lib/live";
import type { OrderRow } from "@/lib/types";
import { useApi } from "@/lib/useApi";
import { useCall } from "./useCall";

const today = () => new Intl.DateTimeFormat("en-CA", { timeZone: RESTAURANT_TZ }).format(new Date()); // YYYY-MM-DD

export function ConfirmedOrders() {
  const ordersVersion = useLive((s) => s.ordersVersion);
  const kotNo = useCall((s) => s.kotNo);
  const currentId = useCall((s) => s.order?.order_id ?? null);
  const day = today();
  const res = useApi(() => api.orders({ source: "tadka", from: day, to: day, sort: "newest", limit: 20, with_items: true }),
    [ordersVersion, kotNo, day]);
  const orders = res.data?.orders ?? [];
  if (!res.data || orders.length === 0) return null;
  const summary = res.data.summary;

  return (
    <section aria-label="Confirmed orders" className="mt-4 border-t-2 border-ink pt-4">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h2 className="font-display text-xl leading-none">Confirmed orders</h2>
        <p className="text-sm text-muted">
          Today · <span className="num text-ink">{summary.orders}</span> {summary.orders === 1 ? "order" : "orders"} ·{" "}
          <span className="num text-ink">{rupees(summary.revenue)}</span>
        </p>
      </div>
      <ul className="flex flex-col gap-2">
        {orders.map((o) => <OrderCard key={o.order_id} order={o} current={o.order_id === currentId} onRetried={res.reload} />)}
      </ul>
      {res.data.total > orders.length && (
        <Link to="/orders" className="mt-3 inline-block text-sm text-indigo underline underline-offset-4">
          All {res.data.total} orders today
        </Link>
      )}
    </section>
  );
}

function Status({ pos }: { pos: OrderRow["pos"] }) {
  if (!pos) return null;
  const s = pos.status;
  const [dot, label] = s === "acked" ? ["bg-leaf", "In the kitchen"]
    : s === "failed" || s === "needs_attention" ? ["bg-chilli", "Not sent"]
    : ["bg-haldi", "Sending to the PoS"];
  return (
    <span className="flex shrink-0 items-center gap-1.5 text-sm" role="status">
      <span className={`h-2 w-2 rounded-full ${dot} ${s === "pending" || s === "sent" ? "motion-safe:animate-pulse" : ""}`} aria-hidden />
      {label}
    </span>
  );
}

function OrderCard({ order: o, current, onRetried }: { order: OrderRow; current: boolean; onRetried: () => void }) {
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const failed = o.pos?.status === "failed" || o.pos?.status === "needs_attention";
  const items = o.items ?? [];
  const retry = async () => {
    setBusy(true);
    setErr(null);
    try {
      await api.retry(o.order_id);
      onRetried();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  };

  return (
    <li className={`rounded-sm border bg-card px-3.5 py-3 ${current ? "border-indigo/60 shadow-[inset_3px_0_0_rgb(var(--haldi))]" : "border-ink/15"}`}>
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
        <Link to={`/orders/${o.order_id}`} className="font-medium underline-offset-4 hover:underline">
          {o.pos?.kot_no ? `KOT ${o.pos.kot_no}` : o.order_id}
        </Link>
        <span className="num text-sm text-muted">{time(o.confirmed_at ?? o.ts)}</span>
        <span className="text-sm text-muted">{CHANNEL_LABEL[o.channel] ?? o.channel}{o.customer_name ? ` · ${o.customer_name}` : ""}</span>
        {current && <span className="rounded-sm bg-haldi/70 px-1.5 text-[11px] leading-5 text-ink">This call</span>}
        <span className="ml-auto"><Status pos={o.pos} /></span>
      </div>
      <p className="mt-1.5 text-sm leading-relaxed">
        {items.map((i, k) => (
          <span key={k}>{k > 0 && <span className="text-muted">, </span>}<span className="num">{i.qty}</span> × {i.name}</span>
        ))}
      </p>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-2">
        <span className="num text-md font-medium">{rupees(o.total)}</span>
        {o.discount > 0 && <span className="text-sm text-muted">Combo saving {rupees(o.discount)}</span>}
        {failed && (
          <button className="btn-secondary ml-auto h-8 px-3 text-sm" onClick={retry} disabled={busy}>
            <Icon name="retry" size={14} /> {busy ? "Retrying…" : "Send again"}
          </button>
        )}
      </div>
      {(err || (failed && o.pos?.error)) && <p role="alert" className="mt-1.5 text-sm text-chilli">{err ?? o.pos?.error}</p>}
    </li>
  );
}
