// Public restaurant menu (improve.md, section 7). Reads GET /public/menu, so menu edits from the PoS or a
// CSV import show here without a rebuild.
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { ErrorState, Loading } from "@/components/ui";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { useLive } from "@/lib/live";
import { useApi } from "@/lib/useApi";
import { MenuCategoryBlock } from "./MenuCard";

interface Credit { file: string; title: string; author: string; license: string; license_url: string | null; source: string }

/** Dish photos come from Wikimedia Commons under free licences, which ask for the author and licence. */
function PhotoCredits() {
  const [open, setOpen] = useState(false);
  const [credits, setCredits] = useState<[string, Credit][] | null>(null);
  useEffect(() => {
    if (!open || credits) return;
    fetch("/dishes/credits.json").then((r) => (r.ok ? r.json() : {})).then((c: Record<string, Credit>) => setCredits(Object.entries(c)))
      .catch(() => setCredits([]));
  }, [open, credits]);
  return (
    <details className="mt-6 border-t border-ink/15 pt-4 text-sm text-muted" onToggle={(e) => setOpen((e.target as HTMLDetailsElement).open)}>
      <summary className="cursor-pointer select-none">Photo credits</summary>
      {credits === null ? <p className="mt-2">Loading…</p> : credits.length === 0 ? <p className="mt-2">No photo credits.</p> : (
        <ul className="mt-2 grid gap-x-8 gap-y-1 sm:grid-cols-2">
          {credits.map(([dish, c]) => (
            <li key={dish}>
              <span className="text-ink">{dish}</span>: <a href={c.source} target="_blank" rel="noreferrer" className="underline underline-offset-2">{c.author}</a>,{" "}
              {c.license_url ? <a href={c.license_url} target="_blank" rel="noreferrer" className="underline underline-offset-2">{c.license}</a> : c.license}, Wikimedia Commons
            </li>
          ))}
        </ul>
      )}
    </details>
  );
}

export default function PublicMenu() {
  const dataVersion = useLive((s) => s.dataVersion);
  const menu = useApi(() => api.publicMenu(), [dataVersion]);
  const name = useCatalog((s) => s.restaurantName);
  const [vegOnly, setVegOnly] = useState(false);
  const [q, setQ] = useState("");

  const cats = (menu.data?.categories ?? [])
    .map((c) => ({ ...c, items: c.items.filter((i) => (!vegOnly || i.veg) && (!q || i.name.toLowerCase().includes(q.toLowerCase()))) }))
    .filter((c) => c.items.length);

  return (
    <div>
      <div className="sticky top-nav z-20 border-b border-ink/15 bg-plate">
        <div className="mx-auto flex max-w-5xl items-center gap-4 overflow-x-auto px-4 py-2 sm:px-6">
          {(menu.data?.categories ?? []).map((c) => (
            <a key={c.id} href={`#cat-${c.id}`} className="shrink-0 text-sm text-ink/80 underline-offset-4 hover:text-ink hover:underline">{c.name}</a>
          ))}
        </div>
      </div>
      <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
        <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="font-display text-3xl leading-none">{name || "Menu"}</h1>
            {name && <p className="mt-2 text-base text-muted">Menu</p>}
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="relative">
              <span className="sr-only">Search the menu</span>
              <Icon name="search" size={18} className="pointer-events-none absolute left-2.5 top-1/2 -translate-y-1/2 text-muted" />
              <input className="field h-10 w-56 pl-8" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search" />
            </label>
            <label className="flex cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" className="h-4 w-4 accent-[rgb(var(--leaf))]" checked={vegOnly} onChange={(e) => setVegOnly(e.target.checked)} />
              Veg only
            </label>
          </div>
        </div>
        {menu.loading && !menu.data ? <Loading label="Setting the menu" /> : menu.error ? <ErrorState message={menu.error} onRetry={menu.reload} /> :
          !menu.data?.categories.length ? (
            <p className="text-base">The menu is empty. Upload a menu or sales CSV from <Link to="/upload" className="text-indigo underline underline-offset-4">Upload CSV</Link>.</p>
          ) : cats.length === 0 ? <p className="text-base">Nothing matches. Clear the search or the veg filter.</p> : (
            <div className="gap-14 md:columns-2">{cats.map((c) => <MenuCategoryBlock key={c.id} category={c} />)}</div>
          )}
        <PhotoCredits />
      </div>
    </div>
  );
}
