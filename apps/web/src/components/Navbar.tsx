// Top navbar: 68 px of ivory with a gold double hairline beneath, the name set in Cormorant with a gold
// ornament. The active link is maroon with a fine gold underline that slides to the new link (220 ms).
// Under 900 px the links collapse into a drawer from the top; Call desk stays visible.
import { AnimatePresence, LayoutGroup, motion } from "motion/react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";
import { Link, NavLink, useLocation } from "react-router-dom";
import { useCatalog } from "@/lib/catalog";
import { DUR, EASE, useMediaQuery } from "@/lib/motion";
import { Icon } from "./Icon";
import { ThemeSwitch } from "./ThemeSwitch";

export const LINKS = [
  { to: "/desk", label: "Call desk" },
  { to: "/menu", label: "Menu" },
  { to: "/analytics", label: "Analytics" },
  { to: "/combos", label: "Combos" },
  { to: "/orders", label: "Orders" },
  { to: "/recordings", label: "Recordings" },
];
export const MORE = [
  { to: "/pricing", label: "Pricing lab" },
  { to: "/settings", label: "Settings" },
];

const active = (path: string, to: string) => path === to || path.startsWith(to + "/");

export function Navbar() {
  const { pathname } = useLocation();
  const narrow = useMediaQuery("(max-width: 899px)");
  const [drawer, setDrawer] = useState(false);
  const [more, setMore] = useState(false);
  const name = useCatalog((s) => s.restaurantName);
  const linkRefs = useRef<(HTMLAnchorElement | null)[]>([]);
  const moreRef = useRef<HTMLLIElement>(null);

  useEffect(() => {
    setDrawer(false);
    setMore(false);
  }, [pathname]);

  useEffect(() => {
    if (!more && !drawer) return;
    const onKey = (e: globalThis.KeyboardEvent) => e.key === "Escape" && (setMore(false), setDrawer(false));
    const onClick = (e: MouseEvent) => more && !moreRef.current?.contains(e.target as Node) && setMore(false);
    window.addEventListener("keydown", onKey);
    window.addEventListener("mousedown", onClick);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("mousedown", onClick);
    };
  }, [more, drawer]);

  // Arrow keys move across the links.
  const onLinkKey = (e: KeyboardEvent, i: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const n = linkRefs.current.length;
    linkRefs.current[(i + (e.key === "ArrowRight" ? 1 : n - 1)) % n]?.focus();
  };

  const moreActive = MORE.some((m) => active(pathname, m.to));

  return (
    <header className="sticky top-0 z-40 border-b border-haldi bg-plate shadow-[0_3px_0_-2px_rgb(var(--haldi)/0.5)]">
      <nav aria-label="Main" className="mx-auto flex h-nav max-w-[1600px] items-center gap-4 px-4 sm:px-6">
        <Link to="/" className="group flex items-center gap-2 leading-none" aria-label="Tadka, home">
          <span className="text-[15px] text-haldi transition-transform duration-base group-hover:rotate-45" aria-hidden>❖</span>
          <span className="font-display text-[32px] font-bold tracking-[0.01em] text-indigo">Tadka</span>
        </Link>

        {narrow ? (
          <>
            <NavLink to="/desk" className={`ml-1 border-b-2 px-1 py-1 text-sm font-medium ${active(pathname, "/desk") ? "border-haldi text-indigo" : "border-transparent"}`}>
              Call desk
            </NavLink>
            <div className="ml-auto flex items-center gap-1">
              <ThemeSwitch compact />
              <button className="btn-quiet h-10 w-10 px-0" aria-expanded={drawer} aria-controls="nav-drawer"
                onClick={() => setDrawer(!drawer)}>
                <Icon name={drawer ? "close" : "burger"} size={22} />
                <span className="sr-only">{drawer ? "Close menu" : "Open menu"}</span>
              </button>
            </div>
          </>
        ) : (
          <>
            <LayoutGroup id="nav">
              <ul className="ml-4 flex items-center gap-1">
                {LINKS.map((l, i) => {
                  const on = active(pathname, l.to);
                  return (
                    <li key={l.to}>
                      <NavLink ref={(el) => (linkRefs.current[i] = el)} to={l.to} onKeyDown={(e) => onLinkKey(e, i)}
                        aria-current={on ? "page" : undefined}
                        className={`relative block px-3 py-2 text-[15px] tracking-[0.01em] transition-colors duration-fast ${on ? "font-medium text-indigo" : "text-ink/75 hover:text-indigo"}`}>
                        {on && (
                          <motion.span layoutId="nav-highlight" aria-hidden
                            className="absolute inset-x-3 bottom-0 h-[2px] bg-haldi"
                            transition={{ duration: DUR.base, ease: EASE }} />
                        )}
                        <span className="relative">{l.label}</span>
                      </NavLink>
                    </li>
                  );
                })}
                <li className="relative" ref={moreRef}>
                  <button className={`relative flex items-center gap-1 px-3 py-2 text-[15px] tracking-[0.01em] ${moreActive ? "font-medium text-indigo" : "text-ink/75 hover:text-indigo"}`}
                    aria-haspopup="menu" aria-expanded={more} onClick={() => setMore(!more)}>
                    {moreActive && (
                      <motion.span layoutId="nav-highlight" aria-hidden
                        className="absolute inset-x-3 bottom-0 h-[2px] bg-haldi"
                        transition={{ duration: DUR.base, ease: EASE }} />
                    )}
                    <span className="relative">More</span>
                    <Icon name="caret" size={14} className="relative" />
                  </button>
                  {more && (
                    <div role="menu" className="absolute left-0 top-12 z-50 w-52 rounded-md border border-haldi/50 bg-card py-1.5 shadow-card">
                      {MORE.map((m) => (
                        <Link key={m.to} role="menuitem" to={m.to}
                          className={`block px-4 py-2 text-sm hover:bg-indigo/5 hover:text-indigo ${active(pathname, m.to) ? "font-medium text-indigo" : ""}`}>
                          {m.label}
                        </Link>
                      ))}
                    </div>
                  )}
                </li>
              </ul>
            </LayoutGroup>
            <div className="ml-auto flex items-center gap-3">
              <Link to="/upload" className="btn-secondary h-9"><Icon name="upload" size={18} />Upload CSV</Link>
              <ThemeSwitch compact />
              {name && <span className="max-w-[12rem] truncate font-display text-md italic text-indigo">{name}</span>}
            </div>
          </>
        )}
      </nav>

      <AnimatePresence>
        {narrow && drawer && (
          <motion.div id="nav-drawer" initial={{ y: -12, opacity: 0 }} animate={{ y: 0, opacity: 1 }} exit={{ y: -12, opacity: 0 }}
            transition={{ duration: DUR.base, ease: EASE }}
            className="absolute inset-x-0 top-full border-b border-haldi bg-plate px-4 pb-5 pt-2 shadow-card">
            <ul className="flex flex-col">
              {[...LINKS, ...MORE].map((l) => (
                <li key={l.to}>
                  <NavLink to={l.to} className={`flex items-center gap-2 border-b border-haldi/25 py-3 text-md ${active(pathname, l.to) ? "font-medium text-indigo" : ""}`}>
                    {active(pathname, l.to) && <span className="text-xs text-haldi" aria-hidden>❖</span>}
                    <span>{l.label}</span>
                  </NavLink>
                </li>
              ))}
            </ul>
            <div className="mt-4 flex items-center gap-3">
              <Link to="/upload" className="btn-secondary"><Icon name="upload" size={18} />Upload CSV</Link>
              {name && <span className="truncate font-display text-md italic text-indigo">{name}</span>}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}
