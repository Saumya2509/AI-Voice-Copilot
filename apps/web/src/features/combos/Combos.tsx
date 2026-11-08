// Combos (improve.md, section 3): text only, set like a menu card. No charts, graphs or node diagrams.
import { useMemo, useState } from "react";
import { toast } from "@/components/toast";
import { ErrorState, Loading } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { num, pct, rupees } from "@/lib/format";
import { useLive } from "@/lib/live";
import type { Combo } from "@/lib/types";
import { useApi } from "@/lib/useApi";

type Sort = "margin" | "popular" | "value";
type Lang = "en" | "hinglish" | "hi";

export default function Combos() {
  const dataVersion = useLive((s) => s.dataVersion);
  const combos = useApi(() => api.combos(30, 60), [dataVersion]);
  const [anchor, setAnchor] = useState("");
  const [category, setCategory] = useState("");
  const [minMargin, setMinMargin] = useState(0);
  const [sort, setSort] = useState<Sort>("margin");
  const [lang, setLang] = useState<Lang>("en");
  const [limit, setLimit] = useState(20);

  const all = combos.data?.combos ?? [];
  const anchors = useMemo(() => Array.from(new Set(all.flatMap((c) => c.items.filter((i) => c.anchor_item_ids.includes(i.id)).map((i) => i.name)))).sort(), [all]);
  const categories = useMemo(() => Array.from(new Set(all.flatMap((c) => c.items.map((i) => i.category).filter(Boolean) as string[]))).sort(), [all]);

  const shown = all
    .filter((c) => !anchor || c.items.some((i) => i.name === anchor && c.anchor_item_ids.includes(i.id)))
    .filter((c) => !category || c.items.some((i) => i.category === category))
    .filter((c) => c.cm_pct * 100 >= minMargin)
    .sort((a, b) => sort === "margin" ? Number(b.added_margin) - Number(a.added_margin)
      : sort === "popular" ? b.support - a.support : Number(b.bundle_price) - Number(a.bundle_price));

  return (
    <div className="mx-auto max-w-4xl px-4 py-6 sm:px-6">
      <div className="title-rule flex flex-wrap items-end justify-between gap-3">
        <h1 className="font-display text-xl">Combos</h1>
        {combos.data && <p className="text-sm text-muted">From {num(combos.data.baskets)} orders with more than one item, last 30 days.</p>}
      </div>

      <div className="mb-6 flex flex-wrap items-end gap-3">
        <label className="flex flex-col gap-1 text-xs text-muted">Built around
          <select className="field h-10" value={anchor} onChange={(e) => setAnchor(e.target.value)}>
            <option value="">Any item</option>
            {anchors.map((a) => <option key={a} value={a}>{a}</option>)}
          </select></label>
        <label className="flex flex-col gap-1 text-xs text-muted">Category
          <select className="field h-10" value={category} onChange={(e) => setCategory(e.target.value)}>
            <option value="">Any category</option>
            {categories.map((c) => <option key={c} value={c}>{c}</option>)}
          </select></label>
        <label className="flex flex-col gap-1 text-xs text-muted">Margin at least
          <select className="field h-10" value={minMargin} onChange={(e) => setMinMargin(Number(e.target.value))}>
            {[0, 50, 55, 60, 65].map((m) => <option key={m} value={m}>{m ? `${m}%` : "Any"}</option>)}
          </select></label>
        <label className="flex flex-col gap-1 text-xs text-muted">Sort
          <select className="field h-10" value={sort} onChange={(e) => setSort(e.target.value as Sort)}>
            <option value="margin">Best margin</option>
            <option value="popular">Most popular</option>
            <option value="value">Highest order value</option>
          </select></label>
        <div className="ml-auto flex flex-col gap-1 text-xs text-muted">
          <span id="lang-label">How it sounds on a call</span>
          <div role="radiogroup" aria-labelledby="lang-label" className="inline-flex rounded-sm border border-ink/25 p-0.5">
            {([["en", "English"], ["hinglish", "Hinglish"], ["hi", "Hindi"]] as const).map(([v, l]) => (
              <button key={v} role="radio" aria-checked={lang === v} onClick={() => setLang(v)}
                className={`h-8 rounded-[2px] px-3 text-sm ${lang === v ? "bg-indigo text-on-indigo" : "text-ink/80 hover:bg-ink/5"}`}>{l}</button>
            ))}
          </div>
        </div>
      </div>

      {combos.loading && !combos.data ? <Loading /> : combos.error ? <ErrorState message={combos.error} onRetry={combos.reload} /> :
        all.length === 0 ? (
          <p className="text-base">No combos yet. Combos come from items that are ordered together, so they need some sales first. Upload a sales CSV to start.</p>
        ) : shown.length === 0 ? (
          <p className="text-base">No combo matches these filters.</p>
        ) : (
          <>
            <ol>{shown.slice(0, limit).map((c) => <ComboEntry key={c.id} combo={c} lang={lang} onChange={combos.reload} />)}</ol>
            {shown.length > limit && (
              <button className="btn-secondary mt-6" onClick={() => setLimit(limit + 20)}>Show more ({shown.length - limit} left)</button>
            )}
          </>
        )}
    </div>
  );
}

