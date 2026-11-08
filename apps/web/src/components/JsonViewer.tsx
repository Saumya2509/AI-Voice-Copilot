// Collapsible JSON tree with a copy button, for the structured order.
import { useState } from "react";
import { Icon } from "./Icon";
import { toast } from "./toast";

export function JsonViewer({ value, label = "Order JSON" }: { value: unknown; label?: string }) {
  return (
    <div className="panel overflow-hidden">
      <div className="flex items-center justify-between border-b border-line px-4 h-11">
        <h3 className="text-sm font-medium">{label}</h3>
        <button
          className="btn-quiet h-8"
          onClick={async () => {
            try {
              await navigator.clipboard.writeText(JSON.stringify(value, null, 2));
              toast("Copied the order JSON.");
            } catch {
              toast("The browser blocked copying. Select the text instead.", "error");
            }
          }}
        >
          <Icon name="copy" size={16} /> Copy
        </button>
      </div>
      <div className="overflow-auto p-4 text-[13px] leading-6" style={{ fontFamily: "ui-monospace, Consolas, monospace" }}>
        <Node k={null} v={value} depth={0} />
      </div>
    </div>
  );
}

function Node({ k, v, depth }: { k: string | null; v: unknown; depth: number }) {
  const [open, setOpen] = useState(depth < 2);
  const key = k !== null ? <span className="text-muted">{k}: </span> : null;
  if (v === null || typeof v !== "object") {
    const cls = typeof v === "number" ? "text-cardamom" : typeof v === "string" ? "text-leaf" : "text-beet";
    return (
      <div style={{ paddingLeft: depth * 14 }}>
        {key}
        <span className={cls}>{JSON.stringify(v)}</span>
      </div>
    );
  }
  const entries = Array.isArray(v) ? v.map((x, i) => [String(i), x] as const) : Object.entries(v as object);
  const brace = Array.isArray(v) ? ["[", "]"] : ["{", "}"];
  return (
    <div style={{ paddingLeft: depth * 14 }}>
      <button className="text-left hover:text-ink" onClick={() => setOpen(!open)} aria-expanded={open}>
        <span className={`inline-block w-3 text-muted transition-transform duration-fast ${open ? "rotate-90" : ""}`}>›</span>
        {key}
        <span className="text-muted">
          {brace[0]}
          {!open && ` ${entries.length} ${entries.length === 1 ? "item" : "items"} ${brace[1]}`}
        </span>
      </button>
      {open && (
        <>
          {entries.map(([ck, cv]) => (
            <Node key={ck} k={Array.isArray(v) ? null : ck} v={cv} depth={1} />
          ))}
          <div className="text-muted">{brace[1]}</div>
        </>
      )}
    </div>
  );
}
