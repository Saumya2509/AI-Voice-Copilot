// Landing page. A maroon hero framed in gold like the cover of a grand menu, then sections with different
// rhythms: a numbered sequence (Roman numerals), the live menu, two real charts, and a short list. The only
// motion is the ticket printing in the hero, once. No scroll-triggered animation, no invented figures.
import { motion } from "motion/react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";
import { useCatalog } from "@/lib/catalog";
import { num, rupees } from "@/lib/format";
import { useLive } from "@/lib/live";
import { EASE, useMotionPref } from "@/lib/motion";
import { useApi } from "@/lib/useApi";
import { colorAt, Donut, Heatmap } from "../analytics/charts";
import { MenuCategoryBlock } from "../public-menu/MenuCard";

const EXAMPLES = ["mujhe do dal makhani chahiye medium spicy", "एक पनीर टिक्का और दो लस्सी", "nahi wo hata do"];

export default function Landing() {
  return (
    <div>
      <Hero />
      <HowACallGoes />
      <MenuPreview />
      <OwnerSection />
      <Languages />
      <footer className="heritage-band border-t-4 border-double border-[#C9A04F]">
        <div className="mx-auto flex max-w-6xl flex-wrap items-baseline gap-x-8 gap-y-2 px-4 py-10 text-sm sm:px-6">
          <span className="flex items-baseline gap-2"><span className="text-[#C9A04F]" aria-hidden>❖</span><span className="font-display text-2xl font-bold">Tadka</span></span>
          <Link to="/desk" className="underline-offset-4 hover:text-[#E5C77F] hover:underline">Call desk</Link>
          <Link to="/menu" className="underline-offset-4 hover:text-[#E5C77F] hover:underline">Menu</Link>
          <Link to="/analytics" className="underline-offset-4 hover:text-[#E5C77F] hover:underline">Analytics</Link>
          <Link to="/upload" className="underline-offset-4 hover:text-[#E5C77F] hover:underline">Upload CSV</Link>
          <span className="font-display text-md italic text-[#E5C77F] sm:ml-auto">Runs on your own computer. No audio leaves the device.</span>
        </div>
      </footer>
    </div>
  );
}

