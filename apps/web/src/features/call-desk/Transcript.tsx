// Live transcript, shown in English. Words the gloss could not translate stay in italic Roman text, so
// nothing is silently dropped. "Show original" reveals what was recognised.
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef } from "react";
import { useCatalog } from "@/lib/catalog";
import { CLASS_COLOR } from "@/lib/format";
import { DUR, EASE } from "@/lib/motion";
import type { GlossPart } from "@/lib/types";
import { useCall, type Line } from "./useCall";

const UNDERLINE: Record<string, string> = {
  leaf: "decoration-leaf", plow: "decoration-plow", plum: "decoration-plum", chilli: "decoration-chilli",
};

export function Transcript() {
  const lines = useCall((s) => s.lines);
  const showOriginal = useCall((s) => s.showOriginal);
  const box = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const el = box.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [lines, showOriginal]);
  return (
    <div ref={box} className="min-h-[140px] overflow-y-auto pr-2"
      style={{ maxHeight: "max(180px, calc(100dvh - 330px))" }} aria-live="polite" aria-relevant="additions" aria-label="Transcript">
      <ol className="flex flex-col gap-2.5">
        <AnimatePresence initial={false}>
          {lines.map((l) => (
            <motion.li key={l.id} layout="position" initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              transition={{ duration: DUR.fast, ease: EASE }} className="grid grid-cols-[64px_1fr] gap-3">
              <span className="pt-1 text-xs text-muted">{l.speaker === "guest" ? "Caller" : "Tadka"}</span>
              <p className={`text-md ${l.partial ? "text-muted" : l.speaker === "assistant" ? "text-ink/75" : "text-ink"}`}
                lang={showOriginal && l.lang === "hi" ? "hi" : "en"}>
                {showOriginal ? l.original : <English line={l} />}
                {l.interrupted && <span className="ml-2 text-xs text-muted">(caller cut in)</span>}
              </p>
            </motion.li>
          ))}
        </AnimatePresence>
      </ol>
    </div>
  );
}

function English({ line }: { line: Line }) {
  if (!line.parts) return <>{line.text}</>;
  return (
    <>
      {line.parts.map((p, i) => (
        <span key={i}>
          {i > 0 && " "}
          <Part part={p} />
        </span>
      ))}
    </>
  );
}

function Part({ part }: { part: GlossPart }) {
  const stats = useCatalog((s) => s.stats);
  if (part.kind === "unknown") return <em className="text-ink/70" title="Not translated">{part.text}</em>;
  if (part.kind === "item") {
    const cls = Object.values(stats).find((s) => s.name === part.text)?.class;
    const color = cls ? UNDERLINE[CLASS_COLOR[cls]] : "decoration-ink/40";
    return <span className={`underline decoration-2 underline-offset-4 ${color}`}>{part.text}</span>;
  }
  return <>{part.text}</>;
}
