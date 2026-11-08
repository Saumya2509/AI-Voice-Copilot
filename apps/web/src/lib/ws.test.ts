import { describe, expect, it } from "vitest";
import type { ServerEvent } from "./types";
import { mergeEvents } from "./ws";

const ev = (seq: number): ServerEvent => ({ type: "pos.sent", order_id: "ORD-1", seq, ts: "2026-10-11T10:00:00Z" });

describe("event ordering", () => {
  it("ignores events with an older seq and keeps order", () => {
    const merged = mergeEvents([ev(1), ev(2)], [ev(2), ev(4), ev(3), ev(1)]);
    expect(merged.map((e) => e.seq)).toEqual([1, 2, 3, 4]);
  });
});
