import { describe, expect, it } from "vitest";
import { isBargeIn, isEcho } from "./bargein";

const spoken = "Added 2 Butter Naan. Anything else? 2 Butter Naan जोड़ दिया। और कुछ?";

describe("barge-in", () => {
  it("treats the agent's own words coming back as echo", () => {
    expect(isEcho("butter naan anything else", spoken)).toBe(true);
    expect(isEcho("जोड़ दिया और कुछ", spoken)).toBe(true);
    expect(isEcho("[unk] [unk]", spoken)).toBe(true);
  });

  it("hears the caller cutting in", () => {
    expect(isBargeIn({ heard: "no make it garlic naan", spoken, level: 0.2 })).toBe(true);
    expect(isBargeIn({ heard: "नहीं गार्लिक नान", spoken, level: 0.2 })).toBe(true);
  });

  it("needs clear speech: two words for a partial, a loud enough microphone", () => {
    expect(isBargeIn({ heard: "wait", spoken, level: 0.3 })).toBe(false);
    expect(isBargeIn({ heard: "wait", spoken, level: 0.01, final: true })).toBe(true);
    expect(isBargeIn({ heard: "one dal makhani", spoken, level: 0.02 })).toBe(false);
  });

  it("ignores echo even when it is loud", () => {
    expect(isBargeIn({ heard: "added two butter naan anything else", spoken: "Added two Butter Naan. Anything else?", level: 0.9 })).toBe(false);
  });
});
