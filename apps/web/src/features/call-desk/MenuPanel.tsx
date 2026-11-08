// The restaurant menu on the Call desk, set like the Menu section's printed card: category headings in
// Rozha One under a double rule, name, spice marks, dotted leader, price, and a one-line description
// (no photos here: they are for the main Menu page).
// Two columns when the panel is wide. Combos the agent offers on calls (chosen on the Combos page) come
// first. A tap adds the dish or the whole combo by hand; a dish the caller names glows for 1.2 s and
// scrolls into view.
import { useEffect, useMemo, useRef, useState } from "react";
import { Icon } from "@/components/Icon";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { useLive } from "@/lib/live";
import { useApi } from "@/lib/useApi";
import { rupees } from "@/lib/format";
import { useMotionPref } from "@/lib/motion";
import type { Combo, MenuItem } from "@/lib/types";
import { useCall } from "./useCall";

export function VegMark({ veg }: { veg: boolean }) {
  return <span className={veg ? "veg-mark" : "nonveg-mark"} role="img" aria-label={veg ? "Veg" : "Non-veg"} />;
}

export function SpiceMarks({ level }: { level: number }) {
  if (level <= 0) return null;
  return (
    <span className="flex shrink-0 text-chilli" role="img" aria-label={`Spice level ${level} of 3`}>
      {Array.from({ length: level }).map((_, k) => <Icon key={k} name="chilli" size={13} />)}
    </span>
  );
}

const slug = (s: string) => s.toLowerCase().replace(/[^a-z0-9]+/g, "-");

