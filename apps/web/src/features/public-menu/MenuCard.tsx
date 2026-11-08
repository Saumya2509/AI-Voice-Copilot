// The restaurant menu set like a printed menu card: category headings in Rozha One under a double rule,
// items as name, dotted leader, price; veg mark; spice as small chilli marks; a 4:3 photo beside each dish
// that has one (the built-in dishes all do; see seed/photos.py).
import { Icon } from "@/components/Icon";
import { rupees } from "@/lib/format";
import type { PublicMenu } from "@/lib/types";
import { VegMark } from "../call-desk/MenuPanel";

export type MenuCategory = PublicMenu["categories"][number];

export function MenuCategoryBlock({ category, anchor = true }: { category: MenuCategory; anchor?: boolean }) {
  return (
    <section id={anchor ? `cat-${category.id}` : undefined} className="mb-10 break-inside-avoid scroll-mt-[140px]">
      <h2 className="double-rule pt-3 font-display text-xl">{category.name}</h2>
      <ul className="mt-3">
        {category.items.map((i) => (
          <li key={i.id} className={`flex gap-3 py-2.5 sm:gap-4 ${i.available ? "" : "opacity-50"}`}>
            {i.image_url && (
              <img src={i.image_url} alt="" loading="lazy" decoding="async" width={96} height={72}
                className="h-[54px] w-[72px] shrink-0 rounded-sm bg-ink/5 object-cover sm:h-[72px] sm:w-24" />
            )}
            <div className="min-w-0 flex-1">
              <div className="flex items-baseline gap-2">
                <span className="translate-y-[2px]"><VegMark veg={i.veg} /></span>
                <span className="text-md">{i.name}</span>
                {i.spice_level > 0 && (
                  <span className="flex text-chilli" aria-label={`Spice level ${i.spice_level} of 3`}>
                    {Array.from({ length: i.spice_level }).map((_, k) => <Icon key={k} name="chilli" size={13} />)}
                  </span>
                )}
                <span className="leader" aria-hidden />
                <span className="num text-md">{rupees(i.price)}</span>
              </div>
              {i.description && <p className="ml-6 mt-0.5 text-sm leading-snug text-muted">{i.description}</p>}
              {!i.available && <p className="ml-6 text-sm text-muted">Not available today</p>}
            </div>
          </li>
        ))}
      </ul>
    </section>
  );
}
