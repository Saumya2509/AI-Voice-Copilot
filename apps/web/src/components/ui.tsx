// Small shared pieces: class tag, number tween, empty and loading states, tabs, segmented control.
import { animate, useMotionValue, useMotionValueEvent } from "motion/react";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { CLASS_COLOR, CLASS_LABEL, rupees } from "@/lib/format";
import { useMotionPref } from "@/lib/motion";
import type { ItemClass } from "@/lib/types";
import { Icon } from "./Icon";

const DOT: Record<string, string> = {
  leaf: "bg-leaf", plow: "bg-plow", plum: "bg-plum", chilli: "bg-chilli",
};

/** Coloured dot plus word, sentence case. Colour never carries meaning alone. */
export function ClassTag({ cls, className = "" }: { cls: ItemClass; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-sm text-ink ${className}`}>
      <ClassDot cls={cls} />
      {CLASS_LABEL[cls]}
    </span>
  );
}

/** Each class has its own dot shape too, matching the bubble outline patterns on the menu field. */
export function ClassDot({ cls, size = 10 }: { cls: ItemClass; size?: number }) {
  const color = DOT[CLASS_COLOR[cls]];
  const shape = cls === "star" ? "rounded-full" : cls === "plowhorse" ? "rounded-[2px]" : cls === "puzzle" ? "rounded-full ring-2 ring-offset-1 ring-offset-card ring-plum/40" : "rotate-45 rounded-[1px]";
  return <span aria-hidden className={`inline-block shrink-0 ${color} ${shape}`} style={{ width: size * 0.8, height: size * 0.8 }} />;
}

/** Tweens to a new value over 500 ms; instant under reduced motion. */
export function NumberTween({ value, format = rupees, duration = 0.5, className = "" }: {
  value: number; format?: (n: number) => string; duration?: number; className?: string;
}) {
  const { reduced } = useMotionPref();
  const mv = useMotionValue(value);
  const [shown, setShown] = useState(value);
  useMotionValueEvent(mv, "change", (v) => setShown(v));
  useEffect(() => {
    if (reduced) {
      mv.set(value);
      return;
    }
    const c = animate(mv, value, { duration, ease: [0.2, 0.8, 0.2, 1] });
    return () => c.stop();
  }, [value, reduced, duration, mv]);
  return <span className={`num ${className}`}>{format(Math.round(shown * 100) / 100)}</span>;
}

export function EmptyState({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-start gap-3 py-10 max-w-prose">
      <h3 className="font-display text-xl">{title}</h3>
      {children && <div className="text-sm text-muted">{children}</div>}
      {action}
    </div>
  );
}

export function Loading({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-3 py-10 text-sm text-muted">
      <span className="h-3 w-3 rounded-full border-2 border-muted border-t-transparent animate-spin" aria-hidden />
      {label}…
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div role="alert" className="flex flex-col items-start gap-3 py-8 max-w-prose">
      <p className="flex items-start gap-2 text-sm">
        <span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-chilli" aria-hidden />
        {message}
      </p>
      {onRetry && (
        <button className="btn-secondary" onClick={onRetry}>
          <Icon name="retry" size={16} /> Retry
        </button>
      )}
    </div>
  );
}

export function Segmented<T extends string | number>({ value, options, onChange, label }: {
  value: T; options: { value: T; label: string }[]; onChange: (v: T) => void; label: string;
}) {
  return (
    <div role="radiogroup" aria-label={label} className="inline-flex rounded-sm border border-line bg-raised p-0.5">
      {options.map((o) => (
        <button
          key={String(o.value)}
          role="radio"
          aria-checked={o.value === value}
          onClick={() => onChange(o.value)}
          className={`h-8 px-3 text-sm rounded-[3px] transition-colors duration-fast ${
            o.value === value ? "bg-indigo text-on-indigo" : "text-ink/80 hover:text-ink hover:bg-ink/5"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Tabs<T extends string>({ value, tabs, onChange, label }: {
  value: T; tabs: { value: T; label: string }[]; onChange: (v: T) => void; label: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  return (
    <div role="tablist" aria-label={label} className="flex gap-1 border-b border-line overflow-x-auto">
      {tabs.map((t, i) => (
        <button
          key={t.value}
          ref={(el) => (refs.current[i] = el)}
          role="tab"
          aria-selected={t.value === value}
          tabIndex={t.value === value ? 0 : -1}
          onClick={() => onChange(t.value)}
          onKeyDown={(e) => {
            if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
            const next = (i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
            refs.current[next]?.focus();
            onChange(tabs[next].value);
          }}
          className={`relative h-10 px-3 text-sm whitespace-nowrap transition-colors duration-fast ${
            t.value === value ? "text-ink font-medium" : "text-muted hover:text-ink"
          }`}
        >
          {t.label}
          {t.value === value && <span className="absolute inset-x-2 -bottom-px h-0.5 bg-haldi" />}
        </button>
      ))}
    </div>
  );
}

export function Switch({ checked, onChange, label, description }: {
  checked: boolean; onChange: (v: boolean) => void; label: string; description?: ReactNode;
}) {
  return (
    <label className="flex items-start justify-between gap-6 py-3 cursor-pointer">
      <span>
        <span className="block text-sm font-medium">{label}</span>
        {description && <span className="block text-sm text-muted mt-0.5">{description}</span>}
      </span>
      <button
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={(e) => {
          e.preventDefault();
          onChange(!checked);
        }}
        className={`relative mt-0.5 h-6 w-11 shrink-0 rounded-full transition-colors duration-base ${checked ? "bg-indigo" : "bg-line"}`}
      >
        <span className={`absolute left-0 top-0.5 h-5 w-5 rounded-full bg-raised shadow-soft transition-transform duration-base ease-out ${checked ? "translate-x-[22px]" : "translate-x-0.5"}`} />
      </button>
    </label>
  );
}

export function PageHeader({ title, children, meta }: { title: string; children?: ReactNode; meta?: ReactNode }) {
  return (
    <header className="flex flex-wrap items-end justify-between gap-4 pb-5">
      <div>
        <h1 className="text-xl font-semibold">{title}</h1>
        {meta && <p className="mt-1 text-sm text-muted">{meta}</p>}
      </div>
      {children && <div className="flex flex-wrap items-center gap-2">{children}</div>}
    </header>
  );
}
