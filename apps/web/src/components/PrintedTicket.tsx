// A KOT as printed, rendered from the PoS's KOT record.
import { useCatalog } from "@/lib/catalog";
import { CHANNEL_LABEL, rupees, time } from "@/lib/format";
import type { Kot } from "@/lib/types";

export function PrintedTicket({ kot }: { kot: Kot }) {
  const name = useCatalog((s) => s.restaurantName);
  return (
    <article aria-label={`Ticket ${kot.kot_no}`} className="ticket ticket-torn bg-paper px-5 pb-6 pt-5 font-ticket text-[13px] leading-[1.55] text-paper-ink shadow-ticket">
      <header className="border-b border-dashed border-paper-ink/40 pb-3">
        <p className="text-[15px] uppercase tracking-wide">{name || "Kitchen order ticket"}</p>
        <div className="mt-1 flex justify-between"><span>KOT {kot.kot_no}</span><span>{time(kot.created_at)}</span></div>
        <div className="flex justify-between"><span>{CHANNEL_LABEL[kot.channel]} order</span><span>{kot.order_id}</span></div>
        {(kot.customer.name || kot.customer.phone) && (
          <p>{[kot.customer.name, kot.customer.phone].filter(Boolean).join("  ")}</p>
        )}
      </header>
      {kot.stations.map((st) => (
        <section key={st} className="pt-2">
          <p className="text-paper-ink/60">-- {st.charAt(0).toUpperCase() + st.slice(1)} --</p>
          {kot.lines.filter((l) => l.station === st).map((l, i) => (
            <div key={i}>
              <p>{l.qty} x {l.item}</p>
              {l.mods.map((m) => <p key={m} className="pl-5 text-paper-ink/75">{m}</p>)}
              {l.note && <p className="pl-5 text-paper-ink/75">NOTE: {l.note}</p>}
            </div>
          ))}
        </section>
      ))}
      <div className="mt-3 flex justify-between border-t border-dashed border-paper-ink/40 pt-2 text-[16px]">
        <span>TOTAL</span><span>{rupees(kot.total)}</span>
      </div>
    </article>
  );
}