function Hero() {
  return (
    <section className="heritage-band relative overflow-hidden border-b-4 border-double border-[#C9A04F]">
      {/* An inset gold frame with corner ornaments, like the cover of a grand menu. */}
      <div className="pointer-events-none absolute inset-3 border border-[#C9A04F]/45 sm:inset-5" aria-hidden>
        {["-left-[7px] -top-[9px]", "-right-[7px] -top-[9px]", "-bottom-[9px] -left-[7px]", "-bottom-[9px] -right-[7px]"].map((pos) => (
          <span key={pos} className={`absolute ${pos} text-[13px] leading-none text-[#C9A04F]`}>❖</span>
        ))}
      </div>
      <div className="relative mx-auto grid max-w-6xl gap-10 px-6 py-16 sm:px-10 md:grid-cols-[2fr_1fr] md:py-24">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-[0.28em] text-[#C9A04F]">The restaurant’s phone, answered</p>
          <h1 className="mt-5 font-display text-[46px] leading-[0.98] sm:text-3xl lg:text-4xl">
            Take the order.<br /><em className="font-medium text-[#E5C77F]">Sell the extra naan.</em>
          </h1>
          <div className="my-7 flex max-w-[22rem] items-center gap-3 text-[#C9A04F]" aria-hidden>
            <span className="h-px flex-1 bg-[#C9A04F]/60" /><span className="text-xs">❖</span><span className="h-px flex-1 bg-[#C9A04F]/60" />
          </div>
          <p className="max-w-[34rem] text-md text-[#F3E9D6]/90">
            Tadka answers the phone in Hindi, English or Hinglish, prints the ticket as the caller speaks, and offers the dish
            your own sales say goes with it.
          </p>
          <div className="mt-9 flex flex-wrap gap-3">
            <Link to="/desk" className="btn h-12 bg-[#C9A04F] px-7 text-base text-[#3B0D14] shadow-[inset_0_0_0_1px_rgb(255_255_255/0.25)] hover:bg-[#D9B26A]">
              Open the call desk
            </Link>
            <Link to="/menu" className="btn h-12 border border-[#C9A04F]/80 px-7 text-base text-[#F7F1E3] hover:bg-[#C9A04F]/10">See the menu</Link>
          </div>
        </div>
        <HeroTicket />
      </div>
    </section>
  );
}

/** A ticket that prints a short order from the real menu once on load. */
function HeroTicket() {
  const menu = useCatalog((s) => s.menu);
  const name = useCatalog((s) => s.restaurantName);
  const { reduced } = useMotionPref();
  const items = Object.values(menu);
  const picks = [items.find((i) => i.category === "main"), items.find((i) => i.category === "bread"), items.find((i) => i.category === "beverage")]
    .filter(Boolean)
    .map((i, k) => ({ item: i!, qty: k === 1 ? 2 : 1 }));
  const lines = picks.length ? picks : items.slice(0, 3).map((item) => ({ item, qty: 1 }));
  const total = lines.reduce((s, l) => s + l.qty * Number(l.item.price), 0);
  return (
    <div className="relative hidden md:block">
      <motion.div
        initial={reduced ? { opacity: 0 } : { y: -40, clipPath: "inset(0 0 100% 0)" }}
        animate={reduced ? { opacity: 1 } : { y: 0, clipPath: "inset(0 0 0% 0)" }}
        transition={{ duration: 0.9, ease: EASE, delay: 0.2 }}
        className="ticket-torn absolute -right-4 top-2 w-[300px] rotate-[3deg] bg-paper px-6 pb-8 pt-5 font-ticket text-[13px] leading-[1.6] text-paper-ink shadow-ticket"
        aria-label="Example ticket"
      >
        <p className="text-[15px]">{name || "Kitchen order ticket"}</p>
        <p className="border-b border-dashed border-paper-ink/40 pb-2">Phone order · example</p>
        {lines.length ? (
          <>
            <ul className="py-2">
              {lines.map((l, i) => (
                <motion.li key={l.item.id} className="flex justify-between gap-2" initial={reduced ? false : { opacity: 0 }}
                  animate={{ opacity: 1 }} transition={{ delay: 1.1 + i * 0.35 }}>
                  <span className="truncate">{l.qty} x {l.item.name}</span><span>{rupees(Number(l.item.price) * l.qty)}</span>
                </motion.li>
              ))}
            </ul>
            <p className="flex justify-between border-t border-dashed border-paper-ink/40 pt-2 text-[15px]"><span>TOTAL</span><span>{rupees(total)}</span></p>
          </>
        ) : (
          <p className="py-4 text-paper-ink/70">Your menu prints here once it is uploaded.</p>
        )}
      </motion.div>
      <span className="absolute -left-4 top-[236px] rotate-[-8deg] border border-[#C9A04F] bg-[#3B0D14] px-3 py-1.5 font-display text-md italic text-[#E5C77F] shadow-ticket">
        Hindi, English, Hinglish
      </span>
    </div>
  );
}

function HowACallGoes() {
  const steps = [
    { title: "The caller speaks.", text: "In Hindi, English or a mix. The transcript appears in English, and each dish the caller names lights up on the menu.", img: "/landing/step-1.png" },
    { title: "The ticket prints, with the reason for each offer.", text: "Garlic naan with the dal, because your sales show they go together. Two offers at most, never while the caller is still choosing.", img: "/landing/step-2.png" },
    { title: "The kitchen gets the KOT.", text: "The order goes to the PoS with a KOT number, grouped by station: tandoor, curry, cold.", img: "/landing/step-3.png" },
  ];
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <p className="eyebrow">The call</p>
      <h2 className="title-rule mt-2 font-display text-2xl">How a call goes</h2>
      <ol className="flex flex-col gap-10">
        {steps.map((s, i) => (
          <li key={s.title} className="grid items-start gap-6 md:grid-cols-[3fr_4fr]">
            <div className="flex gap-4">
              <span className="w-12 shrink-0 text-right font-display text-3xl italic leading-none text-gold-ink">{["I", "II", "III"][i]}</span>
              <div>
                <h3 className="font-display text-xl">{s.title}</h3>
                <p className="mt-2 max-w-prose text-base text-muted">{s.text}</p>
              </div>
            </div>
            <Crop src={s.img} alt={`The ${["call desk transcript", "ticket tray", "order record"][i]} in Tadka`} />
          </li>
        ))}
      </ol>
    </section>
  );
}

/** A crop of the real UI, taken by the screenshot script. Hidden if it has not been captured yet. */
function Crop({ src, alt }: { src: string; alt: string }) {
  const [ok, setOk] = useState(true);
  if (!ok) return <div className="hidden md:block" />;
  // Framed like a picture: cream mat, gold hairline, soft shadow.
  return (
    <div className="border border-haldi/50 bg-card p-2 shadow-card">
      <img src={src} alt={alt} loading="lazy" onError={() => setOk(false)} className="w-full border border-haldi/25" />
    </div>
  );
}

