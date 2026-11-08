// Side sheet (right) on desktop, slide-up sheet on mobile. Escape closes it.
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, type ReactNode } from "react";
import { DUR, EASE, useMediaQuery, useMotionPref } from "@/lib/motion";
import { Icon } from "./Icon";

export function Sheet({ open, onClose, title, children, width = 400 }: {
  open: boolean; onClose: () => void; title: string; children: ReactNode; width?: number;
}) {
  const mobile = useMediaQuery("(max-width: 767px)");
  const { reduced } = useMotionPref();
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const prev = document.activeElement as HTMLElement | null;
    ref.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => {
      window.removeEventListener("keydown", onKey);
      prev?.focus?.();
    };
  }, [open, onClose]);

  const from = mobile ? { y: "100%" } : { x: width };
  return (
    <AnimatePresence>
      {open && (
        <motion.aside
          ref={ref}
          tabIndex={-1}
          role="dialog"
          aria-label={title}
          initial={reduced ? { opacity: 0 } : from}
          animate={reduced ? { opacity: 1 } : { x: 0, y: 0 }}
          exit={reduced ? { opacity: 0 } : from}
          transition={{ duration: DUR.layout, ease: EASE }}
          style={mobile ? undefined : { width }}
          className={
            mobile
              ? "fixed inset-x-0 bottom-0 z-50 max-h-[85vh] overflow-y-auto rounded-t-lg border-t border-line bg-raised shadow-ticket outline-none"
              : "fixed right-0 top-0 z-30 h-full overflow-y-auto border-l border-line bg-raised shadow-soft outline-none"
          }
        >
          <div className="sticky top-0 z-10 flex h-14 items-center justify-between border-b border-line bg-raised px-5">
            <h2 className="truncate font-display text-xl">{title}</h2>
            <button className="btn-quiet h-9 w-9 px-0" onClick={onClose} aria-label="Close">
              <Icon name="close" size={18} />
            </button>
          </div>
          <div className="p-5">{children}</div>
        </motion.aside>
      )}
    </AnimatePresence>
  );
}
