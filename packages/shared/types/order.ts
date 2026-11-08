/* Generated from packages/shared/schemas. Run `npm run gen:types` after editing a schema. */

/**
 * A finalized order from the voice copilot. Money is in whole rupees; the server recomputes every total from menu prices.
 */
export interface Order {
  order_id: string;
  call_id: string | null;
  channel: "dine_in" | "phone" | "takeaway";
  language: "en" | "hi" | "hinglish" | "mr" | "gu";
  customer: {
    name: string | null;
    /**
     * Masked: first two and last two digits visible.
     */
    phone: string | null;
    address: string | null;
  };
  /**
   * @minItems 1
   */
  lines: [Line, ...Line[]];
  subtotal: number;
  discount: number;
  total: number;
  upsell: {
    shown: number;
    accepted: number;
    added_revenue: number;
    added_margin: number;
  };
  /**
   * ISO 8601 in UTC, for example 2026-10-11T13:42:08Z.
   */
  confirmed_at: string;
}
export interface Line {
  item_id: number;
  name: string;
  qty: number;
  unit_price: number;
  modifiers: Modifier[];
  notes: string;
  /**
   * customer: said by the caller; upsell or combo: an accepted offer; staff: added by hand from the menu.
   */
  source: "customer" | "upsell" | "combo" | "staff";
  upsell_rule_id?: number | null;
}
export interface Modifier {
  group: string;
  name: string;
  price_delta: number;
}
