// Response shapes from the Tadka API (file 08). The order and KOT types are generated from the
// shared JSON Schemas in packages/shared.
export type { Order, Kot } from "@shared/index";

export type ItemClass = "star" | "plowhorse" | "puzzle" | "dog";
export type Category = "starter" | "main" | "bread" | "rice" | "side" | "dessert" | "beverage";

export interface ItemStat {
  item_id: number;
  name: string;
  category: Category;
  price: number;
  food_cost: number;
  cm: number;
  cm_pct: number;
  units: number;
  velocity: number;
  popularity_share: number;
  popularity_index: number;
  attach_rate: number;
  revenue: number;
  profit: number;
  category_avg_cm: number;
  class: ItemClass;
  reason: string;
  action: string;
  trend: "up" | "flat" | "down";
  available: boolean;
  veg: boolean;
  window: number;
  sample_size: number;
  n_in_category: number;
  elasticity?: number;
  elasticity_source?: "Measured" | "Assumed";
  elasticity_range?: [number, number];
}

export interface StatsItems {
  window: number;
  sample_size: number;
  popularity_factor: number;
  items: ItemStat[];
}

export interface Summary {
  window: number;
  sample_size: number;
  aov: number;
  revenue: number;
  profit: number;
  orders_per_day: number;
  class_counts: Record<ItemClass, number>;
  plowhorse_risk_count: number;
  upside: { monthly: number; from_pricing: number; from_promoting_puzzles: number; basis: string };
}

export interface ListResponse<T> {
  kind: string;
  window: number;
  sample_size: number;
  assumption: string;
  items: T[];
}

export interface MenuModGroup {
  id: number;
  name: string;
  required: boolean;
  options: { id: number; name: string; price_delta: number }[];
}

export interface MenuItem {
  id: number;
  name: string;
  category: Category;
  category_name: string;
  price: number;
  veg: boolean;
  spice_level: number;
  available: boolean;
  station: string;
  description: string | null;
  image_url: string | null;
  chefs_pick: boolean;
  hold_reason: string | null;
  aliases?: string[];
  modifier_groups: MenuModGroup[];
}

export interface Combo {
  id: string;
  items: { id: number; name: string; category: string | null }[];
  added_margin: number;
  pitch_hinglish: string;
  pitch_hi: string;
  anchor_item_ids: number[];
  bundle_price: number;
  list_price: number;
  discount_pct: number;
  cm: number;
  cm_pct: number;
  support: number;
  confidence: number;
  lift: number;
  score: number;
  aov_change_per_order: number;
  margin_change_per_order: number;
  evidence: string;
  classes: ItemClass[];
  in_pool: boolean;
  pitch: string;
}

export interface CombosResponse {
  window: number;
  sample_size: number;
  baskets: number;
  combos: Combo[];
}

export interface ComboGraph {
  window: number;
  sample_size: number;
  nodes: { id: number; name: string; class: ItemClass; category: Category; units: number }[];
  edges: { source: number; target: number; lift: number; confidence: number; support: number }[];
}

export interface PriceRec {
  item_id: number;
  name: string;
  category: Category;
  class: ItemClass;
  action: "raise" | "lower" | "hold" | "rework";
  advice: string;
  price: number;
  suggested_price: number;
  elasticity: number;
  elasticity_source: "Measured" | "Assumed";
  elasticity_range: [number, number];
  monthly_units: number;
  predicted_monthly_units: number;
  monthly_profit_change: number;
  monthly_profit_change_range: [number, number];
  confidence: "high" | "medium" | "low";
  unguarded_price: number;
  unguarded_monthly_profit_change: number;
  unguarded_note: string;
  guardrail_notes: string[];
}

export interface PricePreview {
  item_id: number;
  name: string;
  price: number;
  new_price: number;
  food_cost: number;
  elasticity: number;
  elasticity_source: string;
  monthly_units: number;
  predicted_monthly_units: number;
  monthly_profit: number;
  predicted_monthly_profit: number;
  monthly_profit_change: number;
  monthly_profit_change_range: [number, number];
  cm_pct_after: number;
  warnings: string[];
}

