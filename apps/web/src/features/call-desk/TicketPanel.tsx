// The ticket: a portrait kitchen order ticket in the top-right column of the Call desk (a tab on phones),
// so it never covers the menu. A printer slot sits at the top; when the first item is added the ticket
// feeds down out of it (900 ms), lines print with a typed effect, removals strike through, and on
// acknowledgement the ticket tears and is stamped with the KOT number. Confirm and Send stay pinned at
// the bottom of the column however long the order gets.
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { NumberTween } from "@/components/ui";
import { useCatalog } from "@/lib/catalog";
import { LANGUAGE_LABEL, maskCallId, rupees, time } from "@/lib/format";
import { DUR, EASE, useMotionPref } from "@/lib/motion";
import type { CartLine } from "@/lib/types";
import { useCall } from "./useCall";

const STATION_ORDER = ["tandoor", "curry", "wok", "grill", "cold", "dessert", "beverage"];
const STATION_LABEL: Record<string, string> = {
  tandoor: "Tandoor", curry: "Curry", wok: "Wok", grill: "Grill", cold: "Cold", dessert: "Dessert", beverage: "Beverage",
};
const CPS = 40;
const NO_LINES: CartLine[] = [];

interface ShownLine extends CartLine {
  key: string;
  struck: boolean;
}

const lineKey = (l: CartLine) => `${l.line_id}:${l.qty}:${l.modifiers.map((m) => m.name).join(",")}:${l.notes.join(",")}`;

function useShownLines(lines: CartLine[], reduced: boolean): ShownLine[] {
  const [shown, setShown] = useState<ShownLine[]>([]);
  useEffect(() => {
    const now = new Map(lines.map((l) => [lineKey(l), l]));
    setShown((prev) => {
      if (prev.length === 0 && lines.length === 0) return prev;
      const kept = prev.filter((p) => !p.struck || now.has(p.key));
      const prevKeys = new Set(kept.map((p) => p.key));
      const next: ShownLine[] = kept.map((p) => (now.has(p.key) ? { ...p, ...now.get(p.key)!, struck: false } : { ...p, struck: true }));
      for (const l of lines) if (!prevKeys.has(lineKey(l))) next.push({ ...l, key: lineKey(l), struck: false });
      return next;
    });
    const t = setTimeout(() => setShown((p) => (p.some((x) => x.struck) ? p.filter((x) => !x.struck) : p)), reduced ? 0 : 700);
    return () => clearTimeout(t);
  }, [lines, reduced]);
  return shown;
}

function useTyped(text: string, enabled: boolean) {
  const [n, setN] = useState(enabled ? 0 : text.length);
  useEffect(() => {
    if (!enabled) return setN(text.length);
    setN(0);
    const id = setInterval(() => setN((k) => (k >= text.length ? (clearInterval(id), k) : k + 1)), 1000 / CPS);
    return () => clearInterval(id);
  }, [text, enabled]);
  return text.slice(0, n);
}

/** Item count and total, for the phone tab label. */
export function useTicketSummary() {
  const cart = useCall((s) => s.cart);
  return { count: cart?.lines.reduce((n, l) => n + l.qty, 0) ?? 0, total: cart?.total ?? 0 };
}

