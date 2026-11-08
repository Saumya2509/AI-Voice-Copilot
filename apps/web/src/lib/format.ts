// Formatting for money, counts and times. Money is shown in rupees with Indian digit grouping.
const inr = new Intl.NumberFormat("en-IN", { maximumFractionDigits: 0 });
const inr2 = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const count = new Intl.NumberFormat("en-IN");

export const RESTAURANT_TZ = "Asia/Kolkata";

export function rupees(n: number | null | undefined, opts: { paise?: boolean; sign?: boolean } = {}): string {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  const abs = Math.abs(n);
  const body = opts.paise && !Number.isInteger(n) ? inr2.format(abs) : inr.format(Math.round(abs));
  const sign = n < 0 ? "−" : opts.sign && n > 0 ? "+" : "";
  return `${sign}₹${body}`;
}

export const num = (n: number | null | undefined) => (n === null || n === undefined ? "—" : count.format(n));
export const pct = (x: number, digits = 0) => `${(x * 100).toFixed(digits)}%`;

export function time(iso: string | null | undefined, withDate = false): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-IN", {
    timeZone: RESTAURANT_TZ,
    hour: "2-digit",
    minute: "2-digit",
    ...(withDate ? { day: "numeric", month: "short" } : {}),
  });
}

export function duration(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000));
  return `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;
}

export const CLASS_LABEL = { star: "Star", plowhorse: "Plowhorse", puzzle: "Puzzle", dog: "Dog" } as const;
export const CLASS_PLURAL = { star: "Stars", plowhorse: "Plowhorses", puzzle: "Puzzles", dog: "Dogs" } as const;
export const CLASS_COLOR = { star: "leaf", plowhorse: "plow", puzzle: "plum", dog: "chilli" } as const;

export const CATEGORY_LABEL: Record<string, string> = {
  starter: "Starters", main: "Mains", bread: "Breads", rice: "Rice and noodles", side: "Sides",
  dessert: "Desserts", beverage: "Drinks",
};

export const CHANNEL_LABEL: Record<string, string> = { dine_in: "Dine-in", phone: "Phone", takeaway: "Takeaway" };

export const LANGUAGE_LABEL: Record<string, string> = { en: "English", hi: "Hindi", hinglish: "Hinglish", auto: "Auto" };

export function maskCallId(id: string): string {
  return id.length > 8 ? `${id.slice(0, 5)}…${id.slice(-3)}` : id;
}
