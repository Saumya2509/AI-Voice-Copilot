/* Generated from packages/shared/schemas. Run `npm run gen:types` after editing a schema. */

/**
 * Kitchen order ticket. Lines are grouped by station so each section of the kitchen sees its own work.
 */
export interface Kot {
  kot_no: string;
  order_id: string;
  channel: "dine_in" | "phone" | "takeaway";
  /**
   * ISO 8601 in UTC, for example 2026-10-11T13:42:08Z.
   */
  created_at: string;
  customer: {
    name: string | null;
    phone: string | null;
  };
  /**
   * Station names in the order they appear in `lines`.
   */
  stations: string[];
  /**
   * @minItems 1
   */
  lines: [
    {
      item: string;
      qty: number;
      mods: string[];
      station: string;
      note?: string;
    },
    ...{
      item: string;
      qty: number;
      mods: string[];
      station: string;
      note?: string;
    }[]
  ];
  notes: string;
  total: number;
}
