// Thin client for /api/v1. Every number on screen comes through here.
import type {
  AnalyticsFilters, AnalyticsListRow, AnalyticsMeta, AnalyticsOverview, CallQuery, ItemClass, OrderQuery, OrdersPage,
  PublicMenu, ScatterItem, TopItem, Transcript, UploadPreview, UploadSummary,
  CallRow, ComboGraph, CombosResponse, Insights, ItemStat, ListResponse, MenuItem, OrderRow, PricePreview,
  PriceRec, Sample, Settings, StatsItems, Summary,
} from "./types";

export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string, public details: unknown = {}) {
    super(message);
  }
}

const BASE = "/api/v1";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(BASE + path, {
      ...init,
      headers: init?.body && !(init.body instanceof FormData) ? { "content-type": "application/json" } : undefined,
    });
  } catch {
    throw new ApiError(0, "offline", "Tadka's server is not reachable. Start it with make dev, then retry.");
  }
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const e = body?.error ?? {};
    throw new ApiError(res.status, e.code ?? "http_error", e.message ?? `Request failed (${res.status}).`, e.details);
  }
  return moneyToNumbers(body) as T;
}

// File 08 sends money as whole-rupee integers or two-decimal strings ("928.13"). The app does arithmetic
// on money (what-if prices, sums), so those strings become numbers here, in one place.
const MONEY_STRING = /^-?\d+\.\d{2}$/;

export function moneyToNumbers(v: unknown): unknown {
  if (typeof v === "string") return MONEY_STRING.test(v) ? Number(v) : v;
  if (Array.isArray(v)) return v.map(moneyToNumbers);
  if (v && typeof v === "object") {
    return Object.fromEntries(Object.entries(v as Record<string, unknown>).map(([k, x]) => [k, moneyToNumbers(x)]));
  }
  return v;
}

const json = (data: unknown) => JSON.stringify(data);

/** Query string from an object, skipping empty values. */
export function qs(params: object): string {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => v !== undefined && v !== null && v !== "" && q.set(k, String(v)));
  return q.toString();
}

