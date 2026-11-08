// Client-side copy of the pricing formula from file 04, so the what-if slider responds instantly.
// The server preview is called on release to confirm (they must agree within ₹1).
//
// new_units = units * (new_price / price) ** elasticity
// profit    = (price - food_cost) * units

export interface PriceInputs {
  monthlyUnits: number;
  price: number;
  foodCost: number;
  elasticity: number;
}

export function predict({ monthlyUnits, price, foodCost, elasticity }: PriceInputs, newPrice: number) {
  const newUnits = monthlyUnits * Math.pow(newPrice / price, elasticity);
  const oldProfit = (price - foodCost) * monthlyUnits;
  const newProfit = (newPrice - foodCost) * newUnits;
  return { newUnits, oldProfit, newProfit, delta: newProfit - oldProfit };
}

export function predictRange(inputs: PriceInputs, newPrice: number, band = 0.3): [number, number] {
  const a = predict({ ...inputs, elasticity: inputs.elasticity - band }, newPrice).delta;
  const b = predict({ ...inputs, elasticity: inputs.elasticity + band }, newPrice).delta;
  return [Math.min(a, b), Math.max(a, b)];
}

/** Slider steps: ±10 percent of the current price in ₹5 steps. */
export function priceSteps(price: number): number[] {
  const lo = Math.ceil((price * 0.9) / 5) * 5;
  const hi = Math.floor((price * 1.1) / 5) * 5;
  const out: number[] = [];
  for (let p = lo; p <= hi; p += 5) out.push(p);
  if (!out.includes(price)) out.push(price);
  return out.sort((a, b) => a - b);
}

/** Popularity and margin of an item relative to its category's thresholds (file 04, section 2).
 *  x >= 1 means popular, y >= 1 means high margin, so the quadrant lines sit at 1 for every category. */
export function quadrantPosition(
  item: { item_id: number; units: number; cm: number },
  category: { item_id: number; units: number; cm: number }[],
  popularityFactor = 0.7,
) {
  const total = category.reduce((s, i) => s + i.units, 0);
  const n = category.length;
  const share = total > 0 ? item.units / total : 0;
  const avgCm = total > 0 ? category.reduce((s, i) => s + i.cm * i.units, 0) / total : 0;
  return {
    x: share / (popularityFactor / n),
    y: avgCm > 0 ? item.cm / avgCm : 1,
  };
}

export function classify(x: number, y: number): "star" | "plowhorse" | "puzzle" | "dog" {
  if (x >= 1) return y >= 1 ? "star" : "plowhorse";
  return y >= 1 ? "puzzle" : "dog";
}
