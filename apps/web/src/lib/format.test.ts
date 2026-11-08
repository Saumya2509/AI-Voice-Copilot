import { describe, expect, it } from "vitest";
import { maskCallId, rupees } from "./format";

describe("format", () => {
  it("formats rupees with Indian grouping and signs", () => {
    expect(rupees(125000)).toBe("₹1,25,000");
    expect(rupees(54, { sign: true })).toBe("+₹54");
    expect(rupees(-225.13, { paise: true })).toBe("−₹225.13");
    expect(rupees(null)).toBe("—");
  });
  it("masks call ids", () => {
    expect(maskCallId("call_3f9a2b7c1d0e")).toBe("call_…d0e");
  });
});

import { moneyToNumbers } from "./api";

describe("money on the wire", () => {
  it("turns two-decimal money strings into numbers and leaves other strings alone", () => {
    expect(moneyToNumbers({ aov: "928.13", total: 999, name: "Dal Makhani", id: "ORD-12", items: [{ cm: "-2.50" }] }))
      .toEqual({ aov: 928.13, total: 999, name: "Dal Makhani", id: "ORD-12", items: [{ cm: -2.5 }] });
  });
});
