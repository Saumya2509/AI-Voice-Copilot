import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { utterancePairer } from "./stt";

describe("utterancePairer", () => {
  beforeEach(() => vi.useFakeTimers());
  afterEach(() => vi.useRealTimers());

  it("sends the open transcript with the menu-biased one as an alternative", () => {
    const out: [string, string[]][] = [];
    const p = utterancePairer((t, a) => out.push([t, a]));
    p.open("one dull mug honey");
    p.menu("one dal makhani");
    expect(out).toEqual([["one dull mug honey", ["one dal makhani"]]]);
  });

  it("drops an alternative that adds nothing", () => {
    const out: [string, string[]][] = [];
    const p = utterancePairer((t, a) => out.push([t, a]));
    p.menu("[unk] [unk]");
    p.open("my address is flat four");
    p.menu("two butter naan");
    p.open("two butter naan");
    expect(out).toEqual([["my address is flat four", []], ["two butter naan", []]]);
  });

  it("waits for the second recogniser, then sends what arrived", () => {
    const out: [string, string[]][] = [];
    const p = utterancePairer((t, a) => out.push([t, a]), 600);
    p.menu("one garlic naan [unk]");
    expect(out).toEqual([]);
    vi.advanceTimersByTime(600);
    expect(out).toEqual([["one garlic naan", []]]);
    p.open("");
    vi.advanceTimersByTime(600);
    expect(out).toHaveLength(1); // silence is not sent
  });
});
