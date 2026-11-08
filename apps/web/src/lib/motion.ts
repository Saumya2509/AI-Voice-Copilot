import { useEffect, useState } from "react";

export const EASE = [0.2, 0.8, 0.2, 1] as const;
export const DUR = { fast: 0.12, base: 0.22, layout: 0.42, feed: 0.9 } as const;
export const SPRING = { type: "spring", stiffness: 260, damping: 28 } as const;

/** True when the person asked the system for reduced motion. */
export function useMotionPref(): { reduced: boolean } {
  const query = "(prefers-reduced-motion: reduce)";
  const [reduced, setReduced] = useState(() =>
    typeof window !== "undefined" ? window.matchMedia(query).matches : false,
  );
  useEffect(() => {
    const mq = window.matchMedia(query);
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return { reduced };
}

export function useMediaQuery(q: string): boolean {
  const [m, setM] = useState(() => (typeof window !== "undefined" ? window.matchMedia(q).matches : false));
  useEffect(() => {
    const mq = window.matchMedia(q);
    const on = () => setM(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, [q]);
  return m;
}
