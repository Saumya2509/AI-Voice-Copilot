// Clarification buttons and the offer card. Both also answer by voice ("pehla wala", "haan", "nahi").
import { AnimatePresence, motion } from "motion/react";
import { rupees } from "@/lib/format";
import { DUR, EASE } from "@/lib/motion";
import { useCall } from "./useCall";

export function ClarifyChips() {
  const clarify = useCall((s) => s.clarify);
  const choose = useCall((s) => s.choose);
  return (
    <AnimatePresence>
      {clarify && (
        <motion.div id="clarify-chips" initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }}
          transition={{ duration: DUR.base, ease: EASE }} className="flex flex-col gap-2">
          <p className="text-sm text-muted">{clarify.question}</p>
          <div className="flex flex-wrap gap-2">
            {clarify.options.map((o, i) => (
              <button key={String(o.id)} onClick={() => choose(o.id)} className="btn-secondary h-12 px-5 text-base">
                <span className="num text-sm text-muted">{i + 1}</span>
                {o.label}
              </button>
            ))}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

/** The offer card carries a price-tag corner, a mark taken from the shop floor. */
export function OfferCard() {
  const offer = useCall((s) => s.offer);
  const answer = useCall((s) => s.answerOffer);
  return (
    <AnimatePresence>
      {offer && (
        <motion.section key={offer.offer_id} role="status" aria-label={`Offer: ${offer.reason.headline}`}
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: 6 }}
          transition={{ duration: DUR.base, ease: EASE }} className="panel relative overflow-hidden">
          <div className="absolute right-0 top-0 flex h-12 items-center bg-haldi pl-5 pr-4 text-ink"
            style={{ clipPath: "polygon(14px 0, 100% 0, 100% 100%, 14px 100%, 0 50%)" }}>
            <span className="num text-lg font-medium">{rupees(offer.item.price)}</span>
          </div>
          <div className="flex flex-col gap-3 p-5 pr-28">
            <div>
              <p className="text-sm text-muted">{offer.kind === "combo" ? "Combo offer" : "Offer this next"}</p>
              <h3 className="font-display text-xl">{offer.reason.headline}</h3>
            </div>
            <ul className="flex flex-col gap-1 text-sm">
              {offer.reason.why.map((w) => (
                <li key={w} className="flex gap-2"><span className="mt-[0.55em] h-1 w-1 shrink-0 rounded-full bg-ink/50" aria-hidden />{w}</li>
              ))}
            </ul>
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <button className="btn-primary" onClick={() => answer(true)}>Add to ticket</button>
              <button className="btn-quiet" onClick={() => answer(false)}>Skip</button>
              <span className="num ml-auto text-sm text-muted">{rupees(offer.reason.expected_gain, { sign: true })} margin</span>
            </div>
          </div>
        </motion.section>
      )}
    </AnimatePresence>
  );
}
