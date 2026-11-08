import { chromium } from "playwright";
const out = process.argv[2];
const pages = (process.argv[3] ?? "/,/desk,/menu,/analytics,/combos,/orders,/recordings,/upload,/settings,/pricing").split(",");
const scheme = process.argv[4] ?? "light";
const b = await chromium.launch();
for (const path of pages) {
  const p = await b.newPage({ viewport: { width: 1440, height: 900 }, colorScheme: scheme });
  p.on("pageerror", (e) => console.log(path, "pageerror", e.message));
  await p.goto("http://localhost:5174" + path, { waitUntil: "load" });
  await p.waitForTimeout(2500);
  const name = (path === "/" ? "home" : path.slice(1).replace(/\//g, "-")) + (scheme === "dark" ? "-dark" : "");
  await p.screenshot({ path: `${out}/${name}.png` });
  await p.close();
}
await b.close();
