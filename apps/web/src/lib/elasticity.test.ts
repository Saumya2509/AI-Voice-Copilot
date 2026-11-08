import { describe, expect, it } from "vitest";
import { classify, predict, predictRange, priceSteps, quadrantPosition } from "./elasticity";

describe("price formula", () => {
  it("matches the hand calculation used by the server tests", () => {
    // 100 * (300/280) ** -0.6 = 95.9449 ; (300-98) * 95.9449 - (280-98) * 100 = 1180.88
    const p = predict({ monthlyUnits: 100, price: 280, foodCost: 98, elasticity: -0.6 }, 300);
    expect(p.newUnits).toBeCloseTo(95.9449, 3);
    expect(p.delta).toBeCloseTo(1180.88, 1);
  });
  it("range brackets the estimate", () => {
    const inputs = { monthlyUnits: 400, price: 190, foodCost: 88, elasticity: -0.8 };
    const [lo, hi] = predictRange(inputs, 200);
    const mid = predict(inputs, 200).delta;
    expect(lo).toBeLessThanOrEqual(mid);
    expect(hi).toBeGreaterThanOrEqual(mid);
  });
  it("slider steps stay within 10 percent in ₹5 steps", () => {
    const steps = priceSteps(280);
    expect(steps[0]).toBe(255);
    expect(steps[steps.length - 1]).toBe(305);
    expect(steps).toContain(280);
    expect(steps.every((s) => s % 5 === 0)).toBe(true);
  });
});

describe("quadrant position", () => {
  const cat = [
    { item_id: 1, units: 50, cm: 100 }, { item_id: 2, units: 30, cm: 60 },
    { item_id: 3, units: 15, cm: 120 }, { item_id: 4, units: 5, cm: 40 },
  ];
  it("puts the category thresholds at 1", () => {
    // popular line 0.7 / 4 = 0.175 ; weighted avg cm = 88
    const a = quadrantPosition(cat[0], cat);
    expect(a.x).toBeCloseTo(0.5 / 0.175, 5);
    expect(a.y).toBeCloseTo(100 / 88, 5);
    expect(cat.map((c) => { const p = quadrantPosition(c, cat); return classify(p.x, p.y); }))
      .toEqual(["star", "plowhorse", "puzzle", "dog"]);
  });
});
