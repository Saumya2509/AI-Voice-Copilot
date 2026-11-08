// Toasts sit bottom left and never cover the ticket. Plain sentences.
import { AnimatePresence, motion } from "motion/react";
import { create } from "zustand";
import { DUR, EASE } from "@/lib/motion";

interface Toast {
  id: number;
  text: string;
  tone: "ok" | "error";
}

interface ToastStore {
  toasts: Toast[];
  push: (text: string, tone?: Toast["tone"]) => void;
  dismiss: (id: number) => void;
}

let next = 1;

export const useToasts = create<ToastStore>((set) => ({
  toasts: [],
  push: (text, tone = "ok") => {
    const id = next++;
    set((s) => ({ toasts: [...s.toasts.slice(-2), { id, text, tone }] }));
    setTimeout(() => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })), tone === "error" ? 7000 : 3500);
  },
  dismiss: (id) => set((s) => ({ toasts: s.toasts.filter((t) => t.id !== id) })),
}));

export const toast = (text: string, tone: Toast["tone"] = "ok") => useToasts.getState().push(text, tone);

export function Toaster() {
  const { toasts, dismiss } = useToasts();
  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed bottom-20 left-4 z-50 flex flex-col gap-2 md:bottom-4 md:left-[88px]"
    >
      <AnimatePresence initial={false}>
        {toasts.map((t) => (
          <motion.div
            key={t.id}
            layout
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0 }}
            transition={{ duration: DUR.base, ease: EASE }}
            className="pointer-events-auto flex max-w-sm items-start gap-3 rounded-md border border-haldi/60 bg-indigo px-4 py-3 text-sm text-on-indigo shadow-card"
            role={t.tone === "error" ? "alert" : "status"}
          >
            <span className={`mt-1.5 h-2 w-2 shrink-0 rounded-full ${t.tone === "error" ? "bg-chilli" : "bg-haldi"}`} aria-hidden />
            <span className="flex-1">{t.text}</span>
            <button className="text-on-indigo/70 hover:text-on-indigo" onClick={() => dismiss(t.id)} aria-label="Dismiss">
              ×
            </button>
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