export function MenuPanel() {
  const menu = useCatalog((s) => s.menu);
  const loaded = useCatalog((s) => s.loaded);
  const cart = useCall((s) => s.cart);
  const highlight = useCall((s) => s.highlight);
  const addItem = useCall((s) => s.addItem);
  const addCombo = useCall((s) => s.addCombo);
  const dataVersion = useLive((s) => s.dataVersion);
  const combosRes = useApi(() => api.combos(30, 40), [dataVersion]);
  const [q, setQ] = useState("");
  const [vegOnly, setVegOnly] = useState(false);
  const [glow, setGlow] = useState<number | null>(null);
  const [current, setCurrent] = useState<string | null>(null);
  const heard = useRef<Set<number>>(new Set());
  const list = useRef<HTMLDivElement>(null);
  const { reduced } = useMotionPref();

  const items = useMemo(() => Object.values(menu), [menu]);
  const inCart = useMemo(() => {
    const m: Record<number, number> = {};
    cart?.lines.forEach((l) => (m[l.item_id] = (m[l.item_id] ?? 0) + l.qty));
    return m;
  }, [cart]);

  const scrollTo = (el: HTMLElement | null | undefined, center = false) => {
    const box = list.current;
    if (!el || !box) return;
    const top = center ? el.offsetTop - box.clientHeight / 2 + el.clientHeight / 2 : el.offsetTop - 8;
    box.scrollTo({ top, behavior: reduced ? "auto" : "smooth" });
  };

  // When a dish is heard: clear filters that hide it, glow for 1.2 s, scroll to it.
  useEffect(() => {
    if (!highlight) return;
    const item = menu[highlight.itemId];
    if (!item) return;
    if (highlight.kind === "heard") heard.current.add(item.id);
    if (q && !item.name.toLowerCase().includes(q.toLowerCase())) setQ("");
    if (vegOnly && !item.veg) setVegOnly(false);
    setGlow(item.id);
    const t = setTimeout(() => setGlow(null), 1200);
    requestAnimationFrame(() => scrollTo(list.current?.querySelector<HTMLElement>(`[data-item="${item.id}"]`), true));
    return () => clearTimeout(t);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [highlight]);

  const query = q.trim().toLowerCase();
  const grouped = useMemo(() => {
    const g = new Map<string, MenuItem[]>();
    items.forEach((i) => {
      if (vegOnly && !i.veg) return;
      if (query && !i.name.toLowerCase().includes(query) && !i.aliases?.some((a) => a.includes(query))) return;
      if (!g.has(i.category_name)) g.set(i.category_name, []);
      g.get(i.category_name)!.push(i);
    });
    return Array.from(g.entries());
  }, [items, vegOnly, query]);
  const pool = useMemo(() => (combosRes.data?.combos ?? []).filter((c) => c.in_pool), [combosRes.data]);
  const combos = useMemo(() => pool.filter((c) =>
    (!vegOnly || c.items.every((i) => menu[i.id]?.veg)) && (!query || c.items.some((i) => i.name.toLowerCase().includes(query)))),
  [pool, vegOnly, query, menu]);
  const allCategories = useMemo(() => [...(pool.length ? [COMBOS] : []), ...new Set(items.map((i) => i.category_name))], [items, pool]);
  const shown = grouped.reduce((n, [, rows]) => n + rows.length, 0);
  const sections = [...(combos.length ? [COMBOS] : []), ...grouped.map(([name]) => name)];

  // The jump bar marks the category at the top of the list.
  const onScroll = () => {
    const box = list.current;
    if (!box) return;
    let best: string | null = null;
    let bestTop = -Infinity;
    box.querySelectorAll<HTMLElement>("[data-cat]").forEach((el) => {
      const top = el.offsetTop - box.scrollTop;
      if (top <= 24 && top > bestTop) { bestTop = top; best = el.dataset.cat!; }
    });
    setCurrent(best ?? (sections[0] ? slug(sections[0]) : null));
  };
  useEffect(onScroll, [grouped, combos.length]); // eslint-disable-line react-hooks/exhaustive-deps

  return (
    <section aria-label="Restaurant menu" className="flex min-h-0 flex-1 flex-col">
      <div className="flex flex-wrap items-end gap-x-4 gap-y-3 pb-3">
        <div>
          <h2 className="font-display text-xl leading-none sm:text-2xl">Menu</h2>
          {loaded && items.length > 0 && (
            <p className="mt-1 text-xs text-muted">{query || vegOnly ? `${shown} of ${items.length} dishes` : `${items.length} dishes`} · tap to add</p>
          )}
        </div>
        <div className="flex w-full min-w-0 items-center justify-end gap-3 sm:ml-auto sm:w-auto sm:flex-1">
          <label className="relative min-w-0 flex-1 sm:max-w-[16rem]">
            <span className="sr-only">Search the menu</span>
            <Icon name="search" size={18} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
            <input className="field h-10 w-full pl-8 pr-8" value={q} onChange={(e) => setQ(e.target.value)}
              placeholder="Search" type="search" />
            {q && (
              <button className="absolute right-1.5 top-1/2 grid h-7 w-7 -translate-y-1/2 place-items-center text-muted hover:text-ink"
                onClick={() => setQ("")} aria-label="Clear search"><Icon name="close" size={14} /></button>
            )}
          </label>
          <label className="flex shrink-0 cursor-pointer items-center gap-2 text-sm">
            <input type="checkbox" checked={vegOnly} onChange={(e) => setVegOnly(e.target.checked)} className="h-4 w-4 accent-[rgb(var(--leaf))]" />
            Veg only
          </label>
        </div>
      </div>

      <nav aria-label="Menu categories" className="-mx-1 flex gap-1 overflow-x-auto border-y border-ink/15 py-1.5">
        {allCategories.map((c) => {
          const has = sections.includes(c);
          const on = current === slug(c);
          return (
            <button key={c} disabled={!has} aria-current={on ? "true" : undefined}
              onClick={() => scrollTo(list.current?.querySelector<HTMLElement>(`[data-cat="${slug(c)}"]`))}
              className={`relative shrink-0 rounded-sm px-2.5 py-1 text-sm transition-colors duration-fast disabled:opacity-35 ${
                on ? "text-ink" : "text-ink/70 hover:bg-ink/5 hover:text-ink"}`}>
              {on && <span className="absolute inset-x-2 bottom-0.5 h-[5px] bg-haldi/80" aria-hidden />}
              <span className="relative">{c}</span>
            </button>
          );
        })}
      </nav>

      <div ref={list} onScroll={onScroll} className="menu-panel relative min-h-0 flex-1 overflow-y-auto pr-1 pt-4">
        {!loaded ? <p className="py-6 text-sm text-muted">Setting the menu…</p> : items.length === 0 ? (
          <p className="py-6 text-sm text-muted">No menu yet. Upload a menu CSV first.</p>
        ) : sections.length === 0 ? (
          <p className="py-6 text-sm text-muted">Nothing matches. Clear the search or the veg filter.</p>
        ) : (
          <div className="menu-cols">
            {combos.length > 0 && (
              <section data-cat={slug(COMBOS)} aria-label={COMBOS} className="mb-7 break-inside-avoid">
                <h3 className="double-rule flex items-baseline justify-between gap-3 pt-2.5 font-display text-xl leading-tight">
                  {COMBOS}
                  <span className="font-sans text-xs font-normal text-muted">Offered on calls</span>
                </h3>
                <ul className="mt-2">
                  {combos.map((c) => (
                    <ComboRow key={c.id} combo={c} veg={c.items.every((i) => menu[i.id]?.veg)}
                      onTicket={c.items.every((i) => (inCart[i.id] ?? 0) > 0)} onAdd={() => addCombo(c.id)} />
                  ))}
                </ul>
              </section>
            )}
            {grouped.map(([category, rows]) => (
              <section key={category} data-cat={slug(category)} aria-label={category} className="mb-7 break-inside-avoid">
                <h3 className="double-rule pt-2.5 font-display text-xl leading-tight">{category}</h3>
                <ul className="mt-2">
                  {rows.map((i) => (
                    <MenuRow key={i.id} item={i} qty={inCart[i.id] ?? 0} glowing={glow === i.id}
                      heard={heard.current.has(i.id)} onAdd={(d) => addItem(i.id, d)} />
                  ))}
                </ul>
              </section>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}

const COMBOS = "Combos";

function ComboRow({ combo, veg, onTicket, onAdd }: { combo: Combo; veg: boolean; onTicket: boolean; onAdd: () => void }) {
  const names = combo.items.map((i) => i.name);
  const save = combo.list_price - combo.bundle_price;
  return (
    <li className={`group relative -mx-2 flex items-start gap-2 rounded-sm px-2 py-2 transition-colors duration-fast ${
      onTicket ? "bg-indigo/[0.06]" : "hover:bg-ink/[0.04]"}`}>
      <button className="min-w-0 flex-1 text-left" onClick={onAdd}
        aria-label={`Add the combo ${names.join(", ")}, ${rupees(combo.bundle_price)} instead of ${rupees(combo.list_price)}`}>
        <span className="flex items-baseline gap-2">
          <span className="translate-y-[2px]"><VegMark veg={veg} /></span>
          <span className="min-w-0 text-md leading-snug">{names.join(" + ")}</span>
          <span className="leader" aria-hidden />
          <span className="num shrink-0 text-sm text-muted line-through" aria-hidden>{rupees(combo.list_price)}</span>
          <span className="num shrink-0 text-md">{rupees(combo.bundle_price)}</span>
        </span>
        <span className="ml-6 mt-0.5 block text-sm leading-snug text-muted">
          <span className="mr-1.5 inline-block rounded-sm bg-haldi/70 px-1 align-[1px] text-[11px] leading-4 text-ink">Save {rupees(save)}</span>
          {onTicket ? "On the ticket at the combo price" : `${names.length} dishes, one tap`}
        </span>
      </button>
      {onTicket ? (
        <span className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-sm border border-indigo/50 text-indigo" aria-hidden>
          <Icon name="check" size={14} />
        </span>
      ) : (
        <button tabIndex={-1} aria-hidden onClick={onAdd}
          className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-sm border border-ink/25 text-ink/70 opacity-60 transition-opacity duration-fast hover:bg-ink/5 group-hover:opacity-100">
          <Icon name="plus" size={14} />
        </button>
      )}
    </li>
  );
}

function MenuRow({ item, qty, glowing, heard, onAdd }: {
  item: MenuItem; qty: number; glowing: boolean; heard: boolean; onAdd: (delta: number) => void;
}) {
  const out = !item.available;
  const note = out ? "Not available today" : item.hold_reason?.replace("Held: ", "Low stock: ");
  return (
    <li data-item={item.id}
      className={`group relative -mx-2 flex items-start gap-2 rounded-sm px-2 py-2 transition-colors duration-[1200ms] ${
        glowing ? "bg-haldi/45 duration-0" : qty > 0 ? "bg-indigo/[0.06]" : "hover:bg-ink/[0.04]"} ${out ? "opacity-50" : ""}`}>
      <button className="min-w-0 flex-1 text-left disabled:cursor-not-allowed" disabled={out}
        onClick={() => onAdd(1)} aria-label={`Add ${item.name}, ${rupees(item.price)}`}>
        <span className="flex items-baseline gap-2">
          <span className="translate-y-[2px]"><VegMark veg={item.veg} /></span>
          <span className="min-w-0 text-md leading-snug">{item.name}</span>
          <SpiceMarks level={item.spice_level} />
          {heard && <Icon name="check" size={14} className="shrink-0 text-leaf" aria-label="Heard" />}
          <span className="leader" aria-hidden />
          <span className="num shrink-0 text-md">{rupees(item.price)}</span>
        </span>
        {(item.description || note || item.chefs_pick) && (
          <span className="ml-6 mt-0.5 block text-sm leading-snug text-muted">
            {item.chefs_pick && (
              <span className="mr-1.5 inline-block rounded-sm border border-ink/30 px-1 align-[1px] text-[11px] leading-4 text-ink/75">Chef's pick</span>
            )}
            {note ? <span className="text-ink/80">{note}</span> : item.description}
          </span>
        )}
      </button>
      {qty > 0 ? (
        <span className="mt-0.5 flex shrink-0 items-center rounded-sm border border-indigo/50 bg-plate">
          <button className="grid h-7 w-7 place-items-center hover:bg-ink/5" onClick={() => onAdd(-1)} aria-label={`One less ${item.name}`}>
            <Icon name="minus" size={14} />
          </button>
          <span className="num w-6 text-center text-sm font-medium" aria-label={`${qty} on the ticket`}>{qty}</span>
          <button className="grid h-7 w-7 place-items-center hover:bg-ink/5" onClick={() => onAdd(1)} aria-label={`One more ${item.name}`}>
            <Icon name="plus" size={14} />
          </button>
        </span>
      ) : !out && (
        // The row itself is the accessible add button; this is a mouse target for the same action.
        <button tabIndex={-1} aria-hidden onClick={() => onAdd(1)}
          className="mt-0.5 grid h-7 w-7 shrink-0 place-items-center rounded-sm border border-ink/25 text-ink/70 opacity-60 transition-opacity duration-fast hover:bg-ink/5 group-hover:opacity-100">
          <Icon name="plus" size={14} />
        </button>
      )}
    </li>
  );
}