export function TicketPanel() {
  const s = useCall();
  const { menu, restaurantName } = useCatalog();
  const { reduced } = useMotionPref();
  const lines = useShownLines(s.cart?.lines ?? NO_LINES, reduced);
  const printed = lines.length > 0 || Boolean(s.order);

  const groups = useMemo(() => {
    const by: Record<string, ShownLine[]> = {};
    for (const l of lines) (by[menu[l.item_id]?.station ?? "curry"] ??= []).push(l);
    return [...STATION_ORDER.filter((st) => by[st]), ...Object.keys(by).filter((k) => !STATION_ORDER.includes(k))]
      .map((st) => [st, by[st]] as const);
  }, [lines, menu]);

  const { count } = useTicketSummary();
  const up = s.cart?.upsell;
  const live = !["idle", "done", "error"].includes(s.status);
  const canConfirm = live && count > 0 && ["GREETING", "TAKING_ORDER", "CONFIRMING"].includes(s.serverState ?? "");
  const canSend = live && count > 0 && !s.order && !s.clarify;

  return (
    <section aria-label="Ticket" className="flex min-h-0 flex-1 flex-col">
      <div className="flex items-end justify-between gap-3 pb-3">
        <div className="min-w-0">
          <h2 className="font-display text-2xl leading-none">Ticket</h2>
          <p className="mt-1 truncate text-xs text-muted">
            KOT {s.kotNo ?? "pending"} · {count} {count === 1 ? "item" : "items"}{s.recording && " · Recording"}
          </p>
        </div>
        <div className="flex flex-col items-end">
          {up && up.accepted > 0 && (
            <span className="num mb-1 rounded-sm bg-haldi px-1.5 text-xs font-medium text-ink">Offers {rupees(up.added_revenue, { sign: true })}</span>
          )}
          <span className="num text-xl font-medium leading-none"><NumberTween value={s.cart?.total ?? 0} /></span>
        </div>
      </div>

      {/* The printer slot: a dark slit with a thin highlight. The ticket feeds down out of it. */}
      <div className="relative z-10 h-[6px] shrink-0 rounded-full bg-slot shadow-[inset_0_-1px_0_rgb(255_255_255/0.25)]" aria-hidden />
      <div className="-mt-[3px] flex min-h-0 flex-1 flex-col px-1.5">
        <div className="min-h-0 flex-1 overflow-y-auto">
          <AnimatePresence mode="wait" initial={false}>
            {printed ? (
              <motion.article
                key={s.callId ?? "ticket"}
                aria-label="Kitchen order ticket"
                initial={reduced ? { opacity: 0 } : { y: -60, clipPath: "inset(0 0 100% 0)" }}
                animate={reduced ? { opacity: 1 } : { y: 0, clipPath: "inset(0 0 0% 0)" }}
                exit={{ opacity: 0 }}
                transition={{ duration: reduced ? DUR.fast : DUR.feed, ease: EASE }}
                className={`flex flex-col gap-3 bg-paper px-4 pb-5 pt-4 font-ticket text-[13px] leading-[1.55] text-paper-ink shadow-ticket ${s.order ? "ticket-torn" : ""}`}
              >
                <header className="border-b border-dashed border-paper-ink/40 pb-3 text-center">
                  <p className="text-[15px]">{restaurantName || "Kitchen order ticket"}</p>
                  <p>KOT {s.kotNo ?? "pending"}</p>
                  <p>{time(s.startedAt ? new Date(s.startedAt).toISOString() : null)} · Phone</p>
                  <p className="text-paper-ink/60">{LANGUAGE_LABEL[s.heardLang ?? ""] ?? ""} {s.callId ? maskCallId(s.callId) : ""}</p>
                </header>

                <div className="flex flex-col gap-2">
                  {groups.map(([station, ls]) => (
                    <section key={station}>
                      <p className="text-paper-ink/60">-- {STATION_LABEL[station] ?? station} --</p>
                      <ul>
                        <AnimatePresence initial={false}>
                          {ls.map((l) => <TicketLine key={l.key} line={l} animate={!reduced} />)}
                        </AnimatePresence>
                      </ul>
                    </section>
                  ))}
                </div>

                <div className="flex flex-col gap-2 border-t border-dashed border-paper-ink/40 pt-3">
                  {s.cart && s.cart.discount > 0 && (
                    <div className="flex justify-between"><span>Combo saving</span><span>-{rupees(s.cart.discount)}</span></div>
                  )}
                  <div className="flex justify-between text-[16px]"><span>TOTAL</span><NumberTween value={s.cart?.total ?? 0} /></div>
                  <RupeeMeter revenue={up?.added_revenue ?? 0} margin={up?.added_margin ?? 0} filled={(up?.accepted ?? 0) / 2} />
                  <PosStamp />
                </div>
              </motion.article>
            ) : (
              <motion.p key="empty" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
                className="border border-dashed border-ink/25 px-4 py-6 text-center text-sm text-muted">
                No items yet. Dishes the caller orders, or that you tap on the menu, print here.
              </motion.p>
            )}
          </AnimatePresence>
        </div>

        {!s.order && (
          <div className="flex shrink-0 gap-2 border-t border-ink/15 bg-plate pt-3">
            <button className="btn-secondary h-11 flex-1 px-3" disabled={!canConfirm} onClick={s.confirmOrder}>Confirm order</button>
            <button className="btn-primary h-11 flex-1 px-3" disabled={!canSend} onClick={s.sendToPos}>Send to PoS</button>
          </div>
        )}
      </div>
    </section>
  );
}

