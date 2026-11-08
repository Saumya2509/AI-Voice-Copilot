// Upload flow (improve.md, section 2): choose a CSV, preview 20 rows in the browser, match columns,
// review what will be imported and why rows were rejected, set default food costs if needed, import.
import Papa from "papaparse";
import { useCallback, useEffect, useRef, useState, type DragEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Icon } from "@/components/Icon";
import { toast } from "@/components/toast";
import { Segmented } from "@/components/ui";
import { api, ApiError } from "@/lib/api";
import { num } from "@/lib/format";
import type { UploadPreview } from "@/lib/types";

type Kind = "sales" | "menu";

const FIELD_LABEL: Record<string, string> = {
  order_ref: "Order id", ts: "Date and time", item_name: "Item name", quantity: "Quantity", price: "Price",
  category: "Category", veg: "Veg or non-veg", food_cost: "Food cost", channel: "Channel", image_url: "Image URL",
  customer: "Customer", description: "Description", spice_level: "Spice level",
};
const REQUIRED: Record<Kind, string[]> = {
  sales: ["item_name", "price", "quantity", "order_ref", "ts"],
  menu: ["item_name", "price"],
};

export default function Upload() {
  const [kind, setKind] = useState<Kind>("sales");
  const [file, setFile] = useState<File | null>(null);
  const [rows, setRows] = useState<Record<string, string>[]>([]);
  const [columns, setColumns] = useState<string[]>([]);
  const [report, setReport] = useState<UploadPreview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string | null>>({});
  const [costs, setCosts] = useState<Record<string, string>>({});
  const [checking, setChecking] = useState(false);
  const [progress, setProgress] = useState<number | null>(null);
  const [drag, setDrag] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const input = useRef<HTMLInputElement>(null);
  const nav = useNavigate();

  const check = useCallback(async (f: File, k: Kind, m?: Record<string, string | null>) => {
    setChecking(true);
    setError(null);
    try {
      const r = await api.upload.preview(f, k, m);
      setReport(r);
      setMapping(r.mapping);
      setCosts((c) => Object.fromEntries((r.needs_food_cost ?? []).map((cat) => [cat, c[cat] ?? "35"])));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The file could not be checked.");
    } finally {
      setChecking(false);
    }
  }, []);

  const choose = (f: File | undefined) => {
    if (!f) return;
    if (!f.name.toLowerCase().endsWith(".csv")) {
      setError("Choose a .csv file. Most PoS systems can export one from their sales or item report.");
      return;
    }
    setFile(f);
    setReport(null);
    // The first 20 rows are parsed in the browser for an instant preview.
    Papa.parse<Record<string, string>>(f, {
      header: true, preview: 20, skipEmptyLines: true,
      complete: (res) => {
        setRows(res.data);
        setColumns(res.meta.fields ?? []);
      },
    });
    void check(f, kind);
  };

  useEffect(() => {
    if (file) void check(file, kind);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kind]);

  const remap = (field: string, col: string | null) => {
    const m = { ...mapping, [field]: col };
    setMapping(m);
    if (file) void check(file, kind, m);
  };

  const downloadRejected = () => {
    if (!report) return;
    const csv = Papa.unparse(report.rejected_rows.map((r) => ({ row: r.row, reason: r.reason, ...r.values })));
    const url = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
    const a = document.createElement("a");
    a.href = url;
    a.download = "rejected-rows.csv";
    a.click();
    URL.revokeObjectURL(url);
  };

  const commit = async () => {
    if (!file || !report) return;
    setProgress(0);
    setError(null);
    try {
      const defaults = Object.fromEntries(Object.entries(costs).map(([k, v]) => [k, Number(v)]));
      const summary = await api.upload.commit(file, kind, mapping, defaults, (p) => setProgress(p * 0.6));
      setProgress(1);
      toast(summary.message);
      nav("/analytics");
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "The import failed.");
      setProgress(null);
    }
  };

  const missing = report?.missing_required ?? [];
  const costsOk = (report?.needs_food_cost ?? []).every((c) => Number(costs[c]) > 0 && Number(costs[c]) < 100);
  const onDrop = (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    choose(e.dataTransfer.files?.[0]);
  };

  return (
    <div className="mx-auto max-w-5xl px-4 py-8 sm:px-6">
      <h1 className="title-rule font-display text-2xl">Upload your sales</h1>
      <p className="mb-6 max-w-prose text-base">
        The menu is already in Tadka, so the Call desk works straight away. A sales CSV brings in your order history for
        Analytics: export it from the PoS, one row per item sold. Each row is matched to a dish on the menu by name.
        Nothing is sent anywhere else.
      </p>

      <div className="mb-6 flex flex-wrap items-center gap-4">
        <Segmented label="File type" value={kind} onChange={(k) => setKind(k)}
          options={[{ value: "sales", label: "Sales CSV" }, { value: "menu", label: "Menu CSV" }]} />
        <span className="text-sm text-muted">Download a template:</span>
        <a className="text-sm text-indigo underline underline-offset-4" href={api.upload.templateUrl("sales")} download>sales.csv</a>
        <a className="text-sm text-indigo underline underline-offset-4" href={api.upload.templateUrl("menu")} download>menu.csv</a>
        <a className="text-sm text-indigo underline underline-offset-4" href={api.upload.sampleCsvUrl} download>
          Download a sample sales CSV
        </a>
      </div>

      <div onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)} onDrop={onDrop}
        className={`flex flex-col items-start gap-3 border-2 border-dashed p-8 transition-colors duration-fast ${drag ? "border-indigo bg-indigo/5" : "border-ink/30"}`}>
        <p className="text-md">{file ? file.name : "Drop a CSV file here"}</p>
        <div className="flex flex-wrap gap-3">
          <button className="btn-primary" onClick={() => input.current?.click()}><Icon name="upload" size={18} />Choose a file</button>
        </div>
        <p className="text-sm text-muted">Tadka shows only your own data: what you upload here and the calls you take.</p>
        <input ref={input} type="file" accept=".csv,text/csv" className="sr-only" onChange={(e) => choose(e.target.files?.[0])} />
      </div>

      {error && <p role="alert" className="mt-4 flex gap-2 text-sm"><span className="mt-1.5 h-2 w-2 shrink-0 rounded-full bg-chilli" />{error}</p>}

      {rows.length > 0 && (
        <section className="mt-8" aria-label="Preview">
          <h2 className="mb-2 font-display text-xl">First {rows.length} rows</h2>
          <div className="overflow-x-auto border border-ink/15">
            <table className="min-w-full text-sm">
              <thead><tr className="bg-ink/5 text-left">{columns.map((c) => <th key={c} className="whitespace-nowrap px-3 py-2 font-medium">{c}</th>)}</tr></thead>
              <tbody>
                {rows.map((r, i) => (
                  <tr key={i} className="border-t border-ink/10">{columns.map((c) => <td key={c} className="whitespace-nowrap px-3 py-1.5">{r[c]}</td>)}</tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {report && (
        <>
          <section className="mt-8" aria-label="Column mapping">
            <h2 className="mb-1 font-display text-xl">Match the columns</h2>
            <p className="mb-3 text-sm text-muted">Tadka guessed these from the headers. Required columns are marked.</p>
            <div className="grid gap-x-8 gap-y-2 sm:grid-cols-2">
              {Object.keys(mapping).map((field) => (
                <label key={field} className="flex items-center justify-between gap-3 border-b border-ink/10 py-1.5">
                  <span className="text-sm">
                    {FIELD_LABEL[field] ?? field}
                    {REQUIRED[kind].includes(field) && <span className="ml-1 text-chilli" aria-label="required">*</span>}
                  </span>
                  <select className="field h-9 w-48" value={mapping[field] ?? ""} onChange={(e) => remap(field, e.target.value || null)}>
                    <option value="">Not in the file</option>
                    {report.columns.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                </label>
              ))}
            </div>
          </section>

          <section className="mt-8" aria-label="Check" aria-busy={checking}>
            <h2 className="mb-3 font-display text-xl">{checking ? "Checking the file…" : "What will be imported"}</h2>
            {missing.length > 0 ? (
              <p className="text-sm">Match {missing.map((m) => FIELD_LABEL[m] ?? m).join(", ")} before importing.</p>
            ) : (
              <>
                <dl className="flex flex-wrap gap-x-10 gap-y-3">
                  <Stat label="Rows accepted" value={num(report.accepted)} />
                  <Stat label="Rows rejected" value={num(report.rejected)} />
                  <Stat label="Duplicates skipped" value={num(report.duplicates)} />
                  {kind === "sales" && <Stat label="Orders" value={num(report.orders_found)} />}
                  <Stat label={report.uses_menu ? "Dishes matched" : "Menu items"} value={num(report.items_found)} />
                  {report.date_from && <Stat label="Dates" value={`${report.date_from} to ${report.date_to}`} />}
                </dl>
                {report.rejected > 0 && (
                  <div className="mt-4 text-sm">
                    <ul className="text-muted">{report.rejected_reasons.map((r) => <li key={r.reason}>{num(r.count)} rows: {r.reason}</li>)}</ul>
                    <button className="mt-2 text-indigo underline underline-offset-4" onClick={downloadRejected}>Download rejected rows</button>
                  </div>
                )}
                {report.uses_menu && (
                  <p className="mt-3 text-sm text-muted">
                    Importing replaces the order history and keeps the menu. Rows naming a dish that is not on the menu are rejected.
                  </p>
                )}
                {report.warnings.map((w) => <p key={w} className="mt-3 text-sm text-muted">{w}</p>)}
                {report.needs_food_cost.length > 0 && (
                  <div className="mt-6 border-t-2 border-haldi pt-4">
                    <p className="text-sm font-medium">{report.food_cost_message}</p>
                    <div className="mt-3 grid gap-2 sm:grid-cols-2">
                      {report.needs_food_cost.map((c) => (
                        <label key={c} className="flex items-center justify-between gap-3 text-sm">
                          <span>{c}</span>
                          <span className="flex items-center gap-1">
                            <input className="field h-9 w-20 text-right" inputMode="decimal" value={costs[c] ?? ""}
                              onChange={(e) => setCosts({ ...costs, [c]: e.target.value })} aria-label={`Default food cost for ${c}, percent`} />%
                          </span>
                        </label>
                      ))}
                    </div>
                  </div>
                )}
              </>
            )}
          </section>

          <div className="mt-8 flex flex-wrap items-center gap-4">
            <button className="btn-primary h-11 px-6" onClick={commit}
              disabled={checking || missing.length > 0 || report.accepted === 0 || !costsOk || progress !== null}>
              Import {num(report.orders_found || report.accepted)} {kind === "sales" ? "orders" : "items"}
            </button>
            {kind === "sales" && <p className="text-sm text-muted">This replaces the current menu and orders. Calls and recordings are kept.</p>}
          </div>
        </>
      )}

      {progress !== null && (
        <div className="mt-6" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(progress * 100)}
          aria-label="Import progress">
          <div className="h-2 w-full bg-ink/10"><div className="h-full bg-indigo transition-[width] duration-base" style={{ width: `${Math.max(8, progress * 100)}%` }} /></div>
          <p className="mt-2 text-sm text-muted">{progress < 0.6 ? "Uploading…" : progress < 1 ? "Analysing…" : "Done"}</p>
        </div>
      )}
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <dt className="label">{label}</dt>
      <dd className="num text-lg font-medium">{value}</dd>
    </div>
  );
}
