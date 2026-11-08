// Barge-in: the caller may speak over the agent, and the agent stops to listen, as a person would.
// While the agent speaks the microphone stays open. Recognised speech counts as the caller cutting in
// when it is clearly speech (enough words, a loud enough microphone) and is not the agent's own voice
// coming back through the speakers: echo repeats the words being spoken, so a heard phrase made mostly
// of those words is ignored. The browser's echo cancellation removes most of it before that.

const norm = (s: string) =>
  s.toLowerCase().replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter(Boolean);

/** True when what the microphone heard is (mostly) the agent's own reply. */
export function isEcho(heard: string, spoken: string, threshold = 0.6): boolean {
  const words = norm(heard).filter((w) => w !== "unk");
  if (!words.length) return true;
  const said = new Set(norm(spoken));
  const repeated = words.filter((w) => said.has(w)).length;
  return repeated / words.length >= threshold;
}

export interface BargeInput {
  heard: string;   // recognised text so far (partial or final)
  spoken: string;  // the reply being spoken (both its screen and voice forms)
  level: number;   // microphone level 0..1
  final?: boolean; // a finished utterance
}

/** Whether the caller is cutting in. A partial needs two words or more; a final result needs one. */
export function isBargeIn({ heard, spoken, level, final = false }: BargeInput, minLevel = 0.08): boolean {
  const words = norm(heard).filter((w) => w !== "unk");
  if (words.length < (final ? 1 : 2) || isEcho(heard, spoken)) return false;
  return final || level >= minLevel;
}
