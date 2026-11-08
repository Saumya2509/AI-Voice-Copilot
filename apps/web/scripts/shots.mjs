// Screenshots for the critique pass: every screen in light and dark, at 1440 and 390 px. Also captures
// the three crops of the real UI used on the landing page (public/landing/step-*.png).
// Needs the API on :8000 and the web app on :5173. Run the API on the sample database, not the restaurant's
// own (TADKA_DB=data/seed/tadka.sqlite), because the script places orders. Output: apps/web/shots/.
import { chromium } from "playwright";
import { mkdir } from "node:fs/promises";

const BASE = process.env.TADKA_WEB ?? "http://localhost:5173";
const fsPath = (u) => new URL(u, import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const OUT = fsPath("../shots/");
const CROPS = fsPath("../public/landing/");
const SIZES = { desktop: { width: 1440, height: 900 }, mobile: { width: 390, height: 844 } };
const SCREENS = [
  ["landing", "/"],
  ["menu", "/menu"],
  ["analytics", "/analytics"],
  ["upload", "/upload"],
  ["combos", "/combos"],
  ["orders", "/orders"],
  ["recordings", "/recordings"],
  ["pricing", "/pricing"],
  ["settings", "/settings"],
];

await mkdir(OUT, { recursive: true });
await mkdir(CROPS, { recursive: true });
const browser = await chromium.launch();
const problems = [];

async function page(theme, size) {
  const ctx = await browser.newContext({ viewport: SIZES[size], deviceScaleFactor: 1, colorScheme: theme });
  await ctx.addInitScript((t) => localStorage.setItem("tadka.theme", t), theme);
  const p = await ctx.newPage();
  p.on("pageerror", (e) => problems.push(`${theme}/${size}: ${e.message}`));
  return { ctx, p };
}

async function noHorizontalScroll(p, name) {
  const over = await p.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  if (over > 1) problems.push(`${name}: horizontal scroll of ${over}px`);
}

// 1. A full sample call on the call desk.
for (const theme of ["light", "dark"]) {
  for (const size of ["desktop", "mobile"]) {
    const { ctx, p } = await page(theme, size);
    await p.goto(BASE + "/desk");
    await p.waitForLoadState("load").then(() => p.waitForTimeout(900));
    await p.screenshot({ path: `${OUT}desk-idle-${theme}-${size}.png` });
    await noHorizontalScroll(p, `desk ${theme} ${size}`);
    await p.getByRole("button", { name: /Mute replies/ }).click();
    await p.getByRole("radio", { name: "Typed" }).click();
    await p.getByRole("button", { name: /Start call/ }).click();
    // Type the lines of the first scripted call, waiting for each reply.
    const sample = (await (await fetch(`${BASE}/api/v1/samples`)).json()).samples[0];
    for (const u of sample.utterances.slice(1)) {
      const replies = await p.locator('[aria-label="Transcript"] li').count();
      await p.locator("#typed").fill(u.text);
      await p.keyboard.press("Enter");
      await p.waitForFunction((n) => document.querySelectorAll('[aria-label="Transcript"] li').length >= n + 2, replies, { timeout: 15000 }).catch(() => {});
      if (await p.locator('section[aria-label^="Offer:"]').count()) break;
    }
    await p.waitForSelector("text=/Offer this next|Combo offer/", { timeout: 60000 });
    await p.waitForTimeout(700);
    await p.screenshot({ path: `${OUT}desk-offer-${theme}-${size}.png` });
    if (theme === "light" && size === "desktop") {
      await p.locator('[aria-label="Transcript"]').screenshot({ path: `${CROPS}step-1.png` });
      await p.locator('section[aria-label^="Offer:"]').screenshot({ path: `${CROPS}step-2.png` });
    }
    for (const u of sample.utterances.slice(5)) {
      if (!(await p.locator("#typed").count())) break;
      await p.locator("#typed").fill(u.text);
      await p.keyboard.press("Enter");
      await p.waitForTimeout(1200);
    }
    await p.waitForSelector("text=/Call ended/", { timeout: 90000 });
    await p.waitForTimeout(1500);
    await p.screenshot({ path: `${OUT}desk-done-${theme}-${size}.png` });
    await ctx.close();
  }
}

// 2. Every other screen.
for (const theme of ["light", "dark"]) {
  for (const size of Object.keys(SIZES)) {
    const { ctx, p } = await page(theme, size);
    for (const [name, path] of SCREENS) {
      await p.goto(BASE + path);
      await p.waitForLoadState("load").then(() => p.waitForTimeout(900));
      await p.waitForTimeout(1500);
      await p.screenshot({ path: `${OUT}${name}-${theme}-${size}.png`, fullPage: size === "desktop" });
      await noHorizontalScroll(p, `${name} ${theme} ${size}`);
    }
    // Analytics with a cross filter and the item panel.
    await p.goto(BASE + "/analytics");
    await p.waitForLoadState("load").then(() => p.waitForTimeout(900));
    await p.waitForTimeout(1200);
    await p.getByRole("button", { name: /^Mains/ }).first().click();
    await p.waitForTimeout(1200);
    await p.screenshot({ path: `${OUT}analytics-filtered-${theme}-${size}.png`, fullPage: size === "desktop" });
    // Orders with the newest Tadka order open in the drawer.
    await p.goto(BASE + "/orders");
    await p.waitForLoadState("load").then(() => p.waitForTimeout(900));
    await p.locator("select").nth(1).selectOption("acked").catch(() => {});
    await p.waitForTimeout(800);
    const first = p.locator("tbody tr").first();
    if (await first.count()) {
      await first.click();
      await p.waitForTimeout(900);
      await p.screenshot({ path: `${OUT}order-drawer-${theme}-${size}.png` });
      if (theme === "light" && size === "desktop") {
        await p.locator('[role="dialog"]').screenshot({ path: `${CROPS}step-3.png` });
      }
    }
    // A recording.
    await p.goto(BASE + "/recordings");
    await p.waitForLoadState("load").then(() => p.waitForTimeout(900));
    const call = p.locator("tbody tr").first();
    if (await call.count()) {
      await call.click();
      await p.waitForTimeout(900);
      await p.screenshot({ path: `${OUT}recording-${theme}-${size}.png`, fullPage: size === "desktop" });
    }
    await ctx.close();
  }
}

await browser.close();
console.log(problems.length ? `Problems:\n${problems.join("\n")}` : "No page errors or horizontal scroll found.");
console.log(`Screenshots in ${OUT}`);
