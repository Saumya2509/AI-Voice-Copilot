// UI acceptance checks from improve.md, section 11. Needs the API on :8000 and the web app on :5173, with the
// API on the sample database (TADKA_DB=data/seed/tadka.sqlite), because the checks place an order.
// Run: npm run test:ui
import { chromium } from "playwright";
import { readdir, readFile } from "node:fs/promises";

const BASE = process.env.TADKA_WEB ?? "http://localhost:5173";
const results = [];
const check = (name, ok, detail = "") => results.push({ name, ok, detail });

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 } });
const p = await ctx.newPage();

// 1. Combos has no chart, graph or node element.
await p.goto(BASE + "/combos");
await p.waitForLoadState("load").then(() => p.waitForTimeout(900));
await p.waitForTimeout(800);
const visuals = await p.evaluate(() => {
  const main = document.querySelector("main");
  return {
    canvas: main.querySelectorAll("canvas").length,
    svg: [...main.querySelectorAll("svg")].filter((s) => s.getBoundingClientRect().width > 32).length,
    charts: main.querySelectorAll(".recharts-wrapper, [role=img][aria-label*=chart]").length,
    circles: main.querySelectorAll("svg circle, svg line").length,
    rows: main.querySelectorAll("li").length,
  };
});
check("Combos page has no chart, graph or node element", !visuals.canvas && !visuals.svg && !visuals.charts && !visuals.circles,
  JSON.stringify(visuals));
check("Combos page lists combos as text", visuals.rows > 0, `${visuals.rows} entries`);

// 2. A new order from a call appears in Orders within 2 seconds, without a refresh.
await p.goto(BASE + "/orders");
await p.waitForLoadState("load").then(() => p.waitForTimeout(900));
await p.waitForTimeout(1000);
const before = await p.locator("tbody tr").first().innerText();
const item = (await (await fetch(`${BASE}/api/v1/menu`)).json()).items[0].id;
const t0 = Date.now();
const created = await (await fetch(`${BASE}/api/v1/orders`, {
  method: "POST", headers: { "content-type": "application/json" },
  body: JSON.stringify({ call_id: `ui_check_${t0}`, lines: [{ item_id: item, qty: 1 }] }),
})).json();
const id = created.order.order_id;
const posted = Date.now() - t0;
let seenAt = null;
while (Date.now() - t0 < 8000) {
  if ((await p.locator("tbody tr").first().innerText()).includes(id)) { seenAt = Date.now() - t0; break; }
  await p.waitForTimeout(50);
}
check("New order appears in Orders within 2 seconds", seenAt !== null && seenAt <= 2000,
  seenAt === null ? "not seen" : `${seenAt} ms after the order was placed (the order request took ${posted} ms)`);
check("Orders list changed without a refresh", before !== (await p.locator("tbody tr").first().innerText()));

// 3. Navbar: keyboard and collapse under 900 px.
await p.goto(BASE + "/analytics");
await p.waitForLoadState("load").then(() => p.waitForTimeout(900));
await p.getByRole("link", { name: "Call desk" }).first().focus();
await p.keyboard.press("ArrowRight");
const focused = await p.evaluate(() => document.activeElement?.textContent);
check("Arrow keys move across navbar links", focused === "Menu", `focused: ${focused}`);
await p.getByRole("button", { name: "More" }).click();
await p.keyboard.press("Escape");
check("Escape closes the More menu", (await p.getByRole("menu").count()) === 0);
await p.setViewportSize({ width: 860, height: 900 });
await p.waitForTimeout(300);
const burger = p.getByRole("button", { name: "Open menu" });
check("Navbar collapses under 900 px with Call desk visible",
  (await burger.count()) === 1 && (await p.getByRole("link", { name: "Call desk" }).count()) >= 1);
await burger.click();
check("Collapsed navbar opens a drawer with every link", (await p.locator("#nav-drawer a").count()) >= 8);

// 4. No sidebar remains in the code.
const files = [];
async function walk(dir) {
  for (const e of await readdir(dir, { withFileTypes: true })) {
    const full = `${dir}/${e.name}`;
    if (e.isDirectory()) await walk(full);
    else if (/\.(tsx?|css)$/.test(e.name)) files.push(full);
  }
}
await walk(new URL("../src", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
let sidebar = [];
for (const f of files) {
  const text = await readFile(f, "utf8");
  if (/\bRail\b|sidebar|w-rail|rail-open/i.test(text)) sidebar.push(f.split("/src/")[1]);
}
check("No sidebar code remains", sidebar.length === 0, sidebar.join(", "));

// 5. Landing page shows no invented figures when there is no data: it uses the live API only.
await p.setViewportSize({ width: 1440, height: 900 });
await p.goto(BASE + "/");
await p.waitForLoadState("load").then(() => p.waitForTimeout(900));
const landing = await p.evaluate(() => document.body.innerText);
check("Landing page has no testimonials or logos", !/testimonial|trusted by|customers love|as seen on/i.test(landing));

await browser.close();
let failed = 0;
for (const r of results) {
  if (!r.ok) failed++;
  console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.detail ? `  (${r.detail})` : ""}`);
}
console.log(`${results.length - failed} of ${results.length} checks passed`);
process.exit(failed ? 1 : 0);
