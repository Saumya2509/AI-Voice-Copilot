/** Every colour maps to a CSS variable in src/styles/tokens.css, so the themes swap by tokens only.
 *  Old names (bg, surface, raised, cardamom, beet) stay as aliases; maroon and gold name the heritage
 *  identity (the same tokens as indigo and haldi). */
const v = (name) => `rgb(var(--${name}) / <alpha-value>)`;

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="dark"]'],
  theme: {
    colors: {
      transparent: "transparent",
      current: "currentColor",
      plate: v("plate"),
      card: v("card"),
      ink: v("ink"),
      muted: v("muted"),
      line: v("line"),
      indigo: v("indigo"),
      "on-indigo": v("on-indigo"),
      haldi: v("haldi"),
      chilli: v("chilli"),
      leaf: v("leaf"),
      plow: v("plow"),
      plum: v("plum"),
      paper: v("paper"),
      "paper-ink": v("paper-ink"),
      slot: v("slot"),
      bg: v("plate"),
      surface: v("card"),
      raised: v("card"),
      cardamom: v("plow"),
      beet: v("plum"),
      maroon: v("indigo"),
      gold: v("haldi"),
      "gold-ink": v("gold-ink"),
    },
    fontFamily: {
      sans: ['"Mukta"', "sans-serif"],
      // Cormorant has no Devanagari; Hindi in a heading falls back to Rozha One.
      display: ['"Cormorant Garamond"', '"Rozha One"', "Georgia", "serif"],
      ticket: ['"Share Tech Mono"', '"Mukta"', "monospace"],
    },
    fontSize: {
      xs: ["0.8125rem", { lineHeight: "1.45" }],
      sm: ["0.9375rem", { lineHeight: "1.5" }],
      base: ["1.0625rem", { lineHeight: "1.55" }],
      md: ["1.1875rem", { lineHeight: "1.4" }],
      lg: ["1.5rem", { lineHeight: "1.25" }],
      xl: ["2rem", { lineHeight: "1.15" }],
      "2xl": ["2.75rem", { lineHeight: "1.08" }],
      "3xl": ["4rem", { lineHeight: "1.02" }],
      "4xl": ["5.25rem", { lineHeight: "0.98" }],
    },
    borderRadius: { none: "0", sm: "var(--r-sm)", md: "var(--r-md)", lg: "var(--r-md)", full: "999px" },
    extend: {
      spacing: { nav: "68px", tray: "72px", rail: "0px" },
      transitionTimingFunction: { out: "cubic-bezier(.2,.8,.2,1)" },
      transitionDuration: { fast: "120ms", base: "220ms", layout: "420ms" },
      boxShadow: {
        soft: "0 1px 0 rgb(var(--ink) / 0.08)",
        card: "0 1px 2px rgb(var(--ink) / 0.06), 0 10px 28px -16px rgb(var(--ink) / 0.28)",
        ticket: "0 2px 0 rgb(var(--ink) / 0.06), 0 14px 28px -16px rgb(var(--ink) / 0.45)",
      },
      maxWidth: { prose: "68ch" },
    },
  },
  plugins: [],
};
