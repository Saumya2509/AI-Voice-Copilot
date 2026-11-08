// Orders (improve.md, section 1): live from the database with server-side paging, search, filters and
// sort. New orders slide in at the top when the list is on page one with the default sort; otherwise a
// small bar offers to jump to them. A row opens a drawer with the printed ticket and the order JSON.
import { AnimatePresence, motion } from "motion/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { JsonViewer } from "@/components/JsonViewer";
import { PrintedTicket } from "@/components/PrintedTicket";
import { Sheet } from "@/components/Sheet";
import { StatusTimeline, type Step } from "@/components/StatusTimeline";
import { toast } from "@/components/toast";
import { ErrorState } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { CHANNEL_LABEL, num, rupees, time } from "@/lib/format";
import { useLive } from "@/lib/live";
import { DUR, EASE } from "@/lib/motion";
import type { OrderQuery, OrderRow, OrdersPage as Page } from "@/lib/types";
import { useApi } from "@/lib/useApi";

const STATUS_LABEL: Record<string, string> = {
  pending: "Waiting", sent: "Sent", acked: "Acknowledged", failed: "Failed", needs_attention: "Needs attention",
};
const DEFAULT_SORT = "newest";

export default function OrdersPage() {
  const { id } = useParams();
  const nav = useNavigate();
  const [query, setQuery] = useState<OrderQuery>({ sort: DEFAULT_SORT });
  const [search, setSearch] = useState("");
  const [page, setPage] = useState<Page | null>(null);
  const [rows, setRows] = useState<OrderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [more, setMore] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fresh, setFresh] = useState<Set<string>>(new Set());
  const [pendingNew, setPendingNew] = useState(0);
  const ordersVersion = useLive((s) => s.ordersVersion);
  const dataVersion = useLive((s) => s.dataVersion);
  const seenVersion = useRef(ordersVersion);
  const pagedBeyondFirst = useRef(false);

  useEffect(() => {
    const t = setTimeout(() => setQuery((q) => ({ ...q, q: search.trim() || undefined })), 300);
    return () => clearTimeout(t);
  }, [search]);

  const load = useCallback(async (q: OrderQuery) => {
    setLoading(true);
    setError(null);
    try {
      const p = await api.orders({ ...q, limit: 50 });
      setPage(p);
      setRows(p.orders);
      pagedBeyondFirst.current = false;
      setPendingNew(0);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load(query);
  }, [query, dataVersion, load]);

  const defaultView = query.sort === DEFAULT_SORT && !query.q && !query.channel && !query.status && !query.from &&
    !query.to && query.has_upsell === undefined && !query.source;

  // A new order: slide it in on page one with the default view; otherwise count it in the bar.
  useEffect(() => {
    if (ordersVersion === seenVersion.current) return;
    seenVersion.current = ordersVersion;
    if (defaultView && !pagedBeyondFirst.current) {
      void api.orders({ ...query, limit: 50 }).then((p) => {
        setRows((cur) => {
          const have = new Set(cur.map((r) => r.order_id));
          const added = p.orders.filter((r) => !have.has(r.order_id)).map((r) => r.order_id);
          if (added.length) setFresh(new Set(added));
          return p.orders;
        });
        setPage(p);
      });
    } else {
      setPendingNew((n) => n + 1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ordersVersion]);

  const showMore = async () => {
    if (!page?.next_cursor) return;
    setMore(true);
    try {
      const p = await api.orders({ ...query, limit: 50, cursor: page.next_cursor });
      setRows((cur) => [...cur, ...p.orders]);
      setPage({ ...p, summary: page.summary, total: page.total });
      pagedBeyondFirst.current = true;
    } finally {
      setMore(false);
    }
  };

  const set = (patch: Partial<OrderQuery>) => setQuery((q) => ({ ...q, ...patch }));

  return (
    <div className="mx-auto max-w-[1600px] px-4 py-6 sm:px-6">
      <div className="title-rule flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-xl">Orders</h1>
        {page && (
          <p className="num text-sm text-muted">
            {num(page.summary.orders)} orders · {rupees(page.summary.revenue)}
            {Number(page.summary.upsell_added) > 0 && ` · offers added ${rupees(page.summary.upsell_added)}`}
          </p>
        )}
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <label className="relative min-w-[14rem] flex-1">
          <span className="sr-only">Search orders</span>
          <Icon name="search" size={18} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
          <input className="field h-10 w-full pl-8" value={search} onChange={(e) => setSearch(e.target.value)}
            placeholder="Search order number, item or customer" />
        </label>
        <label className="flex flex-col gap-1 text-xs text-muted">From
          <input type="date" className="field h-10" value={query.from ?? ""} onChange={(e) => set({ from: e.target.value || undefined })} /></label>
        <label className="flex flex-col gap-1 text-xs text-muted">To
          <input type="date" className="field h-10" value={query.to ?? ""} onChange={(e) => set({ to: e.target.value || undefined })} /></label>
        <label className="flex flex-col gap-1 text-xs text-muted">Channel
          <select className="field h-10" value={query.channel ?? ""} onChange={(e) => set({ channel: e.target.value || undefined })}>
            <option value="">All channels</option>
            {Object.entries(CHANNEL_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select></label>
        <label className="flex flex-col gap-1 text-xs text-muted">Status
          <select className="field h-10" value={query.status ?? query.source ?? ""}
            onChange={(e) => {
              const v = e.target.value;
              set(v === "pos_history" ? { source: "pos_history", status: undefined } : { status: v || undefined, source: undefined });
            }}>
            <option value="">All</option>
            <option value="acked">Sent by Tadka</option>
            <option value="needs_attention">Needs attention</option>
            <option value="pos_history">From PoS history</option>
          </select></label>
        <label className="flex flex-col gap-1 text-xs text-muted">Sort
          <select className="field h-10" value={query.sort} onChange={(e) => set({ sort: e.target.value as OrderQuery["sort"] })}>
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="total_desc">Largest total</option>
            <option value="total_asc">Smallest total</option>
          </select></label>
        <label className="flex h-10 items-center gap-2 text-sm">
          <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--indigo))]" checked={query.has_upsell === true}
            onChange={(e) => set({ has_upsell: e.target.checked ? true : undefined })} />
          Has offers
        </label>
        <a className="btn-secondary h-10" href={api.ordersExportUrl(query)} download><Icon name="download" size={18} />Export CSV</a>
      </div>

      <AnimatePresence>
        {pendingNew > 0 && (
          <motion.button initial={{ opacity: 0, y: -6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
            onClick={() => { setSearch(""); setQuery({ sort: DEFAULT_SORT }); }}
            className="mb-3 w-full rounded-sm bg-haldi py-2 text-sm font-medium text-ink">
            {pendingNew} new {pendingNew === 1 ? "order" : "orders"}. Show the newest
          </motion.button>
        )}
      </AnimatePresence>

      {error ? <ErrorState message={error} onRetry={() => void load(query)} /> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead>
              <tr className="border-b border-ink text-left">
                <th className="py-2 pr-4 font-medium">Order</th>
                <th className="py-2 pr-4 font-medium">Time</th>
                <th className="py-2 pr-4 font-medium">Channel</th>
                <th className="py-2 pr-4 font-medium">Customer</th>
                <th className="py-2 pr-4 text-right font-medium">Total</th>
                <th className="py-2 pr-4 text-right font-medium">Offers added</th>
                <th className="py-2 font-medium">Status</th>
              </tr>
            </thead>
            <tbody>
              {loading && rows.length === 0 ? Array.from({ length: 8 }).map((_, i) => (
                <tr key={i} className="border-b border-ink/10">{Array.from({ length: 7 }).map((__, j) => (
                  <td key={j} className="py-3 pr-4"><span className="block h-3 animate-pulse rounded-sm bg-ink/10" style={{ width: `${40 + ((i + j) % 4) * 15}%` }} /></td>))}</tr>
              )) : rows.length === 0 ? (
                <tr><td colSpan={7} className="py-10 text-base">No orders yet. Upload a sales CSV or take a call.</td></tr>
              ) : (
                <AnimatePresence initial={false}>
                  {rows.map((o) => (
                    <motion.tr key={o.order_id} layout initial={fresh.has(o.order_id) ? { opacity: 0, y: -16 } : false}
                      animate={{ opacity: 1, y: 0 }} transition={{ duration: DUR.base, ease: EASE }}
                      onClick={() => nav(`/orders/${o.order_id}`)}
                      className={`cursor-pointer border-b border-ink/10 ${fresh.has(o.order_id) ? "bg-haldi/25" : id === o.order_id ? "bg-ink/5" : "hover:bg-ink/[0.03]"}`}>
                      <td className="py-2.5 pr-4">
                        <a href={`/orders/${o.order_id}`} onClick={(e) => { e.preventDefault(); nav(`/orders/${o.order_id}`); }}
                          className="num underline-offset-4 hover:underline">{o.order_id}</a>
                      </td>
                      <td className="num py-2.5 pr-4">{time(o.ts, true)}</td>
                      <td className="py-2.5 pr-4">{CHANNEL_LABEL[o.channel]}</td>
                      <td className="max-w-[10rem] truncate py-2.5 pr-4">{o.customer_name ?? <span className="text-muted">—</span>}</td>
                      <td className="num py-2.5 pr-4 text-right">{rupees(o.total)}</td>
                      <td className="num py-2.5 pr-4 text-right">{o.upsell_added ? rupees(o.upsell_added, { sign: true }) : "—"}</td>
                      <td className="py-2.5"><StatusCell o={o} /></td>
                    </motion.tr>
                  ))}
                </AnimatePresence>
              )}
            </tbody>
          </table>
          {page?.next_cursor && (
            <button className="btn-secondary mt-4" onClick={showMore} disabled={more}>
              {more ? "Loading…" : `Show more (${num(rows.length)} of ${num(page.total)})`}
            </button>
          )}
        </div>
      )}

      <Sheet open={!!id} onClose={() => nav("/orders")} title={id ?? ""} width={560}>
        {id && <OrderDrawer id={id} onChange={() => void load(query)} />}
      </Sheet>
    </div>
  );
}

function StatusCell({ o }: { o: OrderRow }) {
  if (!o.pos) return <span className="text-muted">From PoS history</span>;
  const bad = o.pos.status === "needs_attention" || o.pos.status === "failed";
  return (
    <span className="inline-flex items-center gap-2">
      <span className={`h-2 w-2 rounded-full ${bad ? "bg-chilli" : o.pos.status === "acked" ? "bg-leaf" : "bg-ink/30"}`} aria-hidden />
      {STATUS_LABEL[o.pos.status]}{o.pos.kot_no ? ` · ${o.pos.kot_no}` : ""}
    </span>
  );
}

function OrderDrawer({ id, onChange }: { id: string; onChange: () => void }) {
  const order = useApi(() => api.order(id), [id]);
  const [retrying, setRetrying] = useState(false);
  if (order.loading && !order.data) return <p className="text-sm text-muted">Loading…</p>;
  if (order.error) return <ErrorState message={order.error} onRetry={order.reload} />;
  const o = order.data!;
  const pos = o.pos;
  const failed = pos?.status === "needs_attention" || pos?.status === "failed";
  const steps: Step[] = pos ? [
    { label: "Confirmed", at: o.confirmed_at, state: "done" },
    { label: "Sent to PoS", at: pos.sent_at, state: pos.sent_at ? "done" : failed ? "failed" : "pending",
      detail: failed && !pos.sent_at ? pos.error ?? undefined : undefined },
    { label: "Acknowledged", at: pos.ack_at, state: pos.ack_at ? "done" : failed && pos.sent_at ? "failed" : "pending" },
    { label: "KOT printed", at: pos.ack_at, state: pos.kot_no ? "done" : "pending", detail: pos.kot_no ?? undefined },
  ] : [];
  const retry = async () => {
    setRetrying(true);
    try {
      const r = await api.retry(id);
      if (r.status === "acked") toast(`Sent to PoS. Ticket ${r.kot_no}.`);
      else toast(r.error ?? "The PoS did not respond. Retry, or keep the order and send later.", "error");
      order.reload();
      onChange();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Retry failed. Check that the server is running.", "error");
    } finally {
      setRetrying(false);
    }
  };
  return (
    <div className="flex flex-col gap-6">
      {pos ? (
        <>
          <StatusTimeline steps={steps} />
          {failed && <button className="btn-primary self-start" onClick={retry} disabled={retrying}>{retrying ? "Sending" : "Retry send to PoS"}</button>}
          {o.kot ? <PrintedTicket kot={o.kot} /> : <p className="text-sm text-muted">The ticket prints when the PoS acknowledges the order.</p>}
          {o.order_json && <JsonViewer value={o.order_json} />}
        </>
      ) : (
        <>
          <p className="text-sm text-muted">From the PoS history{o.external_ref ? ` (bill ${o.external_ref})` : ""}. It was not sent through Tadka, so there is no KOT record.</p>
          <ul className="text-sm">
            {o.lines.map((l, i) => (
              <li key={i} className="flex items-baseline border-b border-ink/10 py-2">
                <span>{l.qty} x {l.name}</span><span className="leader" aria-hidden /><span className="num">{rupees(l.unit_price * l.qty)}</span>
              </li>
            ))}
          </ul>
          <p className="flex items-baseline font-medium"><span>Total</span><span className="leader" aria-hidden /><span className="num">{rupees(o.total)}</span></p>
          <JsonViewer value={{ order_id: o.order_id, ts: o.ts, channel: o.channel, lines: o.lines, total: o.total }} label="Order record" />
        </>
      )}
    </div>
  );
}
