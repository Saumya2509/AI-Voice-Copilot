// One smooth line. Listening: the live mic level from an AnalyserNode. Assistant speaking: a different,
// rounder pattern driven by speech boundary events. Draws in from a flat line when a call starts.
// Runs at 60 fps and pauses when the tab is hidden.
import { useEffect, useRef } from "react";
import { micLevel } from "@/lib/stt";
import { onSpeechLevel } from "@/lib/tts";
import { useMotionPref } from "@/lib/motion";
import type { Status } from "./useCall";

export function Waveform({ analyser, status, startedAt, compact = false }: {
  analyser: AnalyserNode | null; status: Status; startedAt: number | null; compact?: boolean;
}) {
  const canvas = useRef<HTMLCanvasElement>(null);
  const speech = useRef(0);
  const { reduced } = useMotionPref();
  const live = status !== "idle" && status !== "done" && status !== "error";

  useEffect(() => onSpeechLevel((l) => (speech.current = l)), []);

  useEffect(() => {
    const el = canvas.current;
    if (!el) return;
    const ctx = el.getContext("2d")!;
    const buf = new Float32Array(analyser?.fftSize ?? 1024);
    let raf = 0;
    let level = 0;
    let shown = 0;
    let phase = 0;

    const draw = () => {
      const dpr = window.devicePixelRatio || 1;
      const w = el.clientWidth;
      const h = el.clientHeight;
      if (el.width !== w * dpr) {
        el.width = w * dpr;
        el.height = h * dpr;
      }
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, w, h);
      const css = getComputedStyle(document.documentElement);
      const ink = `rgb(${css.getPropertyValue("--ink")})`;
      const haldi = `rgb(${css.getPropertyValue("--haldi")})`;
      const speakingNow = status === "speaking";

      // Draw-in from flat over 300 ms at call start.
      const intro = startedAt ? Math.min(1, (Date.now() - startedAt) / 300) : 0;
      if (live) {
        if (speakingNow) level = speech.current;
        else if (analyser) level = micLevel(analyser, buf);
        else level = 0.04; // typed or sample call: a quiet carrier line
      } else level = 0;
      shown += (level - shown) * 0.18;
      phase += speakingNow ? 0.09 : 0.05;

      ctx.lineWidth = 2;
      ctx.lineCap = "round";
      ctx.strokeStyle = speakingNow ? haldi : ink;
      ctx.globalAlpha = live ? 1 : 0.35;
      ctx.beginPath();
      const mid = h / 2;
      const amp = (h / 2 - 4) * shown * (reduced ? 0.6 : 1) * intro;
      for (let x = 0; x <= w; x += 2) {
        const u = x / w;
        const env = Math.sin(Math.PI * u); // taper at both ends
        const y = speakingNow
          ? Math.sin(u * 9 + phase) * 0.7 + Math.sin(u * 3.1 - phase * 0.6) * 0.3
          : Math.sin(u * 23 + phase) * 0.55 + Math.sin(u * 41 - phase * 1.7) * 0.3 + Math.sin(u * 7 + phase * 0.4) * 0.15;
        const py = mid + y * amp * env;
        x === 0 ? ctx.moveTo(x, py) : ctx.lineTo(x, py);
      }
      ctx.stroke();
      if (!document.hidden && (live || shown > 0.005)) raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    const onVis = () => {
      cancelAnimationFrame(raf);
      if (!document.hidden) raf = requestAnimationFrame(draw);
    };
    document.addEventListener("visibilitychange", onVis);
    void draw;
    return () => {
      cancelAnimationFrame(raf);
      document.removeEventListener("visibilitychange", onVis);
    };
  }, [analyser, status, startedAt, live, reduced]);

  return <canvas ref={canvas} className={`${compact ? "h-9" : "h-16"} w-full`} aria-hidden />;
}