export const api = {
  health: () => request<{ status: string; items: number; orders: number; data_from: string; data_to: string }>("/health"),
  menu: () => request<{ items: MenuItem[] }>("/menu"),
  statsItems: (window = 30) => request<StatsItems>(`/stats/items?window=${window}`),
  summary: (window = 30) => request<Summary>(`/stats/summary?window=${window}`),
  list: <T = ItemStat & Record<string, number | boolean>>(kind: string, window = 30) =>
    request<ListResponse<T>>(`/stats/lists/${kind}?window=${window}`),
  trend: (id: number) => request<{ series: { week_ending: string; units: number }[] }>(`/stats/items/${id}/trend`),
  combos: (window = 30, limit = 40) => request<CombosResponse>(`/combos?window=${window}&limit=${limit}`),
  comboGraph: (window = 30) => request<ComboGraph>(`/combos/graph?window=${window}`),
  setPool: (id: string, inPool: boolean) =>
    request<{ pool: string[] }>(`/combos/${id}/pool`, { method: "POST", body: json({ in_pool: inPool }) }),
  pricing: (window = 30) => request<{ window: number; sample_size: number; note: string; recommendations: PriceRec[] }>(
    `/pricing/recommendations?window=${window}`),
  preview: (item_id: number, new_price: number, window = 30) =>
    request<PricePreview>("/pricing/preview", { method: "POST", body: json({ item_id, new_price, window }) }),
  applyPrice: (item_id: number, new_price: number) =>
    request<{ name: string; old_price: number; new_price: number; predicted_monthly_profit_change: number }>(
      "/pricing/apply", { method: "POST", body: json({ item_id, new_price }) }),
  orders: (params: OrderQuery) => request<OrdersPage>(`/orders?${qs(params)}`),
  ordersExportUrl: (params: OrderQuery) => `${BASE}/orders/export?${qs({ ...params, cursor: undefined, limit: undefined })}`,
  order: (id: string) => request<OrderRow & {
    lines: { item_id: number; name: string; qty: number; unit_price: number; modifiers: unknown[] }[];
    order_json: import("@shared/index").Order | null;
    kot: import("@shared/index").Kot | null;
  }>(`/orders/${id}`),
  retry: (id: string) => request<{ status: string; kot_no: string | null; error: string | null; attempts: number }>(
    `/orders/${id}/retry`, { method: "POST" }),
  startCall: () => request<{ call_id: string; ws: string }>("/calls", { method: "POST", body: json({ channel: "phone" }) }),
  calls: (params: CallQuery = {}) => request<{ calls: CallRow[] }>(`/calls?${qs({ limit: 50, ...params })}`),
  transcript: (id: string, lang: "en" | "original" = "en") => request<Transcript>(`/calls/${id}/transcript?lang=${lang}`),
  recordingUrl: (id: string) => `${BASE}/calls/${id}/recording`,
  uploadRecording: (id: string, blob: Blob, durationS: number) => {
    const fd = new FormData();
    fd.set("file", blob, `${id}.webm`);
    fd.set("duration_s", String(durationS));
    return request<{ has_recording: boolean }>(`/calls/${id}/recording`, { method: "POST", body: fd });
  },
  deleteRecording: (id: string) => request<{ has_recording: boolean }>(`/calls/${id}/recording`, { method: "DELETE" }),
  deleteCall: (id: string) => request<{ deleted: string }>(`/calls/${id}`, { method: "DELETE" }),
  call: (id: string) => request<{
    call_id: string; started_at: string; ended_at: string | null; language: string | null; outcome: string | null;
    order_id: string | null; upsell_shown: number; upsell_accepted: number;
    transcript: { t: string; speaker: "guest" | "assistant"; text: string }[];
    events: import("./types").ServerEvent[];
  }>(`/calls/${id}`),
  deleteCalls: () => request<{ deleted: number }>("/calls", { method: "DELETE" }),
  insights: () => request<Insights>("/insights"),
  samples: () => request<{ samples: Sample[] }>("/samples"),
  settings: () => request<Settings>("/settings"),
  saveSettings: (patch: Partial<Settings>) => request<Settings>("/settings", { method: "PUT", body: json(patch) }),
  publicMenu: () => request<PublicMenu>("/public/menu"),
  parse: (text: string) => request<{ intent: string; language: string; display_text_en: string }>(
    "/nlu/parse", { method: "POST", body: json({ text }) }),
  analytics: {
    overview: (f: AnalyticsFilters) => request<AnalyticsOverview>(`/analytics/overview?${qs(f)}`),
    categoryShare: (f: AnalyticsFilters) =>
      request<AnalyticsMeta & { categories: { category: string; revenue: number; units: number; share: number }[] }>(
        `/analytics/category-share?${qs(f)}`),
    vegSplit: (f: AnalyticsFilters) =>
      request<AnalyticsMeta & { slices: { key: "veg" | "non_veg"; revenue: number; units: number; share: number }[] }>(
        `/analytics/veg-split?${qs(f)}`),
    classSplit: (f: AnalyticsFilters) =>
      request<AnalyticsMeta & { classes: { class: ItemClass; count: number }[] }>(`/analytics/class-split?${qs(f)}`),
    topItems: (f: AnalyticsFilters, by: "units" | "profit", limit = 10) =>
      request<AnalyticsMeta & { items: TopItem[] }>(`/analytics/top-items?${qs({ ...f, by, limit })}`),
    trend: (f: AnalyticsFilters, grain: "day" | "week") =>
      request<AnalyticsMeta & { points: { period: string; revenue: number; orders: number; aov: number }[] }>(
        `/analytics/trend?${qs({ ...f, grain })}`),
    heatmap: (f: AnalyticsFilters) =>
      request<AnalyticsMeta & { weekdays: string[]; max_orders: number;
        cells: { weekday: number; hour: number; orders: number; revenue: number }[] }>(`/analytics/heatmap?${qs(f)}`),
    channelMix: (f: AnalyticsFilters) =>
      request<AnalyticsMeta & { channels: { channel: string; orders: number; revenue: number; aov: number }[] }>(
        `/analytics/channel-mix?${qs(f)}`),
    items: (f: AnalyticsFilters) => request<AnalyticsMeta & { items: ScatterItem[] }>(`/analytics/items?${qs(f)}`),
    list: (kind: string, f: AnalyticsFilters) =>
      request<AnalyticsMeta & { assumption: string; items: AnalyticsListRow[] }>(`/analytics/lists/${kind}?${qs(f)}`),
  },
  upload: {
    templateUrl: (kind: "sales" | "menu") => `${BASE}/import/template/${kind}`,
    sampleCsvUrl: `${BASE}/import/sample-csv`,
    preview: (file: File, kind: "sales" | "menu", mapping?: Record<string, string | null>) => {
      const fd = new FormData();
      fd.set("file", file);
      fd.set("kind", kind);
      if (mapping) fd.set("mapping", JSON.stringify(mapping));
      return request<UploadPreview>("/import/preview", { method: "POST", body: fd });
    },
    commit: (file: File, kind: "sales" | "menu", mapping: Record<string, string | null>,
             defaults: Record<string, number>, onProgress?: (fraction: number) => void) =>
      new Promise<UploadSummary>((resolve, reject) => {
        // XMLHttpRequest, because fetch cannot report upload progress.
        const fd = new FormData();
        fd.set("file", file);
        fd.set("kind", kind);
        fd.set("mapping", JSON.stringify(mapping));
        fd.set("default_cost_pct", JSON.stringify(defaults));
        const xhr = new XMLHttpRequest();
        xhr.open("POST", `${BASE}/import/commit`);
        xhr.upload.onprogress = (e) => e.lengthComputable && onProgress?.(e.loaded / e.total);
        xhr.onload = () => {
          const body = moneyToNumbers(JSON.parse(xhr.responseText || "{}")) as Record<string, unknown>;
          if (xhr.status < 300) resolve(body as unknown as UploadSummary);
          else {
            const e = (body.error ?? {}) as { code?: string; message?: string; details?: unknown };
            reject(new ApiError(xhr.status, e.code ?? "http_error", e.message ?? "The import failed.", e.details));
          }
        };
        xhr.onerror = () => reject(new ApiError(0, "offline", "Tadka's server is not reachable. Start it, then retry."));
        xhr.send(fd);
      }),
    sample: () => request<UploadSummary>("/import/sample", { method: "POST" }),
  },
  importCsv: (kind: "items" | "orders", file: File, opts: Record<string, string>) => {
    const fd = new FormData();
    fd.set("file", file);
    Object.entries(opts).forEach(([k, v]) => fd.set(k, v));
    return request<ImportReport>(`/import/${kind}`, { method: "POST", body: fd });
  },
};

export interface ImportReport {
  kind: string;
  columns: string[];
  mapping: Record<string, string | null>;
  missing_required: string[];
  accepted: number;
  rejected: number;
  rejected_reasons: { reason: string; count: number }[];
  warnings: string[];
  needs_food_cost: string[];
  food_cost_message: string | null;
  committed: boolean;
}