export interface OrderRow {
  order_id: string;
  ts: string;
  channel: "dine_in" | "phone" | "takeaway";
  daypart: string;
  covers: number;
  subtotal: number;
  discount: number;
  total: number;
  external_ref: string | null;
  customer_name?: string | null;
  source: "tadka" | "pos_history";
  upsell_added: number | null;
  confirmed_at: string | null;
  items?: { name: string; qty: number }[]; // with_items=true
  pos: null | {
    status: "pending" | "sent" | "acked" | "failed" | "needs_attention";
    kot_no: string | null;
    attempts: number;
    error: string | null;
    sent_at: string | null;
    ack_at: string | null;
  };
}

export interface CallRow {
  call_id: string;
  started_at: string;
  ended_at: string | null;
  duration_s: number;
  has_recording: boolean;
  language: string | null;
  outcome: string | null;
  order_id: string | null;
  total: number | null;
  upsell_added: number | null;
  upsell_shown: number;
  upsell_accepted: number;
}

export interface Insights {
  calls_with_orders: number;
  offers_shown: number;
  offers_accepted: number;
  aov_with_upsell: number | null;
  aov_without_upsell: number | null;
  added_revenue: number;
  added_margin: number;
  by_hour: { hour: number; shown: number; accepted: number }[];
  top_offers: {
    rule_id: number | null;
    offer_item: string;
    anchor_item: string | null;
    kind: "rule" | "combo";
    shown: number;
    accepted: number;
    accept_rate: number;
    expected_rate: number | null;
  }[];
}

export interface Settings {
  restaurant_name: string;
  upsell: {
    enabled: boolean;
    max_offers_per_call: number;
    daypart_weights: Record<string, number>;
    slow_prep_minutes: number;
  };
  kitchen_busy: boolean;
  inventory_signals: boolean;
  language_packs: string[];
  speech: { engine: "offline" | "typed"; browser_service: boolean; voice?: "natural" | "browser"; barge_in?: boolean };
  combo_pool: string[] | null;
  recording: { enabled: boolean };
  available_packs: { code: string; label: string }[];
  active_signals: { kind: string; text: string; ingredient?: string; items?: string[] }[];
}

export interface Sample {
  id: string;
  title: string;
  description: string;
  language: string;
  utterances: { at: number; text: string }[];
}

// ----- WebSocket events --------------------------------------------------------------

export interface CartLine {
  line_id: number;
  item_id: number;
  name: string;
  qty: number;
  unit_price: number;
  modifiers: { group: string; name: string }[];
  notes: string[];
  source: "customer" | "upsell" | "combo" | "staff";
  combo_id?: string | null;
}

export interface Cart {
  lines: CartLine[];
  subtotal: number;
  discount: number;
  total: number;
  upsell: { shown: number; accepted: number; added_revenue: number; added_margin: number };
}

export interface NluMatch {
  span: [number, number];
  text: string;
  status: "accepted" | "clarify";
  item_id: number | null;
  score: number;
  options: { id: number; label: string; score: number }[];
}

export type CallState =
  | "GREETING" | "TAKING_ORDER" | "CLARIFYING" | "OFFERING" | "CONFIRMING" | "CAPTURING_DETAILS"
  | "FINALIZED" | "ABANDONED";

export type ServerEvent = { seq: number; ts: string } & (
  | { type: "state.changed"; state: CallState }
  | { type: "nlu.result"; intent: string; language: string; matches: NluMatch[] }
  | { type: "cart.updated"; cart: Cart }
  | { type: "clarify.ask"; clarify_id: string; question: string; question_en: string;
      options: { id: number | string; label: string }[] }
  | { type: "transcript"; speaker: "guest"; original_text: string; display_text_en: string; lang: string;
      parts: GlossPart[] }
  | { type: "menu.highlight"; item_id: number; kind: "heard" | "staff" }
  | {
      type: "upsell.offer";
      offer_id: string;
      kind: "rule" | "combo";
      item: { id: number; name: string; price: number };
      reason: { headline: string; why: string[]; expected_gain: number };
    }
  | { type: "reply.say"; text: string; lang: string; display_text_en: string; suggest_typed?: boolean;
      speech_text?: string; speech_lang?: "en" | "hi" } // what the voice reads (Devanagari for Hindi and Hinglish)
  | { type: "order.finalized"; order: import("@shared/index").Order }
  | { type: "pos.sent"; order_id: string }
  | { type: "pos.ack"; order_id: string; kot_no: string }
  | { type: "error"; code: string; message: string }
);