function TicketLine({ line, animate }: { line: ShownLine; animate: boolean }) {
  const label = `${line.qty} x ${line.name}`;
  const typed = useTyped(label, animate);
  const done = typed.length === label.length;
  const extras = [
    ...line.modifiers.map((m) => (m.group === "Spice" ? `${m.name} spicy` : m.group === "Add-ons" ? `+ ${m.name}` : m.name)),
    ...line.notes.map((n) => `NOTE: ${n}`),
  ];
  // A combo staff added from the menu keeps source "staff" (it is not an offer) but carries its combo id.
  const tag = line.source === "staff" && line.combo_id ? "(combo)" : { upsell: "(offer)", combo: "(combo)", staff: "(added)", customer: "" }[line.source];
  return (
    <motion.li layout exit={{ opacity: 0, height: 0 }} transition={{ duration: DUR.base, ease: EASE }} className="relative">
      <div className="flex justify-between gap-3">
        <span className="min-w-0">
          {typed}
          {!done && <span className="ml-px inline-block h-[1em] w-[0.5ch] translate-y-[2px] bg-paper-ink/70" aria-hidden />}
          {tag && done && <span className="ml-2 text-paper-ink/60">{tag}</span>}
        </span>
        <motion.span initial={{ opacity: 0 }} animate={{ opacity: done ? 1 : 0 }} transition={{ duration: DUR.base }} className="shrink-0">
          {rupees(line.unit_price * line.qty)}
        </motion.span>
      </div>
      {done && extras.map((e) => <p key={e} className="pl-5 text-paper-ink/75">{e}</p>)}
      <motion.span aria-hidden className="absolute left-0 top-[0.8em] h-px w-full origin-left bg-paper-ink" initial={false}
        animate={{ scaleX: line.struck ? 1 : 0 }} transition={{ duration: 0.16, ease: EASE }} />
      {line.struck && <span className="sr-only">Removed</span>}
    </motion.li>
  );
}

function RupeeMeter({ revenue, margin, filled }: { revenue: number; margin: number; filled: number }) {
  return (
    <div aria-label="Added by offers on this call">
      <div className="flex justify-between gap-2">
        <span>Offers added</span>
        <span>
          <NumberTween value={revenue} format={(n) => rupees(n, { sign: n > 0 })} />
          {" / "}
          <NumberTween value={margin} format={(n) => `${rupees(n)} margin`} />
        </span>
      </div>
      <div className="mt-1.5 h-1 w-full bg-paper-ink/10">
        <motion.div className="h-full bg-haldi" initial={false} animate={{ width: `${Math.min(1, filled) * 100}%` }}
          transition={{ duration: 0.5, ease: EASE }} />
      </div>
    </div>
  );
}

function PosStamp() {
  const { pos, kotNo, order, error } = useCall();
  if (!order) return null;
  return (
    <div role="status" aria-live="polite" className="mt-1 flex justify-center">
      {pos === "acked" ? (
        <motion.div initial={{ scale: 1.3, opacity: 0, rotate: -8 }} animate={{ scale: 1, opacity: 1, rotate: -6 }}
          transition={{ duration: DUR.base, ease: EASE }}
          className="grid h-24 w-24 place-items-center rounded-full border-[3px] border-[#7A1F2B] text-center text-[11px] uppercase leading-tight tracking-wider text-[#7A1F2B]">
          <span>Sent to PoS<br /><span className="text-[15px]">{kotNo}</span></span>
        </motion.div>
      ) : pos === "failed" ? (
        <p>PoS did not respond. {error ?? ""} Use Send again under Confirmed orders.</p>
      ) : (
        <p className="flex items-center gap-2">
          <span className="h-3 w-3 animate-spin rounded-full border-2 border-paper-ink border-t-transparent" aria-hidden />
          Sending to PoS
        </p>
      )}
    </div>
  );
}