function ComboEntry({ combo, lang, onChange }: { combo: Combo; lang: Lang; onChange: () => void }) {
  const [inPool, setInPool] = useState(combo.in_pool);
  const [busy, setBusy] = useState(false);
  const toggle = async () => {
    setBusy(true);
    try {
      await api.setPool(combo.id, !inPool);
      setInPool(!inPool);
      toast(!inPool ? "Added to offers. The call desk can offer it now." : "Removed from offers.");
      onChange();
    } catch (e) {
      toast(e instanceof ApiError ? e.message : "Offers did not change. Retry.", "error");
    } finally {
      setBusy(false);
    }
  };
  const sounds = lang === "en" ? combo.pitch : lang === "hinglish" ? combo.pitch_hinglish : combo.pitch_hi;
  return (
    <li className="border-b border-ink/15 py-5">
      <div className="flex items-baseline">
        <h2 className="font-display text-xl">{combo.items.map((i) => i.name).join(" + ")}</h2>
        <span className="leader" aria-hidden />
        <span className="num text-md font-medium">{rupees(combo.bundle_price)}</span>
      </div>
      <p className="mt-1 text-base">{combo.evidence}.</p>
      <div className="mt-1 flex flex-wrap items-baseline justify-between gap-3">
        <p className="text-sm text-muted">
          Adds about {rupees(combo.added_margin)} margin per order.
          {combo.discount_pct > 0 ? ` Bundle discount ${pct(combo.discount_pct)} off ${rupees(combo.list_price)}.` : " No discount."}
        </p>
        <button className={inPool ? "btn-secondary h-9" : "btn-primary h-9"} onClick={toggle} disabled={busy} aria-pressed={inPool}>
          {inPool ? "In offers" : "Add to offers"}
        </button>
      </div>
      <p className="mt-2 text-sm" lang={lang === "hi" ? "hi" : "en"}><span className="text-muted">On a call: </span>“{sounds}”</p>
      <details className="mt-2 text-sm">
        <summary className="cursor-pointer text-indigo">Details</summary>
        <dl className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 sm:grid-cols-4">
          <div><dt className="text-muted">Support</dt><dd className="num">{pct(combo.support, 1)} of orders</dd></div>
          <div><dt className="text-muted">Confidence</dt><dd className="num">{pct(combo.confidence)}</dd></div>
          <div><dt className="text-muted">Lift</dt><dd className="num">{combo.lift.toFixed(1)} times chance</dd></div>
          <div><dt className="text-muted">Combo margin</dt><dd className="num">{pct(combo.cm_pct)}</dd></div>
        </dl>
      </details>
    </li>
  );
}