// ----- improve.md additions -------------------------------------------------------------

export interface GlossPart {
  text: string;
  kind: "plain" | "item" | "unknown";
}

export interface AnalyticsFilters {
  from?: string;
  to?: string;
  category?: string;
  veg?: "veg" | "non_veg";
  channel?: "dine_in" | "phone" | "takeaway";
  weekday?: number;
  hour?: number;
}

export interface AnalyticsMeta {
  window: number;
  sample_size: number;
  from: string | null;
  to: string | null;
  filters: Record<string, string>;
  estimated: boolean;
}

export interface AnalyticsOverview extends AnalyticsMeta {
  revenue: number;
  orders: number;
  aov: number;
  items_sold: number;
  gross_margin_pct: number | null;
  busiest_hour: number | null;
  data_from: string | null;
  data_to: string | null;
}

export interface TopItem {
  item_id: number;
  name: string;
  category: string;
  class: ItemClass;
  units: number;
  revenue: number;
  profit: number;
}

export interface ScatterItem extends TopItem {
  cm: number;
  x: number;
  y: number;
  cost_estimated: boolean;
}

export interface AnalyticsListRow {
  item_id: number;
  name: string;
  class: ItemClass;
  units: number;
  cm: number;
  popularity_index: number;
  value: number;
  at_risk?: boolean;
}

export interface UploadPreview {
  kind: string;
  columns: string[];
  mapping: Record<string, string | null>;
  missing_required: string[];
  rows: number;
  accepted: number;
  rejected: number;
  duplicates: number;
  rejected_reasons: { reason: string; count: number }[];
  rejected_rows: { row: number; reason: string; values: Record<string, string> }[];
  items_found: number;
  uses_menu?: boolean;
  orders_found: number;
  date_from: string | null;
  date_to: string | null;
  needs_food_cost: string[];
  food_cost_message: string | null;
  warnings: string[];
}

export interface UploadSummary {
  source?: string;
  orders?: number;
  items: number;
  lines?: number;
  date_from?: string | null;
  date_to?: string | null;
  message: string;
  sample?: boolean;
}

export interface OrderQuery {
  q?: string;
  channel?: string;
  status?: string;
  has_upsell?: boolean;
  source?: "tadka" | "pos_history";
  from?: string;
  to?: string;
  sort?: "newest" | "oldest" | "total_desc" | "total_asc";
  cursor?: string;
  limit?: number;
  with_items?: boolean;
}

export interface OrdersPage {
  total: number;
  next_cursor: string | null;
  sort: string;
  summary: { orders: number; revenue: number; upsell_added: number };
  orders: OrderRow[];
}

export interface CallQuery {
  q?: string;
  outcome?: string;
  language?: string;
  has_recording?: boolean;
  from?: string;
  to?: string;
  limit?: number;
}

export interface Transcript {
  call_id: string;
  lang: string;
  has_recording: boolean;
  lines: { at_s: number; speaker: "guest" | "assistant"; text: string; display_text_en: string;
           original_text: string; lang: string | null; parts: GlossPart[] | null }[];
  markers: { at_s: number; kind: "clarify" | "offer" | "item" | "sent" | "interrupted"; label?: string; item_id?: number }[];
}

export interface PublicMenu {
  items: number;
  categories: { id: number; name: string; kind: string; items: {
    id: number; name: string; price: number; veg: boolean; spice_level: number; description: string | null;
    image_url: string | null; available: boolean }[] }[];
}