function MenuPreview() {
  const dataVersion = useLive((s) => s.dataVersion);
  const menu = useApi(() => api.publicMenu(), [dataVersion]);
  const cats = menu.data?.categories ?? [];
  return (
    <section className="border-y border-haldi/60 bg-card">
      <div className="mx-auto grid max-w-6xl gap-10 px-4 py-16 sm:px-6 md:grid-cols-[1fr_2fr]">
        <div>
          <p className="eyebrow">À la carte</p>
          <h2 className="mt-2 font-display text-2xl">The menu</h2>
          <p className="mt-3 text-base text-muted">The same menu the call desk reads from. Change a price in the PoS or upload a new file, and it changes here.</p>
          {cats.length > 0 && <Link to="/menu" className="btn-primary mt-6">See the full menu</Link>}
        </div>
        <div>
          {cats.length ? (
            <div className="gap-10 sm:columns-2">
              {cats.slice(0, 2).map((c) => <MenuCategoryBlock key={c.id} anchor={false} category={{ ...c, items: c.items.slice(0, 6) }} />)}
            </div>
          ) : (
            <p className="text-base">No menu yet. <Link to="/upload" className="text-indigo underline underline-offset-4">Upload a menu or sales CSV</Link>.</p>
          )}
        </div>
      </div>
    </section>
  );
}

function OwnerSection() {
  const dataVersion = useLive((s) => s.dataVersion);
  const ov = useApi(() => api.analytics.overview({}), [dataVersion]);
  const cats = useApi(() => api.analytics.categoryShare({}), [dataVersion]);
  const heat = useApi(() => api.analytics.heatmap({}), [dataVersion]);
  const has = Boolean(ov.data?.orders);
  return (
    <section className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
      <p className="eyebrow">The owner</p>
      <h2 className="title-rule mt-2 font-display text-2xl">What the owner sees</h2>
      {!has ? (
        <div className="max-w-prose">
          <p className="text-base">Upload your sales from the PoS and this section shows where your money comes from and when the kitchen is busiest.</p>
          <Link to="/upload" className="btn-primary mt-5">Upload CSV</Link>
        </div>
      ) : (
        <div className="grid gap-12 md:grid-cols-[5fr_7fr]">
          <div>
            <p className="mb-4 text-base">Revenue by category over {num(ov.data!.sample_size)} orders.</p>
            <Donut center={rupees(ov.data!.revenue)} centerLabel="total"
              slices={(cats.data?.categories ?? []).map((c, i) => ({ key: c.category, label: c.category, value: Number(c.revenue), color: colorAt(i) }))} />
          </div>
          <div>
            <p className="mb-4 text-base">Busy hours, so you staff the phone when it rings.</p>
            {heat.data && <Heatmap cells={heat.data.cells.map((c) => ({ ...c, revenue: Number(c.revenue) }))} weekdays={heat.data.weekdays} max={heat.data.max_orders} />}
            <Link to="/analytics" className="mt-6 inline-block text-indigo underline underline-offset-4">Open Analytics</Link>
          </div>
        </div>
      )}
    </section>
  );
}

function Languages() {
  const [meanings, setMeanings] = useState<string[]>([]);
  useEffect(() => {
    // The English meaning comes from Tadka's own gloss, not from this page.
    Promise.all(EXAMPLES.map((t) => api.parse(t).then((r) => r.display_text_en).catch(() => ""))).then(setMeanings);
  }, []);
  return (
    <section className="border-t border-haldi/60 bg-card">
      <div className="mx-auto max-w-6xl px-4 py-16 sm:px-6">
        <p className="eyebrow">Languages</p>
        <h2 className="mt-2 font-display text-2xl">What it understands</h2>
        <p className="mt-3 max-w-prose text-base text-muted">
          Hindi in Devanagari or Roman letters, English, and the mix most callers actually speak. Marathi and Gujarati can be added as
          language packs. Ordering language is what it knows best.
        </p>
        <ul className="mt-8 divide-y divide-haldi/30 border-y border-haldi/50">
          {EXAMPLES.map((e, i) => (
            <li key={e} className="grid gap-2 py-5 md:grid-cols-2">
              <span className="font-display text-xl italic text-indigo" lang={/[ऀ-ॿ]/.test(e) ? "hi" : "en"}>“{e}”</span>
              <span className="text-md text-muted">{meanings[i] ? meanings[i] : ""}</span>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
