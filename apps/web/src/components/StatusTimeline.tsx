// Numbered sequence for the KOT status. Numbering is used here because it is a real sequence.
import { motion } from "motion/react";
import { time } from "@/lib/format";
import { DUR, EASE } from "@/lib/motion";

export interface Step {
  label: string;
  at: string | null;
  state: "done" | "failed" | "pending";
  detail?: string;
}

export function StatusTimeline({ steps }: { steps: Step[] }) {
  return (
    <ol className="flex flex-col">
      {steps.map((s, i) => (
        <li key={s.label} className="relative flex gap-3 pb-5 last:pb-0">
          {i < steps.length - 1 && (
            <span className={`absolute left-[13px] top-7 bottom-0 w-px ${s.state === "done" ? "bg-ink/50" : "bg-line"}`} aria-hidden />
          )}
          <motion.span
            layout
            animate={{ scale: s.state === "done" ? [1, 1.12, 1] : 1 }}
            transition={{ duration: DUR.base, ease: EASE }}
            className={`relative z-10 grid h-7 w-7 shrink-0 place-items-center rounded-full border text-xs font-semibold num ${
              s.state === "done" ? "border-indigo bg-indigo text-on-indigo" : s.state === "failed" ? "border-chilli bg-chilli text-paper" : "border-line bg-surface text-muted"
            }`}
          >
            {s.state === "failed" ? "!" : i + 1}
          </motion.span>
          <div className="min-w-0 pt-0.5">
            <p className={`text-sm ${s.state === "pending" ? "text-muted" : "font-medium"}`}>{s.label}</p>
            <p className="text-xs text-muted">
              {s.state === "failed" ? "Failed" : s.at ? time(s.at, true) : "Waiting"}
            </p>
            {s.detail && <p className="mt-1 text-sm">{s.detail}</p>}
          </div>
        </li>
      ))}
    </ol>
  );
}
