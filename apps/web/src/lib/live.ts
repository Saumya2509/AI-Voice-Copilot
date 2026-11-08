// Live updates from the server (GET /orders/stream, server-sent events). Screens subscribe to the
// `version` counters below; a data import resets everything, a new order bumps `orders`.
import { useEffect } from "react";
import { create } from "zustand";
import { useCatalog } from "./catalog";

export interface NewOrder {
  order_id: string;
  total: number;
  channel: string;
}

interface Live {
  dataVersion: number;   // bumps after an upload or sample load
  ordersVersion: number; // bumps on any order change
  lastOrder: NewOrder | null;
  connected: boolean;
}

export const useLive = create<Live>(() => ({ dataVersion: 0, ordersVersion: 0, lastOrder: null, connected: false }));

let source: EventSource | null = null;

export function useLiveData() {
  useEffect(() => {
    if (source || typeof EventSource === "undefined") return;
    source = new EventSource("/api/v1/orders/stream");
    source.onopen = () => useLive.setState({ connected: true });
    source.onerror = () => useLive.setState({ connected: false });
    source.addEventListener("order", (e) => {
      const data = JSON.parse((e as MessageEvent).data) as NewOrder;
      useLive.setState((s) => ({ ordersVersion: s.ordersVersion + 1, lastOrder: data }));
    });
    source.addEventListener("order.status", () => useLive.setState((s) => ({ ordersVersion: s.ordersVersion + 1 })));
    source.addEventListener("reset", () => {
      useLive.setState((s) => ({ dataVersion: s.dataVersion + 1, ordersVersion: s.ordersVersion + 1 }));
      void useCatalog.getState().load();
    });
  }, []);
}
