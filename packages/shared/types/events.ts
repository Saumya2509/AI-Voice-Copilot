/* Generated from packages/shared/schemas. Run `npm run gen:types` after editing a schema. */

/**
 * Events sent by the server on /ws/call/{call_id}. Every event has an increasing seq; clients ignore events with an older seq.
 */
export type ServerEvent = {
  [k: string]: unknown;
} & {
  type:
    | "state.changed"
    | "nlu.result"
    | "cart.updated"
    | "clarify.ask"
    | "upsell.offer"
    | "reply.say"
    | "order.finalized"
    | "pos.sent"
    | "pos.ack"
    | "error"
    | "transcript"
    | "menu.highlight";
  seq: number;
  ts: string;
};
